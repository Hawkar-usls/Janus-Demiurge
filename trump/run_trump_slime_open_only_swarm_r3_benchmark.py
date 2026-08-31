#!/usr/bin/env python3
"""Execute the pre-frozen OPEN-only Slime swarm R3 coverage benchmark."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import random
from typing import Any, Sequence

from trump_slime_open_only_swarm_r3 import (
    load_frozen_spec,
    load_pinned_solver,
    load_pinned_v3_donor,
    solve_open_only_swarm,
)

FREEZE_COMMIT = "9b44d7679001ada9a12917225f3a30042bf27ad6"


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
    donor, donor_manifest = load_pinned_v3_donor()
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
    winners: dict[str, int] = {}
    work_totals = {
        "canonical_exact_paid_work": 0,
        "challenger_exact_paid_work": 0,
        "replay_verification_work": 0,
        "slime_generation_ops": 0,
        "pivot_projection_ops": 0,
        "combined_ecology_work": 0,
    }
    open_formula_front_attempts = 0
    open_formula_count = 0

    for seed in spec["holdout"]["seeds"]:
        formula = connected_random_3cnf(
            int(seed), variables=int(gen["variables"]), clauses=int(gen["clauses"])
        )
        fingerprint = solver.fingerprint(solver.canon_cnf(formula))
        fingerprints.append(fingerprint)
        run = solve_open_only_swarm(solver, formula, donor_module=donor, **profile)
        baseline_status = str(run["baseline"]["status"])
        final_status = str(run["final_result"]["status"])
        if baseline_status in {"SAT", "UNSAT"}:
            canonical_decisive += 1
            if final_status != baseline_status or run["winner"] != "CANONICAL" or run["donor_generated"] is not False:
                canonical_preserved = False
        else:
            open_formula_count += 1
            open_formula_front_attempts += int(run["fronts_attempted"])
        if final_status in {"SAT", "UNSAT"}:
            ecology_decisive += 1
        if run["winner"] is not None:
            winners[str(run["winner"])] = winners.get(str(run["winner"]), 0) + 1
        for key in work_totals:
            work_totals[key] += int(run["work"][key])
        rows.append({
            "seed": int(seed),
            "fingerprint": fingerprint,
            "baseline_status": baseline_status,
            "final_status": final_status,
            "winner": run["winner"],
            "donor_generated": bool(run["donor_generated"]),
            "fronts_attempted": int(run["fronts_attempted"]),
            "front_attempts": run["front_attempts"],
            "work": run["work"],
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("HOLDOUT_FINGERPRINT_COLLISION")
    added_decisive = ecology_decisive - canonical_decisive
    decisive_not_worse = ecology_decisive >= canonical_decisive
    strict_gain = ecology_decisive > canonical_decisive
    status = "PASS" if canonical_preserved and decisive_not_worse and strict_gain else "FAIL"

    return {
        "schema": "janus.trump.slime_open_only_swarm_r3.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R3_implementation": FREEZE_COMMIT,
        "winner_preregistered": False,
        "profile": profile,
        "solver_source": source,
        "donor_commit": donor_manifest["pinned_commit"],
        "holdout": {
            "formula_count": len(rows),
            "fingerprints": fingerprints,
            "canonical_decisive_count": canonical_decisive,
            "canonical_open_count": len(rows) - canonical_decisive,
            "ecology_decisive_count": ecology_decisive,
            "ecology_open_count": len(rows) - ecology_decisive,
            "added_decisive_count": added_decisive,
            "canonical_decisive_preserved": canonical_preserved,
            "winner_counts": winners,
            "open_formula_count": open_formula_count,
            "open_formula_front_attempts": open_formula_front_attempts,
            "mean_front_attempts_per_canonical_open": (
                open_formula_front_attempts / open_formula_count if open_formula_count else 0.0
            ),
            "work": work_totals,
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
            "Slime_front_is_proof": False,
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
