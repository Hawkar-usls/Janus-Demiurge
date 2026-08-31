#!/usr/bin/env python3
"""Frozen causal R5A2 hash-cons benchmark on fresh wrapped GT collisions."""
from __future__ import annotations

import argparse
import copy
import itertools
import json
from math import comb
from pathlib import Path
import random
from typing import Any, Iterable, Sequence

import trump_slime_preelim_compression_r5 as r5

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R5A2_WRAPPED_GT_HASH_CONS_FROZEN_BENCH_V1.json"
FREEZE_COMMIT = "e4b9d924462a762bb4cdad4df14576373589a8d7"
R5_BLOB_SHA = "bb9471e3e3c7129ec394ad02f727d9ca6691439b"


class NoHitDict(dict):
    """Benchmark-only memo mapping: writes persist, retrieval membership is disabled."""
    def __contains__(self, key: object) -> bool:
        return False


def load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R5A2_WRAPPED_GT_HASH_CONS_FROZEN_C1K0_BENCH_V1":
        raise RuntimeError("R5A2_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R5A2_IMPLEMENTATION":
        raise RuntimeError("R5A2_SPEC_STATUS_DRIFT")
    if spec["runtime_under_test"].get("git_blob_sha") != R5_BLOB_SHA:
        raise RuntimeError("R5A2_RUNTIME_BLOB_SPEC_DRIFT")
    if spec["runtime_under_test"].get("R5_runtime_modification_allowed") is not False:
        raise RuntimeError("R5A2_RUNTIME_MODIFICATION_FORBIDDEN")
    return spec


def local_canon_clause(row: Iterable[int]) -> tuple[int, ...] | None:
    xs = set(int(x) for x in row)
    if 0 in xs:
        raise ValueError("R5A2_ZERO_LITERAL")
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
    pair_var: dict[tuple[int, int], int] = {}
    nxt = 1
    for left in range(n):
        for right in range(left + 1, n):
            pair_var[(left, right)] = nxt
            nxt += 1

    def lt(left: int, right: int) -> int:
        return pair_var[(left, right)] if left < right else -pair_var[(right, left)]

    clauses = []
    for vertex in range(n):
        clauses.append(tuple(lt(other, vertex) for other in range(n) if other != vertex))
    for first, second, third in itertools.permutations(range(n), 3):
        clauses.append((lt(first, second), lt(second, third), lt(third, first)))
    return local_canon_cnf(clauses), nxt - 1


def seeded_base_mapping(variable_count: int, seed: int) -> dict[int, int]:
    target = list(range(2, variable_count + 2))
    random.Random(int(seed)).shuffle(target)
    mapping = {logical: target[logical - 1] for logical in range(1, variable_count + 1)}
    canonical_shift = {logical: logical + 1 for logical in range(1, variable_count + 1)}
    if mapping == canonical_shift:
        raise RuntimeError("R5A2_CANONICAL_DEVELOPMENT_NUMBERING_FORBIDDEN")
    return mapping


def rename_cnf(cnf: Sequence[Sequence[int]], mapping: dict[int, int]) -> tuple[tuple[int, ...], ...]:
    return local_canon_cnf(
        tuple(mapping[abs(lit)] if lit > 0 else -mapping[abs(lit)] for lit in clause)
        for clause in cnf
    )


def inverse_rename_cnf(cnf: Sequence[Sequence[int]], mapping: dict[int, int]) -> tuple[tuple[int, ...], ...]:
    inverse = {numeric: logical for logical, numeric in mapping.items()}
    return local_canon_cnf(
        tuple(inverse[abs(lit)] if lit > 0 else -inverse[abs(lit)] for lit in clause)
        for clause in cnf
    )


def selector_wrap(base: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    rows = []
    for clause in base:
        rows.append((1, *clause))
        rows.append((-1, *clause))
    return local_canon_cnf(rows)


def brute_status(cnf: Sequence[Sequence[int]], variables: Sequence[int]) -> str:
    ordered = sorted(int(v) for v in variables)
    for bits in itertools.product((0, 1), repeat=len(ordered)):
        assignment = {v: bits[i] for i, v in enumerate(ordered)}
        if all(any(assignment[abs(lit)] == int(lit > 0) for lit in clause) for clause in cnf):
            return "SAT"
    return "UNSAT"


def tiny_wrapped_truth_regression() -> str:
    logical, count = logical_graph_tautology(3)
    mapping = {v: v + 1 for v in range(1, count + 1)}
    base = rename_cnf(logical, mapping)
    root = selector_wrap(base)
    status = brute_status(root, range(1, count + 2))
    if status != "UNSAT":
        raise RuntimeError("R5A2_TINY_WRAPPED_GT_TRUTH_REGRESSION_FAILED")
    return status


def structural_certificate(order: int, seed: int) -> dict[str, Any]:
    logical, variable_count = logical_graph_tautology(order)
    if variable_count != comb(order, 2) or len(logical) != order + 2 * comb(order, 3):
        raise RuntimeError("R5A2_GT_SCHEMA_DRIFT")
    mapping = seeded_base_mapping(variable_count, seed)
    base = rename_cnf(logical, mapping)
    if inverse_rename_cnf(base, mapping) != logical:
        raise RuntimeError("R5A2_RENAMING_CERTIFICATE_FAILED")
    root = selector_wrap(base)
    return {
        "order": int(order),
        "seed": int(seed),
        "base_variable_count": int(variable_count),
        "base_clause_count": len(base),
        "root_variable_count": int(variable_count + 1),
        "root_clause_count": len(root),
        "structural_truth": "UNSAT",
        "truth_basis": "WRAPPER_EQUIVALENT_TO_3_CYCLE_FREE_GRAPH_TAUTOLOGY__FINITE_TRANSITIVE_TOURNAMENT_HAS_MINIMUM",
        "inverse_renaming_reconstructs_logical_GT": True,
        "base": [list(c) for c in base],
        "root": [list(c) for c in root]
    }


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


def combined_telemetry_work(telemetry: dict[str, Any]) -> int:
    return (
        int(telemetry.get("child_c025_exact_paid_work", 0))
        + int(telemetry.get("structural_work", 0))
        + int(telemetry.get("split_verification_work", 0))
    )


def run_no_memo_counterfactual(solver, root, profile: dict[str, int]) -> dict[str, Any]:
    root_cnf = solver.canon_cnf(root)
    N = int(solver.input_size_units(root_cnf))
    root_state_cap = N ** int(profile["cap_exponent"])
    base_r5_spec = r5.load_frozen_spec()
    max_depth = int(base_r5_spec["bounded_continuation"]["maximum_factor_depth"])
    node_budget = min(N * N, 128)
    ctx = r5.R5Context(
        solver=solver,
        profile=profile,
        root_cnf=root_cnf,
        root_state_cap=root_state_cap,
        node_budget=node_budget,
        max_depth=max_depth,
    )
    ctx.memo = NoHitDict()
    result = ctx.solve_node(root_cnf, 0, root_known_open=True)
    return {
        "status": result["status"],
        "reason": result["reason"],
        "telemetry": dict(ctx.telemetry),
        "combined_fallback_work": combined_telemetry_work(ctx.telemetry),
        "memo_retrieval_disabled": True,
        "proof_authority": False
    }


def execute() -> dict[str, Any]:
    spec = load_spec()
    tiny = tiny_wrapped_truth_regression()
    solver, source = r5.load_pinned_solver()
    cache_stats = install_pure_resolution_cache(solver)
    profile = {k: int(v) for k, v in spec["profile"].items()}

    subjects = []
    for family in ("GT6_WRAPPED", "GT7_WRAPPED"):
        order = int(spec["holdout"][family]["order"])
        for seed in spec["holdout"][family]["seeds"]:
            subjects.append((family, structural_certificate(order, int(seed))))
    if len(subjects) != 24:
        raise RuntimeError("R5A2_HOLDOUT_COUNT_DRIFT")

    rows = []
    fingerprints = []
    eligible_count = 0
    eligible_per_family = {"GT6_WRAPPED": 0, "GT7_WRAPPED": 0}
    actual_hash_hit_formulas = 0
    actual_unsat_clean = 0
    actual_sat_failures = 0
    actual_replay_failures = 0
    no_memo_unsat = 0
    totals = {
        "actual_canonical_child_calls": 0,
        "no_memo_canonical_child_calls": 0,
        "actual_child_exact_paid_work": 0,
        "no_memo_child_exact_paid_work": 0,
        "actual_structural_work": 0,
        "no_memo_structural_work": 0,
        "actual_split_verification_work": 0,
        "no_memo_split_verification_work": 0,
        "actual_combined_fallback_work": 0,
        "no_memo_combined_fallback_work": 0,
        "actual_hash_cons_cache_hits": 0,
        "actual_verified_splits": 0,
        "no_memo_verified_splits": 0,
        "max_actual_child_state_units": 0,
        "max_no_memo_child_state_units": 0,
        "actual_node_budget_exhaustions": 0,
        "actual_depth_budget_exhaustions": 0,
        "no_memo_node_budget_exhaustions": 0,
        "no_memo_depth_budget_exhaustions": 0
    }

    for family, cert in subjects:
        root = solver.canon_cnf(cert["root"])
        base = solver.canon_cnf(cert["base"])
        fp = solver.fingerprint(root)
        fingerprints.append(fp)
        child0 = solver.restrict(root, 1, 0)
        child1 = solver.restrict(root, 1, 1)
        collision_ok = child0 == child1 == base and solver.fingerprint(child0) == solver.fingerprint(child1)
        selected_pivot, proposed0, proposed1, pressure = r5.branch_pressure(solver, root)
        selector_ok = selected_pivot == 1 and proposed0 == child0 and proposed1 == child1

        actual = r5.solve_canonical_then_r5(solver, cert["root"], **profile)
        baseline = str(actual["baseline"]["status"])
        final = str(actual["final_result"]["status"])
        eligibility = bool(collision_ok and selector_ok and baseline == "OPEN")

        actual_summary = None
        no_memo = None
        if eligibility:
            eligible_count += 1
            eligible_per_family[family] += 1
            rr = actual.get("r5") if actual.get("r5_invoked") else None
            if not rr:
                raise RuntimeError("R5A2_ELIGIBLE_FORMULA_DID_NOT_INVOKE_R5")
            replay = rr.get("replay")
            replay_clean_unsat = final == "UNSAT" and replay is not None and replay.get("status") == "UNSAT"
            if replay_clean_unsat:
                actual_unsat_clean += 1
            elif final == "SAT":
                actual_sat_failures += 1
            else:
                actual_replay_failures += 1
            t = rr["telemetry"]
            hits = int(t["hash_cons_cache_hits"])
            if hits >= 1:
                actual_hash_hit_formulas += 1
            no_memo = run_no_memo_counterfactual(solver, cert["root"], profile)
            if no_memo["status"] == "UNSAT":
                no_memo_unsat += 1

            totals["actual_canonical_child_calls"] += int(t["canonical_child_calls"])
            totals["no_memo_canonical_child_calls"] += int(no_memo["telemetry"]["canonical_child_calls"])
            totals["actual_child_exact_paid_work"] += int(t["child_c025_exact_paid_work"])
            totals["no_memo_child_exact_paid_work"] += int(no_memo["telemetry"]["child_c025_exact_paid_work"])
            totals["actual_structural_work"] += int(t["structural_work"])
            totals["no_memo_structural_work"] += int(no_memo["telemetry"]["structural_work"])
            totals["actual_split_verification_work"] += int(t["split_verification_work"])
            totals["no_memo_split_verification_work"] += int(no_memo["telemetry"]["split_verification_work"])
            totals["actual_combined_fallback_work"] += int(rr["combined_fallback_work"])
            totals["no_memo_combined_fallback_work"] += int(no_memo["combined_fallback_work"])
            totals["actual_hash_cons_cache_hits"] += hits
            totals["actual_verified_splits"] += int(t["verified_splits"])
            totals["no_memo_verified_splits"] += int(no_memo["telemetry"]["verified_splits"])
            totals["max_actual_child_state_units"] = max(totals["max_actual_child_state_units"], int(t["max_child_state_units"]))
            totals["max_no_memo_child_state_units"] = max(totals["max_no_memo_child_state_units"], int(no_memo["telemetry"]["max_child_state_units"]))
            totals["actual_node_budget_exhaustions"] += int(t["node_budget_exhaustions"])
            totals["actual_depth_budget_exhaustions"] += int(t["depth_budget_exhaustions"])
            totals["no_memo_node_budget_exhaustions"] += int(no_memo["telemetry"]["node_budget_exhaustions"])
            totals["no_memo_depth_budget_exhaustions"] += int(no_memo["telemetry"]["depth_budget_exhaustions"])

            actual_summary = {
                "status": final,
                "reason": actual["final_result"].get("reason"),
                "replay_clean_UNSAT": replay_clean_unsat,
                "telemetry": t,
                "combined_fallback_work": int(rr["combined_fallback_work"]),
                "replay_work": int(rr["replay_work"])
            }

        rows.append({
            "family": family,
            "seed": cert["seed"],
            "fingerprint": fp,
            "structural_truth": cert["structural_truth"],
            "collision_exact": collision_ok,
            "selector_selected": selector_ok,
            "selected_pivot": int(selected_pivot),
            "selected_score": pressure.get("selected_score"),
            "canonical_status": baseline,
            "canonical_reason": actual["baseline"].get("reason"),
            "eligible": eligibility,
            "actual_R5": actual_summary,
            "no_memo_counterfactual": no_memo
        })

    if len(fingerprints) != len(set(fingerprints)):
        raise RuntimeError("R5A2_HOLDOUT_FINGERPRINT_COLLISION_BETWEEN_FORMULAS")

    gate = spec["gate"]
    eligibility_threshold = (
        eligible_count >= int(gate["minimum_total_eligible_formulas"])
        and eligible_per_family["GT6_WRAPPED"] >= int(gate["minimum_GT6_eligible"])
        and eligible_per_family["GT7_WRAPPED"] >= int(gate["minimum_GT7_eligible"])
    )
    all_actual_clean = actual_unsat_clean == eligible_count and actual_sat_failures == 0 and actual_replay_failures == 0
    all_hash_hit = actual_hash_hit_formulas == eligible_count
    all_no_memo_unsat = no_memo_unsat == eligible_count
    call_saving = totals["actual_canonical_child_calls"] < totals["no_memo_canonical_child_calls"]
    exact_work_saving = totals["actual_child_exact_paid_work"] < totals["no_memo_child_exact_paid_work"]
    combined_saving = totals["actual_combined_fallback_work"] < totals["no_memo_combined_fallback_work"]
    saved_calls = totals["no_memo_canonical_child_calls"] - totals["actual_canonical_child_calls"]
    saved_exact_work = totals["no_memo_child_exact_paid_work"] - totals["actual_child_exact_paid_work"]
    saved_combined_work = totals["no_memo_combined_fallback_work"] - totals["actual_combined_fallback_work"]
    status = "PASS" if (
        eligibility_threshold
        and all_actual_clean
        and all_hash_hit
        and all_no_memo_unsat
        and call_saving
        and exact_work_saving
        and combined_saving
        and saved_calls >= int(gate["minimum_saved_canonical_child_calls"])
    ) else "FAIL"

    return {
        "schema": "janus.trump.slime_r5a2_wrapped_gt_hash_cons.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R5A2_implementation": FREEZE_COMMIT,
        "discovery_boundary": spec["discovery_boundary"],
        "runtime_under_test": spec["runtime_under_test"],
        "solver_source": source,
        "profile": profile,
        "tiny_wrapped_GT3_truth_regression": tiny,
        "holdout": {
            "formula_count": 24,
            "eligible_formulas": eligible_count,
            "eligible_per_family": eligible_per_family,
            "actual_replay_clean_UNSAT": actual_unsat_clean,
            "actual_hash_hit_formulas": actual_hash_hit_formulas,
            "actual_SAT_soundness_failures": actual_sat_failures,
            "actual_replay_failures": actual_replay_failures,
            "no_memo_UNSAT": no_memo_unsat,
            "totals": totals,
            "saved_canonical_child_calls": saved_calls,
            "saved_child_exact_paid_work": saved_exact_work,
            "saved_combined_fallback_work": saved_combined_work,
            "saved_child_call_fraction": (saved_calls / totals["no_memo_canonical_child_calls"]) if totals["no_memo_canonical_child_calls"] else 0.0,
            "saved_child_exact_work_fraction": (saved_exact_work / totals["no_memo_child_exact_paid_work"]) if totals["no_memo_child_exact_paid_work"] else 0.0,
            "saved_combined_work_fraction": (saved_combined_work / totals["no_memo_combined_fallback_work"]) if totals["no_memo_combined_fallback_work"] else 0.0,
            "gate": {
                "eligibility_threshold_met": eligibility_threshold,
                "all_eligible_actual_replay_clean_UNSAT": all_actual_clean,
                "all_eligible_actual_hash_hit": all_hash_hit,
                "all_eligible_no_memo_UNSAT": all_no_memo_unsat,
                "strict_child_call_saving": call_saving,
                "strict_child_exact_work_saving": exact_work_saving,
                "strict_combined_fallback_work_saving": combined_saving,
                "minimum_saved_calls_met": saved_calls >= int(gate["minimum_saved_canonical_child_calls"])
            },
            "rows": rows
        },
        "physical_execution_cache": {"kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION", "cache_stats": cache_stats, "logical_solver_work_charged_unchanged": True},
        "scientific_boundary": spec["scientific_boundary"]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = execute()
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if args.require_pass and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
