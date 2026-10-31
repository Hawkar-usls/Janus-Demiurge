"""JANUS DADDY_KEYMASTER immutable queue segments + Git-CAS rollover.

Rollover is one git commit: archived exact prior state, archive-chain head,
per-source tombstones, and empty active v1 queue. A non-force remote push is
the only commit point. An active or uncertain lease always stops rollover.
Not a backup at a different trust/provider domain.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from daddy_keymaster.broker import canonical, sha
from daddy_keymaster.git_cas_queue import (
    Conflict, GitCAS, RUNTIME_BRANCH, ZERO, _git, empty, verify,
)

HEAD_PATH = "state/relay_archive_head.json"
ARCHIVE_DIR = "state/archive_segments"
MARKER_DIR = "state/processed_sources"
HEAD_SCHEMA = "janus.daddy_keymaster.archive_head.v1"
ARCHIVE_SCHEMA = "janus.daddy_keymaster.archive_segment.v1"
MARKER_SCHEMA = "janus.daddy_keymaster.retired_source.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_SEGMENTS_PER_READ = 2  # Latest plus previous checksum, not a full mirror.


def _read_at(repo, head, path):
    # Check the exact immutable commit instead of local working files.
    check = _git(repo, "ls-tree", "-r", "--name-only", head, "--", path)
    names = check.stdout.decode().splitlines()
    if not names:
        return None
    if names != [path]:
        raise ValueError("ARCHIVE_AMBIGUOUS_GIT_TREE")
    result = _git(repo, "show", f"{head}:{path}")
    if len(result.stdout) > 200000:
        raise ValueError("ARCHIVE_FILE_TOO_LARGE")
    return json.loads(result.stdout)


def _verify_receipt(document, schema, body_fields):
    if not isinstance(document, dict):
        raise ValueError("ARCHIVE_RECEIPT_REQUIRED")
    expected = {"schema", *body_fields, "receipt_sha256"}
    if set(document) != expected or document["schema"] != schema:
        raise ValueError("ARCHIVE_BAD_RECEIPT_SCHEMA")
    actual = document["receipt_sha256"]
    if not isinstance(actual, str) or not HEX64.fullmatch(actual):
        raise ValueError("ARCHIVE_BAD_RECEIPT_DIGEST")
    if sha({k: v for k, v in document.items() if k != "receipt_sha256"}) != actual:
        raise ValueError("ARCHIVE_RECEIPT_TAMPERED")
    return document


def _archive_context(store, head):
    archive_head = _read_at(store.repo, head, HEAD_PATH)
    if archive_head is None:
        return 0, ZERO, None
    _verify_receipt(archive_head, HEAD_SCHEMA, (
        "serial", "segment_path", "segment_digest_sha256", "previous_head_digest_sha256",
    ))
    serial = archive_head["serial"]
    if type(serial) is not int or serial < 1 or serial > 1000000:
        raise ValueError("ARCHIVE_SERIAL_INVALID")
    path = f"{ARCHIVE_DIR}/{serial:08d}.json"
    if archive_head["segment_path"] != path:
        raise ValueError("ARCHIVE_PATH_MISMATCH")
    segment = _read_at(store.repo, head, path)
    _verify_receipt(segment, ARCHIVE_SCHEMA, (
        "serial", "source_ref", "previous_segment_digest_sha256",
        "queue", "queue_tip_sha256",
    ))
    if (segment["serial"] != serial or
        segment["receipt_sha256"] != archive_head["segment_digest_sha256"] or
        segment["queue_tip_sha256"] != segment["queue"]["tip_sha256"]):
        raise ValueError("ARCHIVE_SEGMENT_INCONSISTENT")
    verify(segment["queue"])
    previous_digest = segment["previous_segment_digest_sha256"]
    if previous_digest != archive_head["previous_head_digest_sha256"]:
        raise ValueError("ARCHIVE_LINK_MISMATCH")
    if serial == 1 and previous_digest != ZERO:
        raise ValueError("ARCHIVE_FIRST_LINK_MISMATCH")
    if serial > 1:
        previous_path = f"{ARCHIVE_DIR}/{serial-1:08d}.json"
        previous = _read_at(store.repo, head, previous_path)
        _verify_receipt(previous, ARCHIVE_SCHEMA, (
            "serial", "source_ref", "previous_segment_digest_sha256",
            "queue", "queue_tip_sha256",
        ))
        if previous["receipt_sha256"] != previous_digest:
            raise ValueError("ARCHIVE_CHAIN_TIP_MISMATCH")
    return serial, segment["receipt_sha256"], archive_head


def marker_at(store, head, source_digest):
    if not isinstance(source_digest, str) or not HEX64.fullmatch(source_digest):
        raise ValueError("ARCHIVE_SOURCE_INVALID")
    path = f"{MARKER_DIR}/{source_digest}.json"
    marker = _read_at(store.repo, head, path)
    if marker is None:
        return None
    _verify_receipt(marker, MARKER_SCHEMA, (
        "source_sha256", "segment", "segment_digest_sha256",
        "task_ids", "terminal_states",
    ))
    if marker["source_sha256"] != source_digest:
        raise ValueError("ARCHIVE_MARKER_SOURCE_MISMATCH")
    serial = marker["segment"]
    if type(serial) is not int or not 1 <= serial <= 1000000:
        raise ValueError("ARCHIVE_MARKER_SEGMENT_INVALID")
    segment_path = f"{ARCHIVE_DIR}/{serial:08d}.json"
    segment = _read_at(store.repo, head, segment_path)
    _verify_receipt(segment, ARCHIVE_SCHEMA, (
        "serial", "source_ref", "previous_segment_digest_sha256",
        "queue", "queue_tip_sha256",
    ))
    if (segment["receipt_sha256"] != marker["segment_digest_sha256"] or
        not isinstance(marker["task_ids"], list) or
        not isinstance(marker["terminal_states"], list) or
        len(marker["task_ids"]) != len(marker["terminal_states"])):
        raise ValueError("ARCHIVE_MARKER_SEGMENT_MISMATCH")
    actual = sorted(
        (tid, row["state"]) for tid, row in segment["queue"]["tasks"].items()
        if row["source_sha256"] == source_digest
    )
    if (actual != sorted(zip(marker["task_ids"], marker["terminal_states"])) or
        any(state not in ("COMPLETE", "SKIPPED") for _, state in actual)):
        raise ValueError("ARCHIVE_MARKER_PROJECTION_MISMATCH")
    return marker


def _sign(schema, body):
    obj = {"schema": schema, **body}
    return {**obj, "receipt_sha256": sha(obj)}


def status(store, current_source_sha256):
    head, active = store.read()
    serial, prev_digest, _ = _archive_context(store, head)
    archived = marker_at(store, head, current_source_sha256)
    return {"head": head, "state": active, "serial": serial,
            "previous_digest": prev_digest, "current_already_archived": archived is not None}


def _plan(state, source_sha256):
    verify(state)
    if not state["tasks"]:
        return "EMPTY"
    source_set = {row["source_sha256"] for row in state["tasks"].values()}
    if source_sha256 in source_set:
        return "CURRENT_SOURCE_IN_ACTIVE"
    if any(row["state"] in ("LEASED", "HOLD") for row in state["tasks"].values()):
        return "UNRESOLVED_LEASE"
    if any(row["state"] not in ("COMPLETE", "SKIPPED") for row in state["tasks"].values()):
        return "NONTERMINAL_TASK"
    return "READY"


def rotate_once(store, current_source_sha256):
    """One attempt. Caller may rerun after a Conflict, never force."""
    info = status(store, current_source_sha256)
    head, state = info["head"], info["state"]
    decision = _plan(state, current_source_sha256)
    if decision != "READY":
        return {"status": decision, "segment": info["serial"]}
    serial = info["serial"] + 1
    if serial > 1000000:
        raise ValueError("ARCHIVE_SEGMENT_BOUND")
    archive_path = f"{ARCHIVE_DIR}/{serial:08d}.json"
    if _read_at(store.repo, head, archive_path) is not None:
        raise ValueError("ARCHIVE_EXISTING_SEGMENT_COLLISION")
    source_groups = {}
    for tid, row in sorted(state["tasks"].items()):
        source_groups.setdefault(row["source_sha256"], []).append((tid, row["state"]))
    for source in source_groups:
        if marker_at(store, head, source) is not None:
            raise ValueError("ARCHIVE_SOURCE_ALREADY_RETIRED")
    segment = _sign(ARCHIVE_SCHEMA, {
        "serial": serial,
        "source_ref": head,
        "previous_segment_digest_sha256": info["previous_digest"],
        "queue": state,
        "queue_tip_sha256": state["tip_sha256"],
    })
    archive_head = _sign(HEAD_SCHEMA, {
        "serial": serial,
        "segment_path": archive_path,
        "segment_digest_sha256": segment["receipt_sha256"],
        "previous_head_digest_sha256": info["previous_digest"],
    })
    files = {
        "state/relay_queue.json": empty(),
        archive_path: segment,
        HEAD_PATH: archive_head,
    }
    for source, tasks in source_groups.items():
        files[f"{MARKER_DIR}/{source}.json"] = _sign(MARKER_SCHEMA, {
            "source_sha256": source, "segment": serial,
            "segment_digest_sha256": segment["receipt_sha256"],
            "task_ids": [tid for tid, _ in tasks],
            "terminal_states": [state for _, state in tasks],
        })
    if _git(store.repo, "status", "--porcelain").stdout.strip():
        raise ValueError("ARCHIVE_GIT_CLONE_DIRTY")
    # In particular, NEVER reset an active queue before the archival commit
    # is present on the same atomic remote ref update.
    current_head, current_state = store.read()
    if current_head != head or current_state != state:
        raise Conflict("ARCHIVE_STATE_MOVED")
    _git(store.repo, "checkout", "--detach", head)
    for path, content in files.items():
        dest = store.repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(canonical(content) + b"\n")
    # Force-add ONLY the explicit SHA/serial allowlist above: global project
    # .gitignore ignores state/ by design, but the dedicated state branch
    # must persist these immutable archive proofs together in one commit.
    _git(store.repo, "add", "-f", "--", *files)
    _git(store.repo, "-c", "user.name=janus-archive[bot]",
         "-c", "user.email=janus-archive@users.noreply.github.com",
         "commit", "-m", f"daddy-archive: immutable segment {serial}")
    pushed = _git(store.repo, "push", "--porcelain", "origin",
                  "HEAD:refs/heads/" + store.branch, check=False)
    if pushed.returncode:
        raise Conflict("ARCHIVE_CAS_PUSH_REFUSED")
    confirmed = status(store, current_source_sha256)
    if (confirmed["serial"] != serial or confirmed["state"] != empty() or
        confirmed["previous_digest"] != segment["receipt_sha256"]):
        raise ValueError("ARCHIVE_POSTCOMMIT_WITNESS_FAILED")
    return {"status": "ARCHIVED_ATOMIC_AND_RESET",
            "segment": serial, "archived_epoch": state["epoch"],
            "archive_sha256": segment["receipt_sha256"],
            "source_count": len(source_groups)}


def rotate_if_ready(store, source_sha256, attempts=3):
    if not isinstance(source_sha256, str) or not HEX64.fullmatch(source_sha256):
        raise ValueError("ARCHIVE_SOURCE_REQUIRED")
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("ARCHIVE_RETRY_BOUND")
    for n in range(attempts):
        try:
            return rotate_once(store, source_sha256)
        except Conflict:
            if n == attempts - 1:
                raise
    raise Conflict("ARCHIVE_NEVER_UNBOUNDED_RETRY")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    store = GitCAS(args.repo, branch=RUNTIME_BRANCH)
    result = rotate_if_ready(store, args.source_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
