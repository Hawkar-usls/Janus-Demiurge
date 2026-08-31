#!/usr/bin/env python3
"""Frozen R6.1 benchmark: unchanged R6 memory/routing plus regret guard only."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import trump_slime_r6_keymaster_m2r as base
import trump_slime_r6_1_regret_guard as guard

FREEZE_COMMIT = "9a9cc0a53d7aaeea351630644d45dbdb900a0020"


def install_pure_resolution_cache(solver) -> dict[str, int]:
    original = solver.bounded_width_resolution_refutes
    cache = {}
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


def holdout_subjects(spec: dict[str, Any]) -> list[tuple[str, int]]:
    rows = []
    for family in ("CONNECTED_RANDOM_3CNF_V1", "GT6", "GT7", "GT6_WRAPPED", "GT7_WRAPPED"):
        rows.extend((family, int(seed)) for seed in spec["fresh_holdout"][family])
    if len(rows) != int(spec["fresh_holdout"]["formula_count"]):
        raise RuntimeError("R6_1_HOLDOUT_COUNT_DRIFT")
    return rows


def same_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(right, sort_keys=True, separators=(",", ":"))


def execute() -> dict[str, Any]:
    spec = guard.load_frozen_spec()
    solver, source = base.r5.load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {"cap_exponent": 1, "extension_exponent": 0, "bounded_resolution_width": 3}

    # Single-change causal boundary: build exactly the old R6 memory from the
    # unchanged old corrected R6 spec and finalized prior receipts.
    old_spec = base.load_frozen_spec()
    memory = base.build_frozen_memory(solver, old_spec)
    memory_identity_before = str(memory["memory_state_identity"])
    memory_digest_before = base.stable_hash(memory)

    rows = []
    fingerprints = []
    canonical_decisive = 0
    canonical_open = 0
    baseline_decisive = 0
    final_decisive = 0
    contradictions = 0
    selected_split_failures = 0
    supported_formulas = 0
    nonbaseline_routes = 0
    direct_fallback = 0
    forced_open_fallback = 0
    exploration_triggers = 0
    exploration_with_supported_alternate = 0
    exploration_exact_executed = 0
    high_regret_triggered = 0
    high_regret_shadow_rejected = 0
    invalid_high_regret_exact_execution = 0
    low_regret_exact_exploration = 0

    per_family = {
        family: {"formulas": 0, "canonical_OPEN": 0, "baseline_decisive": 0, "R6_1_final_decisive": 0, "forced_routes": 0, "shadow_rejections": 0}
        for family in ("CONNECTED_RANDOM_3CNF_V1", "GT6", "GT7", "GT6_WRAPPED", "GT7_WRAPPED")
    }
    work = {
        "baseline_execution_work": 0,
        "baseline_replay_work": 0,
        "baseline_full_work": 0,
        "R6_1_forced_route_execution_work": 0,
        "R6_1_forced_route_replay_work": 0,
        "R6_1_fallback_execution_work": 0,
        "R6_1_fallback_replay_work": 0,
        "R6_1_feature_inference_work": 0,
        "R6_1_execution_work": 0,
        "R6_1_full_work": 0,
    }

    for family, seed in holdout_subjects(spec):
        per_family[family]["formulas"] += 1
        clauses = base.formula_for(family, seed)
        root = solver.canon_cnf(clauses)
        fp = solver.fingerprint(root)
        fingerprints.append(fp)
        canonical = solver.solve_fail_closed(clauses, **profile)
        if canonical["status"] in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            replay = solver.solve_fail_closed(clauses, **profile)
            if not same_result(canonical, replay):
                raise RuntimeError("R6_1_CANONICAL_DECISIVE_REPLAY_MISMATCH")
            rows.append({
                "family": family, "seed": seed, "fingerprint": fp,
                "canonical_status": canonical["status"], "R6_1_invoked": False,
                "final_status": canonical["status"], "selection": None,
                "baseline_R5": None, "forced_route": None, "fallback_used": False,
            })
            continue

        canonical_open += 1
        per_family[family]["canonical_OPEN"] += 1
        baseline = base.r5.solve_r5_fallback(solver, clauses, **profile)
        baseline_status = str(baseline["exact_result"]["status"])
        baseline_exec = int(baseline["combined_fallback_work"])
        baseline_replay = int(baseline["replay_work"])
        baseline_full = baseline_exec + baseline_replay
        work["baseline_execution_work"] += baseline_exec
        work["baseline_replay_work"] += baseline_replay
        work["baseline_full_work"] += baseline_full
        if baseline_status in {"SAT", "UNSAT"}:
            baseline_decisive += 1
            per_family[family]["baseline_decisive"] += 1

        selection = guard.select_root_route(solver, root, memory)
        inference = int(selection["feature_inference_work"])
        work["R6_1_feature_inference_work"] += inference
        supported = selection.get("supported") or []
        if supported:
            supported_formulas += 1
        if selection.get("exploration_trigger"):
            exploration_triggers += 1
        alternate = selection.get("diversity_alternate")
        ratio = selection.get("predicted_regret_ratio")
        if selection.get("exploration_trigger") and alternate is not None:
            exploration_with_supported_alternate += 1
            if ratio is None:
                raise RuntimeError("R6_1_TRIGGERED_ALTERNATE_MISSING_REGRET_RATIO")
            if float(ratio) > 1.25:
                high_regret_triggered += 1
                if selection.get("regret_guard_shadow_reject"):
                    high_regret_shadow_rejected += 1
                    per_family[family]["shadow_rejections"] += 1
                if selection.get("exploration_alternate_exact_executed"):
                    invalid_high_regret_exact_execution += 1
            else:
                if selection.get("exploration_alternate_exact_executed"):
                    low_regret_exact_exploration += 1

        selected = selection.get("selected")
        forced = None
        fallback_used = False
        r61_exec = 0
        r61_replay = 0
        final_status = baseline_status
        final_reason = baseline["exact_result"].get("reason")

        if selected is None:
            direct_fallback += 1
            fallback_used = True
            r61_exec = baseline_exec
            r61_replay = baseline_replay
            work["R6_1_fallback_execution_work"] += baseline_exec
            work["R6_1_fallback_replay_work"] += baseline_replay
        else:
            nonbaseline_routes += 1
            per_family[family]["forced_routes"] += 1
            if selection.get("exploration_alternate_exact_executed"):
                exploration_exact_executed += 1
            forced = base.run_forced_root_route(solver, clauses, int(selected["pivot_id_local"]), profile)
            if not forced.get("selected_split_verified"):
                selected_split_failures += 1
            r61_exec += int(forced["execution_work"])
            r61_replay += int(forced["replay_work"])
            work["R6_1_forced_route_execution_work"] += int(forced["execution_work"])
            work["R6_1_forced_route_replay_work"] += int(forced["replay_work"])
            if forced["status"] in {"SAT", "UNSAT"}:
                final_status = str(forced["status"])
                final_reason = str(forced["reason"])
            else:
                forced_open_fallback += 1
                fallback_used = True
                r61_exec += baseline_exec
                r61_replay += baseline_replay
                work["R6_1_fallback_execution_work"] += baseline_exec
                work["R6_1_fallback_replay_work"] += baseline_replay
                final_status = baseline_status
                final_reason = baseline["exact_result"].get("reason")

        if baseline_status in {"SAT", "UNSAT"}:
            if final_status not in {"SAT", "UNSAT"} or final_status != baseline_status:
                contradictions += 1
        if final_status in {"SAT", "UNSAT"}:
            final_decisive += 1
            per_family[family]["R6_1_final_decisive"] += 1

        r61_full = r61_exec + r61_replay + inference
        work["R6_1_execution_work"] += r61_exec
        work["R6_1_full_work"] += r61_full
        selected_public = None if selected is None else {k: v for k, v in selected.items() if k != "vector"}
        best = selection.get("memory_best")
        alt = selection.get("diversity_alternate")
        rows.append({
            "family": family, "seed": seed, "fingerprint": fp,
            "canonical_status": "OPEN",
            "baseline_R5": {"status": baseline_status, "execution_work": baseline_exec, "replay_work": baseline_replay, "full_work": baseline_full},
            "selection": {
                "selected": selected_public,
                "memory_best": None if best is None else {k: v for k, v in best.items() if k != "vector"},
                "diversity_alternate": None if alt is None else {k: v for k, v in alt.items() if k != "vector"},
                "supported_count": len(supported),
                "exploration_trigger": bool(selection.get("exploration_trigger")),
                "predicted_regret_ratio": ratio,
                "regret_threshold": selection.get("regret_threshold"),
                "regret_guard_shadow_reject": bool(selection.get("regret_guard_shadow_reject")),
                "exploration_alternate_exact_executed": bool(selection.get("exploration_alternate_exact_executed")),
                "feature_inference_work": inference,
            },
            "forced_route": None if forced is None else {"status": forced["status"], "execution_work": forced["execution_work"], "replay_work": forced["replay_work"], "selected_split_verified": forced["selected_split_verified"]},
            "fallback_used": fallback_used,
            "final_status": final_status, "final_reason": final_reason,
            "online_work": {"R6_1_execution": r61_exec, "R6_1_full": r61_full},
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R6_1_HOLDOUT_FINGERPRINT_COLLISION")
    memory_identity_after = str(memory["memory_state_identity"])
    memory_digest_after = base.stable_hash(memory)
    memory_frozen = memory_identity_before == memory_identity_after and memory_digest_before == memory_digest_after

    after_feature_execution = work["R6_1_execution_work"] + work["R6_1_feature_inference_work"]
    saved_execution = work["baseline_execution_work"] - after_feature_execution
    saved_full = work["baseline_full_work"] - work["R6_1_full_work"]
    gate_spec = spec["gate"]
    gate = {
        "minimum_canonical_OPEN_met": canonical_open >= int(gate_spec["minimum_canonical_OPEN_eligible_formulas"]),
        "decisive_coverage_not_worse": final_decisive >= baseline_decisive,
        "zero_contradictions": contradictions == 0,
        "minimum_nonbaseline_routes_met": nonbaseline_routes >= int(gate_spec["minimum_nonbaseline_root_routes_executed"]),
        "minimum_exploration_triggers_met": exploration_triggers >= int(gate_spec["minimum_exploration_triggers"]),
        "all_high_regret_triggered_alternates_shadow_blocked": high_regret_shadow_rejected == high_regret_triggered,
        "no_high_regret_alternate_exact_executed": invalid_high_regret_exact_execution == 0,
        "strict_online_execution_reduction_after_feature_charge": saved_execution > 0,
        "strict_online_full_work_reduction": saved_full > 0,
        "selected_root_splits_all_verified": selected_split_failures == 0,
        "memory_frozen_during_holdout": memory_frozen,
    }
    status = "PASS" if all(gate.values()) else "FAIL"

    return {
        "schema": "janus.trump.slime_r6_1_regret_bounded_exploration.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R6_1_implementation": FREEZE_COMMIT,
        "single_successor_change": spec["single_successor_change"],
        "base_R6_code_provenance": {"failed_R6_head": "eec57982582037cd70dc10460acb4d66b16836a6", "base_runtime_blob": "d043abe6ccfc9ca00ba46999cab990c175abc570", "base_spec_blob": "b019f126feec611028bb83ec54a3f04a00a84929"},
        "solver_source": source,
        "memory": {
            "state_identity": memory_identity_before,
            "digest_before_holdout": memory_digest_before,
            "digest_after_holdout": memory_digest_after,
            "frozen_unchanged_during_holdout": memory_frozen,
            "calibration_subject_count": memory["calibration_subject_count"],
            "calibration_canonical_OPEN_subjects": memory["calibration_canonical_OPEN_subjects"],
            "episode_count": memory["episode_count"],
            "decisive_episode_count": memory["decisive_episode_count"],
            "OPEN_exposure_count": memory["OPEN_exposure_count"],
            "context_bucket_count": len(memory["aggregates"]),
            "calibration_work": memory["calibration_work"],
        },
        "holdout": {
            "formula_count": len(rows),
            "canonical_decisive": canonical_decisive,
            "canonical_OPEN": canonical_open,
            "baseline_R5_decisive": baseline_decisive,
            "R6_1_final_decisive": final_decisive,
            "contradictions": contradictions,
            "supported_memory_formulas": supported_formulas,
            "nonbaseline_root_routes": nonbaseline_routes,
            "direct_R5_fallback": direct_fallback,
            "forced_OPEN_fallback": forced_open_fallback,
            "exploration": {
                "triggers": exploration_triggers,
                "triggers_with_supported_alternate": exploration_with_supported_alternate,
                "exact_alternate_executed_under_guard": exploration_exact_executed,
                "low_regret_exact_exploration": low_regret_exact_exploration,
                "high_regret_triggered": high_regret_triggered,
                "high_regret_shadow_rejected": high_regret_shadow_rejected,
                "invalid_high_regret_exact_execution": invalid_high_regret_exact_execution,
            },
            "per_family": per_family,
            "work": {
                **work,
                "R6_1_execution_plus_feature_inference": after_feature_execution,
                "saved_online_execution_after_feature_charge": saved_execution,
                "saved_online_full_work": saved_full,
                "saved_execution_fraction": saved_execution / work["baseline_execution_work"] if work["baseline_execution_work"] else 0.0,
                "saved_full_fraction": saved_full / work["baseline_full_work"] if work["baseline_full_work"] else 0.0,
                "calibration_work_reported_separately": int(memory["calibration_work"]["total"]),
                "amortized_speedup_claimed": False,
            },
            "gate": gate,
            "rows": rows,
        },
        "physical_execution_cache": {"kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION", "cache_stats": cache_stats, "logical_solver_work_charged_unchanged": True},
        "authority": {"proof_authority": False, "scientific_claim_promotion_authority": False, "command_authority": False, "external_effect_authority": False},
        "scientific_boundary": spec["scientific_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if args.require_pass and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
