#!/usr/bin/env python3
"""Frozen R6.2 causal regret-guard exposure benchmark.

This benchmark does not change R5, C025, frozen R6 memory/routing, or the R6.1
regret guard. It deterministically preselects fresh formulas using only root
structure, root fingerprint, frozen pre-holdout M2R support, and predicted work.
Exact solver outcomes/work are evaluated only after that preselection.

The authority lane executes the frozen guard decision. The shadow-rejected
alternate is exact-executed in a non-authoritative counterfactual lane solely
to measure the work the guard avoided. Counterfactual outcomes never influence
the authority-lane result. P_VS_NP remains OPEN.
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
SPEC_PATH = HERE / "TRUMP_SLIME_R6_2_CAUSAL_REGRET_GUARD_EXPOSURE_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "557c2c55ee344562795f6f9a32a985902bbed767"


class R62Error(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R6_2_CAUSAL_REGRET_GUARD_EXPOSURE_FROZEN_C1K0_BENCH_V1":
        raise R62Error("R6_2_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R6_2_BENCHMARK_IMPLEMENTATION":
        raise R62Error("R6_2_SPEC_STATUS_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise R62Error("R6_2_WINNER_PREREGISTRATION_FORBIDDEN")
    if float(spec["immutable_runtime_sources"]["guard_exact_execution_threshold"]) != 1.25:
        raise R62Error("R6_2_THRESHOLD_DRIFT")
    return spec


def same_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":"))
    )


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


def _scan_range(spec: dict[str, Any], family: str) -> range:
    raw = spec["fresh_pre_result_candidate_pool"][f"{family}_seed_scan"]
    return range(int(raw["start"]), int(raw["stop_inclusive"]) + 1)


def _selection_public(selection: dict[str, Any]) -> dict[str, Any]:
    def clean(candidate):
        if candidate is None:
            return None
        return {k: v for k, v in candidate.items() if k != "vector"}

    return {
        "memory_best": clean(selection.get("memory_best")),
        "diversity_alternate": clean(selection.get("diversity_alternate")),
        "selected": clean(selection.get("selected")),
        "supported_count": len(selection.get("supported") or []),
        "feature_inference_work": int(selection.get("feature_inference_work") or 0),
        "exploration_trigger": bool(selection.get("exploration_trigger")),
        "predicted_regret_ratio": selection.get("predicted_regret_ratio"),
        "regret_threshold": selection.get("regret_threshold"),
        "regret_guard_shadow_reject": bool(selection.get("regret_guard_shadow_reject")),
        "exploration_alternate_exact_executed": bool(
            selection.get("exploration_alternate_exact_executed")
        ),
    }


def preselect_subjects(solver, memory: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Select without consulting exact holdout truth/outcomes/work."""
    target = int(spec["fresh_pre_result_candidate_pool"]["selection_target_per_family"])
    threshold = float(spec["immutable_runtime_sources"]["guard_exact_execution_threshold"])
    selected: list[dict[str, Any]] = []
    fingerprints: set[str] = set()

    for family in spec["fresh_pre_result_candidate_pool"]["families"]:
        family_rows = 0
        for seed in _scan_range(spec, family):
            clauses = base.formula_for(family, seed)
            root = solver.canon_cnf(clauses)
            fp = solver.fingerprint(root)
            if fp in fingerprints:
                continue
            selection = guard.select_root_route(solver, root, memory)
            best = selection.get("memory_best")
            alternate = selection.get("diversity_alternate")
            ratio = selection.get("predicted_regret_ratio")
            if not selection.get("exploration_trigger"):
                continue
            if best is None or alternate is None or ratio is None:
                continue
            if int(best["pivot_id_local"]) == int(alternate["pivot_id_local"]):
                continue
            if float(ratio) <= threshold:
                continue
            if not selection.get("regret_guard_shadow_reject"):
                raise R62Error("R6_2_PRESELECTION_HIGH_REGRET_NOT_SHADOW_REJECTED")
            if selection.get("exploration_alternate_exact_executed"):
                raise R62Error("R6_2_PRESELECTION_HIGH_REGRET_EXACT_EXECUTION_FLAG")
            selected.append(
                {
                    "family": family,
                    "seed": int(seed),
                    "fingerprint": fp,
                    "selection": _selection_public(selection),
                }
            )
            fingerprints.add(fp)
            family_rows += 1
            if family_rows >= target:
                break
        if family_rows < target:
            return []
    return selected


def _route_with_fallback(
    solver,
    clauses,
    profile: dict[str, int],
    pivot: int,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    forced = base.run_forced_root_route(solver, clauses, int(pivot), profile)
    if not forced.get("selected_split_verified"):
        raise R62Error("R6_2_FORCED_ROOT_SPLIT_NOT_VERIFIED")
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


def execute() -> dict[str, Any]:
    spec = load_frozen_spec()
    solver, source = base.r5.load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}

    old_spec = base.load_frozen_spec()
    memory = base.build_frozen_memory(solver, old_spec)
    memory_digest_before = base.stable_hash(memory)
    memory_identity_before = str(memory["memory_state_identity"])

    preselected = preselect_subjects(solver, memory, spec)
    target_total = int(spec["fresh_pre_result_candidate_pool"]["selection_target_per_family"]) * len(
        spec["fresh_pre_result_candidate_pool"]["families"]
    )
    if len(preselected) < target_total:
        return {
            "schema": "janus.trump.slime_r6_2_causal_regret_guard_exposure.frozen_benchmark.result.v1",
            "benchmark_id": spec["benchmark_id"],
            "status": "UNKNOWN_PRE_RESULT_EXPOSURE_INSUFFICIENT",
            "claim": "NO_SCOPED_CAUSAL_R6_2_REGRET_GUARD_WORK_SAVING_ESTABLISHED",
            "freeze_commit": FREEZE_COMMIT,
            "preselected_count": len(preselected),
            "required_preselected_count": target_total,
            "authority": {
                "proof_authority": False,
                "scientific_claim_promotion_authority": False,
                "command_authority": False,
                "external_effect_authority": False
            },
            "scientific_boundary": spec["scientific_boundary"]
        }

    rows: list[dict[str, Any]] = []
    canonical_open = 0
    canonical_decisive = 0
    baseline_decisive = 0
    actual_decisive = 0
    contradictions = 0
    actual_split_failures = 0
    counterfactual_split_failures = 0
    shadow_rejections = 0
    authority_high_regret_exact_exec = 0

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
        "counterfactual_forced_execution": 0,
        "counterfactual_forced_replay": 0,
        "counterfactual_fallback_execution": 0,
        "counterfactual_fallback_replay": 0,
        "counterfactual_execution_including_feature": 0,
        "counterfactual_full": 0
    }

    for chosen in preselected:
        family = str(chosen["family"])
        seed = int(chosen["seed"])
        clauses = base.formula_for(family, seed)
        root = solver.canon_cnf(clauses)
        fp = solver.fingerprint(root)
        if fp != chosen["fingerprint"]:
            raise R62Error("R6_2_PRESELECTED_FINGERPRINT_DRIFT")

        canonical = solver.solve_fail_closed(clauses, **profile)
        if canonical["status"] in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            replay = solver.solve_fail_closed(clauses, **profile)
            if not same_result(canonical, replay):
                raise R62Error("R6_2_CANONICAL_DECISIVE_REPLAY_MISMATCH")
            rows.append({
                "family": family,
                "seed": seed,
                "fingerprint": fp,
                "canonical_status": canonical["status"],
                "causal_exposure": False,
                "pre_result_selection": chosen["selection"]
            })
            continue

        canonical_open += 1
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

        selection = guard.select_root_route(solver, root, memory)
        best = selection.get("memory_best")
        alternate = selection.get("diversity_alternate")
        ratio = selection.get("predicted_regret_ratio")
        inference = int(selection["feature_inference_work"])
        work["feature_inference"] += inference

        if not selection.get("exploration_trigger") or best is None or alternate is None or ratio is None:
            raise R62Error("R6_2_CAUSAL_EXPOSURE_DISAPPEARED_AFTER_EXACT_OPEN")
        if float(ratio) <= float(spec["immutable_runtime_sources"]["guard_exact_execution_threshold"]):
            raise R62Error("R6_2_CAUSAL_EXPOSURE_RATIO_NOT_HIGH")
        if not selection.get("regret_guard_shadow_reject"):
            raise R62Error("R6_2_HIGH_REGRET_NOT_SHADOW_REJECTED")
        shadow_rejections += 1
        if selection.get("exploration_alternate_exact_executed"):
            authority_high_regret_exact_exec += 1

        selected = selection.get("selected")
        if selected is None or int(selected["pivot_id_local"]) != int(best["pivot_id_local"]):
            raise R62Error("R6_2_AUTHORITY_LANE_DID_NOT_SELECT_MEMORY_BEST")

        actual = _route_with_fallback(solver, clauses, profile, int(best["pivot_id_local"]), baseline)
        if not actual["forced"].get("selected_split_verified"):
            actual_split_failures += 1

        # Non-authoritative causal measurement only. Its terminal outcome is never
        # consulted to alter `actual` or the authority-lane final result.
        counterfactual = _route_with_fallback(solver, clauses, profile, int(alternate["pivot_id_local"]), baseline)
        if not counterfactual["forced"].get("selected_split_verified"):
            counterfactual_split_failures += 1

        actual_exec = int(actual["execution_work"]) + inference
        actual_full = int(actual["full_route_work"]) + inference
        cf_exec = int(counterfactual["execution_work"]) + inference
        cf_full = int(counterfactual["full_route_work"]) + inference

        work["actual_forced_execution"] += int(actual["forced"]["execution_work"])
        work["actual_forced_replay"] += int(actual["forced"]["replay_work"])
        if actual["fallback_used"]:
            work["actual_fallback_execution"] += baseline_exec
            work["actual_fallback_replay"] += baseline_replay
        work["actual_execution_including_feature"] += actual_exec
        work["actual_full"] += actual_full

        work["counterfactual_forced_execution"] += int(counterfactual["forced"]["execution_work"])
        work["counterfactual_forced_replay"] += int(counterfactual["forced"]["replay_work"])
        if counterfactual["fallback_used"]:
            work["counterfactual_fallback_execution"] += baseline_exec
            work["counterfactual_fallback_replay"] += baseline_replay
        work["counterfactual_execution_including_feature"] += cf_exec
        work["counterfactual_full"] += cf_full

        if baseline_status in {"SAT", "UNSAT"}:
            if actual["final_status"] != baseline_status:
                contradictions += 1
            else:
                actual_decisive += 1
        elif actual["final_status"] in {"SAT", "UNSAT"}:
            actual_decisive += 1

        cf_status = str(counterfactual["final_status"])
        if baseline_status in {"SAT", "UNSAT"} and cf_status in {"SAT", "UNSAT"} and cf_status != baseline_status:
            raise R62Error("R6_2_COUNTERFACTUAL_EXACT_CONTRADICTS_BASELINE")

        rows.append({
            "family": family,
            "seed": seed,
            "fingerprint": fp,
            "canonical_status": "OPEN",
            "causal_exposure": True,
            "baseline_R5": {
                "status": baseline_status,
                "execution_work": baseline_exec,
                "replay_work": baseline_replay,
                "full_work": baseline_full
            },
            "selection": _selection_public(selection),
            "authority_lane": {
                "route": best["view"],
                "pivot_id_local": int(best["pivot_id_local"]),
                "forced_status": actual["forced"]["status"],
                "final_status": actual["final_status"],
                "fallback_used": actual["fallback_used"],
                "execution_including_feature": actual_exec,
                "full_work": actual_full
            },
            "counterfactual_lane": {
                "authority": False,
                "route": alternate["view"],
                "pivot_id_local": int(alternate["pivot_id_local"]),
                "forced_status": counterfactual["forced"]["status"],
                "final_status_measurement_only": counterfactual["final_status"],
                "fallback_used": counterfactual["fallback_used"],
                "execution_including_feature": cf_exec,
                "full_work": cf_full,
                "execution_regret_avoided": cf_exec - actual_exec,
                "full_regret_avoided": cf_full - actual_full
            }
        })

    memory_digest_after = base.stable_hash(memory)
    memory_identity_after = str(memory["memory_state_identity"])
    memory_frozen = memory_digest_before == memory_digest_after and memory_identity_before == memory_identity_after

    causal_execution_saving = work["counterfactual_execution_including_feature"] - work["actual_execution_including_feature"]
    causal_full_saving = work["counterfactual_full"] - work["actual_full"]

    gate_spec = spec["gate"]
    gate = {
        "minimum_pre_result_selected_formulas_met": len(preselected) >= int(gate_spec["minimum_pre_result_selected_formulas"]),
        "minimum_canonical_OPEN_causal_exposures_met": canonical_open >= int(gate_spec["minimum_canonical_OPEN_causal_exposures"]),
        "all_causal_exposures_have_supported_high_regret_alternate": shadow_rejections == canonical_open,
        "all_authority_lane_high_regret_alternates_shadow_rejected": shadow_rejections == canonical_open,
        "zero_high_regret_alternate_exact_execution_in_authority_lane": authority_high_regret_exact_exec == 0,
        "baseline_R5_decisive_coverage_preserved": actual_decisive >= baseline_decisive,
        "zero_actual_vs_baseline_decisive_contradictions": contradictions == 0,
        "all_actual_selected_root_splits_exact_verified": actual_split_failures == 0,
        "all_counterfactual_root_splits_exact_verified": counterfactual_split_failures == 0,
        "strict_guard_causal_execution_work_saving_after_feature_charge": causal_execution_saving > 0,
        "strict_guard_causal_full_work_saving": causal_full_saving > 0,
        "memory_digest_unchanged": memory_frozen
    }
    status = "PASS" if all(gate.values()) else "FAIL"

    return {
        "schema": "janus.trump.slime_r6_2_causal_regret_guard_exposure.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_benchmark_implementation": FREEZE_COMMIT,
        "immutable_runtime_sources": spec["immutable_runtime_sources"],
        "solver_source": source,
        "pre_result_selection": {
            "selected_count": len(preselected),
            "selection_target_per_family": spec["fresh_pre_result_candidate_pool"]["selection_target_per_family"],
            "families": spec["fresh_pre_result_candidate_pool"]["families"],
            "selected": preselected,
            "uses_exact_solver_result": False,
            "uses_holdout_truth": False,
            "uses_exact_route_work": False
        },
        "memory": {
            "state_identity": memory_identity_before,
            "digest_before_holdout": memory_digest_before,
            "digest_after_holdout": memory_digest_after,
            "frozen_unchanged_during_holdout": memory_frozen,
            "episode_count": memory["episode_count"],
            "decisive_episode_count": memory["decisive_episode_count"],
            "context_bucket_count": len(memory["aggregates"]),
            "calibration_work": memory["calibration_work"]
        },
        "holdout": {
            "preselected_formulas": len(preselected),
            "canonical_decisive": canonical_decisive,
            "canonical_OPEN_causal_exposures": canonical_open,
            "baseline_R5_decisive": baseline_decisive,
            "actual_R6_2_decisive": actual_decisive,
            "contradictions": contradictions,
            "shadow_rejections": shadow_rejections,
            "authority_high_regret_alternate_exact_executions": authority_high_regret_exact_exec,
            "work": {
                **work,
                "causal_execution_regret_avoided_after_feature_charge": causal_execution_saving,
                "causal_full_regret_avoided": causal_full_saving
            },
            "gate": gate,
            "rows": rows
        },
        "physical_execution_cache": {
            "kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION",
            "logical_solver_work_charged_unchanged": True,
            "cache_stats": cache_stats
        },
        "authority": {
            "counterfactual_proof_authority": False,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False
        },
        "scientific_boundary": spec["scientific_boundary"]
    }


def selftest() -> dict[str, Any]:
    spec = load_frozen_spec()
    imm = spec["immutable_runtime_sources"]
    if imm["R6_base_runtime_blob"] != "d043abe6ccfc9ca00ba46999cab990c175abc570":
        raise AssertionError("R6_2_BASE_RUNTIME_BLOB_DRIFT")
    if imm["R6_1_guard_runtime_blob"] != "dbac55a9eb1f507e9f87ad7456cddc52c2562eca":
        raise AssertionError("R6_2_GUARD_RUNTIME_BLOB_DRIFT")
    return {
        "status": "PASS",
        "P_VS_NP": "OPEN",
        "freeze_commit": FREEZE_COMMIT,
        "counterfactual_authority": False,
        "threshold": imm["guard_exact_execution_threshold"]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    result = selftest() if args.selftest else execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.require_pass and result.get("status") != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
