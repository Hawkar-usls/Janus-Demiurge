#!/usr/bin/env python3
"""Development-only R5A2 collision calibration on burned GT6/GT7 instances.

The exact GT6/GT7 canonical numberings were already exposed by PR #60 and are
not future frozen evidence.  This microscope asks only whether wrapping each GT
clause C with both (s OR C) and (-s OR C) creates a root that remains canonical
OPEN while the unchanged R5 runtime reaches an exact repeated residual.
"""
from __future__ import annotations

from itertools import permutations
import json

from trump_slime_preelim_compression_r5 import branch_pressure, load_pinned_solver, solve_canonical_then_r5


def graph_tautology_cnf(n: int) -> list[list[int]]:
    pair_var = {}
    nxt = 2  # reserve selector 1
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


def selector_wrap(base: list[list[int]]) -> list[list[int]]:
    root = []
    for clause in base:
        root.append([1, *clause])
        root.append([-1, *clause])
    return root


def main() -> int:
    solver, source = load_pinned_solver()
    profile = {"cap_exponent": 1, "extension_exponent": 0, "bounded_resolution_width": 3}
    rows = []
    for n in (6, 7):
        base = solver.canon_cnf(graph_tautology_cnf(n))
        root = solver.canon_cnf(selector_wrap([list(c) for c in base]))
        c0 = solver.restrict(root, 1, 0)
        c1 = solver.restrict(root, 1, 1)
        collision = c0 == c1 == base
        pivot, p0, p1, pressure = branch_pressure(solver, root)
        canonical = solver.solve_fail_closed([list(c) for c in root], **profile)
        ecology = solve_canonical_then_r5(solver, [list(c) for c in root], **profile)
        rr = ecology.get("r5")
        rows.append({
            "n": n,
            "base_variables": len(solver.vars_of(base)),
            "base_clauses": len(base),
            "root_variables": len(solver.vars_of(root)),
            "root_clauses": len(root),
            "root_N": solver.input_size_units(root),
            "exact_selector_collision": collision,
            "child_fingerprint": solver.fingerprint(base),
            "branch_pressure_selected_pivot": pivot,
            "branch_pressure_selector_selected": pivot == 1,
            "branch_pressure_children_match_collision": p0 == c0 and p1 == c1,
            "branch_pressure_selected_score": pressure.get("selected_score"),
            "canonical_status": canonical.get("status"),
            "canonical_reason": canonical.get("reason"),
            "ecology_status": ecology["final_result"].get("status"),
            "ecology_reason": ecology["final_result"].get("reason"),
            "winner": ecology.get("winner"),
            "r5_invoked": ecology.get("r5_invoked"),
            "r5_replay_status": None if rr is None or rr.get("replay") is None else rr["replay"].get("status"),
            "r5_telemetry": None if rr is None else rr.get("telemetry")
        })
    print(json.dumps({
        "schema": "janus.trump.r5a2.gt_collision.development_calibration.v1",
        "status": "DEVELOPMENT_ONLY_NOT_FROZEN_EVIDENCE",
        "burned_instances": ["WRAPPED_GT6_CANONICAL_NUMBERING", "WRAPPED_GT7_CANONICAL_NUMBERING"],
        "runtime_source": source,
        "P_VS_NP": "OPEN",
        "rows": rows
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
