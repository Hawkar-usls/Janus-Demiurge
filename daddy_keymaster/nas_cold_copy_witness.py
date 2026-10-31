#!/usr/bin/env python3
"""Offline, read-only integrity witness for owner-NAS Keymaster cold copies."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

POINTER_SCHEMA = "janus.nas.keymaster_meta_json_cold_pointer.v1"
OUTPUT_SCHEMA = "janus.keymaster.local_cold_copy_integrity_witness.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SIDECAR = re.compile(r"^([0-9a-fA-F]{64})\s+\*?MIRROR\.json$")
MAX_POINTER = 65536
MAX_MIRROR = 2_000_000


class WitnessHold(ValueError):
    pass


def _read(root: Path, relative: str, maximum: int) -> bytes:
    p = root / relative
    if p.is_symlink() or not p.is_file():
        raise WitnessHold("MISSING_OR_SYMLINK_COLD_FILE_HOLD:" + relative)
    before = p.stat()
    if not 0 < before.st_size <= maximum:
        raise WitnessHold("COLD_FILE_SIZE_HOLD:" + relative)
    raw = p.read_bytes()
    after = p.stat()
    if len(raw) != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise WitnessHold("CHANGED_DURING_READ_HOLD:" + relative)
    return raw


def verify(root: Path) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise WitnessHold("OFFLINE_COLD_ROOT_REQUIRED")
    if (root / "snapshots").is_symlink() or not (root / "snapshots").is_dir():
        raise WitnessHold("OFFLINE_SNAPSHOTS_DIR_REQUIRED")
    try:
        pointer = json.loads(_read(root, "LATEST.json", MAX_POINTER))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WitnessHold("LATEST_JSON_PARSE_HOLD") from exc
    if not isinstance(pointer, dict) or pointer.get("schema") != POINTER_SCHEMA:
        raise WitnessHold("LATEST_SCHEMA_HOLD")
    if pointer.get("mode") != "PASSIVE_COLD_COPY_NO_MODEL_EXECUTION":
        raise WitnessHold("COLD_COPY_MODE_HOLD")
    epoch, archives = pointer.get("active_epoch"), pointer.get("archive_count")
    if type(epoch) is not int or not 0 <= epoch <= 1_000_000:
        raise WitnessHold("EPOCH_BOUNDS_HOLD")
    if type(archives) is not int or not 0 <= archives <= 100_000:
        raise WitnessHold("ARCHIVE_COUNT_BOUNDS_HOLD")
    commit = pointer.get("source_commit_sha")
    target_hash = pointer.get("mirror_file_sha256")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise WitnessHold("SOURCE_COMMIT_SHA_HOLD")
    if not isinstance(target_hash, str) or not HEX64.fullmatch(target_hash):
        raise WitnessHold("MIRROR_EXPECTED_HASH_HOLD")
    semantic = pointer.get("snapshot_sha256")
    if not isinstance(semantic, str) or not HEX64.fullmatch(semantic):
        raise WitnessHold("UNVERIFIED_SEMANTIC_HASH_FORMAT_HOLD")
    mirror = _read(root, "MIRROR.json", MAX_MIRROR)
    digest = hashlib.sha256(mirror).hexdigest()
    if digest != target_hash:
        raise WitnessHold("LATEST_MIRROR_SHA256_MISMATCH")
    sidecar = _read(root, "MIRROR.sha256", 256)
    try:
        match = SIDECAR.fullmatch(sidecar.decode("ascii").strip())
    except UnicodeDecodeError as exc:
        raise WitnessHold("INVALID_SIDECAR_FORMAT_HOLD") from exc
    if match is None or match.group(1).lower() != digest:
        raise WitnessHold("SIDECAR_SHA256_MISMATCH")
    archived = _read(root, "snapshots/" + commit + ".json", MAX_MIRROR)
    if archived != mirror:
        raise WitnessHold("ARCHIVED_SNAPSHOT_NOT_BYTE_IDENTICAL")
    # The private mirror payload is never parsed, returned or imported.
    return {
        "schema": OUTPUT_SCHEMA,
        "status": "PASS_LOCAL_COLD_COPY_FILE_INTEGRITY_ONLY",
        "observed": {
            "active_epoch": epoch, "reported_archive_count": archives,
            "source_commit_sha": commit, "mirror_sha256": digest,
            "mirror_bytes": len(mirror), "pointer_match": True,
            "sidecar_match": True, "snapshot_byte_identical": True
        },
        "authority": {
            "read_only": True, "copy_contents_exposed": False,
            "source_commit_verified_over_network": False,
            "semantic_snapshot_hash_verified": False,
            "reported_archive_count_independently_verified": False,
            "offsite_backup_independence_verified": False,
            "disaster_restore_tested": False,
            "automatic_restore_or_promotion": False
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Owner-approved stable offline cold-copy directory")
    args = parser.parse_args()
    print(json.dumps(verify(args.root), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
