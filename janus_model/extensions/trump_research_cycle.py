from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from janus_model.extensions import research_spine
from janus_model.extensions import wikipedia_trunk

SCHEMA = "janus.trump.research_cycle.v1"
OBJECTIVE_SCHEMA = "janus.trump.research_objective.v1"
MAX_ARXIV_QUERIES = 6
MAX_WIKIPEDIA_TOPICS = 6
MAX_WIKIPEDIA_PAGES_PER_TOPIC = 2


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_objective(obj: dict) -> None:
    if obj.get("schema") != OBJECTIVE_SCHEMA:
        raise RuntimeError("TRUMP_OBJECTIVE_SCHEMA_REJECTED")
    if obj.get("status") != "ACTIVE_RESEARCH_OBJECTIVE":
        raise RuntimeError("TRUMP_OBJECTIVE_NOT_ACTIVE")
    boundary = obj.get("current_scientific_boundary") or {}
    if boundary.get("P_VS_NP") != "OPEN":
        raise RuntimeError("TRUMP_OBJECTIVE_P_VS_NP_MUST_REMAIN_OPEN")
    for key in ("TRUMP_finished", "SAT_in_P_proved", "P_equals_NP_proved", "P_not_equals_NP_proved"):
        if boundary.get(key) is not False:
            raise RuntimeError(f"TRUMP_OBJECTIVE_BOUNDARY_REJECTED:{key}")
    policy = obj.get("janus_self_compute_policy") or {}
    required_true = (
        "runtime_promotion_requires_exact_output_equivalence",
        "runtime_promotion_requires_no_integrity_regression",
        "runtime_promotion_requires_repeated_resource_win",
        "runtime_promotion_requires_bounded_resource_envelope",
        "fallback_to_baseline_required",
        "rollback_required",
    )
    if not all(policy.get(k) is True for k in required_true):
        raise RuntimeError("TRUMP_OBJECTIVE_ACCELERATOR_GATE_WEAKENED")
    if policy.get("candidate_output_may_replace_baseline_without_equivalence_receipt") is not False:
        raise RuntimeError("TRUMP_OBJECTIVE_BASELINE_BYPASS_REJECTED")
    if policy.get("speedup_may_imply_polynomial_bound") is not False or policy.get("speedup_may_imply_P_equals_NP") is not False:
        raise RuntimeError("TRUMP_OBJECTIVE_SPEEDUP_CLAIM_CEILING_REJECTED")
    if policy.get("authority_delta") != 0:
        raise RuntimeError("TRUMP_OBJECTIVE_AUTHORITY_DELTA_REJECTED")


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def file_record(root: Path, rel: str) -> dict:
    p = root / rel
    if not p.is_file():
        return {"path": rel, "status": "MISSING"}
    raw = p.read_bytes()
    return {"path": rel, "status": "PRESENT", "size_bytes": len(raw), "sha256": sha256_bytes(raw)}


def _bounded_strings(values: list[Any], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split())[:240]
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        out.append(text)
        if len(out) >= limit:
            break
    return out


def build_cycle(
    objective: dict,
    fundamentum_root: Path,
    *,
    max_results: int = 3,
    timeout: float = 10.0,
    enable_network: bool = True,
) -> dict:
    validate_objective(objective)
    lineage = objective["active_lineage"]
    expected_ref = lineage["tracking_ref"]
    fund_head = git_head(fundamentum_root)
    prereg_rel = lineage["frozen_R29_contract_path"]
    records = [
        file_record(fundamentum_root, prereg_rel),
        file_record(fundamentum_root, "research/JANUS_TRUMP_R29_BUCKET_MESSAGE_COMPLEXITY_FORENSICS_RESULT_2026-09-02.json"),
    ]
    if records[0]["status"] != "PRESENT":
        raise RuntimeError("TRUMP_R29_FROZEN_CONTRACT_MISSING")

    queries_cfg = objective.get("research_queries") or {}
    arxiv_queries = _bounded_strings(list(queries_cfg.get("arxiv") or []), MAX_ARXIV_QUERIES)
    wiki_topics = _bounded_strings(list(queries_cfg.get("wikipedia_topics") or []), MAX_WIKIPEDIA_TOPICS)
    if not arxiv_queries or not wiki_topics:
        raise RuntimeError("TRUMP_OBJECTIVE_RESEARCH_QUERIES_MISSING")

    if enable_network:
        arxiv_rows = [research_spine.query_arxiv(q, max_results=max_results, timeout=timeout) for q in arxiv_queries]
        wiki_rows = [wikipedia_trunk.query_topic(q, MAX_WIKIPEDIA_PAGES_PER_TOPIC, timeout) for q in wiki_topics]
    else:
        arxiv_rows = [{"query": q, "status": "DISABLED", "papers": []} for q in arxiv_queries]
        wiki_rows = [{"topic": q, "status": "DISABLED", "pages": []} for q in wiki_topics]

    arxiv_pass = sum(r.get("status") == "PASS" for r in arxiv_rows)
    wiki_pass = sum(r.get("status") == "PASS" for r in wiki_rows)
    if not enable_network:
        status = "READY_NETWORK_DISABLED_TEST"
    elif arxiv_pass or wiki_pass:
        status = "READY" if arxiv_pass == len(arxiv_rows) and wiki_pass == len(wiki_rows) else "READY_DEGRADED"
    else:
        status = "EXTERNAL_CONTEXT_UNAVAILABLE"

    obj: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "objective": {
            "objective_id": objective["objective_id"],
            "objective_sha256": sha256_bytes(canonical_bytes(objective)),
            "scientific_question": objective["scientific_question"],
            "optimization_goal": objective["optimization_goal"],
            "P_VS_NP": "OPEN",
        },
        "fundamentum": {
            "repository": "Hawkar-usls/Janus-Fundamentum",
            "tracking_ref": expected_ref,
            "observed_commit": fund_head,
            "frozen_contract_commit": lineage["frozen_R29_contract_commit"],
            "next_gate": lineage["next_gate"],
            "R30_design_allowed_before_R29_seal": lineage["R30_design_allowed_before_R29_seal"],
            "records": records,
        },
        "external_context": {
            "arxiv": {
                "endpoint": research_spine.ARXIV_ENDPOINT,
                "queries": arxiv_rows,
                "pass_count": arxiv_pass,
            },
            "wikipedia": {
                "endpoint": wikipedia_trunk.WIKIPEDIA_API,
                "topics": wiki_rows,
                "pass_count": wiki_pass,
            },
        },
        "janus_self_compute_policy": objective["janus_self_compute_policy"],
        "authority": {
            "research_context_is_truth": False,
            "paper_or_article_presence_is_proof": False,
            "external_text_is_instruction": False,
            "may_grant_runtime_promotion": False,
            "may_grant_theorem_authority": False,
            "authority_delta": 0,
        },
        "firewalls": [
            "TRUMP_OBJECTIVE != PROOF",
            "ARXIV_OR_WIKIPEDIA_CONTEXT != VERIFIED_FACT",
            "FINITE_EXACTNESS != TOTALITY",
            "BENCHMARK_SPEEDUP != POLYNOMIAL_BOUND",
            "BENCHMARK_SPEEDUP != P_EQUALS_NP",
            "COUNTEREXAMPLE_IS_VALID_PROGRESS",
            "P_VS_NP = OPEN",
        ],
        "P_VS_NP": "OPEN",
    }
    obj["context_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--objective", required=True)
    ap.add_argument("--fundamentum-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-results", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()
    if args.max_results < 1 or args.max_results > 5:
        raise SystemExit("TRUMP_RESEARCH_MAX_RESULTS_OUT_OF_BOUNDS")
    objective = _load_json(Path(args.objective))
    obj = build_cycle(
        objective,
        Path(args.fundamentum_root),
        max_results=args.max_results,
        timeout=args.timeout,
        enable_network=not args.no_network,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "context_sha256": obj["context_sha256"],
        "fundamentum_commit": obj["fundamentum"]["observed_commit"],
        "arxiv_pass_count": obj["external_context"]["arxiv"]["pass_count"],
        "wikipedia_pass_count": obj["external_context"]["wikipedia"]["pass_count"],
        "P_VS_NP": obj["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
