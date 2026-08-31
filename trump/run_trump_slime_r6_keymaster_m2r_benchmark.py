#!/usr/bin/env python3
"""Execute the pre-frozen R6 Keymaster/M2R advisory routing benchmark."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import trump_slime_preelim_compression_r5 as r5
import trump_slime_r6_keymaster_m2r as r6

FREEZE_COMMIT = "ae172de3c4873441545021ef9cba7e5611ec7930"


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
        raise RuntimeError("R6_HOLDOUT_COUNT_DRIFT")
    return rows


def execute() -> dict[str, Any]:
    spec = r6.load_frozen_spec()
    solver, source = r5.load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}

    # Calibration is complete before the first holdout subject is generated.
    memory = r6.build_frozen_memory(solver, spec)
    memory_identity_before = str(memory["memory_state_identity"])
    memory_digest_before = r6.stable_hash(memory)
    holdout = holdout_subjects(spec)

    rows = []
    fingerprints = []
    canonical_open = 0
    canonical_decisive = 0
    baseline_r5_decisive = 0
    final_r6_decisive = 0
    contradictions = 0
    selected_root_split_failures = 0
    nonbaseline_routes = 0
    supported_formulas = 0
    exploration_triggers = 0
    exploration_routes = 0
    direct_fallback_sentinel = 0
    forced_route_open_fallbacks = 0
    extra_decisive_vs_baseline = 0
    per_family = {family: {"formulas": 0, "canonical_OPEN": 0, "baseline_decisive": 0, "R6_final_decisive": 0, "forced_routes": 0} for family in ("CONNECTED_RANDOM_3CNF_V1", "GT6", "GT7", "GT6_WRAPPED", "GT7_WRAPPED")}
    work = {
        "baseline_execution_work": 0,
        "baseline_replay_work": 0,
        "baseline_full_work": 0,
        "R6_forced_route_execution_work": 0,
        "R6_forced_route_replay_work": 0,
        "R6_fallback_execution_work": 0,
        "R6_fallback_replay_work": 0,
        "R6_feature_inference_work": 0,
        "R6_execution_work": 0,
        "R6_full_work": 0,
        "shadow_reference_execution_physically_run": 0,
        "shadow_reference_replay_physically_run": 0,
    }

    for family, seed in holdout:
        per_family[family]["formulas"] += 1
        clauses = r6.formula_for(family, seed)
        root = solver.canon_cnf(clauses)
        fp = solver.fingerprint(root)
        fingerprints.append(fp)
        canonical = solver.solve_fail_closed(clauses, **profile)
        if canonical["status"] in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            replay = solver.solve_fail_closed(clauses, **profile)
            if json.dumps(canonical, sort_keys=True, separators=(",", ":")) != json.dumps(replay, sort_keys=True, separators=(",", ":")):
                raise RuntimeError("R6_CANONICAL_DECISIVE_REPLAY_MISMATCH")
            rows.append({
                "family": family, "seed": seed, "fingerprint": fp,
                "canonical_status": canonical["status"], "canonical_reason": canonical.get("reason"),
                "R6_invoked": False, "baseline_R5": None, "selection": None,
                "forced_route": None, "fallback_used": False,
                "final_status": canonical["status"], "final_reason": canonical.get("reason"),
                "online_work": {"baseline_execution": 0, "baseline_full": 0, "R6_execution": 0, "R6_full": 0}
            })
            continue

        canonical_open += 1
        per_family[family]["canonical_OPEN"] += 1
        # Shadow baseline reference: exact deterministic R5 reference.  Its work
        # is the baseline comparator.  It is not charged to a successful forced
        # R6 route, but it supplies the exact fallback result when fallback is logically required.
        baseline = r5.solve_r5_fallback(solver, clauses, **profile)
        baseline_status = str(baseline["exact_result"]["status"])
        baseline_exec = int(baseline["combined_fallback_work"])
        baseline_replay = int(baseline["replay_work"])
        baseline_full = baseline_exec + baseline_replay
        work["baseline_execution_work"] += baseline_exec
        work["baseline_replay_work"] += baseline_replay
        work["baseline_full_work"] += baseline_full
        work["shadow_reference_execution_physically_run"] += baseline_exec
        work["shadow_reference_replay_physically_run"] += baseline_replay
        if baseline_status in {"SAT", "UNSAT"}:
            baseline_r5_decisive += 1
            per_family[family]["baseline_decisive"] += 1

        selection = r6.select_root_route(solver, root, memory)
        inference_work = int(selection["feature_inference_work"])
        work["R6_feature_inference_work"] += inference_work
        if selection.get("supported"):
            supported_formulas += 1
        if selection.get("exploration_trigger"):
            exploration_triggers += 1

        selected = selection.get("selected")
        forced = None
        fallback_used = False
        r6_exec = 0
        r6_replay = 0
        final_status = baseline_status
        final_reason = baseline["exact_result"].get("reason")
        if selected is None:
            direct_fallback_sentinel += 1
            # No forced route was attempted.  The exact shadow baseline is the
            # logically required unchanged-R5 fallback and its full work is charged.
            fallback_used = True
            r6_exec = baseline_exec
            r6_replay = baseline_replay
            work["R6_fallback_execution_work"] += baseline_exec
            work["R6_fallback_replay_work"] += baseline_replay
        else:
            nonbaseline_routes += 1
            per_family[family]["forced_routes"] += 1
            if selection.get("exploration_trigger") and selection.get("diversity_alternate") is not None and int(selected["pivot_id_local"]) == int(selection["diversity_alternate"]["pivot_id_local"]):
                exploration_routes += 1
            forced = r6.run_forced_root_route(solver, clauses, int(selected["pivot_id_local"]), profile)
            if not forced.get("selected_split_verified"):
                selected_root_split_failures += 1
            r6_exec += int(forced["execution_work"])
            r6_replay += int(forced["replay_work"])
            work["R6_forced_route_execution_work"] += int(forced["execution_work"])
            work["R6_forced_route_replay_work"] += int(forced["replay_work"])
            if forced["status"] in {"SAT", "UNSAT"}:
                final_status = str(forced["status"])
                final_reason = str(forced["reason"])
            else:
                forced_route_open_fallbacks += 1
                fallback_used = True
                # Exact shadow reference is reused as the deterministic fallback
                # result but its full logical cost is charged to R6.
                r6_exec += baseline_exec
                r6_replay += baseline_replay
                work["R6_fallback_execution_work"] += baseline_exec
                work["R6_fallback_replay_work"] += baseline_replay
                final_status = baseline_status
                final_reason = baseline["exact_result"].get("reason")

        if baseline_status in {"SAT", "UNSAT"} and final_status in {"SAT", "UNSAT"} and baseline_status != final_status:
            contradictions += 1
        if baseline_status in {"SAT", "UNSAT"} and final_status not in {"SAT", "UNSAT"}:
            contradictions += 1
        if baseline_status == "OPEN" and final_status in {"SAT", "UNSAT"}:
            extra_decisive_vs_baseline += 1
        if final_status in {"SAT", "UNSAT"}:
            final_r6_decisive += 1
            per_family[family]["R6_final_decisive"] += 1

        r6_full = r6_exec + r6_replay + inference_work
        work["R6_execution_work"] += r6_exec
        work["R6_full_work"] += r6_full
        rows.append({
            "family": family, "seed": seed, "fingerprint": fp,
            "canonical_status": "OPEN", "canonical_reason": canonical.get("reason"),
            "R6_invoked": True,
            "baseline_R5": {"status": baseline_status, "reason": baseline["exact_result"].get("reason"), "execution_work": baseline_exec, "replay_work": baseline_replay, "full_work": baseline_full},
            "selection": {
                "selected": None if selected is None else {k: v for k, v in selected.items() if k != "vector"},
                "supported_count": len(selection.get("supported") or []),
                "top_k": selection.get("top_k"),
                "exploration_trigger": bool(selection.get("exploration_trigger")),
                "memory_stale": bool(selection.get("memory_stale")),
                "feature_inference_work": inference_work
            },
            "forced_route": None if forced is None else {"status": forced["status"], "reason": forced["reason"], "execution_work": forced["execution_work"], "replay_work": forced["replay_work"], "telemetry": forced["telemetry"], "selected_split_verified": forced["selected_split_verified"]},
            "fallback_used": fallback_used,
            "final_status": final_status, "final_reason": final_reason,
            "online_work": {"baseline_execution": baseline_exec, "baseline_full": baseline_full, "R6_execution": r6_exec, "R6_full": r6_full}
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R6_HOLDOUT_FINGERPRINT_COLLISION")
    memory_identity_after = str(memory["memory_state_identity"])
    memory_digest_after = r6.stable_hash(memory)
    memory_frozen = memory_identity_before == memory_identity_after and memory_digest_before == memory_digest_after
    gate_spec = spec["gate"]
    eligible_threshold = canonical_open >= int(gate_spec["minimum_canonical_OPEN_eligible_formulas"])
    coverage_preserved = final_r6_decisive >= baseline_r5_decisive
    nonbaseline_threshold = nonbaseline_routes >= int(gate_spec["minimum_nonbaseline_root_routes_executed"])
    split_clean = selected_root_split_failures == 0
    execution_reduction = work["R6_execution_work"] + work["R6_feature_inference_work"] < work["baseline_execution_work"]
    full_reduction = work["R6_full_work"] < work["baseline_full_work"]
    contradiction_clean = contradictions == 0
    status = "PASS" if all((eligible_threshold, coverage_preserved, nonbaseline_threshold, split_clean, execution_reduction, full_reduction, contradiction_clean, memory_frozen)) else "FAIL"

    calibration_work = int(memory["calibration_work"]["total"])
    return {
        "schema": "janus.trump.slime_r6_keymaster_m2r_root_routing.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R6_implementation": FREEZE_COMMIT,
        "runtime_under_test": spec["runtime_under_test"],
        "keymaster_donors": spec["keymaster_donors"],
        "solver_source": source,
        "profile": profile,
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
            "calibration_episode_digest": memory["calibration_episode_digest"],
            "aggregate_digest": memory["aggregate_digest"],
            "calibration_work": memory["calibration_work"],
            "source_receipts_verified": memory["receipt_source_verification"]
        },
        "holdout": {
            "formula_count": len(rows),
            "canonical_decisive": canonical_decisive,
            "canonical_OPEN": canonical_open,
            "baseline_R5_decisive_on_canonical_OPEN": baseline_r5_decisive,
            "R6_final_decisive_on_canonical_OPEN": final_r6_decisive,
            "extra_decisive_vs_baseline": extra_decisive_vs_baseline,
            "contradictory_exact_decisive_results": contradictions,
            "supported_memory_formulas": supported_formulas,
            "nonbaseline_root_routes_executed": nonbaseline_routes,
            "direct_R5_fallback_sentinel": direct_fallback_sentinel,
            "forced_route_OPEN_then_fallback": forced_route_open_fallbacks,
            "exploration_triggers": exploration_triggers,
            "exploration_routes_executed": exploration_routes,
            "selected_root_split_failures": selected_root_split_failures,
            "per_family": per_family,
            "work": {
                **work,
                "saved_online_execution_work_before_feature_charge": work["baseline_execution_work"] - work["R6_execution_work"],
                "saved_online_execution_work_after_feature_charge": work["baseline_execution_work"] - (work["R6_execution_work"] + work["R6_feature_inference_work"]),
                "saved_online_full_work": work["baseline_full_work"] - work["R6_full_work"],
                "calibration_work_reported_separately": calibration_work,
                "amortized_calibration_plus_R6_full_work": calibration_work + work["R6_full_work"],
                "amortized_speedup_claimed": False
            },
            "gate": {
                "minimum_canonical_OPEN_met": eligible_threshold,
                "decisive_coverage_not_worse": coverage_preserved,
                "minimum_nonbaseline_routes_met": nonbaseline_threshold,
                "selected_root_splits_all_verified": split_clean,
                "strict_online_execution_reduction_after_feature_charge": execution_reduction,
                "strict_online_full_work_reduction": full_reduction,
                "zero_contradictions": contradiction_clean,
                "memory_frozen_during_holdout": memory_frozen
            },
            "rows": rows
        },
        "physical_execution_cache": {"kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION", "cache_stats": cache_stats, "logical_solver_work_charged_unchanged": True, "shadow_baseline_reference_excluded_from_R6_policy_work_unless_used_as_fallback": True},
        "authority": {"proof_authority": False, "scientific_claim_promotion_authority": False, "command_authority": False, "external_effect_authority": False},
        "scientific_boundary": spec["scientific_boundary"]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--memory-output", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.memory_output:
        # Benchmark result already carries the immutable memory identity/digests;
        # export only public frozen memory summary to avoid accidental holdout mutation.
        args.memory_output.write_text(json.dumps(result["memory"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(text)
    return 1 if args.require_pass and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
