#!/usr/bin/env python3
"""Execute the pre-frozen Keymaster exact-lookahead R4 OPEN-rescue holdout."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import random
from typing import Any, Sequence

from trump_slime_exact_lookahead_r4 import (
    load_frozen_spec,
    load_pinned_solver,
    solve_canonical_then_r4,
)

FREEZE_COMMIT = "91220a6db0a79f45d788f0bad2a7cda115664ab3"


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
    """Physical-only memoization; returned cert retains original logical work."""
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
    winner_counts: dict[str, int] = {}
    work = {
        "canonical_exact_paid_work": 0,
        "canonical_decisive_replay_work": 0,
        "R4_fallback_exact_paid_work": 0,
        "R4_feature_work": 0,
        "R4_combined_fallback_work": 0,
        "R4_full_fallback_replay_work": 0,
    }
    telemetry_totals = {
        "shortlist_calls": 0,
        "shortlist_size_sum": 0,
        "lookahead_candidates_attempted": 0,
        "verified_candidates": 0,
        "failed_cap_candidates": 0,
        "selected_noncanonical": 0,
        "selected_certificate_ready": 0,
        "roots_only_calls": 0,
    }

    for seed in spec["holdout"]["seeds"]:
        formula = connected_random_3cnf(
            int(seed), variables=int(gen["variables"]), clauses=int(gen["clauses"])
        )
        fp = solver.fingerprint(solver.canon_cnf(formula))
        fingerprints.append(fp)
        run = solve_canonical_then_r4(solver, formula, **profile)
        baseline_status = str(run["baseline"]["status"])
        final_status = str(run["final_result"]["status"])
        if baseline_status in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            if final_status != baseline_status or run["winner"] != "CANONICAL" or run["r4_invoked"] is not False:
                canonical_preserved = False
        if final_status in {"SAT", "UNSAT"}:
            ecology_decisive += 1
        if run["winner"] is not None:
            winner_counts[str(run["winner"])] = winner_counts.get(str(run["winner"]), 0) + 1

        work["canonical_exact_paid_work"] += int(run["canonical_exact_paid_work"])
        work["canonical_decisive_replay_work"] += int(run.get("canonical_replay_work", 0))
        if run["r4_invoked"]:
            rr = run["r4"]
            work["R4_fallback_exact_paid_work"] += int(rr["exact_paid_work"])
            work["R4_feature_work"] += int(rr["feature_work"])
            work["R4_combined_fallback_work"] += int(rr["combined_fallback_work"])
            work["R4_full_fallback_replay_work"] += int(run["r4_replay_verification_work"])
            t = rr["telemetry"]
            for key in telemetry_totals:
                telemetry_totals[key] += int(t[key])

        rows.append({
            "seed": int(seed),
            "fingerprint": fp,
            "baseline_status": baseline_status,
            "baseline_reason": run["baseline"].get("reason"),
            "final_status": final_status,
            "final_reason": run["final_result"].get("reason"),
            "winner": run["winner"],
            "r4_invoked": bool(run["r4_invoked"]),
            "canonical_exact_paid_work": int(run["canonical_exact_paid_work"]),
            "r4": None if not run["r4_invoked"] else {
                "exact_paid_work": int(run["r4"]["exact_paid_work"]),
                "feature_work": int(run["r4"]["feature_work"]),
                "combined_fallback_work": int(run["r4"]["combined_fallback_work"]),
                "telemetry": run["r4"]["telemetry"],
            },
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R4_HOLDOUT_FINGERPRINT_COLLISION")
    added = ecology_decisive - canonical_decisive
    decisive_not_worse = ecology_decisive >= canonical_decisive
    strict_gain = ecology_decisive > canonical_decisive
    status = "PASS" if canonical_preserved and decisive_not_worse and strict_gain else "FAIL"
    shortlist_calls = telemetry_totals["shortlist_calls"]

    return {
        "schema": "janus.trump.slime_exact_lookahead_r4.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R4_implementation": FREEZE_COMMIT,
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
            "winner_counts": winner_counts,
            "work": {
                **work,
                "ecology_execution_plus_full_replay_work": (
                    work["canonical_exact_paid_work"]
                    + work["canonical_decisive_replay_work"]
                    + work["R4_combined_fallback_work"]
                    + work["R4_full_fallback_replay_work"]
                ),
            },
            "lookahead": {
                **telemetry_totals,
                "mean_shortlist_size": (
                    telemetry_totals["shortlist_size_sum"] / shortlist_calls if shortlist_calls else 0.0
                ),
            },
            "gate": {
                "canonical_decisive_preserved": canonical_preserved,
                "ecology_decisive_count_not_worse": decisive_not_worse,
                "strict_capability_gain": strict_gain,
            },
            "rows": rows,
        },
        "physical_execution_cache": {
            "kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION",
            "cache_stats": dict(cache_stats),
            "logical_solver_work_charged_unchanged": True,
            "candidate_metric_changed": False,
        },
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "coverage_boost_implies_speedup": False,
            "finite_holdout_implies_polynomial": False,
            "exact_one_step_best_is_global_optimum": False,
        },
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
