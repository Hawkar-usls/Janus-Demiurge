"""Versioned, thresholded Memory Cortex intake. Text is data, never authority.

Durable CAS, cursors, rejections and generations live on memory-cortex-state.
SQLite is reproducible from a sealed active generation, not the storage authority.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from janus_model.memory_512_audit_index_r3 import (
    Hold, audit_catalog, classify, digest, git_head, raw_from_tree, _chunks,
)

SCHEMA = "janus.memory_cortex.growth.v1"
REGISTRY = "Hawkar-usls/janus-meta-registry"
BEETLE = "Hawkar-usls/janus-lapis"
MAX_DOC = 1024 * 1024
TARGET = 512 * 1024 * 1024
BASE_SOURCE = "c8e47bb54e954ab122e111c97198131f048bd5fd"
BASE_CATALOG = "6c9259c43d89569b11351bf8579a3775025fa2f0"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sealed(obj):
    body = {k: v for k, v in obj.items() if k != "receipt_sha256"}
    return {**body, "receipt_sha256": digest(canonical(body))}


def checked(obj):
    if not isinstance(obj, dict) or sealed(obj) != obj:
        raise Hold("GROWTH_RECEIPT_HASH_MISMATCH")
    return obj


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise Hold("GROWTH_SYMLINK_DESTINATION")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def object_path(root: Path, sha: str):
    if not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise Hold("GROWTH_INVALID_CONTENT_DIGEST")
    return root / "objects" / sha[:2] / (sha[2:] + ".txt")


def read_object(root: Path, sha: str, size: int):
    if type(size) is not int or not 0 <= size <= MAX_DOC:
        raise Hold("GROWTH_INVALID_OBJECT_SIZE")
    raw = raw_from_tree(root, str(object_path(root, sha).relative_to(root)), MAX_DOC)
    if len(raw) != size or digest(raw) != sha:
        raise Hold("GROWTH_CONTENT_HASH_MISMATCH")
    raw.decode("utf-8", errors="strict")
    return raw


def new_state():
    return {"schema": SCHEMA, "records": {}, "active": [], "pending": [],
            "generation": -1, "seen_registry_blobs": {}, "beetle_offsets": {},
            "beetle_queue": {}, "beetle_done": {}, "last_sources": {}}


def load_state(root: Path):
    path = root / "STATE.json"
    if not path.exists():
        if (root / "CURRENT.json").exists():
            raise Hold("GROWTH_PARTIAL_STATE")
        return new_state()
    if path.is_symlink() or path.stat().st_size > 32 * MAX_DOC:
        raise Hold("GROWTH_STATE_UNSAFE")
    state = checked(json.loads(path.read_text(encoding="utf-8")))
    if state["schema"] != SCHEMA:
        raise Hold("GROWTH_SCHEMA_MISMATCH")
    active, pending = set(state["active"]), set(state["pending"])
    if (len(active) != len(state["active"]) or len(pending) != len(state["pending"])
            or active & pending or active | pending != set(state["records"])):
        raise Hold("GROWTH_DUPLICATED_OR_UNACCOUNTED_RECORD")
    if state["generation"] >= 0:
        pointer = checked(json.loads((root / "CURRENT.json").read_text()))
        if (pointer.get("generation") != state["generation"] or
                pointer.get("manifest_path") != f"generations/{state['generation']:06d}.json"):
            raise Hold("GROWTH_ACTIVE_MANIFEST_DRIFT")
        manifest = checked(json.loads((root / pointer["manifest_path"]).read_text()))
        if (pointer["generation"] != state["generation"] or
                pointer["manifest_path"] != f"generations/{state['generation']:06d}.json" or
                manifest["receipt_sha256"] != pointer["manifest_sha256"] or
                manifest["documents"] != sorted(state["active"]) or
                manifest["verified_unique_source_bytes"] != sum(state["records"][s]["size"] for s in active)):
            raise Hold("GROWTH_ACTIVE_MANIFEST_DRIFT")
    return state


def add_text(root: Path, state: dict, raw: bytes, origin: dict):
    if not raw or len(raw) > MAX_DOC:
        raise Hold("GROWTH_SOURCE_SIZE_LIMIT")
    raw.decode("utf-8", errors="strict")
    sha = digest(raw)
    if sha in state["records"]:
        return False
    # The capacity ceiling is on distinct source bytes, not SQLite or metadata.
    if sum(r["size"] for r in state["records"].values()) + len(raw) > TARGET:
        raise Hold("GROWTH_CAPACITY_BUDGET_REACHED")
    path = object_path(root, sha)
    if path.exists():
        read_object(root, sha, len(raw))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    state["records"][sha] = {"size": len(raw), "origin": origin}
    state["pending"].append(sha)
    return True


def git_files(root: Path):
    result = subprocess.run(["git", "-C", str(root), "ls-tree", "-rlz", "HEAD"],
                            check=True, capture_output=True).stdout
    for entry in result.split(b"\0"):
        if not entry:
            continue
        header, name = entry.split(b"\t", 1)
        mode, kind, blob, size = header.decode().split()
        path = name.decode("utf-8", errors="strict")
        if kind == "blob" and mode == "100644":
            yield path, blob, int(size)


def bootstrap(root: Path, state: dict, catalog: Path, source: Path):
    if state["generation"] >= 0 or state["records"]:
        raise Hold("GROWTH_BOOTSTRAP_ALREADY_DONE")
    if git_head(source) != BASE_SOURCE or git_head(catalog) != BASE_CATALOG:
        raise Hold("GROWTH_BASELINE_GIT_MISMATCH")
    audit, docs = audit_catalog(catalog, source)
    if len(docs) != 4712 or audit["hash_verified_unique_candidate_text_bytes"] != 49460266:
        raise Hold("GROWTH_BASELINE_COUNTS_MISMATCH")
    blobs = {p: b for p, b, _ in git_files(source)}
    for doc in docs:
        raw = raw_from_tree(source, doc["path"], MAX_DOC)
        if digest(raw) != doc["sha256"]:
            raise Hold("GROWTH_BASELINE_REPLAY_FAILED")
        add_text(root, state, raw, {"repository": REGISTRY, "commit": BASE_SOURCE,
                 "path": doc["path"], "kind": "PUBLIC_REGISTRY_TEXT_NOT_SCIENTIFIC_PROOF"})
        state["seen_registry_blobs"][blobs[doc["path"]]] = "MIGRATED_BASELINE"
    publish(root, state, reason="MIGRATED_R3_BASELINE_NOT_NEW_INFORMATION")


def collect_registry(root: Path, state: dict, source: Path, max_documents=512):
    commit = git_head(source)
    if state["last_sources"].get("registry") == commit:
        return {"new_documents": 0, "already_scanned_snapshot": True}
    new, inspected = 0, 0
    complete = True
    for path, blob, size in git_files(source):
        if blob in state["seen_registry_blobs"]:
            continue
        if inspected >= max_documents:
            complete = False
            break
        meta = {"path": path, "size_bytes": size, "extension": Path(path).suffix,
                "read_only": True, "scientific_authority_granted": False}
        reason = classify(meta)
        if reason != "CANDIDATE_TEXT":
            state["seen_registry_blobs"][blob] = reason
            continue
        inspected += 1
        try:
            raw = raw_from_tree(source, path, MAX_DOC)
            raw.decode("utf-8", errors="strict")
            if Path(path).suffix == ".json":
                json.loads(raw)
            elif Path(path).suffix == ".jsonl":
                for line in raw.splitlines():
                    if line.strip():
                        json.loads(line)
        except (UnicodeError, ValueError):
            state["seen_registry_blobs"][blob] = "INVALID_UTF8_OR_JSON"
            continue
        # Replay Git's blob digest as well as independently digesting raw text.
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual_blob != blob or len(raw) != size:
            raise Hold("GROWTH_GIT_BLOB_SOURCE_MISMATCH")
        if add_text(root, state, raw, {"repository": REGISTRY, "commit": commit,
                    "path": path, "git_blob": blob,
                    "kind": "PUBLIC_REGISTRY_TEXT_NOT_SCIENTIFIC_PROOF"}):
            new += 1
        state["seen_registry_blobs"][blob] = "VERIFIED_OR_CONTENT_DUPLICATE"
    if complete:
        state["last_sources"]["registry"] = commit
    return {"new_documents": new, "candidate_documents_read": inspected,
            "snapshot_scan_complete": complete, "source_commit": commit}


def canonical_lead(url):
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except ValueError:
        return None
    if p.scheme != "https" or port is not None or p.username or p.query or p.fragment:
        return None
    if p.hostname in {"arxiv.org", "export.arxiv.org"}:
        m = re.fullmatch(r"/abs/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?|[a-z-]+/[0-9]{7}(?:v[0-9]+)?)", p.path)
        if m:
            ident = m[1]
            return "arxiv:" + ident, "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": ident})
    if p.hostname == "zenodo.org":
        m = re.fullmatch(r"/records/([0-9]+)", p.path)
        if m:
            return "zenodo:" + m[1], "https://zenodo.org/api/records/" + m[1]
    return None


def read_beetle_leads(state: dict, beetle: Path, max_lines=2000):
    base = beetle / "data/beetle-state/candidates.parts"
    if not base.is_dir():
        return {"available": False, "lines_consumed": 0}
    commit = git_head(beetle)
    consumed = 0
    for part in sorted(base.glob("part-*.jsonl")):
        if part.is_symlink():
            raise Hold("GROWTH_BEETLE_SYMLINK")
        rel = str(part.relative_to(beetle))
        cursor = state["beetle_offsets"].get(rel, {"offset": 0, "tail": ""})
        offset = cursor["offset"]
        with part.open("rb") as f:
            if offset > part.stat().st_size:
                raise Hold("GROWTH_BEETLE_LEDGER_TRUNCATED")
            if offset:
                n = min(offset, 128)
                f.seek(offset - n)
                if digest(f.read(n)) != cursor["tail"]:
                    raise Hold("GROWTH_BEETLE_CURSOR_REWRITTEN")
            f.seek(offset)
            while consumed < max_lines and len(state["beetle_queue"]) < 8192:
                line = f.readline(131073)
                if not line:
                    break
                if len(line) > 131072 or not line.endswith(b"\n"):
                    raise Hold("GROWTH_BEETLE_LINE_INVALID")
                row = json.loads(line)
                lead = canonical_lead(str(row.get("url", "")))
                if lead and row.get("schema") == "janus.universal_beetle.candidate.v1":
                    ident, url = lead
                    if ident not in state["beetle_done"] and ident not in state["beetle_queue"]:
                        state["beetle_queue"][ident] = {"url": url, "candidate_id": row.get("candidate_id"),
                            "beetle_commit": commit, "beetle_path": rel,
                            "discovered_at": str(row.get("discovered_at", "")), "attempts": 0, "retry_at": 0}
                offset = f.tell()
                consumed += 1
            n = min(offset, 128)
            f.seek(offset - n)
            state["beetle_offsets"][rel] = {"offset": offset, "tail": digest(f.read(n))}
        if consumed >= max_lines or len(state["beetle_queue"]) >= 8192:
            break
    if consumed:
        state["last_sources"]["beetle"] = commit
    return {"available": True, "source_commit": commit, "lines_consumed": consumed}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Hold("GROWTH_PRIMARY_REDIRECT_REFUSED")


def fetch_primary(url):
    req = urllib.request.Request(url, headers={"User-Agent": "JANUS-Memory-Cortex/1.0",
                                             "Accept": "application/json, application/atom+xml"})
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(req, timeout=25) as response:
        raw = response.read(MAX_DOC + 1)
        if len(raw) > MAX_DOC:
            raise Hold("GROWTH_PRIMARY_TOO_LARGE")
        return raw


def primary_text(ident, raw):
    if len(raw) > MAX_DOC:
        raise Hold("GROWTH_PRIMARY_TOO_LARGE")
    if ident.startswith("arxiv:"):
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise Hold("GROWTH_XML_ENTITIES_REFUSED")
        tree = ET.fromstring(raw)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = tree.findall("a:entry", ns)
        if len(entries) != 1:
            raise Hold("GROWTH_PRIMARY_ID_NOT_FOUND")
        e = entries[0]
        returned = canonical_lead(e.findtext("a:id", "", ns).replace("http://", "https://"))
        target = ident.split(":", 1)[1]
        got = returned[0].split(":", 1)[1] if returned else ""
        if (got != target if re.search(r"v[0-9]+$", target) else re.sub(r"v[0-9]+$", "", got) != target):
            raise Hold("GROWTH_ARXIV_ID_MISMATCH")
        title, body = e.findtext("a:title", "", ns), e.findtext("a:summary", "", ns)
    else:
        record = json.loads(raw)
        if str(record.get("id")) != ident.split(":", 1)[1]:
            raise Hold("GROWTH_ZENODO_ID_MISMATCH")
        meta = record.get("metadata", {})
        title, body = meta.get("title", ""), meta.get("description", "")
        body = html.unescape(re.sub(r"<[^>]*>", " ", body))
    title, body = " ".join(title.split()), " ".join(body.split())
    if not title or len(body) < 40:
        raise Hold("GROWTH_PRIMARY_TEXT_EMPTY")
    # Do not count our citation envelope or timestamp as new source information.
    return (title + "\n\n" + body + "\n").encode("utf-8")


def consume_beetle(root: Path, state: dict, max_fetches=8, fetch=fetch_primary, now=None):
    now = time.time() if now is None else now
    fetched, added, errors = 0, 0, 0
    queue = state["beetle_queue"]
    for ident in sorted(queue, key=lambda k: queue[k]["discovered_at"], reverse=True):
        item = queue[ident]
        if fetched >= max_fetches:
            break
        if item["retry_at"] > now:
            continue
        fetched += 1
        try:
            raw = fetch(item["url"])
            text = primary_text(ident, raw)
            origin = {"kind": "PRIMARY_ABSTRACT_METADATA_NOT_FULL_PAPER_OR_PROOF",
                      "url": item["url"], "primary_id": ident, "provider_sha256": digest(raw),
                      "beetle_repository": BEETLE, "beetle_commit": item["beetle_commit"],
                      "beetle_path": item["beetle_path"], "candidate_id": item["candidate_id"]}
            if add_text(root, state, text, origin):
                added += 1
            state["beetle_done"][ident] = {"status": "PRIMARY_TEXT_VERIFIED_OR_DUPLICATE", "sha256": digest(text)}
            del queue[ident]
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            item["attempts"] += 1
            item["retry_at"] = now + min(86400, 1200 * 2 ** min(item["attempts"], 6))
            item["last_error"] = type(exc).__name__
            if item["attempts"] >= 5:
                state["beetle_done"][ident] = {"status": "PAUSED_AFTER_FIVE_FAILED_FETCHES", "error": type(exc).__name__}
                del queue[ident]
            errors += 1
        except (Hold, ValueError, ET.ParseError) as exc:
            state["beetle_done"][ident] = {"status": "REJECTED_PRIMARY_RECORD", "reason": str(exc)[:160]}
            del queue[ident]
            errors += 1
    return {"primary_fetches": fetched, "new_primary_texts": added,
            "fetch_errors": errors, "queued": len(queue)}


def build_active_index(root: Path, state: dict, hashes: list, db: Path):
    if db.exists():
        raise Hold("GROWTH_INDEX_MUST_BE_NEW")
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE docs(sha TEXT PRIMARY KEY, size INTEGER NOT NULL)")
        conn.execute("CREATE VIRTUAL TABLE snippets USING fts5(sha UNINDEXED,content)")
        for sha in sorted(hashes):
            raw = read_object(root, sha, state["records"][sha]["size"])
            conn.execute("INSERT INTO docs VALUES(?,?)", (sha, len(raw)))
            conn.executemany("INSERT INTO snippets VALUES(?,?)",
                             ((sha, chunk) for _, _, chunk in _chunks(raw.decode("utf-8"))))
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        # Exercise FTS as well as table integrity on a real indexed token.
        count, size = conn.execute("SELECT COUNT(*),COALESCE(SUM(size),0) FROM docs").fetchone()
        conn.execute("SELECT sha FROM snippets WHERE snippets MATCH ? LIMIT 1", ('"schema"',)).fetchall()
        if integrity != "ok" or count != len(hashes):
            raise Hold("GROWTH_INDEX_REPLAY_FAILED")
        return {"sqlite_integrity": integrity, "indexed_documents": count, "verified_unique_source_bytes": size}
    finally:
        conn.close()


def publish(root: Path, state: dict, reason: str):
    hashes = sorted(set(state["active"]) | set(state["pending"]))
    with tempfile.TemporaryDirectory() as tmp:
        metrics = build_active_index(root, state, hashes, Path(tmp) / "index.sqlite")
    generation = state["generation"] + 1
    previous = root / "CURRENT.json"
    parent = checked(json.loads(previous.read_text()))["manifest_sha256"] if previous.exists() else None
    manifest = sealed({"schema": SCHEMA, "generation": generation, "parent_manifest_sha256": parent,
                       "reason": reason, "documents": hashes, **metrics,
                       "new_documents": len(state["pending"]),
                       "new_verified_bytes": sum(state["records"][s]["size"] for s in state["pending"]),
                       "model_weights_updated": False, "independent_qa_passed": False,
                       "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
    path = f"generations/{generation:06d}.json"
    if (root / path).exists():
        raise Hold("GROWTH_GENERATION_OVERWRITE_REFUSED")
    write_json(root / path, manifest)
    write_json(previous, sealed({"schema": SCHEMA, "generation": generation,
               "manifest_path": path, "manifest_sha256": manifest["receipt_sha256"]}))
    state["active"], state["pending"], state["generation"] = hashes, [], generation
    return manifest


def collect(root: Path, source: Path, beetle: Path | None, policy: dict,
            baseline_catalog=None, baseline_source=None, fetch=fetch_primary):
    state = load_state(root)
    before = canonical(sealed(state))
    if state["generation"] < 0:
        if baseline_catalog is None or baseline_source is None:
            raise Hold("GROWTH_BASELINE_MIGRATION_REQUIRED")
        bootstrap(root, state, baseline_catalog, baseline_source)
    old_generation = state["generation"]
    registry = collect_registry(root, state, source, policy["max_registry_documents_per_scan"])
    beetle_scan = read_beetle_leads(state, beetle) if beetle else {"available": False}
    beetle_read = consume_beetle(root, state, policy["max_primary_fetches_per_scan"], fetch=fetch)
    pending_bytes = sum(state["records"][s]["size"] for s in state["pending"])
    if (pending_bytes >= policy["publish_new_bytes"] or
            len(state["pending"]) >= policy["publish_new_documents"]):
        publish(root, state, "NOVEL_VERIFIED_TEXT_THRESHOLD_REACHED")
    changed = canonical(sealed(state)) != before
    if changed:
        write_json(root / "STATE.json", sealed(state))
    active_bytes = sum(state["records"][s]["size"] for s in state["active"])
    report = sealed({"schema": SCHEMA, "status": "GENERATION_PUBLISHED" if state["generation"] > old_generation
                     else "ACCUMULATING" if changed else "NO_NEW_INFORMATION",
                    "generation": state["generation"], "state_changed": changed,
                    "active_verified_unique_source_bytes": active_bytes,
                    "active_documents": len(state["active"]),
                    "pending_unique_source_bytes": sum(state["records"][s]["size"] for s in state["pending"]),
                    "pending_documents": len(state["pending"]),
                    "remaining_to_512_mib": max(0, TARGET - active_bytes),
                    "registry": registry, "beetle_scan": beetle_scan, "beetle_read": beetle_read,
                    "model_weights_updated": False, "independent_qa_passed": False,
                    "cold_source_store": "GIT_CONTENT_ADDRESSED_TEXT_AND_VERSIONED_MANIFESTS",
                    "sqlite_is_rebuildable": True})
    if changed:
        write_json(root / "LATEST.json", report)
    return report


def query(root: Path, text: str, limit=5):
    if not isinstance(text, str) or not text.strip() or len(text) > 120 or not 1 <= limit <= 8:
        raise Hold("GROWTH_QUERY_BUDGET_INVALID")
    state = load_state(root)
    if state["generation"] < 0:
        return {"schema": SCHEMA, "status": "UNINITIALIZED", "citations": []}
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "index.sqlite"
        metrics = build_active_index(root, state, state["active"], db)
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            tokens = re.findall(r"\w+", text, re.UNICODE)[:12]
            if not tokens:
                raise Hold("GROWTH_QUERY_NO_TOKENS")
            expression = " OR ".join('"' + t + '"' for t in tokens)
            rows = conn.execute("SELECT sha,bm25(snippets) FROM snippets WHERE snippets MATCH ? ORDER BY bm25(snippets) LIMIT 128", (expression,)).fetchall()
        finally:
            conn.close()
    citations, seen = [], set()
    for sha, score in rows:
        if sha in seen:
            continue
        seen.add(sha)
        record = state["records"][sha]
        read_object(root, sha, record["size"])
        citations.append({"sha256": sha, "verified_bytes": record["size"],
                          "origin": record["origin"], "score": score,
                          "content_is_untrusted_data": True})
        if len(citations) >= limit:
            break
    return sealed({"schema": SCHEMA, "status": "VERIFIED_SOURCE_POINTERS_ONLY" if citations else "NO_MATCH",
                   "generation": state["generation"], "citations": citations, **metrics,
                   "model_inference_executed": False, "scientific_authority_granted": False})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["collect", "query"])
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--registry", type=Path)
    ap.add_argument("--beetle", type=Path)
    ap.add_argument("--baseline-catalog", type=Path)
    ap.add_argument("--baseline-source", type=Path)
    ap.add_argument("--policy", type=Path, default=Path("beetle/MEMORY_CORTEX_GROWTH.json"))
    ap.add_argument("--query", default="memory")
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    root = args.state.resolve()
    # Never let state writes target a source checkout.
    for src in (args.registry, args.beetle, args.baseline_catalog, args.baseline_source):
        if src and (root.is_relative_to(src.resolve()) or src.resolve().is_relative_to(root)):
            raise Hold("GROWTH_STATE_SOURCE_OVERLAP")
    if args.mode == "collect":
        policy = json.loads(args.policy.read_text())
        if (policy.get("schema") != SCHEMA or not 1 <= policy["max_primary_fetches_per_scan"] <= 16 or
                not 1 <= policy["max_registry_documents_per_scan"] <= 1024 or
                not 1 <= policy["publish_new_documents"] <= 4096 or
                not 4096 <= policy["publish_new_bytes"] <= 64 * MAX_DOC):
            raise Hold("GROWTH_POLICY_INVALID")
        result = collect(root, args.registry, args.beetle, policy,
                         args.baseline_catalog, args.baseline_source)
    else:
        result = query(root, args.query)
    write_json(args.report, result)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
