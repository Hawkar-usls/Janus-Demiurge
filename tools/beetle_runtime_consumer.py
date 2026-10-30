#!/usr/bin/env python3
"""Triage durable Beetle discoveries into source-bound research questions.

Offline, single-writer consumer. Results and receipts are immutable; the cursor
advances only after both exist. The receiver workflow commits them together.
This proves deterministic triage, not model learning or independent verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

REPOSITORY = "Hawkar-usls/Janus-Demiurge"
CONTEXT_SCHEMA = "janus.beetle.runtime_context.v1"
RESULT_SCHEMA = "janus.beetle.triage_result.v1"
RECEIPT_SCHEMA = "janus.beetle.processing_receipt.v1"
CURSOR_SCHEMA = "janus.beetle.processing_ack.v1"
PROCESSOR = "BEETLE_RESEARCH_TRIAGE_V1"
STATUS = "TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED"
INBOX_STATUS = "INBOX_DURABLE_UNVERIFIED__NOT_RUNTIME_CONSUMPTION"
CLAIM_CEILING = "DISCOVERY_MEMORY_ONLY__TARGET_REPO_MUST_VERIFY_INDEPENDENTLY"
CAPABILITIES = {"may_generate_research_questions": True, "is_verified_evidence": False,
                "may_grant_mutation_authority": False, "is_direct_gradient_signal": False}
MAX_ROUTES = 8


def canonical_bytes(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, limit: int) -> tuple[dict, bytes]:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("BEETLE_INPUT_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("BEETLE_OBJECT_REQUIRED")
    return obj, raw


def _hex(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("BEETLE_TEXT_REQUIRED")
    return " ".join(value.split())[:limit]


def _identity(value: object, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or any(c.isspace() for c in value):
        raise ValueError("BEETLE_IDENTITY_REJECTED")
    return value


def _write(path: Path, obj: dict, *, immutable: bool = False) -> None:
    raw = canonical_bytes(obj) + b"\n"
    if immutable and path.exists():
        if path.read_bytes() != raw:
            raise ValueError("BEETLE_IMMUTABLE_ARTIFACT_CONFLICT")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # One writer is required (the receiver's workflow concurrency group).
    fd, temporary = tempfile.mkstemp(prefix=".beetle-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_queue(queue: dict, ack: dict) -> list[dict]:
    entries = queue.get("entries")
    if (queue.get("schema") != "janus.beetle.delivery_queue.v1" or
            queue.get("target_repository") != REPOSITORY or
            not isinstance(entries, list) or len(entries) > 10000 or
            type(queue.get("next_sequence")) is not int or queue["next_sequence"] != len(entries) + 1):
        raise ValueError("BEETLE_QUEUE_REJECTED")
    seen = set()
    for number, entry in enumerate(entries, 1):
        if (not isinstance(entry, dict) or type(entry.get("sequence")) is not int or
                entry["sequence"] != number or not _hex(entry.get("batch_id"), 20) or
                not _hex(entry.get("sha256"), 64) or entry["batch_id"] in seen):
            raise ValueError("BEETLE_QUEUE_SEQUENCE_OR_ID_REJECTED")
        seen.add(entry["batch_id"])
    last = ack.get("last_sequence")
    if (ack.get("schema") != "janus.beetle.inbox_ack.v1" or
            ack.get("target_repository") != REPOSITORY or ack.get("status") != INBOX_STATUS or
            type(last) is not int or not 0 <= last <= len(entries)):
        raise ValueError("BEETLE_DELIVERY_ACK_REJECTED")
    if last and any(ack.get(k) != entries[last - 1][k] for k in ("batch_id", "sha256")):
        raise ValueError("BEETLE_DELIVERY_ACK_BINDING_REJECTED")
    return entries[:last]


def triage(packet: dict, entry: dict, processor_sha256: str) -> dict:
    if (packet.get("schema") != "janus.beetle.repo_memory_batch.v1" or
            packet.get("target_repository") != REPOSITORY or packet.get("batch_id") != entry["batch_id"] or
            packet.get("claim_ceiling") != CLAIM_CEILING):
        raise ValueError("BEETLE_BATCH_REJECTED")
    items = packet.get("items")
    if not isinstance(items, list) or len(items) > 1024:
        raise ValueError("BEETLE_ITEMS_REJECTED")
    rows = []
    for index, item in enumerate(items):
        if (not isinstance(item, dict) or item.get("schema") not in {
                "janus.beetle.repo_memory_item.v1", "janus.beetle.repo_memory_item.v2"} or
                item.get("target_repository") != REPOSITORY or
                item.get("epistemic_status") != "DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY"):
            raise ValueError("BEETLE_ITEM_AUTHORITY_OR_ADDRESS_REJECTED")
        url = _identity(item.get("url"), 2048)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("BEETLE_SOURCE_URL_REJECTED")
        score = item.get("score", 0)
        if type(score) not in {int, float} or not math.isfinite(score):
            raise ValueError("BEETLE_PRIORITY_REJECTED")
        rows.append({
            "item_index": index, "candidate_id": _identity(item.get("candidate_id"), 128),
            "context_id": _identity(item.get("context_id"), 128), "title": _text(item.get("title"), 140),
            "source_url": url, "direction_id": _identity(item.get("direction_id"), 160),
            "score": score, "disposition": "DEFERRED_BY_BOUNDED_WINDOW",
        })
    selected = []
    seen_urls = set()
    seen_directions = set()
    ranked = sorted(rows, key=lambda r: (-r["score"], r["item_index"]))
    # Preserve direction diversity before filling spare slots. Neither priority
    # nor repeated lenses of one URL establish independent corroboration.
    for diverse in (True, False):
        for row in ranked:
            if row["source_url"] in seen_urls or (diverse and row["direction_id"] in seen_directions):
                continue
            if len(selected) == MAX_ROUTES:
                break
            row["disposition"] = "RESEARCH_QUESTION_QUEUED"
            selected.append(row)
            seen_urls.add(row["source_url"])
            seen_directions.add(row["direction_id"])
    return {"schema": RESULT_SCHEMA, "processor_id": PROCESSOR, "processor_sha256": processor_sha256,
            "batch_id": entry["batch_id"], "sequence": entry["sequence"], "input_sha256": entry["sha256"],
            "status": STATUS, "items_triaged": len(rows), "items": rows,
            "research_routes": [{k: row[k] for k in ("candidate_id", "context_id", "title", "source_url", "direction_id")}
                                for row in selected], "capabilities": dict(CAPABILITIES)}


def _validate_saved(output: Path, entry: dict, processor_sha256: str) -> tuple[dict, dict]:
    receipt, _ = _read(output / "receipts" / f"{entry['batch_id']}.json", 100_000)
    result, raw = _read(output / "results" / f"{entry['batch_id']}.json", 8_000_000)
    if (receipt.get("schema") != RECEIPT_SCHEMA or result.get("schema") != RESULT_SCHEMA or
            receipt.get("result_sha256") != digest(raw) or receipt.get("status") != STATUS or
            result.get("status") != STATUS or result.get("capabilities") != CAPABILITIES or
            receipt.get("authority_delta") != 0 or type(receipt.get("authority_delta")) is not int):
        raise ValueError("BEETLE_SAVED_RESULT_REJECTED")
    for obj in (receipt, result):
        if (obj.get("processor_id") != PROCESSOR or obj.get("processor_sha256") != processor_sha256 or
                obj.get("batch_id") != entry["batch_id"] or obj.get("sequence") != entry["sequence"] or
                obj.get("input_sha256") != entry["sha256"]):
            raise ValueError("BEETLE_SAVED_BINDING_REJECTED")
    return result, receipt


def _context(results: list[dict], sequence: int) -> dict:
    routes = []
    seen = set()
    for result in reversed(results):
        for route in result["research_routes"]:
            if route["source_url"] in seen:
                continue
            routes.append({**route, "batch_id": result["batch_id"], "input_sha256": result["input_sha256"]})
            seen.add(route["source_url"])
            if len(routes) == MAX_ROUTES:
                break
        if len(routes) == MAX_ROUTES:
            break
    obj = {"schema": CONTEXT_SCHEMA, "status": STATUS, "target_repository": REPOSITORY,
           "last_processed_sequence": sequence, "research_routes": routes,
           "hypothesis_routes": [r["title"] for r in routes], "capabilities": dict(CAPABILITIES)}
    obj["context_sha256"] = digest(canonical_bytes(obj))
    return obj


def load_context(path: Path) -> dict:
    obj, _ = _read(path, 100_000)
    body = dict(obj)
    context_sha = body.pop("context_sha256", None)
    routes = obj.get("research_routes")
    sequence = obj.get("last_processed_sequence")
    if (obj.get("schema") != CONTEXT_SCHEMA or obj.get("status") != STATUS or
            obj.get("target_repository") != REPOSITORY or obj.get("capabilities") != CAPABILITIES or
            context_sha != digest(canonical_bytes(body)) or not isinstance(routes, list) or len(routes) > MAX_ROUTES or
            type(sequence) is not int or sequence < 0 or (sequence == 0 and routes) or
            any(not isinstance(r, dict) or not isinstance(r.get("title"), str) or not r["title"].strip() or
                len(r["title"]) > 140 or not _hex(r.get("batch_id"), 20) or not _hex(r.get("input_sha256"), 64)
                for r in routes) or
            obj.get("hypothesis_routes") != [r["title"] for r in routes]):
        raise ValueError("BEETLE_RUNTIME_CONTEXT_REJECTED")
    return obj


def consume(queue_path: Path, inbox: Path, output: Path, *, source_commit: str,
            consumer_commit: str, max_batches: int = 16) -> dict:
    if not _hex(source_commit, 40) or not _hex(consumer_commit, 40) or type(max_batches) is not int or not 1 <= max_batches <= 96:
        raise ValueError("BEETLE_CONSUMER_BOUNDS_REJECTED")
    queue, queue_raw = _read(queue_path, 32_000_000)
    ack, _ = _read(inbox / "ACK.json", 100_000)
    delivered = validate_queue(queue, ack)
    processor_sha = digest(Path(__file__).read_bytes())
    cursor_path = output / "PROCESSING_ACK.json"
    cursor = _read(cursor_path, 100_000)[0] if cursor_path.exists() else None
    last = cursor.get("last_sequence") if cursor else 0
    if cursor and (cursor.get("schema") != CURSOR_SCHEMA or cursor.get("status") != STATUS or
                   cursor.get("target_repository") != REPOSITORY or cursor.get("processor_sha256") != processor_sha):
        raise ValueError("BEETLE_PROCESSING_CURSOR_REJECTED")
    if type(last) is not int or not 0 <= last <= len(delivered):
        raise ValueError("BEETLE_PROCESSING_SEQUENCE_REJECTED")
    results = []
    for entry in delivered[:last]:
        result, receipt = _validate_saved(output, entry, processor_sha)
        results.append(result)
    if last and (cursor.get("batch_id") != delivered[last - 1]["batch_id"] or
                 cursor.get("receipt_sha256") != digest((output / "receipts" / f"{delivered[last - 1]['batch_id']}.json").read_bytes())):
        raise ValueError("BEETLE_PROCESSING_CURSOR_BINDING_REJECTED")
    # Validate the entire bounded window before creating any result or cursor.
    prepared = []
    for entry in delivered[last:last + max_batches]:
        packet, raw = _read(inbox / "batches" / f"{entry['batch_id']}.json", 4_000_000)
        if digest(raw) != entry["sha256"]:
            raise ValueError("BEETLE_BATCH_HASH_REJECTED")
        prepared.append((entry, triage(packet, entry, processor_sha)))
    for entry, result in prepared:
        result_path = output / "results" / f"{entry['batch_id']}.json"
        receipt_path = output / "receipts" / f"{entry['batch_id']}.json"
        _write(result_path, result, immutable=True)
        if receipt_path.exists():
            _validate_saved(output, entry, processor_sha)
        else:
            _write(receipt_path, {"schema": RECEIPT_SCHEMA, "status": STATUS, "processor_id": PROCESSOR,
                   "processor_sha256": processor_sha, "consumer_source_commit": consumer_commit,
                   "delivery_source_commit": source_commit, "delivery_manifest_sha256": digest(queue_raw),
                   "batch_id": entry["batch_id"], "sequence": entry["sequence"], "input_sha256": entry["sha256"],
                   "result_sha256": digest(result_path.read_bytes()), "authority_delta": 0}, immutable=True)
        results.append(result)
        last = entry["sequence"]
        _write(cursor_path, {"schema": CURSOR_SCHEMA, "status": STATUS, "target_repository": REPOSITORY,
               "processor_sha256": processor_sha, "last_sequence": last, "batch_id": entry["batch_id"],
               "receipt_sha256": digest(receipt_path.read_bytes())})
    # A crash after cursor persistence is repaired by rebuilding this derived cache.
    context = _context(results, last)
    _write(output / "CONTEXT.json", context)
    return {"status": STATUS, "new_batches": len(prepared), "last_sequence": last,
            "remaining_delivered": len(delivered) - last, "research_route_count": len(context["hypothesis_routes"]),
            "context_sha256": context["context_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-manifest", required=True)
    parser.add_argument("--inbox-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--consumer-commit", required=True)
    parser.add_argument("--max-batches", type=int, default=16)
    args = parser.parse_args()
    print(json.dumps(consume(Path(args.delivery_manifest), Path(args.inbox_dir), Path(args.out_dir),
          source_commit=args.source_commit, consumer_commit=args.consumer_commit, max_batches=args.max_batches), sort_keys=True))


if __name__ == "__main__":
    main()
