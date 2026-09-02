from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "janus.semantic_synthesis_context.v1"
SOURCE_SCHEMA = "janus.inaihr.semantic_evolution.v2"
MAX_CANDIDATES = 12
MAX_ROUTES = 8


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _clean(text: Any, limit: int = 140) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit]


def _validate_candidate(c: dict) -> None:
    if c.get("kind") != "SEMANTIC_CANDIDATE":
        raise RuntimeError("SEMANTIC_CONTEXT_NON_CANDIDATE_REJECTED")
    if c.get("status") != "CANDIDATE_AWAITING_CORROBORATION":
        raise RuntimeError("SEMANTIC_CONTEXT_STATUS_REJECTED")
    authority = c.get("authority") or {}
    required_false = ("truth", "proof", "causal", "mutation", "automatic_promotion")
    if any(authority.get(k) is not False for k in required_false):
        raise RuntimeError("SEMANTIC_CONTEXT_AUTHORITY_REJECTED")
    depth = int(c.get("depth") or 0)
    if not 1 <= depth <= 4:
        raise RuntimeError("SEMANTIC_CONTEXT_DEPTH_REJECTED")
    evidence = ((c.get("meaning") or {}).get("evidence") or {})
    if not evidence.get("registry_source_commit"):
        raise RuntimeError("SEMANTIC_CONTEXT_PROVENANCE_REJECTED")
    records = evidence.get("source_records") or []
    if len(records) < 2:
        raise RuntimeError("SEMANTIC_CONTEXT_SOURCE_COUNT_REJECTED")


def _candidate_row(c: dict) -> dict:
    meaning = c.get("meaning") or {}
    evidence = meaning.get("evidence") or {}
    return {
        "candidate_id": c.get("id"),
        "label": _clean(c.get("label"), 180),
        "depth": int(c.get("depth") or 1),
        "focus_key": _clean(c.get("focus_key"), 120),
        "purpose": _clean(meaning.get("purpose"), 360),
        "mechanism": _clean(meaning.get("mechanism"), 420),
        "next_steps": [_clean(x, 220) for x in (meaning.get("next_steps") or [])[:3]],
        "source_registry_commit": evidence.get("registry_source_commit"),
        "source_records": [
            {
                "id": r.get("id"),
                "path": r.get("path"),
                "status": r.get("status"),
                "sha256": r.get("sha256"),
                "lineage_key": r.get("lineage_key"),
            }
            for r in (evidence.get("source_records") or [])[:4]
        ],
        "claim_status": "HYPOTHESIS_ROUTE_ONLY",
    }


def _route_seed(row: dict) -> str:
    label = re.sub(r"^S\d+\s*·\s*", "", row.get("label") or "")
    label = label.replace("↔", " ")
    label = re.sub(r"[/_\-]+", " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    return _clean(label, 110)


def build_context(source: dict, *, max_candidates: int = MAX_CANDIDATES, max_routes: int = MAX_ROUTES) -> dict:
    if source.get("schema") != SOURCE_SCHEMA:
        raise RuntimeError("SEMANTIC_CONTEXT_SOURCE_SCHEMA_REJECTED")
    attention = source.get("attention") or {}
    if attention.get("attention_weight_is_evidence_weight") is not False:
        raise RuntimeError("SEMANTIC_CONTEXT_ATTENTION_AUTHORITY_REJECTED")
    if max_candidates < 1 or max_candidates > 24 or max_routes < 1 or max_routes > 12:
        raise RuntimeError("SEMANTIC_CONTEXT_BOUNDS_REJECTED")

    raw_candidates = list(source.get("candidates") or [])
    for c in raw_candidates:
        _validate_candidate(c)

    # Prefer recent candidates while preserving focus diversity. No ranking is truth.
    selected: list[dict] = []
    seen_focus: set[str] = set()
    for c in reversed(raw_candidates):
        fk = str(c.get("focus_key") or "")
        if fk and fk not in seen_focus:
            selected.append(c)
            seen_focus.add(fk)
        if len(selected) >= max_candidates:
            break
    if len(selected) < max_candidates:
        chosen = {c.get("id") for c in selected}
        for c in reversed(raw_candidates):
            if c.get("id") in chosen:
                continue
            selected.append(c)
            if len(selected) >= max_candidates:
                break
    selected.reverse()
    rows = [_candidate_row(c) for c in selected]

    routes: list[str] = []
    seen_route: set[str] = set()
    for row in reversed(rows):
        seed = _route_seed(row)
        key = seed.casefold()
        if seed and key not in seen_route:
            seen_route.add(key)
            routes.append(seed)
        if len(routes) >= max_routes:
            break

    obj: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "READY_CANDIDATE_HYPOTHESIS_CONTEXT" if rows else "READY_NO_CANDIDATES",
        "source": {
            "repository": "Hawkar-usls/iNaiHR",
            "source_schema": SOURCE_SCHEMA,
            "state_sha256": source.get("state_sha256"),
            "registry_source_commit": (source.get("registry") or {}).get("source_commit"),
            "generated_at": source.get("generated_at"),
            "candidate_count_total": source.get("candidate_count", len(raw_candidates)),
            "candidate_count_selected": len(rows),
        },
        "attention": {
            "policy": attention.get("policy"),
            "focus_key": attention.get("focus_key"),
            "focus_age": attention.get("focus_age"),
            "attention_weight_is_evidence_weight": False,
        },
        "candidate_context": rows,
        "research_route_seeds": routes,
        "capabilities": {
            "may_generate_research_questions": True,
            "may_generate_counterexample_search_routes": True,
            "may_inform_wikipedia_or_arxiv_queries": True,
            "may_be_used_as_world_truth": False,
            "may_be_used_as_proof": False,
            "may_be_direct_gradient_signal": False,
            "may_grant_mutation_authority": False,
            "may_auto_promote_semantic_candidate": False,
        },
        "laws": [
            "SYNTHESIS != TRUTH",
            "SEMANTIC_CANDIDATE != VERIFIED_FACT",
            "ATTENTION_WEIGHT != EVIDENCE_WEIGHT",
            "CANDIDATE_EDGE != CAUSAL_EDGE",
            "SEMANTIC_CONTEXT MAY GENERATE QUESTIONS BUT NOT ANSWERS",
            "NO CORROBORATION OR TARGET-LOCAL VERIFY => NO PROMOTION",
        ],
    }
    obj["context_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--max-routes", type=int, default=MAX_ROUTES)
    args = ap.parse_args()
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    obj = build_context(source, max_candidates=args.max_candidates, max_routes=args.max_routes)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "candidate_count_selected": obj["source"]["candidate_count_selected"],
        "research_route_count": len(obj["research_route_seeds"]),
        "context_sha256": obj["context_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
