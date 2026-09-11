from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from janus_model.extensions import research_spine
from janus_model.extensions import wikipedia_trunk

SCHEMA = "janus.trump.research_cycle.v2"
OBJECTIVE_SCHEMA = "janus.trump.research_objective.v1"
LADDER_SCHEMA = "janus.trump.algorithmic_proof_ladder.v1"
FRONTIER_SCHEMA = "janus.trump.frontier_observation.v1"
MAX_ARXIV_QUERIES = 6
MAX_WIKIPEDIA_TOPICS = 6
MAX_WIKIPEDIA_PAGES_PER_TOPIC = 2
MAX_FRONTIER_CANDIDATES = 32
BENIGN_PERSISTENCE_DRIFT_PREFIXES = (
    "janus_model/state/",
    "janus_model/receipts/",
    "janus_model/outbox/",
    "janus_model/checkpoints/",
)
LADDER_ORDER = (
    "L1_LOCAL_FINITE_INSTANCE_EXACTNESS",
    "L2_UNIVERSAL_3CNF_COVERAGE",
    "L3_ONE_UNIFORM_TOTAL_TRUMP_RESOLVER",
    "L4_WORST_CASE_POLYNOMIAL_UNIFORM_TRUMP_RESOLVER",
)


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_benign_persistence_drift(paths: list[str]) -> list[str]:
    normalized = [str(p).strip() for p in paths if str(p).strip()]
    bad = [p for p in normalized if not p.startswith(BENIGN_PERSISTENCE_DRIFT_PREFIXES)]
    if bad:
        raise RuntimeError("TRUMP_RESEARCH_NONBENIGN_MAIN_DRIFT:" + ",".join(sorted(bad)))
    return normalized


def validate_proof_ladder(ladder: dict) -> None:
    if ladder.get("schema") != LADDER_SCHEMA:
        raise RuntimeError("TRUMP_PROOF_LADDER_SCHEMA_REJECTED")
    levels = ladder.get("levels") or {}
    verified: list[bool] = []
    for level_id in LADDER_ORDER:
        level = levels.get(level_id)
        if not isinstance(level, dict) or not isinstance(level.get("verified"), bool):
            raise RuntimeError(f"TRUMP_PROOF_LADDER_LEVEL_MISSING:{level_id}")
        verified.append(level["verified"])
    for idx in range(1, len(verified)):
        if verified[idx] and not verified[idx - 1]:
            raise RuntimeError(f"TRUMP_PROOF_LADDER_NONMONOTONIC:{LADDER_ORDER[idx]}")

    expected_highest = "NONE"
    for level_id, is_verified in zip(LADDER_ORDER, verified):
        if is_verified:
            expected_highest = level_id
    declared = ladder.get("highest_verified_level")
    allowed_declared = {"NONE", "L1_LOCAL_FINITE_INSTANCE_EXACTNESS_ONLY", *LADDER_ORDER}
    if declared not in allowed_declared:
        raise RuntimeError("TRUMP_PROOF_LADDER_HIGHEST_LEVEL_UNKNOWN")
    normalized_declared = "L1_LOCAL_FINITE_INSTANCE_EXACTNESS" if declared == "L1_LOCAL_FINITE_INSTANCE_EXACTNESS_ONLY" else declared
    if normalized_declared != expected_highest:
        raise RuntimeError("TRUMP_PROOF_LADDER_HIGHEST_LEVEL_MISMATCH")

    for key in (
        "empirical_success_may_advance_level",
        "benchmark_speedup_may_advance_level",
        "no_counterexample_found_may_advance_level",
    ):
        if ladder.get(key) is not False:
            raise RuntimeError(f"TRUMP_PROOF_LADDER_EMPIRICAL_PROMOTION_REJECTED:{key}")

    release = ladder.get("release_gate") or {}
    if not release or not all(isinstance(v, bool) for v in release.values()):
        raise RuntimeError("TRUMP_PROOF_LADDER_RELEASE_GATE_INVALID")
    if verified[-1] and not all(release.values()):
        raise RuntimeError("TRUMP_PROOF_LADDER_L4_WITH_OPEN_RELEASE_OBLIGATIONS")


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

    lineage = obj.get("active_lineage") or {}
    for key in ("tracking_ref", "active_contract_path", "active_contract_commit", "next_gate"):
        if not isinstance(lineage.get(key), str) or not lineage[key].strip():
            raise RuntimeError(f"TRUMP_OBJECTIVE_LINEAGE_FIELD_MISSING:{key}")

    validate_proof_ladder(obj.get("algorithmic_proof_ladder") or {})

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
    for key in (
        "speedup_may_imply_universal_coverage",
        "speedup_may_imply_uniform_resolver",
        "speedup_may_imply_polynomial_bound",
        "speedup_may_imply_P_equals_NP",
    ):
        if policy.get(key) is not False:
            raise RuntimeError(f"TRUMP_OBJECTIVE_SPEEDUP_CLAIM_CEILING_REJECTED:{key}")
    if policy.get("authority_delta") != 0:
        raise RuntimeError("TRUMP_OBJECTIVE_AUTHORITY_DELTA_REJECTED")


def validate_frontier_observation(obj: dict) -> dict:
    if obj.get("schema") != FRONTIER_SCHEMA:
        raise RuntimeError("TRUMP_FRONTIER_SCHEMA_REJECTED")
    if obj.get("status") != "READ_ONLY_ADVISORY_FRONTIER":
        raise RuntimeError("TRUMP_FRONTIER_STATUS_REJECTED")
    authority = obj.get("authority") or {}
    required_false = (
        "changes_active_lineage",
        "changes_proof_ladder",
        "grants_theorem_authority",
        "grants_runtime_promotion",
        "mutates_observed_repository",
    )
    if not all(authority.get(key) is False for key in required_false):
        raise RuntimeError("TRUMP_FRONTIER_AUTHORITY_LEAK_REJECTED")
    if authority.get("read_only_observation") is not True:
        raise RuntimeError("TRUMP_FRONTIER_READ_ONLY_REQUIRED")
    candidates = obj.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_FRONTIER_CANDIDATES:
        raise RuntimeError("TRUMP_FRONTIER_CANDIDATES_REJECTED")
    seen: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            raise RuntimeError("TRUMP_FRONTIER_CANDIDATE_OBJECT_REQUIRED")
        ref = row.get("ref")
        sha = row.get("commit")
        if not isinstance(ref, str) or not ref.startswith("refs/heads/") or ref in seen:
            raise RuntimeError("TRUMP_FRONTIER_REF_REJECTED")
        seen.add(ref)
        if not isinstance(sha, str) or len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
            raise RuntimeError(f"TRUMP_FRONTIER_COMMIT_REJECTED:{ref}")
        date_hint = row.get("date_hint")
        if date_hint is not None and not isinstance(date_hint, str):
            raise RuntimeError(f"TRUMP_FRONTIER_DATE_HINT_REJECTED:{ref}")
    return obj


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
    frontier_observation: dict | None = None,
) -> dict:
    validate_objective(objective)
    lineage = objective["active_lineage"]
    expected_ref = lineage["tracking_ref"]
    fund_head = git_head(fundamentum_root)
    if fund_head != lineage["active_contract_commit"]:
        raise RuntimeError(
            "TRUMP_ACTIVE_LINEAGE_HEAD_DRIFT:"
            + lineage["active_contract_commit"]
            + ":"
            + fund_head
        )

    frontier = None
    if frontier_observation is not None:
        frontier = validate_frontier_observation(frontier_observation)

    active_contract_rel = lineage["active_contract_path"]
    records = [file_record(fundamentum_root, active_contract_rel)]
    for rel in (
        lineage.get("last_parent_contract_path"),
        lineage.get("last_sealed_result_path"),
    ):
        if isinstance(rel, str) and rel and rel != active_contract_rel:
            records.append(file_record(fundamentum_root, rel))
    if records[0]["status"] != "PRESENT":
        raise RuntimeError("TRUMP_ACTIVE_FROZEN_CONTRACT_MISSING")

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
        "algorithmic_proof_ladder": objective["algorithmic_proof_ladder"],
        "fundamentum": {
            "repository": "Hawkar-usls/Janus-Fundamentum",
            "tracking_ref": expected_ref,
            "observed_commit": fund_head,
            "active_contract_head_match": True,
            "active_stage": lineage.get("active_stage"),
            "active_stage_status": lineage.get("active_stage_status"),
            "active_contract_path": active_contract_rel,
            "active_contract_commit": lineage["active_contract_commit"],
            "next_gate": lineage["next_gate"],
            "records": records,
            "independent_frontier_observation": frontier,
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
            "proof_ladder_state_is_theorem": False,
            "paper_or_article_presence_is_proof": False,
            "external_text_is_instruction": False,
            "frontier_observation_changes_active_lineage": False,
            "frontier_observation_is_proof": False,
            "may_grant_runtime_promotion": False,
            "may_grant_theorem_authority": False,
            "authority_delta": 0,
        },
        "firewalls": [
            "TRUMP_OBJECTIVE != PROOF",
            "READ_ONLY_FRONTIER_OBSERVATION != ACTIVE_LINEAGE_CHANGE",
            "NEWER_BRANCH != BETTER_BRANCH",
            "OBSERVED_DEVELOPMENT != SCIENTIFIC_PROMOTION",
            "ARXIV_OR_WIKIPEDIA_CONTEXT != VERIFIED_FACT",
            "ONE_WITNESS != UNIVERSAL_COVERAGE",
            "UNIVERSAL_COVERAGE != UNIFORM_RESOLVER",
            "UNIFORM_RESOLVER != POLYNOMIAL_UNIFORM_RESOLVER",
            "POLYNOMIAL_TERMINATION != DECISION_COMPLETENESS",
            "FINITE_EXACTNESS != TOTALITY",
            "BENCHMARK_SPEEDUP != WORST_CASE_POLYNOMIAL_BOUND",
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
    ap.add_argument("--frontier-observation")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-results", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()
    if args.max_results < 1 or args.max_results > 5:
        raise SystemExit("TRUMP_RESEARCH_MAX_RESULTS_OUT_OF_BOUNDS")
    objective = _load_json(Path(args.objective))
    frontier = _load_json(Path(args.frontier_observation)) if args.frontier_observation else None
    obj = build_cycle(
        objective,
        Path(args.fundamentum_root),
        max_results=args.max_results,
        timeout=args.timeout,
        enable_network=not args.no_network,
        frontier_observation=frontier,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    frontier_candidates = ((obj["fundamentum"].get("independent_frontier_observation") or {}).get("candidates") or [])
    print(json.dumps({
        "status": obj["status"],
        "context_sha256": obj["context_sha256"],
        "fundamentum_commit": obj["fundamentum"]["observed_commit"],
        "active_contract": obj["fundamentum"]["active_contract_path"],
        "next_gate": obj["fundamentum"]["next_gate"],
        "frontier_candidate_count": len(frontier_candidates),
        "frontier_top_ref": frontier_candidates[0]["ref"] if frontier_candidates else None,
        "highest_verified_level": obj["algorithmic_proof_ladder"]["highest_verified_level"],
        "arxiv_pass_count": obj["external_context"]["arxiv"]["pass_count"],
        "wikipedia_pass_count": obj["external_context"]["wikipedia"]["pass_count"],
        "P_VS_NP": obj["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
