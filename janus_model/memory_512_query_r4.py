"""JANUS Memory Cortex R4: controlled, exact-source JSON read API.

Reads the R3 SQLite FTS5 index from a verified local build. It never exposes
unbounded JSON, acts on retrieved text, or calls native inference. A small
allowlist of public scalar JSON fields can produce an exact, cited answer.
Everything else is source pointers only or honest refusal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from janus_model.memory_512_audit_index_r3 import (
    Hold, git_head, raw_from_tree, secure_relative, search_index, digest,
)

SCHEMA = "janus.native.memory_512_r4_controlled_read.v1"
MAX_QUERY_CHARS = 120
MAX_RESULT_COUNT = 8
MAX_DB_BYTES = 512 * 1024 * 1024
FIELDS = frozenset({
    "latest_completed_source_run",
    "latest_archived_source_run",
    "latest_durable_external_run",
    "coordination_status",
    "pilot_status",
    "latest_scientific_status",
    "schema_id",
})
STATUS_SCALAR = "VERIFIED_JSON_SCALAR"
STATUS_ABSENT = "VERIFIED_SOURCE_FIELD_NOT_PRESENT"
STATUS_NO_MATCH = "NO_VERIFIED_SOURCE_MATCH"
STATUS_POINTERS = "VERIFIED_SOURCE_POINTERS_ONLY"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


def _source_rows(db: Path, path: str) -> list[dict]:
    # Database and its path are runner-controlled; source paths are untrusted.
    secure_relative(path)
    conn = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT path,source_sha256,size_bytes,source_commit "
            "FROM documents WHERE path=?", (path,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return []
    return [{
        "path": row[0], "source_sha256": row[1],
        "size_bytes": row[2], "source_commit": row[3],
    }]


def _read_checked(row: dict, source_root: Path, commit: str) -> tuple[str, dict]:
    path = secure_relative(row.get("path"))
    if row.get("source_commit") != commit:
        raise Hold("R4_DB_SOURCE_COMMIT_DRIFT")
    claimed_sha = row.get("source_sha256")
    size = row.get("size_bytes")
    if (not isinstance(claimed_sha, str) or
            not re.fullmatch(r"[0-9a-f]{64}", claimed_sha) or
            type(size) is not int or size < 0):
        raise Hold("R4_BAD_SOURCE_ROW")
    raw = raw_from_tree(source_root, path, 1024 * 1024)
    if digest(raw) != claimed_sha or len(raw) != size:
        raise Hold("R4_SOURCE_SHA_OR_LENGTH_MISMATCH")
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise Hold("R4_SOURCE_ENCODING_HOLD") from exc
    citation = {
        "repository": "Hawkar-usls/janus-meta-registry",
        "commit": commit,
        "path": path,
        "source_sha256": claimed_sha,
        "verified_bytes": len(raw),
        "source_is_untrusted_data": True,
        "scientific_truth_inferred": False,
    }
    return value, citation


def controlled_query(db_path: Path, source_root: Path, *,
                     expected_commit: str, query: str, source_path: str = "",
                     field: str = "", limit: int = 5) -> dict:
    if (not isinstance(query, str) or not query.strip() or
            len(query) > MAX_QUERY_CHARS or
            not 1 <= limit <= MAX_RESULT_COUNT):
        raise Hold("R4_QUERY_BUDGET_INVALID")
    if not isinstance(expected_commit, str) or not SHA40.fullmatch(expected_commit):
        raise Hold("R4_EXPECTED_COMMIT_INVALID")
    if field and (field not in FIELDS or not source_path):
        raise Hold("R4_FIELD_NOT_ALLOWLISTED_OR_UNBOUND")
    if source_path:
        secure_relative(source_path)
    if (not db_path.is_file() or db_path.is_symlink() or
            db_path.stat().st_size > MAX_DB_BYTES):
        raise Hold("R4_INDEX_UNAVAILABLE_OR_TOO_LARGE")
    if git_head(source_root) != expected_commit:
        raise Hold("R4_PINNED_SOURCE_COMMIT_DRIFT")
    rows = (_source_rows(db_path, source_path) if source_path
            else search_index(db_path, query, limit=limit))
    rows = rows[:limit]
    citations = []
    answer_value = None
    answer_field = None
    answer_source_sha = None
    status = STATUS_NO_MATCH if not rows else STATUS_POINTERS

    for row in rows:
        text, cite = _read_checked(row, source_root, expected_commit)
        citations.append(cite)
        if field:
            try:
                data = json.loads(text)
            except (ValueError, TypeError) as exc:
                raise Hold("R4_JSON_SOURCE_MALFORMED") from exc
            if not isinstance(data, dict):
                raise Hold("R4_TOP_LEVEL_OBJECT_REQUIRED")
            value = data.get(field)
            if value is None:
                status = STATUS_ABSENT
            elif type(value) in (int, bool, float, str):
                answer_value = str(value)
                if len(answer_value.encode("utf-8")) > 256:
                    raise Hold("R4_SCALAR_ANSWER_TOO_LONG")
                answer_field = field
                answer_source_sha = cite["source_sha256"]
                status = STATUS_SCALAR
            else:
                status = STATUS_ABSENT
    report = {
        "schema": SCHEMA,
        "status": status,
        "read_mode": "PINNED_EXACT_PATH_FIELD" if source_path else "BOUNDED_FTS_SOURCE_POINTERS",
        "query_sha256": digest(query.encode("utf-8")),
        "source_commit": expected_commit,
        "request_field": field or None,
        "requested_source_path": source_path or None,
        "source_count": len(citations),
        "source_citations": citations,
        "answer_field": answer_field,
        "answer_scalar": answer_value,
        "answer_source_sha256": answer_source_sha,
        "native_model_inference_executed": False,
        "model_answer_quality_claimed": False,
        "new_model_weights_created": False,
        "source_command_executed": False,
        "registry_modified": False,
        "scientific_authority_delta": 0,
        "training_authority_granted": False,
    }
    report["receipt_sha256"] = digest(json.dumps(
        report, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        allow_nan=False,
    ).encode("utf-8"))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="JANUS R4 read-only source-grounded memory query")
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--expected-commit", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--source-path", default="")
    ap.add_argument("--field", default="")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.source_root.resolve(strict=True)
    if args.output.resolve().is_relative_to(root) or args.output.exists():
        raise Hold("R4_SOURCE_WRITE_OR_RECEIPT_OVERWRITE_FORBIDDEN")
    result = controlled_query(args.db, root, expected_commit=args.expected_commit,
                              query=args.query, source_path=args.source_path,
                              field=args.field, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "source_count": result["source_count"],
        "source_commit": result["source_commit"],
        "request_field": result["request_field"],
        "answer_scalar": result["answer_scalar"],
        "receipt_sha256": result["receipt_sha256"],
        "native_model_inference_executed": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
