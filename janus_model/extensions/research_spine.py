from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCHEMA = "janus.research_spine.v1"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"
PRIMARY_TARGET = "Hawkar-usls/Janus-Fundamentum"
CRITICAL_OVERRIDE_CLASSES = ("CRITICAL_INTEGRITY", "CRITICAL_SECURITY", "CRITICAL_SAFETY")
DEFAULT_ARXIV_QUERIES = (
    'all:"formula caching" AND (cat:cs.CC OR cat:cs.LO)',
    'all:"proof complexity" AND (cat:cs.CC OR cat:cs.LO)',
    'all:"matroid pathwidth" OR all:"subspace arrangement"',
)
TOPA_ROUTER = Path("integrations/janus-distributed-ai-swarm/topa_epistemic_router.py")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def file_record(root: Path, rel: str) -> dict:
    path = root / rel
    if not path.is_file():
        return {"path": rel, "status": "MISSING"}
    raw = path.read_bytes()
    return {"path": rel, "status": "PRESENT", "sha256": sha256_bytes(raw), "size_bytes": len(raw)}


def repo_snapshot(root: Path, repository: str, role: str, key_files: list[str]) -> dict:
    if not root.is_dir():
        return {"repository": repository, "role": role, "status": "UNAVAILABLE", "commit": None, "key_files": []}
    try:
        commit = git_head(root)
    except Exception as exc:
        return {
            "repository": repository,
            "role": role,
            "status": "UNAVAILABLE",
            "commit": None,
            "error": f"{type(exc).__name__}:{exc}",
            "key_files": [],
        }
    records = [file_record(root, rel) for rel in key_files]
    status = "BOUND_READ_ONLY" if all(r["status"] == "PRESENT" for r in records) else "BOUND_READ_ONLY_WITH_MISSING_KEYS"
    return {"repository": repository, "role": role, "status": status, "commit": commit, "key_files": records}


def run_topa_self_test(topa_root: Path) -> dict:
    router = topa_root / TOPA_ROUTER
    if not router.is_file():
        return {"status": "BLOCKED", "router_path": str(TOPA_ROUTER), "reason": "TOPA_ROUTER_MISSING"}
    proc = subprocess.run(
        [sys.executable, str(router)], cwd=str(topa_root), text=True, capture_output=True, timeout=30
    )
    markers = (
        "JANUS_TOPA_EPISTEMIC_ROUTER_V1_3_SELF_TEST=PASS",
        "JANUS_TOPA_EPISTEMIC_ROUTER_V1_2_SELF_TEST=PASS",
    )
    observed = next((m for m in markers if m in proc.stdout), None)
    passed = proc.returncode == 0 and observed is not None
    return {
        "status": "PASS" if passed else "BLOCKED",
        "router_path": str(TOPA_ROUTER),
        "router_sha256": sha256_file(router),
        "returncode": proc.returncode,
        "self_test_marker_observed": observed,
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def demi_head_property_snapshot(root: Path) -> dict:
    snap = repo_snapshot(
        root,
        "Hawkar-usls/Demi_Head",
        "PROPERTY_AND_META_COGNITIVE_CONTEXT",
        ["README.md", "PROJECT_STATUS.json"],
    )
    links: list[dict] = []
    janus_dir = root / ".janus"
    if janus_dir.is_dir():
        for path in sorted(janus_dir.glob("*.json"))[:64]:
            links.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            })
    snap["property_link_count"] = len(links)
    snap["property_links"] = links
    snap["authority"] = {
        "internal_property_context": True,
        "independent_evidence": False,
        "world_truth": False,
        "may_generate_test_routes": True,
    }
    return snap


def _text(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.split())


def query_arxiv(query: str, max_results: int, timeout: float) -> dict:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "lastUpdatedDate",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JANUS-Research-Spine/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)",
            "Accept": "application/atom+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(1_500_000)
    except Exception as exc:
        return {
            "query": query,
            "status": "UNAVAILABLE",
            "source": ARXIV_ENDPOINT,
            "error": f"{type(exc).__name__}:{exc}",
            "papers": [],
        }
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return {
            "query": query,
            "status": "MALFORMED_RESPONSE",
            "source": ARXIV_ENDPOINT,
            "error": f"ParseError:{exc}",
            "response_sha256": sha256_bytes(raw),
            "papers": [],
        }
    ns = {"a": "http://www.w3.org/2005/Atom"}
    papers: list[dict] = []
    for entry in root.findall("a:entry", ns):
        authors = [_text(a.find("a:name", ns)) for a in entry.findall("a:author", ns)]
        categories = [c.attrib.get("term", "") for c in entry.findall("a:category", ns)]
        papers.append({
            "id": _text(entry.find("a:id", ns)),
            "title": _text(entry.find("a:title", ns)),
            "authors": [a for a in authors if a],
            "published": _text(entry.find("a:published", ns)),
            "updated": _text(entry.find("a:updated", ns)),
            "categories": [c for c in categories if c],
            "summary": _text(entry.find("a:summary", ns))[:1200],
        })
    return {
        "query": query,
        "status": "PASS",
        "source": ARXIV_ENDPOINT,
        "paper_set_sha256": sha256_bytes(canonical_bytes(papers)),
        "paper_count": len(papers),
        "papers": papers,
    }


def build_research_spine(
    topa_root: Path,
    demi_head_root: Path,
    fundamentum_root: Path,
    arxiv_queries: list[str],
    max_results: int = 4,
    timeout: float = 12.0,
    enable_arxiv: bool = True,
) -> dict:
    topa = repo_snapshot(
        topa_root,
        "Hawkar-usls/TOPA",
        "EPISTEMIC_PROVENANCE_AND_FALSIFICATION_ENGINE",
        [
            "protocols/TOPA_FOUNDATION.json",
            "data/TOPA-MATHEMATICAL-RESEARCH-MODE-2026-08-24-v1.1.json",
            TOPA_ROUTER.as_posix(),
        ],
    )
    topa["router_self_test"] = run_topa_self_test(topa_root)

    demi_head = demi_head_property_snapshot(demi_head_root)

    fundamentum = repo_snapshot(
        fundamentum_root,
        PRIMARY_TARGET,
        "PRIMARY_DEFAULT_IMPROVEMENT_TARGET",
        ["README.md", "docs/CURRENT_RESEARCH_STATUS.md"],
    )
    fundamentum["improvement_focus"] = {
        "primary": True,
        "normal_repair_candidates_outside_target_are_deferred_when_policy_is_active": True,
        "critical_override_classes": list(CRITICAL_OVERRIDE_CLASSES),
    }

    if enable_arxiv:
        arxiv_results = [query_arxiv(q, max_results=max_results, timeout=timeout) for q in arxiv_queries]
    else:
        arxiv_results = [{"query": None, "status": "DISABLED", "source": ARXIV_ENDPOINT, "papers": []}]
    if enable_arxiv and arxiv_results and all(r["status"] == "PASS" for r in arxiv_results):
        arxiv_status = "PASS"
    elif enable_arxiv:
        arxiv_status = "PARTIAL_OR_UNAVAILABLE"
    else:
        arxiv_status = "DISABLED"
    arxiv = {
        "role": "EXTERNAL_SCIENTIFIC_LITERATURE_SOURCE",
        "status": arxiv_status,
        "endpoint": ARXIV_ENDPOINT,
        "queries": arxiv_results,
        "authority": {
            "literature_metadata_is_source_bound_context": True,
            "paper_claims_are_automatically_true": False,
            "independent_replication_established_by_presence": False,
            "may_generate_hypotheses_or_prior_art_search_routes": True,
            "may_verify_repository_patch": False,
        },
    }

    required_ready = (
        topa.get("status", "").startswith("BOUND_READ_ONLY")
        and (topa.get("router_self_test") or {}).get("status") == "PASS"
        and demi_head.get("status", "").startswith("BOUND_READ_ONLY")
        and fundamentum.get("status", "").startswith("BOUND_READ_ONLY")
    )
    if required_ready and arxiv_status == "PASS":
        status = "READY"
    elif required_ready:
        status = "READY_WITH_ARXIV_DEGRADED"
    else:
        status = "BLOCKED_REQUIRED_RESEARCH_ORGAN"

    obj: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "research_spine": {
            "topa": topa,
            "arxiv": arxiv,
            "demi_head": demi_head,
            "fundamentum": fundamentum,
        },
        "improvement_policy": {
            "policy_id": "FUNDAMENTUM_FIRST_WITH_CRITICAL_OVERRIDE",
            "primary_target": PRIMARY_TARGET,
            "critical_override_classes": list(CRITICAL_OVERRIDE_CLASSES),
            "no_novel_bounded_evidence_means_no_action": True,
            "selection_is_verification": False,
            "direct_target_main_write": False,
            "autonomous_merge": False,
        },
        "claim_ceiling": {
            "topa_output_is_world_truth": False,
            "arxiv_presence_is_truth": False,
            "demi_head_property_is_independent_evidence": False,
            "model_selection_is_verified_fix": False,
            "target_local_verify_required": True,
        },
        "laws": [
            "TOPA_CONTEXT != EMPIRICAL_TRUTH",
            "ARXIV_PAPER != INDEPENDENT_REPLICATION",
            "DEMI_HEAD_PROPERTY != EVIDENCE",
            "FUNDAMENTUM_FIRST != FUNDAMENTUM_ALWAYS",
            "CRITICAL_INTEGRITY_SECURITY_SAFETY_MAY_OVERRIDE_PRIMARY_TARGET",
            "NO_NOVEL_BOUNDED_EVIDENCE => NO_ACTION",
            "MODEL_SELECTION != VERIFIED_FIX",
            "TARGET_BRANCH + VERIFY + RECEIPT BEFORE PASS",
        ],
    }
    obj["context_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topa-root", required=True)
    ap.add_argument("--demi-head-root", required=True)
    ap.add_argument("--fundamentum-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arxiv-query", action="append", default=[])
    ap.add_argument("--max-results", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--no-arxiv", action="store_true")
    args = ap.parse_args()

    if args.max_results < 1 or args.max_results > 8:
        raise SystemExit("ARXIV_MAX_RESULTS_OUT_OF_BOUNDS")
    queries = args.arxiv_query or list(DEFAULT_ARXIV_QUERIES)
    if len(queries) > 6:
        raise SystemExit("ARXIV_QUERY_COUNT_OUT_OF_BOUNDS")

    obj = build_research_spine(
        Path(args.topa_root),
        Path(args.demi_head_root),
        Path(args.fundamentum_root),
        queries,
        max_results=args.max_results,
        timeout=args.timeout,
        enable_arxiv=not args.no_arxiv,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "schema": obj["schema"],
        "status": obj["status"],
        "context_sha256": obj["context_sha256"],
        "primary_target": obj["improvement_policy"]["primary_target"],
        "arxiv_status": obj["research_spine"]["arxiv"]["status"],
        "topa_router": obj["research_spine"]["topa"]["router_self_test"]["status"],
    }, indent=2))
    if obj["status"] == "BLOCKED_REQUIRED_RESEARCH_ORGAN":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
