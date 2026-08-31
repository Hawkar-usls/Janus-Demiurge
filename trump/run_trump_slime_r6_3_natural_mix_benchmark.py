#!/usr/bin/env python3
"""Frozen R6.3 natural un-enriched replication benchmark.

All 60 formulas are fixed before implementation. The unchanged receipt-grounded
R6 M2R memory and unchanged 1.25 regret guard are evaluated against standard R5
on canonical-OPEN cases. No formula is selected by trigger/support/regret/truth,
result, or exact work. Naturally occurring high-regret shadow rejections may be
exact-measured in a non-authoritative counterfactual lane. P_VS_NP remains OPEN.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import trump_slime_r6_keymaster_m2r as base
import trump_slime_r6_1_regret_guard as guard

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R6_3_NATURAL_MIX_REPLICATION_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "1be4d56372debe44566bf70bd8a39d149f095bad"


class R63Error(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R6_3_NATURAL_MIX_REPLICATION_FROZEN_C1K0_BENCH_V1":
        raise R63Error("R6_3_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R6_3_BENCHMARK_IMPLEMENTATION":
        raise R63Error("R6_3_SPEC_STATUS_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise R63Error("R6_3_WINNER_PREREGISTRATION_FORBIDDEN")
    return spec


def install_pure_resolution_cache(solver) -> dict[str, int]:
    original = solver.bounded_width_resolution_refutes
    cache: dict[tuple[Any, int], tuple[bool, Any]] = {}
    stats = {"requests": 0, "hits": 0, "misses": 0}

    def cached(cnf, width=3):
        stats["requests"] += 1
        key = (cnf, int(width))
        if key in cache:
            stats["hits"] += 1
            refuted, cert = cache[key]
            return refuted, copy.deepcopy(cert)
        stats["misses"] += 1
        refuted, cert = original(cnf, width)
        cache[key] = (refuted, copy.deepcopy(cert))
        return refuted, cert

    solver.bounded_width_resolution_refutes = cached
    return stats


def same_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def holdout_subjects(spec: dict[str, Any]) -> list[tuple[str, int]]:
    raw = spec["fresh_fixed_unenriched_holdout"]
    families = ("CONNECTED_RANDOM_3CNF_V1", "GT6", "GT7", "GT6_WRAPPED", "GT7_WRAPPED")
    rows: list[tuple[str, int]] = []
    for family in families:
        rows.extend((family, int(seed)) for seed in raw[family])
    if len(rows) != int(raw["formula_count"]):
        raise R63Error("R6_3_HOLDOUT_COUNT_DRIFT")
    return rows


def _route_with_fallback(solver, clauses, profile: dict[str, int], pivot: int, baseline: dict[str, Any]) -> dict[str, Any]:
    forced = base.run_forced_root_route(solver, clauses, int(pivot), profile)
    if not forced.get("selected_split_verified"):
        raise R63Error("R6_3_FORCED_ROOT_SPLIT_NOT_VERIFIED")
    execution = int(forced["execution_work"])
    replay = int(forced["replay_work"])
    fallback_used = False
    final_status = str(forced["status"])
    final_reason = str(forced["reason"])
    if final_status not in {"SAT", "UNSAT"}:
        fallback_used = True
        execution += int(baseline["combined_fallback_work"])
        replay += int(baseline["replay_work"])
        final_status = str(baseline["exact_result"]["status"])
        final_reason = str(baseline["exact_result"].get("reason"))
    return {
        "forced": forced,
        "fallback_used": fallback_used,
        "execution_work": execution,
        "replay_work": replay,
        "full_route_work": execution + replay,
        "final_status": final_status,
        "final_reason": final_reason,
    }


def _clean(candidate):
    if candidate is None:
        return None
    return {k: v for k, v in candidate.items() if k != "vector"}


def execute() -> dict[str, Any]:
    spec = load_frozen_spec()
    solver, source = base.r5.load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}
    memory = base.build_frozen_memory(solver, base.load_frozen_spec())
    memory_digest_before = base.stable_hash(memory)
    memory_identity_before = str(memory["memory_state_identity"])

    rows: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    canonical_decisive = 0
    canonical_open = 0
    baseline_decisive = 0
    actual_decisive = 0
    contradictions = 0
    selected_split_failures = 0
    supported_memory_formulas = 0
    nonbaseline_routes = 0
    direct_fallback = 0
    forced_open_fallback = 0
    exploration_triggers = 0
    supported_triggered_alternates = 0
    high_regret_exposures = 0
    high_regret_shadow_rejected = 0
    high_regret_authority_exact_exec = 0
    low_regret_exact_exploration = 0
    counterfactual_split_failures = 0

    per_family = {
        family: {
            "formulas": 0,
            "canonical_OPEN": 0,
            "baseline_decisive": 0,
            "actual_decisive": 0,
            "supported_memory": 0,
            "exploration_triggers": 0,
            "supported_triggered_alternates": 0,
            "high_regret_exposures": 0,
        }
        for family in ("CONNECTED_RANDOM_3CNF_V1", "GT6", "GT7", "GT6_WRAPPED", "GT7_WRAPPED")
    }

    work = {
        "baseline_R5_execution": 0,
        "baseline_R5_replay": 0,
        "baseline_R5_full": 0,
        "actual_forced_execution": 0,
        "actual_forced_replay": 0,
        "actual_fallback_execution": 0,
        "actual_fallback_replay": 0,
        "feature_inference": 0,
        "actual_execution_including_feature": 0,
        "actual_full": 0,
        "counterfactual_high_regret_execution_including_feature": 0,
        "counterfactual_high_regret_full": 0,
        "actual_high_regret_execution_including_feature": 0,
        "actual_high_regret_full": 0,
    }

    for family, seed in holdout_subjects(spec):
        per_family[family]["formulas"] += 1
        clauses = base.formula_for(family, seed)
        root = solver.canon_cnf(clauses)
        fp = solver.fingerprint(root)
        if fp in fingerprints:
            raise R63Error("R6_3_HOLDOUT_FINGERPRINT_COLLISION")
        fingerprints.add(fp)

        canonical = solver.solve_fail_closed(clauses, **profile)
        if canonical["status"] in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            replay = solver.solve_fail_closed(clauses, **profile)
            if not same_result(canonical, replay):
                raise R63Error("R6_3_CANONICAL_DECISIVE_REPLAY_MISMATCH")
            rows.append({
                "family": family,
                "seed": seed,
                "fingerprint": fp,
                "canonical_status": canonical["status"],
                "R6_invoked": False,
                "final_status": canonical["status"],
            })
            continue

        canonical_open += 1
        per_family[family]["canonical_OPEN"] += 1
        baseline = base.r5.solve_r5_fallback(solver, clauses, **profile)
        baseline_status = str(baseline["exact_result"]["status"])
        baseline_exec = int(baseline["combined_fallback_work"])
        baseline_replay = int(baseline["replay_work"])
        baseline_full = baseline_exec + baseline_replay
        work["baseline_R5_execution"] += baseline_exec
        work["baseline_R5_replay"] += baseline_replay
        work["baseline_R5_full"] += baseline_full
        if baseline_status in {"SAT", "UNSAT"}:
            baseline_decisive += 1
            per_family[family]["baseline_decisive"] += 1

        selection = guard.select_root_route(solver, root, memory)
        inference = int(selection["feature_inference_work"])
        work["feature_inference"] += inference
        supported = selection.get("supported") or []
        if supported:
            supported_memory_formulas += 1
            per_family[family]["supported_memory"] += 1

        trigger = bool(selection.get("exploration_trigger"))
        best = selection.get("memory_best")
        alternate = selection.get("diversity_alternate")
        ratio = selection.get("predicted_regret_ratio")
        if trigger:
            exploration_triggers += 1
            per_family[family]["exploration_triggers"] += 1
        if trigger and best is not None and alternate is not None and ratio is not None:
            supported_triggered_alternates += 1
            per_family[family]["supported_triggered_alternates"] += 1
            if float(ratio) > float(spec["immutable_runtime_sources"]["guard_threshold"]):
                high_regret_exposures += 1
                per_family[family]["high_regret_exposures"] += 1
                if selection.get("regret_guard_shadow_reject"):
                    high_regret_shadow_rejected += 1
                if selection.get("exploration_alternate_exact_executed"):
                    high_regret_authority_exact_exec += 1
            elif selection.get("exploration_alternate_exact_executed"):
                low_regret_exact_exploration += 1

        selected = selection.get("selected")
        actual = None
        if selected is None:
            direct_fallback += 1
            actual_exec = baseline_exec + inference
            actual_replay = baseline_replay
            actual_full = actual_exec + actual_replay
            final_status = baseline_status
            final_reason = str(baseline["exact_result"].get("reason"))
            fallback_used = True
            work["actual_fallback_execution"] += baseline_exec
            work["actual_fallback_replay"] += baseline_replay
        else:
            nonbaseline_routes += 1
            actual = _route_with_fallback(solver, clauses, profile, int(selected["pivot_id_local"]), baseline)
            if not actual["forced"].get("selected_split_verified"):
                selected_split_failures += 1
            work["actual_forced_execution"] += int(actual["forced"]["execution_work"])
            work["actual_forced_replay"] += int(actual["forced"]["replay_work"])
            if actual["fallback_used"]:
                forced_open_fallback += 1
                work["actual_fallback_execution"] += baseline_exec
                work["actual_fallback_replay"] += baseline_replay
            actual_exec = int(actual["execution_work"]) + inference
            actual_replay = int(actual["replay_work"])
            actual_full = int(actual["full_route_work"]) + inference
            final_status = str(actual["final_status"])
            final_reason = str(actual["final_reason"])
            fallback_used = bool(actual["fallback_used"])

        work["actual_execution_including_feature"] += actual_exec
        work["actual_full"] += actual_full

        if baseline_status in {"SAT", "UNSAT"}:
            if final_status != baseline_status:
                contradictions += 1
            else:
                actual_decisive += 1
                per_family[family]["actual_decisive"] += 1
        elif final_status in {"SAT", "UNSAT"}:
            actual_decisive += 1
            per_family[family]["actual_decisive"] += 1

        counterfactual = None
        if (
            trigger
            and best is not None
            and alternate is not None
            and ratio is not None
            and float(ratio) > float(spec["immutable_runtime_sources"]["guard_threshold"])
        ):
            counterfactual = _route_with_fallback(
                solver, clauses, profile, int(alternate["pivot_id_local"]), baseline
            )
            if not counterfactual["forced"].get("selected_split_verified"):
                counterfactual_split_failures += 1
            cf_exec = int(counterfactual["execution_work"]) + inference
            cf_full = int(counterfactual["full_route_work"]) + inference
            work["counterfactual_high_regret_execution_including_feature"] += cf_exec
            work["counterfactual_high_regret_full"] += cf_full
            work["actual_high_regret_execution_including_feature"] += actual_exec
            work["actual_high_regret_full"] += actual_full
            cf_status = str(counterfactual["final_status"])
            if baseline_status in {"SAT", "UNSAT"} and cf_status in {"SAT", "UNSAT"} and cf_status != baseline_status:
                raise R63Error("R6_3_COUNTERFACTUAL_CONTRADICTS_BASELINE")

        rows.append({
            "family": family,
            "seed": seed,
            "fingerprint": fp,
            "canonical_status": "OPEN",
            "baseline_R5": {
                "status": baseline_status,
                "execution_work": baseline_exec,
                "replay_work": baseline_replay,
                "full_work": baseline_full,
            },
            "selection": {
                "selected": _clean(selected),
                "memory_best": _clean(best),
                "diversity_alternate": _clean(alternate),
                "supported_count": len(supported),
                "exploration_trigger": trigger,
                "predicted_regret_ratio": ratio,
                "regret_guard_shadow_reject": bool(selection.get("regret_guard_shadow_reject")),
                "exploration_alternate_exact_executed": bool(selection.get("exploration_alternate_exact_executed")),
                "feature_inference_work": inference,
            },
            "actual": {
                "final_status": final_status,
                "final_reason": final_reason,
                "fallback_used": fallback_used,
                "execution_including_feature": actual_exec,
                "full_work": actual_full,
            },
            "counterfactual_high_regret": None if counterfactual is None else {
                "authority": False,
                "final_status_measurement_only": counterfactual["final_status"],
                "fallback_used": counterfactual["fallback_used"],
                "execution_including_feature": int(counterfactual["execution_work"]) + inference,
                "full_work": int(counterfactual["full_route_work"]) + inference,
            },
        })

    memory_digest_after = base.stable_hash(memory)
    memory_identity_after = str(memory["memory_state_identity"])
    memory_frozen = memory_digest_before == memory_digest_after and memory_identity_before == memory_identity_after

    saved_execution = work["baseline_R5_execution"] - work["actual_execution_including_feature"]
    saved_full = work["baseline_R5_full"] - work["actual_full"]
    high_regret_counterfactual_execution_avoided = (
        work["counterfactual_high_regret_execution_including_feature"]
        - work["actual_high_regret_execution_including_feature"]
    )
    high_regret_counterfactual_full_avoided = (
        work["counterfactual_high_regret_full"] - work["actual_high_regret_full"]
    )

    gate_spec = spec["gate"]
    base_gate = {
        "minimum_canonical_OPEN_met": canonical_open >= int(gate_spec["minimum_canonical_OPEN_formulas"]),
        "baseline_R5_decisive_coverage_preserved": actual_decisive >= baseline_decisive,
        "zero_decisive_contradictions": contradictions == 0,
        "all_selected_root_splits_exact_verified": selected_split_failures == 0,
        "strict_online_execution_work_reduction_after_feature_charge_vs_R5": saved_execution > 0,
        "strict_online_full_work_reduction_vs_R5": saved_full > 0,
        "memory_digest_unchanged": memory_frozen,
    }
    guard_exposed = high_regret_exposures >= int(
        gate_spec["minimum_natural_supported_high_regret_trigger_exposures_for_full_guard_replication"]
    )
    guard_gate = {
        "minimum_natural_supported_high_regret_trigger_exposures_met": guard_exposed,
        "all_natural_high_regret_triggered_alternates_shadow_rejected": high_regret_shadow_rejected == high_regret_exposures,
        "zero_high_regret_alternate_exact_execution_in_authority_lane": high_regret_authority_exact_exec == 0,
        "all_counterfactual_root_splits_exact_verified": counterfactual_split_failures == 0,
    }

    if all(base_gate.values()) and guard_exposed and all(guard_gate.values()):
        status = "PASS"
        claim = spec["pass_claim"]
    elif all(base_gate.values()) and not guard_exposed:
        status = "PASS_MEMORY_ROUTING_ONLY__GUARD_NATURAL_EXPOSURE_NOT_OBSERVED"
        claim = spec["memory_only_claim"]
    else:
        status = "FAIL"
        claim = spec["fail_claim"]

    return {
        "schema": "janus.trump.slime_r6_3_natural_mix_replication.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": claim,
        "freeze_commit_before_benchmark_implementation": FREEZE_COMMIT,
        "solver_source": source,
        "immutable_runtime_sources": spec["immutable_runtime_sources"],
        "memory": {
            "state_identity": memory_identity_before,
            "digest_before_holdout": memory_digest_before,
            "digest_after_holdout": memory_digest_after,
            "frozen_unchanged_during_holdout": memory_frozen,
            "episode_count": memory["episode_count"],
            "decisive_episode_count": memory["decisive_episode_count"],
            "context_bucket_count": len(memory["aggregates"]),
            "calibration_work": memory["calibration_work"],
        },
        "holdout": {
            "formula_count": len(rows),
            "canonical_decisive": canonical_decisive,
            "canonical_OPEN": canonical_open,
            "baseline_R5_decisive": baseline_decisive,
            "actual_R6_3_decisive": actual_decisive,
            "contradictions": contradictions,
            "supported_memory_formulas": supported_memory_formulas,
            "nonbaseline_routes": nonbaseline_routes,
            "direct_R5_fallback": direct_fallback,
            "forced_OPEN_fallback": forced_open_fallback,
            "exploration": {
                "triggers": exploration_triggers,
                "supported_triggered_alternates": supported_triggered_alternates,
                "natural_high_regret_exposures": high_regret_exposures,
                "high_regret_shadow_rejected": high_regret_shadow_rejected,
                "high_regret_authority_exact_executions": high_regret_authority_exact_exec,
                "low_regret_exact_exploration": low_regret_exact_exploration,
                "empirical_high_regret_exposure_fraction_of_all_formulas": high_regret_exposures / max(1, len(rows)),
                "empirical_high_regret_exposure_fraction_of_canonical_OPEN": high_regret_exposures / max(1, canonical_open),
            },
            "work": {
                **work,
                "saved_online_execution_after_feature_charge_vs_R5": saved_execution,
                "saved_online_full_work_vs_R5": saved_full,
                "high_regret_counterfactual_execution_regret_avoided": high_regret_counterfactual_execution_avoided,
                "high_regret_counterfactual_full_regret_avoided": high_regret_counterfactual_full_avoided,
            },
            "per_family": per_family,
            "base_gate": base_gate,
            "guard_gate": guard_gate,
            "rows": rows,
        },
        "physical_execution_cache": {
            "kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION",
            "logical_solver_work_charged_unchanged": True,
            "cache_stats": cache_stats,
        },
        "authority": {
            "proof_authority": False,
            "counterfactual_proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False,
        },
        "scientific_boundary": spec["scientific_boundary"],
    }


def selftest() -> dict[str, Any]:
    spec = load_frozen_spec()
    if int(spec["fresh_fixed_unenriched_holdout"]["formula_count"]) != 60:
        raise AssertionError("R6_3_FORMULA_COUNT_DRIFT")
    if spec["fresh_fixed_unenriched_holdout"]["selection_by_exploration_trigger_forbidden"] is not True:
        raise AssertionError("R6_3_NATURAL_SELECTION_LAW_DRIFT")
    return {
        "status": "PASS",
        "freeze_commit": FREEZE_COMMIT,
        "formula_count": 60,
        "enrichment": False,
        "P_VS_NP": "OPEN",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--require-base-pass", action="store_true")
    args = parser.parse_args()
    result = execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.require_base_pass and result.get("status") == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
