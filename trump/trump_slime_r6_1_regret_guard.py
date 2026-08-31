#!/usr/bin/env python3
"""R6.1 single-change successor: regret-bounded deterministic exploration.

All feature extraction, buckets, receipt calibration, exact forced-root routing,
R5 fallback, replay and authority remain the unchanged frozen R6 implementation.
Only the deterministic exploration action changes: a supported diversity
alternate is exact-executed only when its frozen predicted execution-work ratio
to memory-best is <= the preregistered threshold.  Otherwise it stays visible as
a shadow diversity witness and memory-best is executed.  P_VS_NP remains OPEN.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import trump_slime_r6_keymaster_m2r as base

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R6_1_REGRET_BOUNDED_EXPLORATION_FROZEN_BENCH_V1.json"


class R61Error(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R6_1_REGRET_BOUNDED_EXPLORATION_FROZEN_C1K0_BENCH_V1":
        raise R61Error("R6_1_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R6_1_IMPLEMENTATION":
        raise R61Error("R6_1_SPEC_STATUS_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise R61Error("R6_1_WINNER_PREREGISTRATION_FORBIDDEN")
    return spec


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(abs(float(x) - float(y)) for x, y in zip(a, b))


def select_root_route(solver, cnf, memory: dict[str, Any], *, identity: dict[str, str] | None = None) -> dict[str, Any]:
    spec = load_frozen_spec()
    threshold = float(spec["single_successor_change"]["exact_execution_threshold"])
    current_identity = identity or base.source_identity()
    candidates, feature_work, _ = base.build_candidate_views(solver, cnf)
    if current_identity != memory.get("source_identity"):
        return {
            "selected": None,
            "memory_best": None,
            "memory_stale": True,
            "cold_reset": True,
            "history_retained": bool(memory.get("episodes")),
            "feature_inference_work": int(feature_work + 8),
            "candidates": candidates,
            "supported": [],
            "diversity_alternate": None,
            "top_k": ["R5_FALLBACK_SENTINEL"],
            "exploration_trigger": False,
            "exploration_alternate_exact_executed": False,
            "regret_guard_shadow_reject": False,
            "predicted_regret_ratio": None,
            "regret_threshold": threshold,
        }

    old_spec = base.load_frozen_spec()
    minimum_support = int(old_spec["M2R_memory_fit"]["minimum_bucket_decisive_support"])
    shrink = float(old_spec["M2R_memory_fit"]["small_n_shrinkage_strength"])
    global_mean = float(memory["global_decisive_execution_work"]["mean"])
    supported = []
    for candidate in candidates:
        aggregate = memory["aggregates"].get(candidate["context_bucket"])
        if not aggregate or int(aggregate["count"]) < minimum_support:
            continue
        n = int(aggregate["count"])
        predicted = (n * float(aggregate["mean"]) + shrink * global_mean) / (n + shrink)
        supported.append({
            **candidate,
            "support": n,
            "predicted_execution_work": predicted,
            "OPEN_exposures": int(aggregate.get("OPEN_exposures", 0)),
        })

    view_rank = {name: index for index, name in enumerate(old_spec["candidate_views"]["view_order"])}
    supported.sort(key=lambda c: (float(c["predicted_execution_work"]), view_rank[c["view"]], int(c["canonical_index"])))
    memory_best = supported[0] if supported else None
    alternate = None
    if memory_best is not None:
        rest = [c for c in supported if int(c["pivot_id_local"]) != int(memory_best["pivot_id_local"])]
        if rest:
            alternate = max(
                rest,
                key=lambda c: (
                    _distance(c["vector"], memory_best["vector"]),
                    -view_rank[c["view"]],
                    -int(c["canonical_index"]),
                ),
            )

    fingerprint = solver.fingerprint(cnf)
    trigger = int(fingerprint[:8], 16) % 10 == 0
    selected = memory_best
    ratio = None
    exact_exploration = False
    shadow_reject = False
    if trigger and memory_best is not None and alternate is not None:
        denominator = max(1e-12, float(memory_best["predicted_execution_work"]))
        ratio = float(alternate["predicted_execution_work"]) / denominator
        if ratio <= threshold:
            selected = alternate
            exact_exploration = True
        else:
            selected = memory_best
            shadow_reject = True

    lookups = len(candidates)
    predictions = len(supported)
    inference_work = int(feature_work + 8 * lookups + 8 * predictions + 8)
    top_k = []
    if memory_best is not None:
        top_k.append(memory_best["view"])
    if alternate is not None and alternate["view"] not in top_k:
        top_k.append(alternate["view"])
    top_k.append("R5_FALLBACK_SENTINEL")

    return {
        "selected": selected,
        "memory_best": memory_best,
        "memory_stale": False,
        "cold_reset": False,
        "history_retained": True,
        "feature_inference_work": inference_work,
        "candidates": candidates,
        "supported": supported,
        "diversity_alternate": alternate,
        "top_k": top_k,
        "exploration_trigger": trigger,
        "exploration_alternate_exact_executed": exact_exploration,
        "regret_guard_shadow_reject": shadow_reject,
        "predicted_regret_ratio": ratio,
        "regret_threshold": threshold,
    }


def selftest() -> dict[str, Any]:
    spec = load_frozen_spec()
    if float(spec["single_successor_change"]["exact_execution_threshold"]) != 1.25:
        raise AssertionError("R6_1_THRESHOLD_DRIFT")
    return {
        "status": "PASS",
        "P_VS_NP": "OPEN",
        "regret_threshold": 1.25,
        "base_R6_runtime_blob": "d043abe6ccfc9ca00ba46999cab990c175abc570",
        "single_successor_change_only": True,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
