#!/usr/bin/env python3
"""Frozen R5A collision-rich hash-cons benefit gate over unchanged R5."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from pathlib import Path
import random
from typing import Any, Sequence

from looking_for_something_policy import paid_work
from trump_candidate import canonical_bytes
from trump_slime_preelim_compression_r5 import branch_pressure, load_pinned_solver, solve_canonical_then_r5

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R5A_COLLISION_RICH_HASH_CONS_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "4c085079bbab3c497387c9ad8a550988d4b51b0e"


def load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R5A_COLLISION_RICH_HASH_CONS_FROZEN_C1K0_BENCH_V1":
        raise RuntimeError("R5A_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R5A_IMPLEMENTATION":
        raise RuntimeError("R5A_SPEC_STATUS_DRIFT")
    if spec.get("runtime_under_test", {}).get("R5_runtime_modification_allowed") is not False:
        raise RuntimeError("R5A_RUNTIME_MODIFICATION_MUST_REMAIN_FORBIDDEN")
    return spec


def canon_clause(values: Sequence[int]) -> tuple[int, ...]:
    xs = set(int(v) for v in values)
    if any(-x in xs for x in xs):
        raise ValueError("R5A_GENERATOR_TAUTOLOGY")
    return tuple(sorted(xs, key=lambda z: (abs(z), z < 0)))


def complete_blocker(triple: Sequence[int]) -> list[tuple[int, ...]]:
    if len(tuple(triple)) != 3:
        raise ValueError("R5A_BLOCKER_REQUIRES_TRIPLE")
    a, b, c = map(int, triple)
    rows = []
    for signs in itertools.product((-1, 1), repeat=3):
        rows.append(canon_clause([signs[0] * a, signs[1] * b, signs[2] * c]))
    return rows


def collision_formula(seed: int) -> dict[str, Any]:
    ids = list(range(2, 14))
    random.Random(int(seed)).shuffle(ids)
    triples = [tuple(ids[i:i + 3]) for i in range(0, 12, 3)]
    base: list[tuple[int, ...]] = []
    for triple in triples:
        base.extend(complete_blocker(triple))
    root: list[tuple[int, ...]] = []
    for clause in base:
        root.append(canon_clause((1, *clause)))
        root.append(canon_clause((-1, *clause)))
    return {
        "triples": [list(t) for t in triples],
        "base_child": [list(c) for c in base],
        "root": [list(c) for c in root],
    }


def formula_satisfied(clauses: Sequence[Sequence[int]], assignment: dict[int, int]) -> bool:
    return all(any(assignment[abs(lit)] == int(lit > 0) for lit in clause) for clause in clauses)


def exact_truth_oracle_13var(clauses: Sequence[Sequence[int]]) -> dict[str, Any]:
    variables = sorted({abs(lit) for clause in clauses for lit in clause})
    if variables != list(range(1, 14)):
        raise RuntimeError("R5A_TRUTH_ORACLE_EXPECTS_VARIABLES_1_TO_13")
    tested = 0
    for bits in itertools.product((0, 1), repeat=13):
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


def execute() -> dict[str, Any]:
    spec = load_spec()
    solver, source = load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}
    rows = []
    fingerprints = []
    precondition_failures = 0
    soundness_failures = 0
    replay_failures = 0
    formulas_with_hash_hit = 0
    actual_child_calls = 0
    no_share_child_calls = 0
    actual_child_work = 0
    no_share_child_work = 0
    total_hash_hits = 0
    total_verified_splits = 0
    max_child_units = 0
    total_actual_r5_work = 0
    total_actual_replay_work = 0

    for seed in spec["holdout"]["seeds"]:
        generated = collision_formula(int(seed))
        root = solver.canon_cnf(generated["root"])
        base = solver.canon_cnf(generated["base_child"])
        fp = solver.fingerprint(root)
        fingerprints.append(fp)
        truth = exact_truth_oracle_13var(generated["root"])
        child0 = solver.restrict(root, 1, 0)
        child1 = solver.restrict(root, 1, 1)
        collision_ok = child0 == child1 == base and solver.fingerprint(child0) == solver.fingerprint(child1)

        pivot, proposed0, proposed1, pressure = branch_pressure(solver, root)
        selector_ok = pivot == 1 and proposed0 == child0 and proposed1 == child1

        canonical = solver.solve_fail_closed(generated["root"], **profile)
        canonical_open = canonical.get("status") == "OPEN"

        child_exact_1 = solver.solve_fail_closed(generated["base_child"], **profile)
        child_exact_2 = solver.solve_fail_closed(generated["base_child"], **profile)
        child_replay_identical = canonical_bytes(child_exact_1) == canonical_bytes(child_exact_2)
        child_unsat = child_exact_1.get("status") == "UNSAT" and child_exact_2.get("status") == "UNSAT"
        no_share_calls_here = 2
        no_share_work_here = int(paid_work(child_exact_1) + paid_work(child_exact_2))

        preconditions_ok = (
            truth.get("status") == "UNSAT"
            and truth.get("assignments_tested") == 8192
            and collision_ok
            and selector_ok
            and canonical_open
            and child_unsat
            and child_replay_identical
        )
        if not preconditions_ok:
            precondition_failures += 1

        run = solve_canonical_then_r5(solver, generated["root"], **profile)
        final = str(run["final_result"]["status"])
        rr = run.get("r5") if run.get("r5_invoked") else None
        r5_ok = bool(rr) and final == "UNSAT" and rr.get("replay") and rr["replay"].get("status") == "UNSAT"
        if final == "SAT":
            soundness_failures += 1
        if rr and final == "UNSAT" and (not rr.get("replay") or rr["replay"].get("status") != "UNSAT"):
            replay_failures += 1

        telemetry = (rr or {}).get("telemetry") or {}
        hits = int(telemetry.get("hash_cons_cache_hits", 0))
        calls = int(telemetry.get("canonical_child_calls", 0))
        child_work = int(telemetry.get("child_c025_exact_paid_work", 0))
        verified = int(telemetry.get("verified_splits", 0))
        child_max = int(telemetry.get("max_child_state_units", 0))
        if hits >= 1:
            formulas_with_hash_hit += 1
        total_hash_hits += hits
        actual_child_calls += calls
        no_share_child_calls += no_share_calls_here
        actual_child_work += child_work
        no_share_child_work += no_share_work_here
        total_verified_splits += verified
        max_child_units = max(max_child_units, child_max)
        if rr:
            total_actual_r5_work += int(rr.get("combined_fallback_work", 0))
            total_actual_replay_work += int(rr.get("replay_work", 0))

        rows.append({
            "seed": int(seed),
            "fingerprint": fp,
            "triples": generated["triples"],
            "truth": truth,
            "preconditions": {
                "collision_exact": collision_ok,
                "selector_selected": selector_ok,
                "selected_pivot": pivot,
                "canonical_root_OPEN": canonical_open,
                "canonical_root_status": canonical.get("status"),
                "shared_child_UNSAT": child_unsat,
                "shared_child_replay_identical": child_replay_identical,
                "shared_child_fingerprint": solver.fingerprint(base),
                "pressure_selected_score": pressure.get("selected_score")
            },
            "actual_R5": {
                "status": final,
                "winner": run.get("winner"),
                "r5_invoked": bool(run.get("r5_invoked")),
                "replay_clean_UNSAT": r5_ok,
                "hash_cons_cache_hits": hits,
                "canonical_child_calls": calls,
                "child_exact_paid_work": child_work,
                "verified_splits": verified,
                "max_child_state_units": child_max
            },
            "no_sharing_counterfactual": {
                "independent_child_calls": no_share_calls_here,
                "child_exact_paid_work": no_share_work_here,
                "both_UNSAT": child_unsat,
                "byte_identical_results": child_replay_identical
            }
        })

    if len(set(fingerprints)) != len(fingerprints):
        raise RuntimeError("R5A_HOLDOUT_FINGERPRINT_COLLISION_BETWEEN_FORMULAS")

    all_preconditions = precondition_failures == 0
    all_unsat_clean = soundness_failures == 0 and replay_failures == 0 and all(row["actual_R5"]["replay_clean_UNSAT"] for row in rows)
    all_have_hash_hit = formulas_with_hash_hit == 24
    call_saving = actual_child_calls < no_share_child_calls
    work_saving = actual_child_work < no_share_child_work
    status = "PASS" if all_preconditions and all_unsat_clean and all_have_hash_hit and call_saving and work_saving else "FAIL"

    return {
        "schema": "janus.trump.slime_r5a_collision_rich_hash_cons.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R5A_implementation": FREEZE_COMMIT,
        "runtime_under_test": spec["runtime_under_test"],
        "solver_source": source,
        "profile": profile,
        "holdout": {
            "formula_count": 24,
            "precondition_failures": precondition_failures,
            "soundness_failures": soundness_failures,
            "replay_failures": replay_failures,
            "formulas_with_hash_cons_hit": formulas_with_hash_hit,
            "total_hash_cons_cache_hits": total_hash_hits,
            "actual_C025_child_calls": actual_child_calls,
            "no_sharing_C025_child_calls": no_share_child_calls,
            "saved_C025_child_calls": no_share_child_calls - actual_child_calls,
            "actual_child_exact_paid_work": actual_child_work,
            "no_sharing_child_exact_paid_work": no_share_child_work,
            "saved_child_exact_paid_work": no_share_child_work - actual_child_work,
            "verified_splits": total_verified_splits,
            "max_child_state_units": max_child_units,
            "actual_R5_fallback_work": total_actual_r5_work,
            "actual_R5_replay_work": total_actual_replay_work,
            "gate": {
                "all_preconditions_pass": all_preconditions,
                "all_R5_results_replay_clean_UNSAT": all_unsat_clean,
                "all_formulas_record_hash_hit": all_have_hash_hit,
                "strict_child_call_saving": call_saving,
                "strict_child_exact_work_saving": work_saving
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
