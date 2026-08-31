#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BENCHMARK_ID = "JANUS_TRUMP_SLIME_R6_1_REGRET_BOUNDED_EXPLORATION_FROZEN_C1K0_BENCH_V1"
FREEZE = "9a9cc0a53d7aaeea351630644d45dbdb900a0020"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", type=Path, required=True)
    ap.add_argument("--artifact-id", type=int, required=True)
    ap.add_argument("--artifact-digest", required=True)
    ap.add_argument("--runtime-merge-commit", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    raw = args.result.read_bytes()
    result = json.loads(raw)
    if result.get("status") != "PASS":
        raise SystemExit("R6_1_RESULT_NOT_PASS")
    if result.get("benchmark_id") != BENCHMARK_ID:
        raise SystemExit("R6_1_BENCHMARK_ID_DRIFT")
    if result.get("freeze_commit_before_R6_1_implementation") != FREEZE:
        raise SystemExit("R6_1_FREEZE_DRIFT")
    holdout = result["holdout"]
    gate = holdout["gate"]
    if not all(bool(v) for v in gate.values()):
        raise SystemExit("R6_1_GATE_NOT_ALL_TRUE")

    receipt = {
        "schema": "janus.trump.slime_r6_1_regret_bounded_exploration.frozen_pass_receipt.v1",
        "date": "2026-08-31",
        "status": "CANONICAL_FROZEN_SCOPED_PASS_RECEIPT",
        "component": "TRUMP_SLIME_R6_1_REGRET_BOUNDED_EXPLORATION",
        "P_VS_NP": "OPEN",
        "runtime_main_commit": args.runtime_merge_commit,
        "freeze": {
            "commit_before_implementation": FREEZE,
            "benchmark_id": BENCHMARK_ID,
            "single_successor_change": result["single_successor_change"],
            "base_R6_code_provenance": result["base_R6_code_provenance"],
            "winner_preregistered": False,
        },
        "provenance": {
            "implementation_pull_request": 68,
            "implementation_head": "5f79064fdd8bd8f4f9e80676e01f09249a75a417",
            "dedicated_frozen_workflow": {
                "run_id": 33434716083,
                "run_number": 1,
                "conclusion": "success",
                "artifact_id": args.artifact_id,
                "artifact_digest": args.artifact_digest,
                "result_json_sha256": hashlib.sha256(raw).hexdigest(),
            },
            "candidate_runtime": {"run_id": 33434716008, "run_number": 137, "conclusion": "success"},
            "restoration_probation": {"run_id": 33434716109, "run_number": 131, "conclusion": "success"},
            "solver_source": result["solver_source"],
        },
        "memory": result["memory"],
        "frozen_result": {
            "formula_count": holdout["formula_count"],
            "canonical_decisive": holdout["canonical_decisive"],
            "canonical_OPEN": holdout["canonical_OPEN"],
            "baseline_R5_decisive": holdout["baseline_R5_decisive"],
            "R6_1_final_decisive": holdout["R6_1_final_decisive"],
            "contradictions": holdout["contradictions"],
            "supported_memory_formulas": holdout["supported_memory_formulas"],
            "nonbaseline_root_routes": holdout["nonbaseline_root_routes"],
            "direct_R5_fallback": holdout["direct_R5_fallback"],
            "forced_OPEN_fallback": holdout["forced_OPEN_fallback"],
            "exploration": holdout["exploration"],
            "per_family": holdout["per_family"],
            "work": holdout["work"],
            "gate": gate,
        },
        "supported_claim": result["claim"],
        "supported_interpretation": {
            "regret_bounded_exploration_restored_scoped_online_work_reduction": True,
            "decisive_coverage_preserved": holdout["R6_1_final_decisive"] >= holdout["baseline_R5_decisive"],
            "contradictory_exact_decisive_results": holdout["contradictions"],
            "all_high_regret_triggered_alternates_shadow_blocked": gate["all_high_regret_triggered_alternates_shadow_blocked"],
            "no_high_regret_alternate_exact_executed": gate["no_high_regret_alternate_exact_executed"],
            "memory_frozen_during_holdout": gate["memory_frozen_during_holdout"],
        },
        "authority": result["authority"],
        "scientific_boundary": result["scientific_boundary"],
        "explicit_nonclaims": {
            "general_solver_or_wall_clock_speedup": False,
            "calibration_amortized_speedup": False,
            "threshold_1_25_universal_optimum": False,
            "finite_same_family_holdout_is_generalization": False,
            "neural_Pivot_Slime_teacher_or_student_deployed": False,
            "R5_or_C025_completeness": False,
            "P_equals_NP": False,
        },
        "next_frontier": {
            "state": "NONNEURAL_RECEIPT_GROUNDED_M2R_ROUTING_SCOPED_PASS_ESTABLISHED",
            "neural_teacher_student": "MAY_BE_FROZEN_ONLY_AS_A_SEPARATE_ADVISORY_EXPERIMENT__NOT_DEPLOYED_BY_THIS_RECEIPT",
            "known_R5_GT8_resource_frontier": "OPEN",
        },
        "law": "R6_1_PASS_MEANS_FROZEN_RECEIPT_GROUNDED_REGRET_BOUNDED_EXPLORATION_REDUCED_ONLINE_EXACT_R5_WORK_WITH_DECISIVE_COVERAGE_PRESERVED_IN_THIS_SCOPE__NOT_GENERAL_OR_AMORTIZED_SPEEDUP__P_VS_NP_OPEN",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
