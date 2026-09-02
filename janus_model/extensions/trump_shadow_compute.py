from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA = "janus.trump.shadow_compute.v1"
MAX_VARS = 16
DEFAULT_REPEATS = 5
MIN_SPEEDUP_RATIO = 1.25


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_candidate(path: Path):
    name = "janus_trump_pinned_c025"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("TRUMP_C025_IMPORT_SPEC_FAILED")
    mod = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    if not callable(getattr(mod, "solve_fail_closed", None)):
        raise RuntimeError("TRUMP_C025_SOLVE_ENTRYPOINT_MISSING")
    if not callable(getattr(mod, "verify_total_assignment", None)):
        raise RuntimeError("TRUMP_C025_WITNESS_VERIFIER_MISSING")
    return mod


def vars_of(clauses) -> list[int]:
    return sorted({abs(int(l)) for c in clauses for l in c if int(l)})


def assignment_satisfies(clauses, assignment: dict[int, int]) -> bool:
    return all(any(assignment.get(abs(int(l))) == int(int(l) > 0) for l in c) for c in clauses)


def brute_force_oracle(clauses) -> dict:
    """Small bounded truth oracle. Never used as the performance baseline."""
    variables = vars_of(clauses)
    if len(variables) > MAX_VARS:
        return {"status": "OUT_OF_BOUNDS", "variables": len(variables), "assignments_tested": 0}
    tested = 0
    for mask in range(1 << len(variables)):
        tested += 1
        assignment = {v: (mask >> i) & 1 for i, v in enumerate(variables)}
        if assignment_satisfies(clauses, assignment):
            return {"status": "SAT", "witness": assignment, "variables": len(variables), "assignments_tested": tested}
    return {"status": "UNSAT", "witness": None, "variables": len(variables), "assignments_tested": tested}


# Backward-compatible name used by existing tests/consumers. Semantics are oracle-only.
brute_force_baseline = brute_force_oracle


def _unit_propagate(clauses, assignment: dict[int, int]):
    work = tuple(tuple(int(l) for l in c) for c in clauses)
    out = dict(assignment)
    while True:
        reduced = []
        unit = None
        for clause in work:
            unresolved = []
            satisfied = False
            for lit in clause:
                var = abs(lit)
                if var in out:
                    if out[var] == int(lit > 0):
                        satisfied = True
                        break
                else:
                    unresolved.append(lit)
            if satisfied:
                continue
            if not unresolved:
                return None, out
            if len(unresolved) == 1 and unit is None:
                unit = unresolved[0]
            reduced.append(tuple(unresolved))
        if not reduced:
            return tuple(), out
        if unit is None:
            return tuple(reduced), out
        var = abs(unit)
        value = int(unit > 0)
        if var in out and out[var] != value:
            return None, out
        out[var] = value
        work = tuple(reduced)


def reference_dpll_baseline(clauses) -> dict:
    """Deterministic exact DPLL reference; performance comparator, not truth authority alone."""
    variables = vars_of(clauses)
    if len(variables) > MAX_VARS:
        return {"status": "OUT_OF_BOUNDS", "variables": len(variables), "search_nodes": 0}
    search_nodes = 0

    def rec(work, assignment):
        nonlocal search_nodes
        search_nodes += 1
        reduced, propagated = _unit_propagate(work, assignment)
        if reduced is None:
            return None
        if not reduced:
            return propagated
        clause = min(reduced, key=lambda c: (len(c), tuple(abs(x) for x in c), c))
        lit = min(clause, key=lambda x: (abs(x), x < 0))
        var = abs(lit)
        for value in (int(lit > 0), int(lit < 0)):
            if var in propagated and propagated[var] != value:
                continue
            child = dict(propagated)
            child[var] = value
            found = rec(reduced, child)
            if found is not None:
                return found
        return None

    witness = rec(tuple(tuple(int(l) for l in c) for c in clauses), {})
    if witness is None:
        return {"status": "UNSAT", "witness": None, "variables": len(variables), "search_nodes": search_nodes}
    complete = {v: int(witness.get(v, 0)) for v in variables}
    if not assignment_satisfies(clauses, complete):
        raise RuntimeError("TRUMP_REFERENCE_DPLL_INVALID_WITNESS")
    return {"status": "SAT", "witness": complete, "variables": len(variables), "search_nodes": search_nodes}


def suite() -> list[dict]:
    n = 16
    unit_all_true = tuple((v,) for v in range(1, n + 1))
    chain = tuple([(1,)] + [(-v, v + 1) for v in range(1, n)])
    contradiction = tuple([(1,), (-1,)] + [(v, -v) for v in range(2, n + 1)])
    return [
        {"id": "UNIT_ALL_TRUE_16", "class": "UNIT_PROPAGATION", "clauses": unit_all_true},
        {"id": "TWO_SAT_CHAIN_ALL_TRUE_16", "class": "TWO_SAT_CHAIN", "clauses": chain},
        {"id": "UNSAT_CONTRADICTION_WITH_TAUTOLOGY_CARRIERS_16", "class": "UNSAT_CONTROL", "clauses": contradiction},
    ]


def _candidate_once(mod, clauses) -> tuple[dict, int]:
    started = time.perf_counter_ns()
    out = mod.solve_fail_closed(clauses)
    elapsed = time.perf_counter_ns() - started
    return out, elapsed


def _reference_once(clauses) -> tuple[dict, int]:
    started = time.perf_counter_ns()
    out = reference_dpll_baseline(clauses)
    elapsed = time.perf_counter_ns() - started
    return out, elapsed


def _candidate_semantics(mod, clauses, out: dict) -> dict:
    status = out.get("status")
    if status == "SAT":
        witness = out.get("witness")
        if not isinstance(witness, dict):
            return {"status": status, "witness_verified": False}
        normalized = {int(k): int(v) for k, v in witness.items()}
        verified = assignment_satisfies(clauses, normalized) and bool(mod.verify_total_assignment(mod.canon_cnf(clauses), normalized))
        return {"status": status, "witness_verified": verified}
    return {"status": status, "witness_verified": None}


def run_shadow(candidate_path: Path, repeats: int = DEFAULT_REPEATS) -> dict:
    if repeats < 3 or repeats > 9:
        raise RuntimeError("TRUMP_SHADOW_REPEAT_COUNT_OUT_OF_BOUNDS")
    mod = load_candidate(candidate_path)
    rows = []
    for workload in suite():
        clauses = workload["clauses"]
        oracle = brute_force_oracle(clauses)
        if oracle["status"] not in {"SAT", "UNSAT"}:
            raise RuntimeError("TRUMP_SHADOW_ORACLE_OUT_OF_BOUNDS")
        reference_times = []
        candidate_times = []
        reference_ref = None
        candidate_ref = None
        candidate_sem = None
        for _ in range(repeats):
            reference, rt = _reference_once(clauses)
            candidate, ct = _candidate_once(mod, clauses)
            reference_times.append(rt)
            candidate_times.append(ct)
            if reference_ref is None:
                reference_ref = reference
                candidate_ref = candidate
                candidate_sem = _candidate_semantics(mod, clauses, candidate)
            if reference["status"] != reference_ref["status"] or candidate.get("status") != candidate_ref.get("status"):
                raise RuntimeError("TRUMP_SHADOW_NONDETERMINISTIC_TERMINAL")
        assert reference_ref is not None and candidate_ref is not None and candidate_sem is not None
        if reference_ref["status"] != oracle["status"]:
            raise RuntimeError("TRUMP_REFERENCE_DPLL_ORACLE_MISMATCH")
        cstatus = candidate_ref.get("status")
        exact_terminal = cstatus in {"SAT", "UNSAT"} and cstatus == reference_ref["status"] == oracle["status"]
        if cstatus == "SAT":
            exact_terminal = exact_terminal and candidate_sem["witness_verified"] is True
        rmed = int(statistics.median(reference_times))
        cmed = int(statistics.median(candidate_times))
        speedup = (rmed / cmed) if cmed > 0 else None
        repeated_resource_win = bool(exact_terminal and speedup is not None and speedup >= MIN_SPEEDUP_RATIO)
        rows.append({
            "id": workload["id"],
            "class": workload["class"],
            "variables": len(vars_of(clauses)),
            "clause_count": len(clauses),
            "oracle_status": oracle["status"],
            "oracle_assignments_tested": oracle["assignments_tested"],
            "reference_solver": "DETERMINISTIC_EXACT_DPLL",
            "reference_status": reference_ref["status"],
            "reference_search_nodes": reference_ref["search_nodes"],
            "candidate_status": cstatus,
            "candidate_witness_verified": candidate_sem["witness_verified"],
            "exact_terminal_equivalence": exact_terminal,
            "reference_median_ns": rmed,
            "candidate_median_ns": cmed,
            "median_speedup_ratio_vs_reference_dpll": speedup,
            "minimum_speedup_ratio": MIN_SPEEDUP_RATIO,
            "repeated_resource_win": repeated_resource_win,
            "candidate_reason": candidate_ref.get("reason"),
        })

    terminal_rows = [r for r in rows if r["exact_terminal_equivalence"]]
    win_rows = [r for r in rows if r["repeated_resource_win"]]
    sat_fast_paths = [r["id"] for r in win_rows if r["candidate_status"] == "SAT" and r["candidate_witness_verified"]]
    if len(terminal_rows) == len(rows) and win_rows:
        status = "SHADOW_EQUIVALENCE_PASS_RESOURCE_WIN_OBSERVED"
    elif terminal_rows:
        status = "SHADOW_EQUIVALENCE_PASS_NO_ELIGIBLE_ACCELERATION" if not win_rows else "SHADOW_PARTIAL_EQUIVALENCE_RESOURCE_WIN_OBSERVED"
    else:
        status = "SHADOW_NO_EXACT_TERMINAL_EQUIVALENCE"
    obj = {
        "schema": SCHEMA,
        "status": status,
        "candidate": {
            "role": "PINNED_C025_SHADOW_ONLY",
            "source_path": str(candidate_path),
            "source_sha256": sha256_bytes(candidate_path.read_bytes()),
        },
        "performance_reference": {
            "solver": "DETERMINISTIC_EXACT_DPLL",
            "truth_oracle": "EXHAUSTIVE_ENUMERATION_NOT_TIMED_AS_PERFORMANCE_BASELINE",
            "minimum_speedup_ratio": MIN_SPEEDUP_RATIO,
        },
        "repeats": repeats,
        "workloads": rows,
        "summary": {
            "workload_count": len(rows),
            "exact_terminal_equivalence_count": len(terminal_rows),
            "repeated_resource_win_count": len(win_rows),
            "verified_sat_fast_path_workloads": sat_fast_paths,
            "general_acceleration_proved": False,
            "polynomial_bound_proved": False,
            "P_equals_NP_proved": False,
        },
        "self_use_gate": {
            "mode": "RECEIPT_LISTED_SAT_FAST_PATH_ONLY",
            "candidate_SAT_may_short_circuit_baseline_only_after_witness_verification": True,
            "candidate_SAT_may_short_circuit_only_for_persisted_speedup_eligible_workload": True,
            "candidate_UNSAT_may_short_circuit_baseline": False,
            "candidate_OPEN_may_short_circuit_baseline": False,
            "unlisted_workload_may_assume_speedup": False,
            "fallback_to_reference_dpll_required": True,
            "authority_delta": 0,
        },
        "firewalls": [
            "EXHAUSTIVE_ORACLE_SPEEDUP != ACCELERATOR_EVIDENCE",
            "DPLL_SHADOW_SPEEDUP != GENERAL_SPEEDUP",
            "SHADOW_SPEEDUP != POLYNOMIAL_BOUND",
            "SHADOW_SPEEDUP != P_EQUALS_NP",
            "SAT_WITNESS_VERIFIED + SPEEDUP_ELIGIBLE_WORKLOAD => BOUNDED_POSITIVE_FAST_PATH_ONLY",
            "CANDIDATE_UNSAT_REQUIRES_INDEPENDENT_RELEASE_GRADE_CERTIFICATE_OR_REFERENCE_SOLVER",
            "UNLISTED_WORKLOAD => REFERENCE_DPLL_FALLBACK",
            "OPEN != NEGATIVE_EVIDENCE",
            "P_VS_NP = OPEN",
        ],
        "P_VS_NP": "OPEN",
    }
    obj["receipt_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def solve_with_verified_sat_fast_path(mod, clauses, shadow_receipt: dict, workload_id: str | None = None) -> dict:
    """Use TRUMP early only for receipt-listed speedup-eligible SAT classes; otherwise DPLL."""
    eligible = set((shadow_receipt.get("summary") or {}).get("verified_sat_fast_path_workloads") or [])
    if workload_id in eligible:
        candidate = mod.solve_fail_closed(clauses)
        sem = _candidate_semantics(mod, clauses, candidate)
        if candidate.get("status") == "SAT" and sem.get("witness_verified") is True:
            return {
                "status": "SAT",
                "source": "TRUMP_VERIFIED_SPEEDUP_ELIGIBLE_SAT_FAST_PATH",
                "witness": candidate.get("witness"),
                "workload_id": workload_id,
            }
        candidate_status = candidate.get("status")
    else:
        candidate_status = "NOT_RUN_UNLISTED_WORKLOAD"
    reference = reference_dpll_baseline(clauses)
    return {
        "status": reference["status"],
        "source": "REFERENCE_DPLL_FALLBACK",
        "witness": reference.get("witness"),
        "candidate_status": candidate_status,
        "workload_id": workload_id,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = ap.parse_args()
    obj = run_shadow(Path(args.candidate), repeats=args.repeats)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "exact": obj["summary"]["exact_terminal_equivalence_count"],
        "wins": obj["summary"]["repeated_resource_win_count"],
        "sat_fast_paths": obj["summary"]["verified_sat_fast_path_workloads"],
        "P_VS_NP": obj["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
