#!/usr/bin/env python3
"""Read-only, metadata-only lineage for early JANUS SQLite code_dna snapshots.

This module NEVER executes, imports, writes, uploads or republishes recovered
source_code. The historical database may also contain sensitive vault data.
Read only from an owner-approved, stable offline SQLite snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

SCHEMA = "janus.nas.code_dna.metadata_only.v1"
MAX_DB_BYTES = 2_500_000_000
MAX_ROWS = 512
MAX_SOURCE_BYTES = 262_144
VALID_TAG = re.compile(r"^v\.[0-9a-f]{8}$")
VALID_BASENAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}\.py$")


class LineageHold(ValueError):
    """No evidence is emitted when an input violates its admission boundary."""


def _source_uri(path: Path) -> str:
    # sqlite accepts file:////server/share on Windows; normal paths use file:///.
    raw = str(path)
    if os.name == "nt" and raw.startswith("\\\\"):
        return "file://" + quote(raw.replace("\\", "/"), safe="/:") + "?mode=ro&immutable=1"
    return path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"


def build(source: Path) -> dict:
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise LineageHold("REGULAR_OFFLINE_SNAPSHOT_REQUIRED")
    before = source.stat()
    if before.st_size < 1024 or before.st_size > MAX_DB_BYTES:
        raise LineageHold("SOURCE_SIZE_BOUND_HOLD")
    if source.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise LineageHold("SQLITE_SNAPSHOT_EXTENSION_HOLD")

    rows = []
    try:
        with closing(sqlite3.connect(_source_uri(source), uri=True, timeout=2)) as db:
            db.execute("PRAGMA query_only=ON")
            # No SELECT from vault, personal memory, chat or model blobs.
            cursor = db.execute(
                "SELECT id, timestamp, version_tag, file_name, source_code "
                "FROM code_dna ORDER BY id ASC LIMIT ?", (MAX_ROWS + 1,)
            )
            for ident, timestamp, version_tag, original_name, code in cursor:
                if len(rows) >= MAX_ROWS:
                    raise LineageHold("CODE_DNA_ROW_CAP_HOLD")
                if type(ident) is not int or ident < 1:
                    raise LineageHold("BAD_ROW_ID_HOLD")
                if not isinstance(timestamp, str) or len(timestamp) > 40:
                    raise LineageHold("BAD_TIMESTAMP_HOLD")
                try:
                    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise LineageHold("BAD_TIMESTAMP_HOLD") from exc
                if not isinstance(version_tag, str) or not VALID_TAG.fullmatch(version_tag):
                    raise LineageHold("BAD_VERSION_TAG_HOLD")
                if not isinstance(original_name, str):
                    raise LineageHold("BAD_SOURCE_NAME_HOLD")
                basename = original_name.replace("\\", "/").rsplit("/", 1)[-1]
                if not VALID_BASENAME.fullmatch(basename):
                    raise LineageHold("BAD_SOURCE_NAME_HOLD")
                if not isinstance(code, str):
                    raise LineageHold("SOURCE_CODE_MUST_BE_TEXT_HOLD")
                encoded = code.encode("utf-8")
                if not encoded or len(encoded) > MAX_SOURCE_BYTES:
                    raise LineageHold("SOURCE_CODE_SIZE_HOLD")
                rows.append({
                    "id": ident,
                    "timestamp": timestamp,
                    "version_tag": version_tag,
                    "source_basename": basename,
                    "source_utf8_bytes": len(encoded),
                    "source_text_sha256": hashlib.sha256(encoded).hexdigest(),
                })
    except sqlite3.DatabaseError as exc:
        raise LineageHold("INVALID_OR_INACCESSIBLE_CODE_DNA_SQLITE_HOLD") from exc

    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise LineageHold("SOURCE_CHANGED_DURING_READ_HOLD")
    if not rows or [x["id"] for x in rows] != sorted({x["id"] for x in rows}):
        raise LineageHold("NO_OR_DUPLICATE_CODE_DNA_ROWS_HOLD")
    hashes = {x["source_text_sha256"] for x in rows}
    return {
        "schema": SCHEMA,
        "status": "READ_ONLY_HISTORICAL_METADATA_NOT_ACTIVE_RUNTIME",
        "authority": {
            "source_execution": False,
            "automatic_model_promotion": False,
            "database_mutation": False,
            "private_row_publication": False,
            "scientific_benchmark_certification": False,
            "source_file_sha256_computed": False,
        },
        "source_class": "OWNER_APPROVED_OFFLINE_SQLITE_CODE_DNA_ONLY",
        "snapshot_rows": len(rows),
        "distinct_code_sha256": len(hashes),
        "duplicate_snapshots": len(rows) - len(hashes),
        "earliest_record": min(x["timestamp"] for x in rows),
        "latest_record": max(x["timestamp"] for x in rows),
        "records": rows,
    }


def save_exclusive(destination: Path, manifest: dict) -> None:
    destination = Path(destination)
    if destination.is_symlink() or destination.suffix.lower() != ".json":
        raise LineageHold("NEW_JSON_OUTPUT_PATH_REQUIRED")
    # The output is deliberately opt-in and cannot overwrite existing data.
    payload = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Stable owner-approved SQLite snapshot; not a live WAL database")
    parser.add_argument("--output", type=Path, help="Optional new local JSON. Never overwrite an existing file")
    args = parser.parse_args()
    report = build(args.source)
    if args.output:
        save_exclusive(args.output, report)
        print(json.dumps({"schema": SCHEMA, "status": "LOCAL_REPORT_CREATED", "record_count": report["snapshot_rows"]}))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
