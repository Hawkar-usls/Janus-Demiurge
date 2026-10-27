#!/usr/bin/env python3
"""Owner-private, fail-closed, incremental HRAiN graph transactions.

Disk write requires an exact snapshot hash, immutable before-image backup,
single-process/cross-process lock, create-only intent and independent
postcondition. No network, agent runtime, GitHub, bulk replace or deletion.
For live deployment, the HRAiN caller MUST also hold its in-process state lock,
verify the in-memory graph is the same persisted revision, and reload only on
successful commit. This module never starts a server or activates an agent.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import uuid

SCHEMA = "janus.hrain.incremental_transaction.v1"
MAX_GRAPH_BYTES = 32_000_000
MAX_PATCH_BYTES = 8_192
MIN_FREE_BYTES = 128_000_000
MAX_ARCHIVES = 250
HEX = re.compile(r"^[a-f0-9]{64}$")
REQUEST = re.compile(r"^[a-fA-F0-9-]{32,36}$")
SAFE_ROLE = re.compile(r"^[a-zA-Z0-9_-]{1,48}$")


class Hold(RuntimeError):
    """Safety interlock: source and authoritative state remain untouched."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _strict_json(raw: bytes) -> dict:
    if not (1 <= len(raw) <= MAX_GRAPH_BYTES):
        raise Hold("GRAPH_SIZE_HOLD")
    try:
        data = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("GRAPH_NONFINITE_HOLD")))
    except (ValueError, UnicodeError) as exc:
        raise Hold("GRAPH_INVALID_JSON_HOLD") from exc
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), dict) or not isinstance(data.get("edges"), dict):
        raise Hold("GRAPH_SCHEMA_HOLD")
    if type(data.get("node_counter")) is not int or type(data.get("tick")) is not int:
        raise Hold("GRAPH_COUNTER_HOLD")
    if data["node_counter"] < 0 or data["tick"] < 0:
        raise Hold("GRAPH_COUNTER_HOLD")
    return data


def _root(root: Path) -> tuple[Path, Path]:
    root = Path(root)
    if root.name != "All Star" or root.is_symlink() or not root.is_dir():
        raise Hold("OWNER_ROOT_HOLD")
    state = root / "raw_logs" / "hrain_graph_state.json"
    if state.is_symlink() or not state.is_file():
        raise Hold("GRAPH_SOURCE_HOLD")
    audit = root / "artifacts" / "audits" / "private_graph_backups"
    if not audit.is_dir() or audit.is_symlink():
        raise Hold("PRIVATE_BACKUPS_REQUIRED_HOLD")
    directory = audit / "incremental"
    if directory.is_symlink():
        raise Hold("TRANSACTION_DIRECTORY_SYMLINK_HOLD")
    return state, directory


def _write_new(path: Path, payload: bytes) -> None:
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())


def _label(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise Hold("UNSAFE_LABEL_HOLD")
    return value


def _apply(state: dict, operation: dict, max_nodes: int) -> tuple[dict, str]:
    if type(operation) is not dict or type(operation.get("op")) is not str:
        raise Hold("INVALID_OPERATION_HOLD")
    nxt = copy.deepcopy(state)
    nodes, edges = nxt["nodes"], nxt["edges"]
    kind = operation["op"]
    if kind == "add_node":
        if set(operation) != {"op", "nodeType", "label"}:
            raise Hold("NODE_FIELDS_HOLD")
        if len(nodes) >= max_nodes:
            raise Hold("GRAPH_CAPACITY_HOLD")
        node_type = operation["nodeType"]
        if not isinstance(node_type, str) or not SAFE_ROLE.fullmatch(node_type):
            raise Hold("NODE_TYPE_HOLD")
        label = _label(operation["label"], 120)
        # Do not trust caller-supplied IDs/counters. Reserve unique IDs.
        count = nxt["node_counter"]
        while True:
            count += 1
            key = "ui_" + str(count)
            if key not in nodes:
                break
        nxt["node_counter"] = count
        nodes[key] = {
            "id": key, "type": node_type,
            "data": {"label": label, "role": "manual"},
            "energy": 1.0, "last_used": nxt["tick"], "cluster": None,
        }
        result = key
    elif kind == "set_label":
        if set(operation) != {"op", "nodeId", "label"}:
            raise Hold("LABEL_FIELDS_HOLD")
        key = operation["nodeId"]
        if not isinstance(key, str) or key not in nodes:
            raise Hold("NODE_NOT_FOUND_HOLD")
        label = _label(operation["label"], 120)
        record = nodes[key]
        if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
            raise Hold("NODE_DATA_HOLD")
        if record["data"].get("label") == label:
            raise Hold("NOOP_HOLD")
        record["data"]["label"] = label
        result = key
    elif kind == "add_edge":
        if set(operation) != {"op", "source", "target"}:
            raise Hold("EDGE_FIELDS_HOLD")
        src, dst = operation["source"], operation["target"]
        if not isinstance(src, str) or not isinstance(dst, str) or src not in nodes or dst not in nodes:
            raise Hold("EDGE_ENDPOINT_HOLD")
        if "->" in src or "->" in dst:
            raise Hold("EDGE_ID_AMBIGUITY_HOLD")
        key = src + "->" + dst
        if key in edges:
            raise Hold("EXISTING_RELATION_HOLD")
        edges[key] = {"weight": 1.0, "direction": "directed", "last_traversal": nxt["tick"]}
        result = key
    else:
        raise Hold("UNAPPROVED_OPERATION_HOLD")
    nxt["tick"] += 1
    if not set(state["nodes"]).issubset(nodes) or not set(state["edges"]).issubset(edges):
        raise Hold("HISTORICAL_GRAPH_ERASURE_HOLD")
    for key, value in state["edges"].items():
        if edges[key] != value:
            raise Hold("HISTORICAL_EDGE_CHANGED_HOLD")
    if len(nodes) > max_nodes:
        raise Hold("GRAPH_CAPACITY_HOLD")
    return nxt, result


def apply_transaction(root: Path, request: dict, *, max_nodes: int = 5000) -> dict:
    """Commit one explicit incremental change, never a full graph replacement.

    Holds on a stale SHA, invalid source, active transaction, no disk budget,
    archive/receipt conflict, or unexpected concurrent external file writer.
    In ambiguous post-crash state, require manual reconciliation rather than
    silently repeating a possibly completed mutation.
    """
    if type(request) is not dict or len(encoded(request)) > MAX_PATCH_BYTES:
        raise Hold("INVALID_REQUEST_BOUNDS_HOLD")
    if set(request) != {"requestId", "expectedSha256", "operation"}:
        raise Hold("REQUEST_FIELDS_HOLD")
    request_id, expected = request["requestId"], request["expectedSha256"]
    if not isinstance(request_id, str) or not REQUEST.fullmatch(request_id):
        raise Hold("REQUEST_ID_HOLD")
    if not isinstance(expected, str) or not HEX.fullmatch(expected):
        raise Hold("REVISION_FORMAT_HOLD")
    if type(max_nodes) is not int or not 1 <= max_nodes <= 100_000:
        raise Hold("CAPACITY_BOUND_HOLD")
    state_path, txdir = _root(root)
    source = state_path.read_bytes()
    _strict_json(source)
    if digest(source) != expected:
        raise Hold("STALE_REVISION_HOLD")
    updated, result = _apply(_strict_json(source), request["operation"], max_nodes)
    dest = encoded(updated)
    if len(dest) > MAX_GRAPH_BYTES:
        raise Hold("NEW_GRAPH_SIZE_HOLD")
    if shutil.disk_usage(state_path.parent).free < max(MIN_FREE_BYTES, len(source) * 3 + len(dest) * 2):
        raise Hold("DISK_RESERVE_HOLD")
    if not txdir.exists():
        txdir.mkdir(mode=0o700)
    if txdir.is_symlink() or not txdir.is_dir():
        raise Hold("TRANSACTION_DIRECTORY_HOLD")
    if len(list(txdir.glob("hrain-before-*.json"))) >= MAX_ARCHIVES:
        raise Hold("ARCHIVE_BUDGET_HOLD")
    lock = txdir / "transaction.lock"
    receipt = txdir / ("receipt-" + request_id.lower() + ".json")
    intent = txdir / ("intent-" + request_id.lower() + ".json")
    if receipt.exists() or intent.exists() or receipt.is_symlink() or intent.is_symlink():
        raise Hold("REQUEST_ALREADY_SEEN_OR_INCOMPLETE_HOLD")
    lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(lock_fd)
        if digest(state_path.read_bytes()) != expected:
            raise Hold("SOURCE_CHANGED_BEFORE_COMMIT_HOLD")
        before = txdir / ("hrain-before-" + expected + ".json")
        if before.is_symlink():
            raise Hold("ARCHIVE_SYMLINK_HOLD")
        if before.exists():
            if digest(before.read_bytes()) != expected:
                raise Hold("ARCHIVE_HASH_HOLD")
        else:
            _write_new(before, source)
        if digest(before.read_bytes()) != expected:
            raise Hold("ARCHIVE_VERIFICATION_HOLD")
        new_sha = digest(dest)
        evidence = {
            "schema": SCHEMA, "requestId": request_id.lower(), "op": request["operation"]["op"],
            "beforeSha256": expected, "afterSha256": new_sha,
            "beforeBytes": len(source), "afterBytes": len(dest),
            "resultId": result, "private": True, "productionUseAuthorized": False,
        }
        _write_new(intent, encoded(evidence))
        tmp = txdir / ("pending-" + request_id.lower() + ".json")
        _write_new(tmp, dest)
        if digest(state_path.read_bytes()) != expected:
            raise Hold("SOURCE_CHANGED_AT_COMMIT_HOLD")
        # NTFS/POSIX same-volume atomic replace, under the same writer lock.
        os.replace(tmp, state_path)
        if digest(state_path.read_bytes()) != new_sha:
            raise Hold("POST_COMMIT_HASH_MISMATCH_HOLD")
        _write_new(receipt, encoded(evidence))
        return {
            "status": "COMMITTED_INCREMENTAL_ONLY",
            "requestId": request_id.lower(),
            "revision": new_sha, "resultId": result,
            "beforeSha256": expected,
            "sourceGraphModified": True, "productionUseAuthorized": False,
        }
    finally:
        # An interrupted intent stays on disk for explicit reconciliation.
        lock.unlink(missing_ok=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--request-file", type=Path, required=True)
    args = parser.parse_args()
    if args.request_file.is_symlink() or args.request_file.stat().st_size > MAX_PATCH_BYTES:
        raise Hold("REQUEST_SOURCE_HOLD")
    req = json.loads(args.request_file.read_text(encoding="utf-8"))
    print(json.dumps(apply_transaction(args.root, req), sort_keys=True))


if __name__ == "__main__":
    main()
