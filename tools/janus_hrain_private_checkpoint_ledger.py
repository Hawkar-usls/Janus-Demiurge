#!/usr/bin/env python3
"""JANUS HRAiN owner-private checkpoint ledger (manual, copy-first gate).

No autonomous engine imports, daemon, network, deletion, private upload, source
overwrite or production admission. Journal and archives stay in owner-local
artifacts/audits/private_graph_backups, never in GitHub.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from janus_hrain_lossless_shadow import make_shadow, expanded_bytes, MAX_BYTES
from janus_hrain_shadow_independent_verify import verify as independent_verify

SCHEMA = "janus.hrain.private_checkpoint_ledger.v1"
MAX_LEDGER_BYTES = 2_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def paths(root: Path) -> tuple[Path, Path, Path]:
    if root.name != "All Star" or root.is_symlink() or not root.is_dir():
        raise ValueError("OWNER_ALL_STAR_ROOT_ONLY")
    root = root.resolve(strict=True)
    logs = root / "raw_logs"
    audit = root / "artifacts" / "audits"
    backups = audit / "private_graph_backups"
    for folder in (logs, root / "artifacts", audit, backups):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("OWNER_PRIVATE_DIRECTORY_REQUIRED")
    source = logs / "hrain_graph_state.json"
    if source.is_symlink() or not source.is_file():
        raise ValueError("OWNER_PRIVATE_SOURCE_REQUIRED")
    ledger = backups / "hrain-checkpoint-ledger.jsonl"
    if ledger.is_symlink():
        raise ValueError("OWNER_LEDGER_SYMLINK_HOLD")
    return source, backups, ledger


def _archive_name(digest: str) -> str:
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("OWNER_ARCHIVE_DIGEST_HOLD")
    return "hrain-checkpoint-" + digest + ".json"


def read_ledger(ledger: Path, backups: Path) -> list[dict]:
    if not ledger.exists():
        return []
    if ledger.is_symlink() or ledger.stat().st_size > MAX_LEDGER_BYTES:
        raise ValueError("OWNER_LEDGER_SIZE_OR_SYMLINK_HOLD")
    raw = ledger.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("OWNER_LEDGER_TORN_WRITE_HOLD")
    entries = []
    previous = "0" * 64
    for line in raw.splitlines():
        entry = json.loads(line)
        if not isinstance(entry, dict) or entry.get("schema") != SCHEMA:
            raise ValueError("OWNER_LEDGER_SCHEMA_HOLD")
        expected = entry.get("entrySha256")
        record = {k: v for k, v in entry.items() if k != "entrySha256"}
        if expected != sha(canonical(record)) or record.get("prevEntrySha256") != previous:
            raise ValueError("OWNER_LEDGER_CHAIN_INVALID_HOLD")
        filename = _archive_name(record.get("sourceSha256", ""))
        if record.get("archive") != filename:
            raise ValueError("OWNER_LEDGER_ARCHIVE_PATH_HOLD")
        archive = backups / filename
        if archive.is_symlink() or not archive.is_file():
            raise ValueError("OWNER_LEDGER_MISSING_ARCHIVE_HOLD")
        if archive.stat().st_size > 42_000_000 or sha(archive.read_bytes()) != record.get("archiveSha256"):
            raise ValueError("OWNER_LEDGER_ARCHIVE_TAMPERED_HOLD")
        previous = expected
        entries.append(entry)
    return entries


def _write_exclusive(path: Path, contents: bytes):
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(contents)
        out.flush()
        os.fsync(out.fileno())


def checkpoint(root: Path, *, create: bool = False) -> dict:
    source_path, backups, ledger = paths(root)
    history = read_ledger(ledger, backups)
    if not create:
        return {
            "status": "CHECK_ONLY_VALID" if history else "CHECK_ONLY_NO_CHECKPOINT",
            "entries": len(history), "sourceModified": False,
            "productionUseAuthorized": False,
        }
    if source_path.stat().st_size > MAX_BYTES:
        raise ValueError("OWNER_SOURCE_SIZE_HOLD")
    original = source_path.read_bytes()
    digest = sha(original)
    if history and history[-1]["sourceSha256"] == digest:
        return {
            "status": "UNCHANGED_ALREADY_CHECKPOINTED",
            "entries": len(history), "sourceSha256": digest,
            "sourceModified": False, "productionUseAuthorized": False,
        }
    archive = backups / _archive_name(digest)
    if archive.is_symlink() or archive.exists():
        raise FileExistsError("OWNER_ARCHIVE_ALREADY_EXISTS_OR_ORPHAN_HOLD")
    lock = backups / "hrain-checkpoint-ledger.lock"
    lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(lock_fd)
        # Re-check the chain while lock is held.
        history = read_ledger(ledger, backups)
        packet = make_shadow(original)
        if expanded_bytes(packet) != original:
            raise ValueError("OWNER_ROUNDTRIP_HOLD")
        archive_bytes = canonical(packet) + b"\n"
        _write_exclusive(archive, archive_bytes)
        # Independent implementation checks exact live *file* bytes again.
        check = independent_verify(source_path, archive)
        if check["sourceSha256"] != digest or source_path.read_bytes() != original:
            raise ValueError("OWNER_SOURCE_CHANGED_DURING_CHECKPOINT_HOLD")
        row = {
            "schema": SCHEMA,
            "utc": datetime.now(timezone.utc).isoformat(),
            "sourceSha256": digest,
            "sourceBytes": len(original),
            "archive": archive.name,
            "archiveSha256": sha(archive_bytes),
            "originalNodes": check["originalNodes"],
            "originalEdges": check["originalEdges"],
            "prevEntrySha256": history[-1]["entrySha256"] if history else "0" * 64,
            "productionUseAuthorized": False,
        }
        row["entrySha256"] = sha(canonical(row))
        if not ledger.exists():
            _write_exclusive(ledger, canonical(row) + b"\n")
        else:
            fd = os.open(str(ledger), os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, "ab") as out:
                out.write(canonical(row) + b"\n")
                out.flush()
                os.fsync(out.fileno())
        checked = read_ledger(ledger, backups)
        if len(checked) != len(history) + 1:
            raise ValueError("OWNER_CHECKPOINT_LEDGER_POSTCONDITION_HOLD")
        return {
            "status": "OWNER_PRIVATE_CHECKPOINT_VERIFIED",
            "entries": len(checked), "sourceSha256": digest,
            "originalNodes": check["originalNodes"],
            "originalEdges": check["originalEdges"],
            "sourceModified": False, "productionUseAuthorized": False,
        }
    finally:
        # Only the lock this invocation created may be removed.
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--create", action="store_true", help="Explicit owner-private checkpoint, never active by default")
    args = parser.parse_args()
    print(json.dumps(checkpoint(args.root, create=args.create), sort_keys=True))


if __name__ == "__main__":
    main()
