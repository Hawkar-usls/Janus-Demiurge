"""JANUS Memory Cortex 512M R3: hash-audited, read-only corpus + bounded FTS.

This indexes a pinned *public* Meta Registry snapshot, not a neural context
window. A catalog row is metadata until its exact source bytes and type are
verified. The index is ephemeral (runner temp), never a Git-tracked brain.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

MANIFEST_SCHEMA = "janus.hrain.full_memory_manifest.v1"
SHARD_SCHEMA = "janus.hrain.full_memory_shard.v1"
REPOSITORY = "Hawkar-usls/janus-meta-registry"
TARGET_BYTES = 512 * 1024 * 1024
INDEX_CAP_BYTES = 16 * 1024 * 1024
CHUNK_BYTES = 4096
MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOTAL_CATALOG_BYTES = 1024 * 1024 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
TEXT_EXTENSIONS = {".json", ".jsonl", ".txt", ".md"}
PUBLIC_NAMESPACES = {"EYE", "data", "docs", "experiments", "modules", "records",
                     "registry", "research", "reports", "scoby-skingpt"}
FORBIDDEN = re.compile(r"(^|[./_-])(holdout|blind|sealed|secret|secrets|password|"
                       r"credential|credentials|api[-_]?key|private|token|tokens)"
                       r"(?=$|[./_-])", re.I)
REF_FIELDS = {"related_paths", "source_paths", "related", "references"}
MAX_RELATIONS_PER_DOC = 12
SCHEMA = "janus.native.memory_cortex_512m_r3_audit.v1"


class Hold(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_head(root: Path) -> str:
    try:
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=15,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise Hold("SOURCE_GIT_HEAD_UNAVAILABLE") from exc
    if not SHA40.fullmatch(head):
        raise Hold("SOURCE_COMMIT_INVALID")
    return head


def secure_relative(path: object) -> str:
    if not isinstance(path, str) or not path or len(path) > 600 or "\\" in path:
        raise Hold("PATH_INVALID")
    parts = path.split("/")
    if path.startswith("/") or any(x in ("", ".", "..", ".git") for x in parts):
        raise Hold("PATH_INVALID")
    return path


def raw_from_tree(root: Path, path: str, max_bytes: int) -> bytes:
    secure_relative(path)
    root = root.resolve(strict=True)
    cursor = root
    for part in path.split("/"):
        cursor = cursor / part
        if cursor.is_symlink():
            raise Hold("SOURCE_SYMLINK_REJECTED")
    try:
        target = cursor.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise Hold("SOURCE_PATH_ESCAPE")
        if target.stat().st_size > max_bytes:
            raise Hold("SOURCE_SIZE_LIMIT")
        return target.read_bytes()
    except (OSError, RuntimeError) as exc:
        raise Hold("SOURCE_MISSING") from exc


def must_be_read_only(authority: object) -> None:
    if not isinstance(authority, dict):
        raise Hold("AUTHORITY_INVALID")
    if (authority.get("read_only") is not True or
            authority.get("delete_allowed") is not False or
            authority.get("source_mutation_allowed") is not False or
            authority.get("scientific_authority_granted") is not False):
        raise Hold("AUTHORITY_ESCALATION")


def classify(meta: dict) -> str:
    path = secure_relative(meta.get("path"))
    if (meta.get("read_only") is not True or
            meta.get("scientific_authority_granted") is not False):
        raise Hold("OBJECT_AUTHORITY_INVALID")
    if meta.get("extension") not in TEXT_EXTENSIONS:
        return "NON_TEXT_EXTENSION"
    if path.split("/")[0] not in PUBLIC_NAMESPACES:
        return "NON_RESEARCH_NAMESPACE"
    if FORBIDDEN.search(path) or "/native_model_reflections/" in path.lower():
        return "PROTECTED_OR_GENERATED"
    if "/generated/" in path.lower() and ("reflection" in path.lower() or "checkpoint" in path.lower()):
        return "PROTECTED_OR_GENERATED"
    if type(meta.get("size_bytes")) is not int or meta["size_bytes"] < 0:
        raise Hold("OBJECT_SIZE_INVALID")
    if meta["size_bytes"] > MAX_SOURCE_BYTES:
        return "OBJECT_TOO_LARGE_FOR_R3"
    return "CANDIDATE_TEXT"


def _read_manifest(root: Path) -> tuple[dict, bytes]:
    raw = raw_from_tree(root, "assets/hrain-full-memory/manifest.json", 500_000)
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or obj.get("schema") != MANIFEST_SCHEMA or
            obj.get("status") != "FULL_CURRENT_TRACKED_TREE_CATALOG" or
            obj.get("source_repository") != REPOSITORY or
            not SHA40.fullmatch(str(obj.get("source_commit") or ""))):
        raise Hold("MANIFEST_SCHEMA_OR_SOURCE_INVALID")
    must_be_read_only(obj.get("authority"))
    if obj.get("coverage", {}).get("coverage_complete") is not True:
        raise Hold("MANIFEST_COVERAGE_NOT_COMPLETE")
    return obj, raw


def audit_catalog(manifest_root: Path, source_root: Path, *,
                  max_total_bytes: int = MAX_TOTAL_CATALOG_BYTES) -> tuple[dict, list[dict]]:
    start = time.monotonic()
    manifest, manifest_raw = _read_manifest(manifest_root)
    source_commit = manifest["source_commit"]
    if git_head(source_root) != source_commit:
        raise Hold("SOURCE_SNAPSHOT_COMMIT_DRIFT")
    shards = manifest.get("sharding", {}).get("shards")
    if (not isinstance(shards, list) or
            len(shards) != manifest.get("sharding", {}).get("shard_count") or
            not 1 <= len(shards) <= 512):
        raise Hold("SHARD_SET_INCOMPLETE")
    seen_paths: set[str] = set()
    metadata_candidate_digests: set[str] = set()
    verified_candidate_digests: set[str] = set()
    eligible: list[dict] = []
    rejected = Counter()
    bytes_by_reason = Counter()
    metadata_bytes = 0
    count = 0
    validated_count = 0
    validated_bytes = 0
    unique_verified_bytes = 0
    unique_metadata_candidate_bytes = 0
    metadata_candidate_count = 0
    manifest_object_limit = max_total_bytes

    for index, shard_meta in enumerate(shards):
        shard_path = secure_relative(shard_meta.get("path"))
        if (shard_meta.get("index") != index or
                shard_path != f"assets/hrain-full-memory/shards/{index:04}.json" or
                not SHA64.fullmatch(str(shard_meta.get("sha256") or ""))):
            raise Hold("SHARD_PATH_OR_ORDER_INVALID")
        raw = raw_from_tree(manifest_root, shard_path, 8_000_000)
        if digest(raw) != shard_meta["sha256"]:
            raise Hold("SHARD_SHA_MISMATCH:" + shard_path)
        doc = json.loads(raw)
        if (doc.get("schema") != SHARD_SCHEMA or
                doc.get("status") != "READ_ONLY_FULL_CURRENT_MEMORY_SHARD" or
                doc.get("source_commit") != source_commit or
                doc.get("source_repository") != REPOSITORY or
                doc.get("shard_index") != index):
            raise Hold("SHARD_SOURCE_OR_SCHEMA_INVALID")
        must_be_read_only(doc.get("authority"))
        objs = doc.get("objects")
        if (not isinstance(objs, list) or
                len(objs) != doc.get("object_count") or
                len(objs) != shard_meta.get("object_count")):
            raise Hold("SHARD_OBJECT_COUNT_MISMATCH")
        if not objs or objs[0].get("path") != shard_meta.get("first_path") or objs[-1].get("path") != shard_meta.get("last_path"):
            raise Hold("SHARD_PATH_RANGE_MISMATCH")
        for meta in objs:
            if not isinstance(meta, dict):
                raise Hold("OBJECT_NOT_MAPPING")
            path = secure_relative(meta.get("path"))
            if path in seen_paths:
                raise Hold("DUPLICATE_CATALOG_PATH")
            seen_paths.add(path)
            sha = meta.get("sha256")
            if not isinstance(sha, str) or not SHA64.fullmatch(sha):
                raise Hold("OBJECT_SHA_INVALID")
            size = meta.get("size_bytes")
            if type(size) is not int or size < 0:
                raise Hold("OBJECT_SIZE_INVALID")
            metadata_bytes += size
            count += 1
            if metadata_bytes > manifest_object_limit:
                raise Hold("CATALOG_BYTE_CAP_EXCEEDED")
            reason = classify(meta)
            if reason == "CANDIDATE_TEXT":
                metadata_candidate_count += 1
                if sha not in metadata_candidate_digests:
                    unique_metadata_candidate_bytes += size
                    metadata_candidate_digests.add(sha)
                try:
                    data = raw_from_tree(source_root, path, MAX_SOURCE_BYTES)
                    if len(data) != size or digest(data) != sha:
                        raise Hold("SOURCE_SHA_OR_SIZE_MISMATCH:" + path)
                    text = data.decode("utf-8", errors="strict")
                    if meta["extension"] == ".json":
                        json.loads(text)
                    elif meta["extension"] == ".jsonl":
                        for line in text.splitlines():
                            if line.strip():
                                json.loads(line)
                    # .md and .txt require UTF8 but not special parsing.
                except Hold:
                    raise
                except (UnicodeError, ValueError):
                    reason = "INVALID_UTF8_OR_JSON"
                if reason == "CANDIDATE_TEXT":
                    validated_count += 1
                    validated_bytes += size
                    if sha not in verified_candidate_digests:
                        unique_verified_bytes += size
                        verified_candidate_digests.add(sha)
                        eligible.append({
                            "path": path, "sha256": sha,
                            "size_bytes": size, "extension": meta["extension"],
                            "namespace": meta["namespace"],
                            "source_commit": source_commit,
                        })
            if reason != "CANDIDATE_TEXT":
                rejected[reason] += 1
                bytes_by_reason[reason] += size

    if (count != manifest.get("coverage", {}).get("cataloged_blob_count") or
            count != manifest.get("coverage", {}).get("tracked_blob_count") -
                manifest.get("coverage", {}).get("generated_self_export_exclusion_count") or
            metadata_bytes != manifest.get("statistics", {}).get("cataloged_bytes")):
        raise Hold("MANIFEST_TOTALS_DO_NOT_RECONCILE")
    body = {
        "schema": SCHEMA,
        "status": "SOURCE_HASHES_AND_TEXT_PARSES_VERIFIED__RETRIEVAL_SCOPE_CANDIDATE",
        "manifest_sha256": digest(manifest_raw),
        "manifest_checkout_commit": git_head(manifest_root),
        "source_commit": source_commit,
        "source_repository": REPOSITORY,
        "target_bytes": TARGET_BYTES,
        "catalog_files": count,
        "cataloged_mixed_bytes": metadata_bytes,
        "manifest_shards_verified": len(shards),
        "metadata_text_candidate_files": metadata_candidate_count,
        "metadata_unique_text_candidate_bytes": unique_metadata_candidate_bytes,
        "hash_verified_parsed_text_files": validated_count,
        "hash_verified_parsed_text_bytes_with_duplicates": validated_bytes,
        "hash_verified_unique_candidate_text_bytes": unique_verified_bytes,
        "unique_retrieval_candidate_objects": len(eligible),
        "remaining_gap_bytes": max(0, TARGET_BYTES - unique_verified_bytes),
        "excluded_objects_by_reason": dict(sorted(rejected.items())),
        "excluded_bytes_by_reason": dict(sorted(bytes_by_reason.items())),
        "scope": "PUBLIC_META_REGISTRY_PINNED_CURRENT_TREE_ONLY",
        "consent_or_training_cleared": False,
        "content_citation_ready_after_exact_source_replay": True,
        "machine_verified_text_is_independent_scientific_evidence": False,
        "full_git_history_covered": False,
        "atlas_external_repositories_included": False,
        "user_private_sources_included": False,
        "native_v1_modified": False,
        "model_answer_quality_measured": False,
        "seconds_audit": round(time.monotonic() - start, 2),
    }
    body["receipt_sha256"] = digest(json.dumps(body,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode("utf-8"))
    return body, eligible


def _chunks(text: str, limit: int = CHUNK_BYTES) -> list[tuple[int, int, str]]:
    raw = text.encode("utf-8")
    out = []
    i = 0
    while i < len(raw):
        j = min(i + limit, len(raw))
        while j < len(raw) and j > i and (raw[j] & 0xC0) == 0x80:
            j -= 1
        if j <= i:
            raise Hold("CHUNK_UTF8_BOUNDARY_INVALID")
        chunk = raw[i:j].decode("utf-8", errors="strict")
        out.append((i, j, chunk))
        i = j
    return out


def _relations(text: str) -> list[str]:
    try:
        obj = json.loads(text)
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    out = []
    for key in REF_FIELDS:
        vals = obj.get(key)
        if not isinstance(vals, list):
            continue
        for value in vals[:MAX_RELATIONS_PER_DOC]:
            if isinstance(value, str) and value.endswith(".json"):
                try:
                    out.append(secure_relative(value))
                except Hold:
                    continue
    return list(dict.fromkeys(out))[:MAX_RELATIONS_PER_DOC]


def _run_ids(text: str) -> list[str]:
    """Only explicit source-run fields are associative keys, never proof."""
    try:
        obj = json.loads(text)
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    fields = {"source_run_id", "run_id", "latest_source_run",
              "latest_archived_source_run", "latest_completed_source_run",
              "latest_durable_external_run", "meta_canonical_run"}
    found = []
    for key, value in obj.items():
        if key in fields and type(value) in (int, str):
            value = str(value)
            if re.fullmatch(r"[0-9]{7,20}", value):
                found.append(value)
        elif key == "latest_source_uri" and isinstance(value, str):
            m = re.search(r"/actions/runs/([0-9]{7,20})(?:$|[/?#])", value)
            if m:
                found.append(m.group(1))
    return list(dict.fromkeys(found))[:8]


def _sha_prefixes(text: str) -> list[str]:
    """Parse explicit SHA references, never infer scientific veracity."""
    try:
        obj = json.loads(text)
    except ValueError:
        return []
    if not isinstance(obj, dict):
        return []
    result = []
    for key in ("archived_receipt_sha256_prefixes", "source_binding_sha256"):
        value = obj.get(key)
        values = value if isinstance(value, list) else [value]
        for token in values[:MAX_RELATIONS_PER_DOC]:
            if isinstance(token, str) and re.fullmatch(r"[0-9a-f]{16,64}", token):
                result.append(token)
    return list(dict.fromkeys(result))[:MAX_RELATIONS_PER_DOC]


def build_index(db_path: Path, source_root: Path, eligible: list[dict], *,
                focus: str = "", max_index_bytes: int = INDEX_CAP_BYTES) -> dict:
    if not 4096 <= max_index_bytes <= TARGET_BYTES:
        raise Hold("INDEX_BYTE_BUDGET_INVALID")
    source_root = source_root.resolve(strict=True)
    if db_path.resolve().is_relative_to(source_root) or db_path.exists():
        raise Hold("INDEX_MUST_BE_NEW_OUTSIDE_SOURCE")
    if len(focus) > 50 or FORBIDDEN.search(focus):
        raise Hold("INDEX_FOCUS_UNSAFE")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("CREATE TABLE documents(path TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, source_commit TEXT NOT NULL)")
        conn.execute("CREATE VIRTUAL TABLE snippets USING fts5(path UNINDEXED, content, tokenize='unicode61')")
        conn.execute("CREATE TABLE relations(from_path TEXT NOT NULL, to_path TEXT NOT NULL, PRIMARY KEY(from_path,to_path))")
        conn.execute("CREATE TABLE run_refs(path TEXT NOT NULL, run_id TEXT NOT NULL, PRIMARY KEY(path,run_id))")
        conn.execute("CREATE INDEX run_ref_lookup ON run_refs(run_id)")
        conn.execute("CREATE TABLE hash_refs(path TEXT NOT NULL, sha_prefix TEXT NOT NULL, PRIMARY KEY(path,sha_prefix))")
        total = 0
        indexed_docs = 0
        chunks = 0
        for item in eligible:
            path = item["path"]
            if focus and focus.casefold() not in path.casefold():
                continue
            size = item["size_bytes"]
            if total + size > max_index_bytes:
                continue
            raw = raw_from_tree(source_root, path, MAX_SOURCE_BYTES)
            if digest(raw) != item["sha256"] or len(raw) != size:
                raise Hold("REPLAY_SOURCE_SHA_MISMATCH:" + path)
            text = raw.decode("utf-8", errors="strict")
            conn.execute("INSERT INTO documents VALUES(?,?,?,?)",
                         (path,item["sha256"],size,item["source_commit"]))
            for begin,end,chunk in _chunks(text):
                conn.execute("INSERT INTO snippets(path,content) VALUES (?,?)",(path,chunk))
                chunks += 1
            if item["extension"] == ".json":
                for target in _relations(text):
                    conn.execute("INSERT OR IGNORE INTO relations VALUES(?,?)", (path,target))
                for run_id in _run_ids(text):
                    conn.execute("INSERT OR IGNORE INTO run_refs VALUES(?,?)", (path,run_id))
                for prefix in _sha_prefixes(text):
                    conn.execute("INSERT OR IGNORE INTO hash_refs VALUES(?,?)", (path,prefix))
            total += size
            indexed_docs += 1
        conn.commit()
        row = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if row != "ok":
            raise Hold("INDEX_INTEGRITY_CHECK_FAILED")
        return {
            "status": "READ_ONLY_HASH_VERIFIED_SHARD_INDEX_READY",
            "database_path_is_ephemeral": True,
            "source_bytes_indexed": total,
            "indexed_docs": indexed_docs,
            "text_chunks": chunks,
            "focus": focus,
            "index_budget_bytes": max_index_bytes,
            "sqlite_integrity": row,
            "model_weights_changed": False,
        }
    finally:
        conn.close()


def search_index(db_path: Path, query: str, *, limit: int = 5) -> list[dict]:
    if (not isinstance(query, str) or not 1 <= len(query) <= 120 or
            not 1 <= limit <= 12):
        raise Hold("QUERY_OR_RESULT_BUDGET_INVALID")
    tokens = re.findall(r"[\w]+",query,flags=re.UNICODE)
    if not tokens:
        return []
    match = " OR ".join('"' + x.replace('"',"") + '"' for x in tokens[:8])
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        # BM25 cannot be nested inside SQL aggregates in FTS5. Rank
        # individual chunks first and deduplicate source documents in Python.
        q = """SELECT snippets.path,d.source_sha256,d.size_bytes,d.source_commit,
                      bm25(snippets) AS score
                 FROM snippets JOIN documents d ON d.path=snippets.path
                WHERE snippets MATCH ?
                ORDER BY score,snippets.path LIMIT ?"""
        rows=conn.execute(q,(match,min(1000,limit*100))).fetchall()
        seen=set()
        result=[]
        for p,sha,size,commit,score in rows:
            if p in seen:
                continue
            seen.add(p)
            result.append({"path":p,"source_sha256":sha,"size_bytes":size,
                           "source_commit":commit, "score":round(score,5)})
            if len(result)>=limit:
                break
        return result
    finally:
        conn.close()


def multi_hop(db_path: Path, query: str, *, limit: int = 5) -> dict:
    first = search_index(db_path, query, limit=limit)
    if not first:
        return {"status":"NO_SUPPORTED_FIRST_HOP","first":[],"second":[]}
    conn=sqlite3.connect(f"file:{db_path.resolve()}?mode=ro",uri=True)
    try:
        second=[]
        paths={x["path"] for x in first}
        for item in first:
            rows=conn.execute("""
                SELECT d.path,d.source_sha256,d.size_bytes,d.source_commit
                  FROM relations r JOIN documents d ON d.path=r.to_path
                 WHERE r.from_path=? ORDER BY d.path LIMIT ?
            """,(item["path"],limit)).fetchall()
            for path,sha,size,commit in rows:
                if path not in paths and len(second)<limit:
                    second.append({"source_path":item["path"],"path":path,
                      "source_sha256":sha,"size_bytes":size,"source_commit":commit,
                      "relation":"EXPLICIT_JSON_REFERENCE_NOT_EVIDENCE"})
                    paths.add(path)
        # SHA-prefix references name *actual* content-addressed receipts.
        # Both sides are backed by exact full-source SHA-256 verified documents.
        # This is trace navigation, not a scientific proof.
        for item in first:
            if len(second)>=limit:
                break
            matches=conn.execute("""
                SELECT d.path,d.source_sha256,d.size_bytes,d.source_commit,
                       r.sha_prefix
                  FROM hash_refs r JOIN documents d
                    ON substr(d.source_sha256,1,length(r.sha_prefix))=r.sha_prefix
                 WHERE r.path=? AND d.path!=r.path
                 ORDER BY d.path LIMIT ?
            """,(item["path"],limit*5)).fetchall()
            for path,sha,size,commit,prefix in matches:
                if path not in paths and len(second)<limit:
                    second.append({"source_path":item["path"],"path":path,
                      "source_sha256":sha,"size_bytes":size,"source_commit":commit,
                      "shared_sha_prefix":prefix,
                      "relation":"EXPLICIT_SOURCE_SHA_PREFIX_LINK_NOT_INDEPENDENT_EVIDENCE"})
                    paths.add(path)
        # If there is no explicit JSON path or hash link, allow a *typed*
        # discovery hop through an exact source-run identifier recorded
        # in both SHA-verified documents. This is associative navigation,
        # not proof, causality, independent evidence, or a source citation.
        for item in first:
            if len(second)>=limit:
                break
            associations=conn.execute("""
                SELECT d.path,d.source_sha256,d.size_bytes,d.source_commit,
                       source.run_id
                  FROM run_refs source JOIN run_refs target
                    ON source.run_id=target.run_id
                  JOIN documents d ON d.path=target.path
                 WHERE source.path=? AND target.path!=?
                 ORDER BY d.path LIMIT ?
            """,(item["path"],item["path"],limit*5)).fetchall()
            for path,sha,size,commit,run_id in associations:
                if path not in paths and len(second)<limit:
                    second.append({"source_path":item["path"],"path":path,
                      "source_sha256":sha,"size_bytes":size,"source_commit":commit,
                      "shared_run_id":run_id,
                      "relation":"SHARED_RUN_ID_ASSOCIATION_NOT_EVIDENCE"})
                    paths.add(path)
        status = ("EXPLICIT_REFERENCE_SECOND_HOP_FOUND" if
                  any(x["relation"]=="EXPLICIT_JSON_REFERENCE_NOT_EVIDENCE" for x in second)
                  else "CONTENT_SHA_REFERENCE_SECOND_HOP" if
                  any(x["relation"]=="EXPLICIT_SOURCE_SHA_PREFIX_LINK_NOT_INDEPENDENT_EVIDENCE"
                      for x in second)
                  else "SHARED_RUN_ID_ASSOCIATIVE_HOP" if second
                  else "NO_VERIFIABLE_SECOND_HOP")
        return {"status":status, "first":first,"second":second}
    finally:
        conn.close()


def trace_source_sha_references(db_path: Path, path: str, *,
                                limit: int = 5) -> dict:
    """An exact selected document -> referenced, independently verified blob."""
    secure_relative(path)
    if not 1 <= limit <= 12:
        raise Hold("TRACE_LIMIT_INVALID")
    conn=sqlite3.connect(f"file:{db_path.resolve()}?mode=ro",uri=True)
    try:
        first=conn.execute(
            "SELECT path,source_sha256,size_bytes,source_commit FROM documents WHERE path=?",
            (path,)).fetchone()
        if first is None:
            return {"status":"SOURCE_NOT_INDEXED","source":path,"references":[]}
        rows=conn.execute("""
            SELECT d.path,d.source_sha256,d.size_bytes,d.source_commit,
                   r.sha_prefix
              FROM hash_refs r JOIN documents d
                ON substr(d.source_sha256,1,length(r.sha_prefix))=r.sha_prefix
             WHERE r.path=? AND d.path!=r.path ORDER BY d.path LIMIT ?
        """,(path,limit)).fetchall()
        targets=[{"path":p,"sha256":sha,"size_bytes":size,
                  "source_commit":commit,"reference_prefix":prefix,
                  "reference_kind":"EXPLICIT_SHA_PREFIX_REFERENCE_NOT_SCIENTIFIC_PROOF"}
                 for p,sha,size,commit,prefix in rows]
        return {"status":"SHA_BOUND_SECOND_HOP_FOUND" if targets
                else "NO_VERIFIED_SHA_REFERENCE","source":path,
                "source_sha256":first[1],"references":targets,
                "claim_independence":False}
    finally:
        conn.close()


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest-root",type=Path,required=True)
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--db",type=Path,required=True)
    ap.add_argument("--focus",default="rowan")
    ap.add_argument("--index-budget",type=int,default=INDEX_CAP_BYTES)
    ap.add_argument("--query",default="rowan")
    ap.add_argument("--trace-source",default="")
    args=ap.parse_args()
    root=args.source_root.resolve(strict=True)
    if any(x.resolve().is_relative_to(root) for x in (args.receipt,args.db)):
        raise Hold("SOURCE_WRITE_FORBIDDEN")
    if args.receipt.exists() or args.db.exists():
        raise Hold("OUTPUT_ALREADY_EXISTS")
    report,eligible=audit_catalog(args.manifest_root,args.source_root)
    report["index"]=build_index(args.db,args.source_root,eligible,
                                focus=args.focus,max_index_bytes=args.index_budget)
    report["readout"]=multi_hop(args.db,args.query)
    if args.trace_source:
        report["source_trace"]=trace_source_sha_references(args.db,args.trace_source)
    report["readout_is_model_answer"]=False
    report["receipt_sha256"]=digest(json.dumps(
        {k:v for k,v in report.items() if k!="receipt_sha256"},
        sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode("utf-8"))
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":report["status"],
        "cataloged_mixed_bytes":report["cataloged_mixed_bytes"],
        "verified_unique_candidate_text_bytes":report["hash_verified_unique_candidate_text_bytes"],
        "remaining_gap_bytes":report["remaining_gap_bytes"],
        "shards_verified":report["manifest_shards_verified"],
        "index":report["index"],
        "readout_status":report["readout"]["status"],
        "first_hops":len(report["readout"]["first"]),
        "second_hops":len(report["readout"]["second"]),
        "source_trace_status":report.get("source_trace",{}).get("status","NOT_REQUESTED"),
        "source_trace_links":len(report.get("source_trace",{}).get("references",[])),
        "claim_of_model_improvement":False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
