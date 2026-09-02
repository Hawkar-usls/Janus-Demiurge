from __future__ import annotations

import argparse
import json
from pathlib import Path

from janus_model.extensions import research_spine as base
from janus_model.extensions.org_surface import SCHEMA as ORG_SCHEMA
from janus_model.extensions.wikipedia_trunk import SCHEMA as WIKI_SCHEMA
from janus_model.extensions.semantic_synthesis_context import SCHEMA as SYNTH_CONTEXT_SCHEMA


def _load(path: Path, schema: str, label: str) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != schema:
        raise RuntimeError(f"RESEARCH_SPINE_V2_{label}_SCHEMA_REJECTED")
    return obj


def build_research_spine_v2(
    topa_root: Path,
    demi_head_root: Path,
    fundamentum_root: Path,
    org_surface_path: Path,
    wikipedia_path: Path,
    arxiv_queries: list[str],
    *,
    semantic_synthesis_path: Path | None = None,
    max_results: int = 4,
    timeout: float = 12.0,
    enable_arxiv: bool = True,
) -> dict:
    obj = base.build_research_spine(
        topa_root,
        demi_head_root,
        fundamentum_root,
        arxiv_queries,
        max_results=max_results,
        timeout=timeout,
        enable_arxiv=enable_arxiv,
    )
    org = _load(org_surface_path, ORG_SCHEMA, "ORG_SURFACE")
    wiki = _load(wikipedia_path, WIKI_SCHEMA, "WIKIPEDIA")
    if org.get("status") != "READY_PUBLIC_ALL_BOUND_PRIVATE_UNMOUNTED":
        obj["status"] = "BLOCKED_REQUIRED_RESEARCH_ORGAN"
    wiki_ready = wiki.get("status") in {"READY", "READY_DEGRADED"}
    obj["research_spine"]["org_surface"] = org
    obj["research_spine"]["wikipedia"] = wiki

    synth = None
    if semantic_synthesis_path is not None:
        synth = _load(semantic_synthesis_path, SYNTH_CONTEXT_SCHEMA, "SEMANTIC_SYNTHESIS")
        caps = synth.get("capabilities") or {}
        if caps.get("may_be_used_as_world_truth") is not False:
            raise RuntimeError("RESEARCH_SPINE_V2_SYNTH_TRUTH_CEILING_REJECTED")
        if caps.get("may_be_direct_gradient_signal") is not False:
            raise RuntimeError("RESEARCH_SPINE_V2_SYNTH_GRADIENT_CEILING_REJECTED")
        if caps.get("may_grant_mutation_authority") is not False:
            raise RuntimeError("RESEARCH_SPINE_V2_SYNTH_MUTATION_CEILING_REJECTED")
        if caps.get("may_auto_promote_semantic_candidate") is not False:
            raise RuntimeError("RESEARCH_SPINE_V2_SYNTH_PROMOTION_CEILING_REJECTED")
        obj["research_spine"]["semantic_synthesis"] = synth

    obj["external_context"] = {
        "org_surface_status": org.get("status"),
        "wikipedia_status": wiki.get("status"),
        "wikipedia_degraded": not wiki_ready,
        "public_repository_count": org.get("public_discovered_count"),
        "public_repository_bound_count": org.get("public_bound_count"),
        "private_repository_unmounted_count": (org.get("private_inventory") or {}).get("unmounted_count"),
        "wikipedia_page_count": wiki.get("page_count"),
        "semantic_synthesis_status": synth.get("status") if synth else "NOT_MOUNTED",
        "semantic_synthesis_candidate_count": ((synth.get("source") or {}).get("candidate_count_selected") if synth else 0),
        "semantic_synthesis_route_count": len(synth.get("research_route_seeds") or []) if synth else 0,
    }
    obj["hypothesis_routes"] = list(synth.get("research_route_seeds") or []) if synth else []
    obj["claim_ceiling"].update({
        "org_surface_presence_is_truth": False,
        "org_surface_grants_authority": False,
        "wikipedia_presence_is_truth": False,
        "wikipedia_article_is_verified_fact": False,
        "wikipedia_text_is_instruction": False,
        "semantic_synthesis_is_truth": False,
        "semantic_synthesis_is_proof": False,
        "semantic_synthesis_is_direct_gradient_signal": False,
        "semantic_synthesis_grants_mutation_authority": False,
        "semantic_synthesis_auto_promotes_candidates": False,
    })
    obj["laws"].extend([
        "ORG_SURFACE_VISIBILITY != AUTHORITY",
        "REPOSITORY_PRESENCE != TRAINING_INCLUSION",
        "WIKIPEDIA_ARTICLE != VERIFIED_FACT",
        "WIKIPEDIA_TEXT != INSTRUCTION",
        "WIKIPEDIA_CONTEXT != TARGET_LOCAL_VERIFICATION",
        "SYNTHESIS != TRUTH",
        "SEMANTIC_CANDIDATE != VERIFIED_FACT",
        "SEMANTIC_CONTEXT MAY GENERATE QUESTIONS BUT NOT ANSWERS",
        "SEMANTIC_SYNTHESIS_CONTEXT != DIRECT_GRADIENT_SIGNAL",
        "NO CORROBORATION OR TARGET_LOCAL_VERIFY => NO SEMANTIC_PROMOTION",
    ])
    obj.pop("context_sha256", None)
    obj["context_sha256"] = base.sha256_bytes(base.canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topa-root", required=True)
    ap.add_argument("--demi-head-root", required=True)
    ap.add_argument("--fundamentum-root", required=True)
    ap.add_argument("--org-surface", required=True)
    ap.add_argument("--wikipedia", required=True)
    ap.add_argument("--semantic-synthesis")
    ap.add_argument("--out", required=True)
    ap.add_argument("--arxiv-query", action="append", default=[])
    ap.add_argument("--max-results", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--no-arxiv", action="store_true")
    args = ap.parse_args()
    queries = args.arxiv_query or list(base.DEFAULT_ARXIV_QUERIES)
    if args.max_results < 1 or args.max_results > 8 or len(queries) > 6:
        raise SystemExit("RESEARCH_SPINE_V2_BOUNDS_REJECTED")
    obj = build_research_spine_v2(
        Path(args.topa_root),
        Path(args.demi_head_root),
        Path(args.fundamentum_root),
        Path(args.org_surface),
        Path(args.wikipedia),
        queries,
        semantic_synthesis_path=Path(args.semantic_synthesis) if args.semantic_synthesis else None,
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
        "org_surface_status": obj["external_context"]["org_surface_status"],
        "public_repository_count": obj["external_context"]["public_repository_count"],
        "wikipedia_status": obj["external_context"]["wikipedia_status"],
        "wikipedia_page_count": obj["external_context"]["wikipedia_page_count"],
        "semantic_synthesis_status": obj["external_context"]["semantic_synthesis_status"],
        "semantic_synthesis_candidate_count": obj["external_context"]["semantic_synthesis_candidate_count"],
        "semantic_synthesis_route_count": obj["external_context"]["semantic_synthesis_route_count"],
    }, indent=2))
    if obj["status"] == "BLOCKED_REQUIRED_RESEARCH_ORGAN":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
