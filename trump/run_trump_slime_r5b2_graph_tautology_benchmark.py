#!/usr/bin/env python3
"""Frozen confirmatory R5B2 benchmark on fresh Graph Tautology renamings."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from math import comb
from pathlib import Path
import random
from typing import Any, Iterable, Sequence

from trump_slime_preelim_compression_r5 import load_pinned_solver, solve_canonical_then_r5

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R5B2_GRAPH_TAUTOLOGY_UNSAT_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "a890b6027ebae6b8e9f27ed8dac290e06dc87fdf"
R5_BLOB_SHA = "bb9471e3e3c7129ec394ad02f727d9ca6691439b"


def load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R5B2_GRAPH_TAUTOLOGY_UNSAT_FROZEN_C1K0_BENCH_V1":
        raise RuntimeError("R5B2_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R5B2_IMPLEMENTATION":
        raise RuntimeError("R5B2_SPEC_STATUS_DRIFT")
    if spec["runtime_under_test"].get("git_blob_sha") != R5_BLOB_SHA:
        raise RuntimeError("R5B2_RUNTIME_BLOB_SPEC_DRIFT")
    if spec["runtime_under_test"].get("R5_runtime_modification_allowed") is not False:
        raise RuntimeError("R5B2_RUNTIME_MODIFICATION_FORBIDDEN")
    return spec


def local_canon_clause(row: Iterable[int]) -> tuple[int, ...] | None:
    xs = set(int(x) for x in row)
    if 0 in xs:
        raise ValueError("R5B2_ZERO_LITERAL")
    if any(-x in xs for x in xs):
        return None
    return tuple(sorted(xs, key=lambda z: (abs(z), z < 0)))


def local_canon_cnf(rows: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    clean = []
    for row in rows:
        clause = local_canon_clause(row)
        if clause is not None:
            clean.append(clause)
    uniq = sorted(set(clean), key=lambda c: (len(c), c))
    # Exact local canonicalizer for this family.  Keep subsumption explicit so
    # the benchmark certificate does not depend on C025 canonicalization code.
    kept: list[tuple[int, ...]] = []
    sets: list[frozenset[int]] = []
    for clause in uniq:
        cs = frozenset(clause)
        if any(prev <= cs for prev in sets):
            continue
        kept.append(clause)
        sets.append(cs)
    return tuple(kept)


def logical_graph_tautology(n: int) -> tuple[tuple[tuple[int, ...], ...], int]:
    if n < 3:
        raise ValueError("R5B2_GT_ORDER_TOO_SMALL")
    pair_var: dict[tuple[int, int], int] = {}
    nxt = 1
    for left in range(n):
        for right in range(left + 1, n):
            pair_var[(left, right)] = nxt
            nxt += 1

    def lt(left: int, right: int) -> int:
        if left == right:
            raise ValueError("R5B2_GT_STRICT_ORDER_SELF_LITERAL")
        return pair_var[(left, right)] if left < right else -pair_var[(right, left)]

    clauses: list[tuple[int, ...]] = []
    for vertex in range(n):
        clauses.append(tuple(lt(other, vertex) for other in range(n) if other != vertex))
    for first, second, third in itertools.permutations(range(n), 3):
        clauses.append((lt(first, second), lt(second, third), lt(third, first)))
    return local_canon_cnf(clauses), nxt - 1


def seeded_bijection(variable_count: int, seed: int) -> dict[int, int]:
    target = list(range(1, variable_count + 1))
    random.Random(int(seed)).shuffle(target)
    mapping = {logical: target[logical - 1] for logical in range(1, variable_count + 1)}
    if all(mapping[v] == v for v in mapping):
        raise RuntimeError("R5B2_IDENTITY_RENAMING_FORBIDDEN")
    return mapping


def rename_cnf(cnf: Sequence[Sequence[int]], mapping: dict[int, int]) -> tuple[tuple[int, ...], ...]:
    rows = []
    for clause in cnf:
        rows.append(tuple(mapping[abs(lit)] if lit > 0 else -mapping[abs(lit)] for lit in clause))
    return local_canon_cnf(rows)


def inverse_rename_cnf(cnf: Sequence[Sequence[int]], mapping: dict[int, int]) -> tuple[tuple[int, ...], ...]:
    inverse = {numeric: logical for logical, numeric in mapping.items()}
    rows = []
    for clause in cnf:
        rows.append(tuple(inverse[abs(lit)] if lit > 0 else -inverse[abs(lit)] for lit in clause))
    return local_canon_cnf(rows)


def brute_status(cnf: Sequence[Sequence[int]], variable_count: int) -> str:
    for bits in itertools.product((0, 1), repeat=variable_count):
        assignment = {i + 1: bits[i] for i in range(variable_count)}
        if all(any(assignment[abs(lit)] == int(lit > 0) for lit in clause) for clause in cnf):
            return "SAT"
    return "UNSAT"


def structural_certificate(order: int, seed: int) -> dict[str, Any]:
    logical, variable_count = logical_graph_tautology(order)
    expected_vars = comb(order, 2)
    expected_clauses = order + 2 * comb(order, 3)
    if variable_count != expected_vars or len(logical) != expected_clauses:
        raise RuntimeError("R5B2_LOGICAL_GT_SCHEMA_DRIFT")
    mapping = seeded_bijection(variable_count, seed)
    renamed = rename_cnf(logical, mapping)
    if inverse_rename_cnf(renamed, mapping) != logical:
        raise RuntimeError("R5B2_RENAMING_CERTIFICATE_FAILED")
    numeric_vars = sorted({abs(lit) for clause in renamed for lit in clause})
    if numeric_vars != list(range(1, variable_count + 1)):
        raise RuntimeError("R5B2_RENAMED_VARIABLE_SET_DRIFT")
    return {
        "order": order,
        "seed": int(seed),
        "variable_count": variable_count,
        "clause_count": len(renamed),
        "expected_variable_count": expected_vars,
        "expected_clause_count": expected_clauses,
        "identity_renaming": False,
        "inverse_renaming_reconstructs_logical_GT": True,
        "structural_truth": "UNSAT",
        "truth_basis": "FINITE_3_CYCLE_FREE_TOURNAMENT_IS_TRANSITIVE_AND_HAS_A_MINIMUM__NONMINIMALITY_CONTRADICTS_MINIMUM",
        "mapping": {str(k): v for k, v in sorted(mapping.items())},
        "cnf": [list(c) for c in renamed]
    }


def tiny_truth_regression() -> dict[str, str]:
    out = {}
    for n in (3, 4):
        cnf, var_count = logical_graph_tautology(n)
        out[f"GT{n}"] = brute_status(cnf, var_count)
        if out[f"GT{n}"] != "UNSAT":
            raise RuntimeError("R5B2_TINY_GT_TRUTH_REGRESSION_FAILED")
    return out


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
    tiny = tiny_truth_regression()
    solver, source = load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}

    subjects: list[tuple[str, dict[str, Any]]] = []
    for family in ("GT6", "GT7"):
        family_spec = spec["holdout"][family]
        order = int(family_spec["order"])
        for seed in family_spec["seeds"]:
            subjects.append((family, structural_certificate(order, int(seed))))
    if len(subjects) != 24:
        raise RuntimeError("R5B2_HOLDOUT_COUNT_DRIFT")

    rows = []
    fingerprints = []
    canonical_unsat = 0
    canonical_open = 0
    canonical_sat_failures = 0
    r5_unsat_rescues = 0
    r5_sat_failures = 0
    replay_failures = 0
    canonical_preserved = True
    per_family = {
        "GT6": {"formulas": 0, "canonical_OPEN": 0, "canonical_UNSAT": 0, "R5_UNSAT_rescues": 0, "final_OPEN": 0},
        "GT7": {"formulas": 0, "canonical_OPEN": 0, "canonical_UNSAT": 0, "R5_UNSAT_rescues": 0, "final_OPEN": 0}
    }
    work = {"canonical_exact_paid_work": 0, "canonical_decisive_replay_work": 0, "R5_combined_fallback_work": 0, "R5_full_replay_work": 0}
    totals = {key: 0 for key in ["unique_factor_dag_nodes", "hash_cons_cache_hits", "split_proposals", "verified_splits", "structural_work", "split_verification_work", "child_c025_exact_paid_work", "max_child_state_units", "node_budget_exhaustions", "depth_budget_exhaustions", "canonical_child_calls"]}

    for family, cert in subjects:
        clauses = cert["cnf"]
        fp = solver.fingerprint(solver.canon_cnf(clauses))
        fingerprints.append(fp)
        per_family[family]["formulas"] += 1
        run = solve_canonical_then_r5(solver, clauses, **profile)
        baseline = str(run["baseline"]["status"])
        final = str(run["final_result"]["status"])
        if baseline == "UNSAT":
            canonical_unsat += 1
            per_family[family]["canonical_UNSAT"] += 1
            if final != "UNSAT" or run.get("winner") != "CANONICAL" or run.get("r5_invoked"):
                canonical_preserved = False
        elif baseline == "OPEN":
            canonical_open += 1
            per_family[family]["canonical_OPEN"] += 1
        elif baseline == "SAT":
            canonical_sat_failures += 1

        work["canonical_exact_paid_work"] += int(run["canonical_exact_paid_work"])
        work["canonical_decisive_replay_work"] += int(run.get("canonical_replay_work", 0))
        r5_summary = None
        if run.get("r5_invoked"):
            rr = run["r5"]
            work["R5_combined_fallback_work"] += int(rr["combined_fallback_work"])
            work["R5_full_replay_work"] += int(rr["replay_work"])
            for key in totals:
                value = int(rr["telemetry"][key])
                totals[key] = max(totals[key], value) if key == "max_child_state_units" else totals[key] + value
            if final == "UNSAT":
                replay = rr.get("replay")
                if not replay or replay.get("status") != "UNSAT":
                    replay_failures += 1
                else:
                    r5_unsat_rescues += 1
                    per_family[family]["R5_UNSAT_rescues"] += 1
            elif final == "SAT":
                r5_sat_failures += 1
            elif final == "OPEN":
                per_family[family]["final_OPEN"] += 1
            r5_summary = {
                "status": final,
                "reason": run["final_result"].get("reason"),
                "combined_fallback_work": int(rr["combined_fallback_work"]),
                "replay_work": int(rr["replay_work"]),
                "telemetry": rr["telemetry"],
                "receipt_nodes": len(rr["receipt"]["nodes"])
            }

        rows.append({
            "family": family,
            "seed": cert["seed"],
            "fingerprint": fp,
            "structural_certificate": {k: v for k, v in cert.items() if k not in {"cnf", "mapping"}},
            "canonical_status": baseline,
            "canonical_reason": run["baseline"].get("reason"),
            "final_status": final,
            "final_reason": run["final_result"].get("reason"),
            "winner": run.get("winner"),
            "r5_invoked": bool(run.get("r5_invoked")),
            "r5": r5_summary
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R5B2_HOLDOUT_FINGERPRINT_COLLISION")

    eligible = canonical_open
    rescue_fraction = (r5_unsat_rescues / eligible) if eligible else 0.0
    gate_spec = spec["gate"]
    all_truth_certificates = all(row["structural_certificate"]["structural_truth"] == "UNSAT" for row in rows)
    no_sat_failures = canonical_sat_failures == 0 and r5_sat_failures == 0
    replay_clean = replay_failures == 0
    threshold = (
        eligible >= int(gate_spec["minimum_canonical_OPEN_eligible_formulas"])
        and r5_unsat_rescues >= int(gate_spec["minimum_total_OPEN_to_R5_UNSAT_rescues"])
        and per_family["GT6"]["R5_UNSAT_rescues"] >= int(gate_spec["minimum_GT6_rescues"])
        and per_family["GT7"]["R5_UNSAT_rescues"] >= int(gate_spec["minimum_GT7_rescues"])
        and rescue_fraction >= float(gate_spec["minimum_rescue_fraction_among_canonical_OPEN"])
    )
    final_unsat = sum(row["final_status"] == "UNSAT" for row in rows)
    count_not_worse = final_unsat >= canonical_unsat
    status = "PASS" if all_truth_certificates and no_sat_failures and canonical_preserved and replay_clean and threshold and count_not_worse else "FAIL"

    return {
        "schema": "janus.trump.slime_r5b2_graph_tautology_unsat.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R5B2_implementation": FREEZE_COMMIT,
        "discovery_boundary": spec["discovery_boundary"],
        "runtime_under_test": spec["runtime_under_test"],
        "solver_source": source,
        "profile": profile,
        "tiny_GT_truth_regression": tiny,
        "holdout": {
            "formula_count": 24,
            "structural_truth_certified_UNSAT": sum(row["structural_certificate"]["structural_truth"] == "UNSAT" for row in rows),
            "canonical_UNSAT": canonical_unsat,
            "canonical_OPEN": canonical_open,
            "canonical_SAT_soundness_failures": canonical_sat_failures,
            "R5_UNSAT_rescues": r5_unsat_rescues,
            "R5_SAT_soundness_failures": r5_sat_failures,
            "final_UNSAT": final_unsat,
            "final_OPEN": sum(row["final_status"] == "OPEN" for row in rows),
            "contradictory_exact_decisive_replays": replay_failures,
            "canonical_decisive_preserved": canonical_preserved,
            "rescue_fraction_among_canonical_OPEN": rescue_fraction,
            "per_family": per_family,
            "factor_dag": totals,
            "work": {**work, "ecology_execution_plus_full_replay_work": sum(work.values())},
            "gate": {
                "all_structural_truth_certificates_pass": all_truth_certificates,
                "no_SAT_soundness_failure": no_sat_failures,
                "canonical_decisive_preserved": canonical_preserved,
                "decisive_replay_clean": replay_clean,
                "preregistered_UNSAT_rescue_threshold_met": threshold,
                "UNSAT_count_not_worse": count_not_worse
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
