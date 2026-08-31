#!/usr/bin/env python3
"""Development-only calibration of current pinned C025/R5 on graph tautologies.

These exact n=6,7,8 subjects are visible development data and MUST NOT be reused
as a later frozen holdout. Graph tautology UNSAT follows structurally: one
Boolean variable orients every unordered pair, triple clauses forbid directed
3-cycles and therefore enforce a finite total order, while every vertex is
required to have a predecessor, contradicting existence of a minimum.
"""
from __future__ import annotations

from itertools import permutations
import json

from looking_for_something_policy import paid_work
from trump_slime_preelim_compression_r5 import load_pinned_solver, solve_canonical_then_r5


def graph_tautology_cnf(n: int) -> list[list[int]]:
    pair_var = {}
    nxt = 1
    for left in range(n):
        for right in range(left + 1, n):
            pair_var[(left, right)] = nxt
            nxt += 1

    def lt(left: int, right: int) -> int:
        return pair_var[(left, right)] if left < right else -pair_var[(right, left)]

    clauses = []
    for vertex in range(n):
        clauses.append([lt(other, vertex) for other in range(n) if other != vertex])
    for first, second, third in permutations(range(n), 3):
        clauses.append([lt(first, second), lt(second, third), lt(third, first)])
    return clauses


def main() -> int:
    solver, source = load_pinned_solver()
    rows = []
    for n in (6, 7, 8):
        clauses = graph_tautology_cnf(n)
        canonical = solver.solve_fail_closed(
            clauses, cap_exponent=1, extension_exponent=0, bounded_resolution_width=3
        )
        ecology = solve_canonical_then_r5(
            solver, clauses, cap_exponent=1, extension_exponent=0, bounded_resolution_width=3
        )
        rr = ecology.get("r5")
        rows.append({
            "n": n,
            "variables": len(solver.vars_of(solver.canon_cnf(clauses))),
            "clauses": len(solver.canon_cnf(clauses)),
            "input_N": solver.input_size_units(solver.canon_cnf(clauses)),
            "structural_truth": "UNSAT",
            "canonical_status": canonical["status"],
            "canonical_reason": canonical.get("reason"),
            "canonical_paid_work": paid_work(canonical),
            "ecology_status": ecology["final_result"]["status"],
            "ecology_reason": ecology["final_result"].get("reason"),
            "winner": ecology.get("winner"),
            "r5_invoked": ecology.get("r5_invoked"),
            "r5_telemetry": None if rr is None else rr.get("telemetry"),
            "r5_replay_status": None if rr is None or rr.get("replay") is None else rr["replay"].get("status"),
            "r5_fallback_work": 0 if rr is None else rr.get("combined_fallback_work", 0),
            "r5_replay_work": 0 if rr is None else rr.get("replay_work", 0)
        })
    result = {
        "schema": "janus.trump.r5.graph_tautology.development_calibration.v1",
        "status": "DEVELOPMENT_ONLY_NOT_FROZEN_EVIDENCE",
        "exact_instances_forbidden_in_future_holdout": ["GT6", "GT7", "GT8"],
        "solver_source": source,
        "P_VS_NP": "OPEN",
        "rows": rows
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
