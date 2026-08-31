#!/usr/bin/env python3
"""Execute the pre-frozen R5 hash-consed pre-elimination compression holdout."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import random
from typing import Any, Sequence

from trump_slime_preelim_compression_r5 import (
    load_frozen_spec,
    load_pinned_solver,
    solve_canonical_then_r5,
)

FREEZE_COMMIT = "28b11782a010e58ae11811915ac1ea78023050d5"


def canonical_clause(values: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted((int(v) for v in values), key=lambda z: (abs(z), z < 0)))


def connected_random_3cnf(seed: int, *, variables: int, clauses: int) -> list[list[int]]:
    rng = random.Random(int(seed))
    out: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()

    def add_support(support: Sequence[int]) -> None:
        lits = [v if rng.getrandbits(1) else -v for v in support]
        clause = canonical_clause(lits)
        if clause not in seen:
            seen.add(clause)
            out.append(clause)

    for i in range(1, variables - 1):
        add_support((i, i + 1, i + 2))
    while len(out) < clauses:
        add_support(rng.sample(range(1, variables + 1), 3))
    return [list(c) for c in out]


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


def execute() -> dict[str, Any]:
    spec = load_frozen_spec()
    solver, source = load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    gen = spec["formula_generator"]
    profile = {
        "cap_exponent": int(spec["profile"]["cap_exponent"]),
        "extension_exponent": int(spec["profile"]["extension_exponent"]),
        "bounded_resolution_width": int(spec["profile"]["bounded_resolution_width"]),
    }
    rows = []
    fingerprints = []
    canonical_decisive = 0
    ecology_decisive = 0
    canonical_preserved = True
    contradictory_replays = 0
    winner_counts: dict[str, int] = {}
    work = {
        "canonical_exact_paid_work": 0,
        "canonical_decisive_replay_work": 0,
        "R5_combined_fallback_work": 0,
        "R5_full_replay_work": 0,
    }
    telemetry_keys = [
        "unique_factor_dag_nodes",
        "hash_cons_cache_hits",
        "split_proposals",
        "verified_splits",
        "structural_work",
        "split_verification_work",
        "child_c025_exact_paid_work",
        "max_child_state_units",
        "node_budget_exhaustions",
        "depth_budget_exhaustions",
        "canonical_child_calls",
    ]
    telemetry_totals = {key: 0 for key in telemetry_keys}
    telemetry_totals["max_child_state_units"] = 0
    decisive_r5_rows = 0

    for seed in spec["holdout"]["seeds"]:
        formula = connected_random_3cnf(
            int(seed), variables=int(gen["variables"]), clauses=int(gen["clauses"])
        )
        fp = solver.fingerprint(solver.canon_cnf(formula))
        fingerprints.append(fp)
        run = solve_canonical_then_r5(solver, formula, **profile)
        baseline_status = str(run["baseline"]["status"])
        final_status = str(run["final_result"]["status"])
        if baseline_status in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            if final_status != baseline_status or run["winner"] != "CANONICAL" or run["r5_invoked"] is not False:
                canonical_preserved = False
        if final_status in {"SAT", "UNSAT"}:
            ecology_decisive += 1
        if run["winner"] is not None:
            winner_counts[str(run["winner"])] = winner_counts.get(str(run["winner"]), 0) + 1

        work["canonical_exact_paid_work"] += int(run["canonical_exact_paid_work"])
        work["canonical_decisive_replay_work"] += int(run.get("canonical_replay_work", 0))
        r5_summary = None
        if run["r5_invoked"]:
            rr = run["r5"]
            work["R5_combined_fallback_work"] += int(rr["combined_fallback_work"])
            work["R5_full_replay_work"] += int(rr["replay_work"])
            t = rr["telemetry"]
            for key in telemetry_keys:
                if key == "max_child_state_units":
                    telemetry_totals[key] = max(telemetry_totals[key], int(t[key]))
                else:
                    telemetry_totals[key] += int(t[key])
            if final_status in {"SAT", "UNSAT"}:
                decisive_r5_rows += 1
                replay = rr.get("replay")
                if not replay or str(replay.get("status")) != final_status:
                    contradictory_replays += 1
            r5_summary = {
                "status": final_status,
                "reason": run["final_result"].get("reason"),
                "combined_fallback_work": int(rr["combined_fallback_work"]),
                "replay_work": int(rr["replay_work"]),
                "telemetry": t,
                "root_receipt_node_count": len(rr["receipt"]["nodes"]),
            }

        rows.append({
            "seed": int(seed),
            "fingerprint": fp,
            "baseline_status": baseline_status,
            "baseline_reason": run["baseline"].get("reason"),
            "final_status": final_status,
            "final_reason": run["final_result"].get("reason"),
            "winner": run["winner"],
            "r5_invoked": bool(run["r5_invoked"]),
            "canonical_exact_paid_work": int(run["canonical_exact_paid_work"]),
            "r5": r5_summary,
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R5_HOLDOUT_FINGERPRINT_COLLISION")
    added = ecology_decisive - canonical_decisive
    decisive_not_worse = ecology_decisive >= canonical_decisive
    strict_gain = ecology_decisive > canonical_decisive
    replay_clean = contradictory_replays == 0
    status = "PASS" if canonical_preserved and decisive_not_worse and strict_gain and replay_clean else "FAIL"

    return {
        "schema": "janus.trump.slime_preelim_compression_r5.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R5_implementation": FREEZE_COMMIT,
        "winner_preregistered": False,
        "profile": profile,
        "solver_source": source,
        "holdout": {
            "formula_count": len(rows),
            "fingerprints": fingerprints,
            "canonical_decisive_count": canonical_decisive,
            "canonical_open_count": len(rows) - canonical_decisive,
            "ecology_decisive_count": ecology_decisive,
            "ecology_open_count": len(rows) - ecology_decisive,
            "added_decisive_count": added,
            "canonical_decisive_preserved": canonical_preserved,
            "contradictory_exact_decisive_replays": contradictory_replays,
            "R5_decisive_rows": decisive_r5_rows,
            "winner_counts": winner_counts,
            "work": {
                **work,
                "ecology_execution_plus_full_replay_work": (
                    work["canonical_exact_paid_work"]
                    + work["canonical_decisive_replay_work"]
                    + work["R5_combined_fallback_work"]
                    + work["R5_full_replay_work"]
                ),
            },
            "factor_dag": telemetry_totals,
            "gate": {
                "canonical_decisive_preserved": canonical_preserved,
                "ecology_decisive_count_not_worse": decisive_not_worse,
                "strict_capability_gain": strict_gain,
                "decisive_replay_clean": replay_clean,
            },
            "rows": rows,
        },
        "physical_execution_cache": {
            "kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION",
            "cache_stats": dict(cache_stats),
            "logical_solver_work_charged_unchanged": true,
            "candidate_metric_changed": false
        },
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": false,
            "finite_holdout_implies_polynomial_time_SAT": false,
            "bounded_factor_DAG_is_complete": false,
            "coverage_boost_implies_speedup": false
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path)
    ap.add_argument("--require-pass", action="store_true")
    args = ap.parse_args()
    result = execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.require_pass and result["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
