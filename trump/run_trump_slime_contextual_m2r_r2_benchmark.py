#!/usr/bin/env python3
"""Run the pre-frozen contextual M2R Slime R2 holdout benchmark."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Sequence

from looking_for_something_policy import paid_work
from trump_candidate import canonical_bytes
from trump_slime_contextual_m2r_r2 import load_frozen_spec, load_pinned_solver, solve_contextual

HERE = Path(__file__).resolve().parent
FREEZE_COMMIT = "f17959eb5f9fa8d9a7d7f08240cc32d8e7c17859"


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


def replay_exact(fn):
    first = fn()
    second = fn()
    if canonical_bytes(first) != canonical_bytes(second):
        raise RuntimeError("EXACT_REPLAY_MISMATCH")
    return first


def exact_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result["status"],
        "reason": result.get("reason"),
        "paid_work": paid_work(result),
        "proposal_work": int((result.get("ledger") or {}).get("proposal_work", 0)),
        "elimination_pair_work": int((result.get("ledger") or {}).get("elimination_pair_work", 0)),
        "digest": hashlib.sha256(canonical_bytes(result)).hexdigest(),
    }


def boundary_ok(result: dict[str, Any]) -> bool:
    sb = result.get("scientific_boundary") or {}
    return (
        result.get("status") in {"SAT", "UNSAT", "OPEN"}
        and sb.get("P_VS_NP") == "OPEN"
        and sb.get("claims_p_eq_np") is False
        and sb.get("claims_p_neq_np") is False
        and sb.get("heuristic_promotion") is False
        and sb.get("general_sat_oracle") is False
        and sb.get("semantic_equivalence_oracle") is False
    )


def run_formula(solver, clauses, profile) -> dict[str, Any]:
    baseline = replay_exact(lambda: solver.solve_fail_closed(clauses, **profile))
    if not boundary_ok(baseline):
        raise RuntimeError("CANONICAL_BOUNDARY_DRIFT")

    contextual_first = solve_contextual(solver, clauses, **profile)
    contextual_second = solve_contextual(solver, clauses, **profile)
    if canonical_bytes(contextual_first["exact_result"]) != canonical_bytes(contextual_second["exact_result"]):
        raise RuntimeError("CONTEXTUAL_EXACT_REPLAY_MISMATCH")
    if contextual_first["slime_telemetry"] != contextual_second["slime_telemetry"]:
        raise RuntimeError("CONTEXTUAL_TELEMETRY_REPLAY_MISMATCH")
    exact = contextual_first["exact_result"]
    if not boundary_ok(exact):
        raise RuntimeError("CONTEXTUAL_BOUNDARY_DRIFT")

    feature_work = int(contextual_first["slime_telemetry"]["feature_work"])
    contextual_summary = exact_summary(exact)
    contextual_summary["feature_work"] = feature_work
    contextual_summary["combined_work"] = contextual_summary["paid_work"] + feature_work
    contextual_summary["slime_telemetry"] = contextual_first["slime_telemetry"]
    return {"canonical": exact_summary(baseline), "contextual": contextual_summary}


def aggregate(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    items = [r[key] for r in rows]
    out = {
        "formula_count": len(items),
        "decisive_count": sum(x["status"] in {"SAT", "UNSAT"} for x in items),
        "sat_count": sum(x["status"] == "SAT" for x in items),
        "unsat_count": sum(x["status"] == "UNSAT" for x in items),
        "open_count": sum(x["status"] == "OPEN" for x in items),
        "total_exact_paid_work": sum(int(x["paid_work"]) for x in items),
        "total_proposal_work": sum(int(x["proposal_work"]) for x in items),
        "total_elimination_pair_work": sum(int(x["elimination_pair_work"]) for x in items),
    }
    if key == "contextual":
        out["total_feature_work"] = sum(int(x["feature_work"]) for x in items)
        out["total_combined_work"] = sum(int(x["combined_work"]) for x in items)
        out["total_pivot_order_calls"] = sum(int(x["slime_telemetry"]["pivot_order_calls"]) for x in items)
        out["total_pivot_order_reorders"] = sum(int(x["slime_telemetry"]["pivot_order_reorders"]) for x in items)
        out["calls_with_certified_safe_pivot"] = sum(int(x["slime_telemetry"]["calls_with_certified_safe_pivot"]) for x in items)
    return out


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
    for seed in spec["holdout"]["seeds"]:
        formula = connected_random_3cnf(seed, variables=int(gen["variables"]), clauses=int(gen["clauses"]))
        fp = solver.fingerprint(solver.canon_cnf(formula))
        fingerprints.append(fp)
        row = run_formula(solver, formula, profile)
        row["seed"] = int(seed)
        row["fingerprint"] = fp
        rows.append(row)
    if len(set(fingerprints)) != len(fingerprints):
        raise RuntimeError("HOLDOUT_FINGERPRINT_COLLISION")

    canonical = aggregate(rows, "canonical")
    contextual = aggregate(rows, "contextual")
    contradictions = 0
    for row in rows:
        a = row["canonical"]["status"]
        b = row["contextual"]["status"]
        if a in {"SAT", "UNSAT"} and b in {"SAT", "UNSAT"} and a != b:
            contradictions += 1

    decisive_ok = contextual["decisive_count"] >= canonical["decisive_count"]
    combined_ok = (
        True
        if contextual["decisive_count"] > canonical["decisive_count"]
        else contextual["total_combined_work"] <= canonical["total_exact_paid_work"]
    )
    strict = (
        contextual["decisive_count"] > canonical["decisive_count"]
        or (
            contextual["decisive_count"] == canonical["decisive_count"]
            and contextual["total_combined_work"] < canonical["total_exact_paid_work"]
        )
    )
    status = "PASS" if contradictions == 0 and decisive_ok and combined_ok and strict else "FAIL"
    return {
        "schema": "janus.trump.slime_contextual_m2r_r2.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": spec["pass_claim"] if status == "PASS" else spec["fail_claim"],
        "freeze_commit_before_R2_implementation": FREEZE_COMMIT,
        "winner_preregistered": False,
        "policy_selected_on_holdout": False,
        "profile": profile,
        "solver_source": source,
        "holdout": {
            "fingerprints": fingerprints,
            "canonical": canonical,
            "contextual_m2r_r2": contextual,
            "contradictory_exact_decisive_results": contradictions,
            "gate": {
                "no_exact_contradictions": contradictions == 0,
                "decisive_count_not_worse": decisive_ok,
                "combined_work_not_worse_when_decisive_equal": combined_ok,
                "strict_improvement": strict,
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
            "finite_holdout_implies_polynomial": False,
            "heuristic_order_is_proof": False,
            "end_to_end_wall_clock_speedup_claimed": False,
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
