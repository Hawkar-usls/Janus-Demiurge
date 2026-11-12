"""JANUS Memory Cortex R5: source-verified cross-run SQLite cache.

GitHub Actions caches are best-effort, revocable/expiring *copies*, not an
authoritative permanent service. Always replay Git/SHA source provenance and
the actual cached SQLite records before using one. Cache source data remains
untrusted; no model weights, research holdouts, or original registry changed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3

from janus_model.memory_512_audit_index_r3 import (
    Hold, _chunks, _relations, _run_ids, _sha_prefixes,
    audit_catalog, build_index, digest, git_head, raw_from_tree,
)

SCHEMA = "janus.native.memory_512_r5_cross_run_cache.v1"
EXPECTED_DOCS = 4712
EXPECTED_BYTES = 49460266
EXPECTED_SOURCE_COMMIT = "c8e47bb54e954ab122e111c97198131f048bd5fd"
EXPECTED_CATALOG_COMMIT = "6c9259c43d89569b11351bf8579a3775025fa2f0"
MAX_DB_BYTES = 512 * 1024 * 1024
MAX_CACHE_RECEIPT_BYTES = 16_384


def _sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DB_BYTES:
        raise Hold("R5_DB_MISSING_TOO_LARGE_OR_SYMLINK")
    h = __import__("hashlib").sha256()
    with path.open("rb") as f:
        while data := f.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def _validate_doc_rows(conn: sqlite3.Connection, eligible: list[dict]) -> tuple[int,int]:
    expected = sorted(eligible, key=lambda x: x["path"])
    actual = conn.execute(
        "SELECT path,source_sha256,size_bytes,source_commit FROM documents ORDER BY path"
    ).fetchall()
    wanted = [(x["path"],x["sha256"],x["size_bytes"],x["source_commit"])
              for x in expected]
    if actual != wanted:
        raise Hold("R5_CACHED_SOURCE_CATALOG_MISMATCH")
    return len(wanted), sum(row[2] for row in wanted)


def _validate_fulltext_and_relations(conn: sqlite3.Connection,
                                     source_root: Path, eligible: list[dict]) -> int:
    # Replay every chunk, not just the metadata rows: a forged cache cannot
    # secretly present different source text. All source inputs are hash-pinned.
    cursor = conn.execute("SELECT path,content FROM snippets ORDER BY rowid")
    got = cursor.fetchone()
    n = 0
    expected_relations = set()
    expected_runs = set()
    expected_hash_refs = set()
    for doc in eligible:
        raw = raw_from_tree(source_root, doc["path"], 1024 * 1024)
        if len(raw) != doc["size_bytes"] or digest(raw) != doc["sha256"]:
            raise Hold("R5_REPLAY_SOURCE_HASH_DRIFT")
        text = raw.decode("utf-8", errors="strict")
        for _, _, chunk in _chunks(text):
            if got != (doc["path"], chunk):
                raise Hold("R5_CACHED_SOURCE_CHUNKS_DIFFER")
            got = cursor.fetchone()
            n += 1
        if doc["extension"] == ".json":
            expected_relations.update((doc["path"],ref) for ref in _relations(text))
            expected_runs.update((doc["path"],ident) for ident in _run_ids(text))
            expected_hash_refs.update((doc["path"],ref) for ref in _sha_prefixes(text))
    if got is not None:
        raise Hold("R5_CACHED_SOURCE_CHUNKS_OVERFLOW")
    tables=[
        ("relations",expected_relations, "SELECT from_path,to_path FROM relations"),
        ("run_refs",expected_runs, "SELECT path,run_id FROM run_refs"),
        ("hash_refs",expected_hash_refs, "SELECT path,sha_prefix FROM hash_refs"),
    ]
    for name, expected, sql in tables:
        values = conn.execute(sql).fetchall()
        if len(values) != len(expected) or set(values) != expected:
            raise Hold("R5_CACHED_GRAPH_RELATIONS_DIFFER:" + name)
    return n


def verify_cached_index(db: Path, cache_receipt: Path,
                        catalog_root: Path, source_root: Path, *,
                        eligible: list[dict] | None = None,
                        audit: dict | None = None) -> dict:
    root = source_root.resolve(strict=True)
    catalog_root = catalog_root.resolve(strict=True)
    if git_head(root) != EXPECTED_SOURCE_COMMIT:
        raise Hold("R5_SOURCE_COMMIT_DRIFT")
    if git_head(catalog_root) != EXPECTED_CATALOG_COMMIT:
        raise Hold("R5_CATALOG_COMMIT_DRIFT")
    if cache_receipt.is_symlink() or not cache_receipt.is_file() or cache_receipt.stat().st_size > MAX_CACHE_RECEIPT_BYTES:
        raise Hold("R5_CACHE_RECEIPT_MISSING_OR_OVERSIZED")
    receipt = json.loads(cache_receipt.read_text(encoding="utf-8"))
    sig = receipt.get("receipt_sha256")
    payload = {k:v for k,v in receipt.items() if k!="receipt_sha256"}
    if not isinstance(sig,str) or sig != digest(
        json.dumps(payload,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode()):
        raise Hold("R5_CACHE_RECEIPT_TAMPERED")
    if (receipt.get("schema") != SCHEMA or
            receipt.get("catalog_commit") != EXPECTED_CATALOG_COMMIT or
            receipt.get("source_commit") != EXPECTED_SOURCE_COMMIT or
            receipt.get("indexed_documents") != EXPECTED_DOCS or
            receipt.get("verified_source_bytes") != EXPECTED_BYTES or
            receipt.get("model_weights_changed") is not False or
            receipt.get("raw_source_uploaded") is not False):
        raise Hold("R5_CACHE_METADATA_PIN_HOLD")
    if eligible is None or audit is None:
        audit, eligible = audit_catalog(catalog_root,root)
    if audit["hash_verified_unique_candidate_text_bytes"] != EXPECTED_BYTES or len(eligible) != EXPECTED_DOCS:
        raise Hold("R5_AUDIT_EXPECTATIONS_CHANGED")
    if receipt.get("manifest_sha256") != audit["manifest_sha256"]:
        raise Hold("R5_MANIFEST_HASH_DRIFT")
    if _sha_file(db) != receipt.get("sqlite_sha256"):
        raise Hold("R5_SQLITE_SHA_MISMATCH")
    conn=sqlite3.connect(f"file:{db.resolve()}?mode=ro",uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise Hold("R5_SQLITE_INTEGRITY_HOLD")
        docs, size = _validate_doc_rows(conn,eligible)
        chunks = _validate_fulltext_and_relations(conn,root,eligible)
        if docs != EXPECTED_DOCS or size != EXPECTED_BYTES or chunks != receipt.get("chunks"):
            raise Hold("R5_SQLITE_COUNTS_HOLD")
    finally:
        conn.close()
    return {
        "status":"REUSED_INDEX_VERIFIED_AGAINST_PINNED_SOURCE",
        "source_commit":EXPECTED_SOURCE_COMMIT,
        "catalog_commit":EXPECTED_CATALOG_COMMIT,
        "sqlite_sha256":receipt["sqlite_sha256"],
        "docs":docs,"verified_source_bytes":size,"chunks":chunks,
        "source_content_replayed":True,"cache_is_permanent":False,
        "model_weights_changed":False,
    }


def ensure_cached_index(cache_dir: Path, catalog_root: Path,
                        source_root: Path, *, allow_rebuild: bool = True) -> dict:
    root = source_root.resolve(strict=True)
    catalog_root = catalog_root.resolve(strict=True)
    dest = cache_dir.resolve()
    if dest.is_relative_to(root) or dest.is_relative_to(catalog_root):
        raise Hold("R5_CACHE_MUST_NOT_WRITE_IN_SOURCE")
    if dest.is_symlink():
        raise Hold("R5_CACHE_SYMLINK_HOLD")
    db=dest/"index.sqlite"
    receipt=dest/"index-receipt.json"
    audit, eligible = audit_catalog(catalog_root,root)
    if (audit["source_commit"] != EXPECTED_SOURCE_COMMIT or
            git_head(catalog_root) != EXPECTED_CATALOG_COMMIT or
            len(eligible) != EXPECTED_DOCS or
            audit["hash_verified_unique_candidate_text_bytes"] != EXPECTED_BYTES):
        raise Hold("R5_PINNED_AUDIT_CHANGED")
    if db.exists() or receipt.exists():
        if not db.is_file() or not receipt.is_file():
            raise Hold("R5_PARTIAL_CACHE_HOLD")
        result=verify_cached_index(db,receipt,catalog_root,root,eligible=eligible,audit=audit)
        return {**result,"db_path":str(db)}
    if not allow_rebuild:
        raise Hold("R5_CACHE_MISS_AND_BUILD_NOT_AUTHORIZED")
    dest.mkdir(parents=True,exist_ok=True)
    try:
        build=build_index(db,root,eligible,focus="",max_index_bytes=64*1024*1024)
        if build["indexed_docs"] != EXPECTED_DOCS or build["source_bytes_indexed"] != EXPECTED_BYTES:
            raise Hold("R5_BUILT_INDEX_COUNTS_HOLD")
        body={
            "schema":SCHEMA,
            "catalog_commit":EXPECTED_CATALOG_COMMIT,
            "source_commit":EXPECTED_SOURCE_COMMIT,
            "manifest_sha256":audit["manifest_sha256"],
            "sqlite_sha256":_sha_file(db),
            "indexed_documents":build["indexed_docs"],
            "verified_source_bytes":build["source_bytes_indexed"],
            "chunks":build["text_chunks"],
            "model_weights_changed":False,
            "raw_source_uploaded":False,
            "cache_is_permanent":False,
        }
        body["receipt_sha256"]=digest(json.dumps(
            body,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode())
        receipt.write_text(json.dumps(body,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        verified=verify_cached_index(db,receipt,catalog_root,root,eligible=eligible,audit=audit)
        return {**verified,"status":"BUILT_NEW_INDEX_AND_VERIFIED","db_path":str(db)}
    except Exception:
        # Do not leave a partial or invalid index to later be cached by Actions.
        db.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)
        raise


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog-root",type=Path,required=True)
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--cache-dir",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    if args.report.exists():
        raise Hold("R5_REPORT_ALREADY_EXISTS")
    if args.report.resolve().is_relative_to(args.source_root.resolve()):
        raise Hold("R5_REPORT_SOURCE_WRITE_FORBIDDEN")
    result=ensure_cached_index(args.cache_dir,args.catalog_root,args.source_root)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    report={k:v for k,v in result.items() if k!="db_path"}
    report["cache_storage"]="GITHUB_ACTIONS_CACHE_BEST_EFFORT_NOT_PERMANENT"
    args.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in (
        "status","source_commit","docs","verified_source_bytes","chunks",
        "cache_is_permanent")},sort_keys=True))


if __name__=="__main__":
    main()
