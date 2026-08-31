#!/usr/bin/env python3
"""Frozen R5B UNSAT-heavy gate over the unchanged merged R5 runtime."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path
import random
from typing import Any, Sequence

from looking_for_something_policy import paid_work
from trump_slime_preelim_compression_r5 import load_pinned_solver, solve_canonical_then_r5

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R5B_UNSAT_HEAVY_OR_LIFT_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "6aeb539d786124c413fdb56b153fc00c0cc86443"


def load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R5B_UNSAT_HEAVY_OR_LIFT_FROZEN_C1K0_BENCH_V1":
        raise RuntimeError("R5B_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R5B_IMPLEMENTATION":
        raise RuntimeError("R5B_SPEC_STATUS_DRIFT")
    if spec.get("runtime_under_test", {}).get("R5_runtime_modification_allowed") is not False:
        raise RuntimeError("R5B_RUNTIME_MODIFICATION_MUST_REMAIN_FORBIDDEN")
    return spec


def canon_clause(values: Sequence[int]) -> tuple[int, ...]:
    xs = set(int(v) for v in values)
    if any(-x in xs for x in xs):
        raise ValueError("R5B_GENERATOR_TAUTOLOGY")
    return tuple(sorted(xs, key=lambda z: (abs(z), z < 0)))


def seeded_bijection(seed: int, logical_count: int = 12) -> dict[int, int]:
    ids = list(range(1, logical_count + 1))
    random.Random(int(seed)).shuffle(ids)
    return {logical: ids[logical] for logical in range(logical_count)}


def php_4_into_3(seed: int) -> list[list[int]]:
    mapping = seeded_bijection(seed)
    def v(p: int, h: int) -> int:
        return mapping[p * 3 + h]
    clauses: list[tuple[int, ...]] = []
    for p in range(4):
        clauses.append(canon_clause([v(p, h) for h in range(3)]))
    for h in range(3):
        for p in range(4):
            for q in range(p + 1, 4):
                clauses.append(canon_clause([-v(p, h), -v(q, h)]))
    return [list(c) for c in clauses]


def k4_three_color(seed: int) -> list[list[int]]:
    mapping = seeded_bijection(seed)
    def v(vertex: int, color: int) -> int:
        return mapping[vertex * 3 + color]
    clauses: list[tuple[int, ...]] = []
    for vertex in range(4):
        clauses.append(canon_clause([v(vertex, c) for c in range(3)]))
        for c0 in range(3):
            for c1 in range(c0 + 1, 3):
                clauses.append(canon_clause([-v(vertex, c0), -v(vertex, c1)]))
    for left in range(4):
        for right in range(left + 1, 4):
            for color in range(3):
                clauses.append(canon_clause([-v(left, color), -v(right, color)]))
    return [list(c) for c in clauses]


def formula_satisfied(clauses: Sequence[Sequence[int]], assignment: dict[int, int]) -> bool:
    return all(any(assignment[abs(lit)] == int(lit > 0) for lit in clause) for clause in clauses)


def exact_truth_oracle_12var(clauses: Sequence[Sequence[int]]) -> dict[str, Any]:
    variables = sorted({abs(lit) for clause in clauses for lit in clause})
    if variables != list(range(1, 13)):
        raise RuntimeError("R5B_TRUTH_ORACLE_EXPECTS_VARIABLES_1_TO_12")
    tested = 0
    for bits in itertools.product((0, 1), repeat=12):
        tested += 1
        assignment = {v: bits[v - 1] for v in variables}
        if formula_satisfied(clauses, assignment):
            return {"status": "SAT", "assignments_tested": tested, "witness": assignment}
    return {"status": "UNSAT", "assignments_tested": tested, "witness": None}


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


def build_holdout(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for family, builder in (("PHP_4_INTO_3", php_4_into_3), ("K4_THREE_COLOR", k4_three_color)):
        for seed in spec["formula_families"][family]["seeds"]:
            clauses = builder(int(seed))
            truth = exact_truth_oracle_12var(clauses)
            rows.append({"family": family, "seed": int(seed), "clauses": clauses, "truth": truth})
    if len(rows) != 24:
        raise RuntimeError("R5B_HOLDOUT_COUNT_DRIFT")
    if any(row["truth"]["status"] != "UNSAT" for row in rows):
        raise RuntimeError("R5B_FROZEN_FORMULA_NOT_CERTIFIED_UNSAT")
    return rows


def execute() -> dict[str, Any]:
    spec = load_spec()
    solver, source = load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    holdout = build_holdout(spec)
    profile = {k: int(v) for k, v in spec["profile"].items()}

    rows = []
    fingerprints = []
    canonical_unsat = 0
    canonical_open = 0
    canonical_sat_soundness_failures = 0
    r5_unsat_rescues = 0
    r5_sat_soundness_failures = 0
    contradictory_replays = 0
    canonical_preserved = True
    work = {"canonical_exact_paid_work": 0, "canonical_decisive_replay_work": 0, "R5_combined_fallback_work": 0, "R5_full_replay_work": 0}
    totals = {key: 0 for key in ["unique_factor_dag_nodes", "hash_cons_cache_hits", "split_proposals", "verified_splits", "structural_work", "split_verification_work", "child_c025_exact_paid_work", "max_child_state_units", "node_budget_exhaustions", "depth_budget_exhaustions", "canonical_child_calls"]}

    for item in holdout:
        clauses = item["clauses"]
        cnf = solver.canon_cnf(clauses)
        fp = solver.fingerprint(cnf)
        fingerprints.append(fp)
        run = solve_canonical_then_r5(solver, clauses, **profile)
        baseline = str(run["baseline"]["status"])
        final = str(run["final_result"]["status"])
        if baseline == "UNSAT":
            canonical_unsat += 1
            if final != "UNSAT" or run["winner"] != "CANONICAL" or run["r5_invoked"]:
                canonical_preserved = False
        elif baseline == "OPEN":
            canonical_open += 1
        elif baseline == "SAT":
            canonical_sat_soundness_failures += 1

        work["canonical_exact_paid_work"] += int(run["canonical_exact_paid_work"])
        work["canonical_decisive_replay_work"] += int(run.get("canonical_replay_work", 0))
        r5_summary = None
        if run["r5_invoked"]:
            rr = run["r5"]
            work["R5_combined_fallback_work"] += int(rr["combined_fallback_work"])
            work["R5_full_replay_work"] += int(rr["replay_work"])
            for key in totals:
                value = int(rr["telemetry"][key])
                totals[key] = max(totals[key], value) if key == "max_child_state_units" else totals[key] + value
            if final == "UNSAT":
                r5_unsat_rescues += 1
                replay = rr.get("replay")
                if not replay or replay.get("status") != "UNSAT":
                    contradictory_replays += 1
            elif final == "SAT":
                r5_sat_soundness_failures += 1
            r5_summary = {"status": final, "reason": run["final_result"].get("reason"), "combined_fallback_work": int(rr["combined_fallback_work"]), "replay_work": int(rr["replay_work"]), "telemetry": rr["telemetry"], "receipt_nodes": len(rr["receipt"]["nodes"])}

        rows.append({
            "family": item["family"],
            "seed": item["seed"],
            "fingerprint": fp,
            "truth": item["truth"],
            "canonical_status": baseline,
            "canonical_reason": run["baseline"].get("reason"),
            "final_status": final,
            "final_reason": run["final_result"].get("reason"),
            "winner": run["winner"],
            "r5_invoked": bool(run["r5_invoked"]),
            "r5": r5_summary,
        })

    if len(set(fingerprints)) != len(fingerprints):
        raise RuntimeError("R5B_HOLDOUT_FINGERPRINT_COLLISION")
    all_truth_unsat = all(row["truth"]["status"] == "UNSAT" and row["truth"]["assignments_tested"] == 4096 for row in rows)
    no_sat_soundness_failure = canonical_sat_soundness_failures == 0 and r5_sat_soundness_failures == 0
    strict_unsat_rescue = r5_unsat_rescues > 0
    replay_clean = contradictory_replays == 0
    final_unsat_count = sum(row["final_status"] == "UNSAT" for row in rows)
    not_worse = final_unsat_count >= canonical_unsat
    status = "PASS" if all_truth_unsat and no_sat_soundness_failure and canonical_preserved and strict_unsat_rescue and replay_clean and not_worse else "FAIL"

    return {
        "schema": "janus.trump.slime_r5b_unsat_heavy_or_lift.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R5B_implementation": FREEZE_COMMIT,
        "runtime_under_test": spec["runtime_under_test"],
        "solver_source": source,
        "profile": profile,
        "holdout": {
            "formula_count": 24,
            "truth_certified_UNSAT": sum(row["truth"]["status"] == "UNSAT" for row in rows),
            "truth_oracle_assignments_per_formula": 4096,
            "canonical_UNSAT": canonical_unsat,
            "canonical_OPEN": canonical_open,
            "canonical_SAT_soundness_failures": canonical_sat_soundness_failures,
            "R5_UNSAT_rescues": r5_unsat_rescues,
            "R5_SAT_soundness_failures": r5_sat_soundness_failures,
            "final_UNSAT": final_unsat_count,
            "final_OPEN": sum(row["final_status"] == "OPEN" for row in rows),
            "contradictory_exact_decisive_replays": contradictory_replays,
            "canonical_decisive_preserved": canonical_preserved,
            "factor_dag": totals,
            "work": {**work, "ecology_execution_plus_full_replay_work": sum(work.values())},
            "gate": {
                "all_truth_certificates_pass": all_truth_unsat,
                "no_SAT_soundness_failure": no_sat_soundness_failure,
                "canonical_decisive_preserved": canonical_preserved,
                "strict_UNSAT_rescue": strict_unsat_rescue,
                "decisive_replay_clean": replay_clean,
                "UNSAT_count_not_worse": not_worse
            },
            "rows": rows
        },
        "physical_execution_cache": {"kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION", "cache_stats": cache_stats, "logical_solver_work_charged_unchanged": True},
        "scientific_boundary": spec["scientific_boundary"]
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
    return 1 if args.require_pass and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
