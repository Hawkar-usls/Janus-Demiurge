#!/usr/bin/env python3
"""Execute the pre-frozen TRUMP Slime pivot-order R1 benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Sequence

from looking_for_something_policy import paid_work
from trump_candidate import canonical_bytes
from trump_slime_pivot_adapter_r1 import (
    generate_root_pivot_priorities,
    load_pinned_solver,
    load_pinned_v3_donor,
    solve_canonical,
    solve_with_front,
)

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_PIVOT_R1_FROZEN_BENCH_V1.json"


def canonical_clause(values: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted((int(v) for v in values), key=lambda z: (abs(z), z < 0)))


def connected_random_3cnf(seed: int, *, variables: int = 10, clauses: int = 42) -> list[list[int]]:
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
        support = rng.sample(range(1, variables + 1), 3)
        add_support(support)
    return [list(c) for c in out]


def exact_digest(result: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(result)).hexdigest()


def run_exact_replay(fn):
    first = fn()
    second = fn()
    if canonical_bytes(first) != canonical_bytes(second):
        raise RuntimeError("EXACT_REPLAY_MISMATCH")
    return first, exact_digest(first)


def summarize_exact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result["status"],
        "reason": result.get("reason"),
        "paid_work": paid_work(result),
        "residual_units": int(result.get("residual_units", 0)),
        "question_count": int((result.get("ledger") or {}).get("question_count", 0)),
        "proposal_work": int((result.get("ledger") or {}).get("proposal_work", 0)),
        "elimination_pair_work": int((result.get("ledger") or {}).get("elimination_pair_work", 0)),
        "digest": exact_digest(result),
    }


def benchmark_formula(
    clauses: list[list[int]],
    *,
    solver,
    donor,
    profile: dict[str, int],
    all_fronts: bool,
    selected_front: str | None = None,
) -> dict[str, Any]:
    generated = generate_root_pivot_priorities(clauses, donor_module=donor)
    root = solver.canon_cnf(clauses)
    fp = solver.fingerprint(root)
    kwargs = {
        "cap_exponent": int(profile["cap_exponent"]),
        "extension_exponent": int(profile["extension_exponent"]),
        "bounded_resolution_width": int(profile["bounded_resolution_width"]),
    }
    baseline, baseline_replay = run_exact_replay(lambda: solve_canonical(solver, clauses, **kwargs))
    row: dict[str, Any] = {
        "fingerprint": fp,
        "slime_generation_ops": generated["slime_generation_ops"],
        "canonical": summarize_exact(baseline),
        "canonical_replay_digest": baseline_replay,
        "fronts": {},
    }
    names = sorted(generated["priorities"]) if all_fronts else [str(selected_front)]
    for name in names:
        if name not in generated["priorities"]:
            raise RuntimeError(f"SELECTED_FRONT_NOT_IN_FROZEN_DONOR:{name}")
        priority = generated["priorities"][name]
        wrapped, replay_digest = run_exact_replay(
            lambda name=name, priority=priority: solve_with_front(
                solver,
                clauses,
                front_name=name,
                pivot_priority=priority,
                **kwargs,
            )
        )
        exact = wrapped["exact_result"]
        row["fronts"][name] = {
            **summarize_exact(exact),
            "pivot_priority": list(priority),
            "pivot_order_calls": wrapped["pivot_adapter"]["pivot_order_calls"],
            "pivot_order_reorders": wrapped["pivot_adapter"]["pivot_order_reorders"],
            "replay_digest": replay_digest,
        }
    return row


def aggregate(rows: list[dict[str, Any]], front_name: str | None) -> dict[str, Any]:
    if front_name is None:
        items = [row["canonical"] for row in rows]
    else:
        items = [row["fronts"][front_name] for row in rows]
    return {
        "formula_count": len(items),
        "decisive_count": sum(x["status"] in {"SAT", "UNSAT"} for x in items),
        "sat_count": sum(x["status"] == "SAT" for x in items),
        "unsat_count": sum(x["status"] == "UNSAT" for x in items),
        "open_count": sum(x["status"] == "OPEN" for x in items),
        "total_exact_paid_work": sum(int(x["paid_work"]) for x in items),
        "total_proposal_work": sum(int(x["proposal_work"]) for x in items),
        "total_elimination_pair_work": sum(int(x["elimination_pair_work"]) for x in items),
    }


def select_front(training_rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    names = sorted(training_rows[0]["fronts"])
    ranked = []
    for name in names:
        stats = aggregate(training_rows, name)
        ranked.append({"front_name": name, **stats})
    ranked.sort(key=lambda r: (-r["decisive_count"], r["total_exact_paid_work"], r["front_name"]))
    return ranked[0]["front_name"], ranked


def contradiction_count(rows: list[dict[str, Any]], selected: str) -> int:
    bad = 0
    for row in rows:
        a = row["canonical"]["status"]
        b = row["fronts"][selected]["status"]
        if a in {"SAT", "UNSAT"} and b in {"SAT", "UNSAT"} and a != b:
            bad += 1
    return bad


def execute() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_PIVOT_R1_FROZEN_C1K0_BENCH_V1":
        raise RuntimeError("FROZEN_SPEC_ID_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise RuntimeError("WINNER_MUST_NOT_BE_PREREGISTERED")

    solver, source = load_pinned_solver()
    donor, donor_manifest = load_pinned_v3_donor()
    if source["pinned_commit"] != spec["solver"]["commit"] or source["git_blob_sha"] != spec["solver"]["git_blob_sha"]:
        raise RuntimeError("SOLVER_PIN_DRIFT")
    if donor_manifest["pinned_commit"] != spec["donor"]["commit"]:
        raise RuntimeError("DONOR_PIN_DRIFT")

    gen = spec["formula_generator"]
    profile = {
        "cap_exponent": spec["solver_profile"]["cap_exponent"],
        "extension_exponent": spec["solver_profile"]["extension_exponent"],
        "bounded_resolution_width": spec["solver_profile"]["bounded_resolution_width"],
    }
    train_formulas = [
        (seed, connected_random_3cnf(seed, variables=gen["variables"], clauses=gen["clauses"]))
        for seed in spec["split"]["training_seeds"]
    ]
    holdout_formulas = [
        (seed, connected_random_3cnf(seed, variables=gen["variables"], clauses=gen["clauses"]))
        for seed in spec["split"]["holdout_seeds"]
    ]

    train_rows = []
    for seed, formula in train_formulas:
        row = benchmark_formula(formula, solver=solver, donor=donor, profile=profile, all_fronts=True)
        row["seed"] = seed
        train_rows.append(row)
    selected, training_ranking = select_front(train_rows)

    # Holdout starts only after the front is selected from training rows.
    holdout_rows = []
    for seed, formula in holdout_formulas:
        row = benchmark_formula(
            formula,
            solver=solver,
            donor=donor,
            profile=profile,
            all_fronts=False,
            selected_front=selected,
        )
        row["seed"] = seed
        holdout_rows.append(row)

    train_fps = {row["fingerprint"] for row in train_rows}
    holdout_fps = {row["fingerprint"] for row in holdout_rows}
    if train_fps & holdout_fps:
        raise RuntimeError("TRAIN_HOLDOUT_FINGERPRINT_COLLISION")

    baseline = aggregate(holdout_rows, None)
    slime = aggregate(holdout_rows, selected)
    contradictions = contradiction_count(holdout_rows, selected)
    decisive_ok = slime["decisive_count"] >= baseline["decisive_count"]
    work_ok = (
        True
        if slime["decisive_count"] > baseline["decisive_count"]
        else slime["total_exact_paid_work"] <= baseline["total_exact_paid_work"]
    )
    strict = (
        slime["decisive_count"] > baseline["decisive_count"]
        or (
            slime["decisive_count"] == baseline["decisive_count"]
            and slime["total_exact_paid_work"] < baseline["total_exact_paid_work"]
        )
    )
    status = "PASS" if contradictions == 0 and decisive_ok and work_ok and strict else "FAIL"
    claim = spec["pass_claim"] if status == "PASS" else spec["fail_claim"]

    return {
        "schema": "janus.trump.slime_pivot_r1.frozen_benchmark.result.v1",
        "benchmark_id": spec["benchmark_id"],
        "status": status,
        "claim": claim,
        "freeze_commit_before_adapter_and_runner": "b035cf9babc2d69bfc122b6d5602b74ab6905ec9",
        "winner_preregistered": False,
        "selected_front_from_training_only": selected,
        "profile": profile,
        "training": {
            "front_ranking": training_ranking,
            "canonical": aggregate(train_rows, None),
            "formula_fingerprints": [row["fingerprint"] for row in train_rows],
            "rows": train_rows,
        },
        "holdout": {
            "canonical": baseline,
            "selected_front": slime,
            "contradictory_exact_decisive_results": contradictions,
            "formula_fingerprints": [row["fingerprint"] for row in holdout_rows],
            "rows": holdout_rows,
            "gate": {
                "no_exact_contradictions": contradictions == 0,
                "decisive_count_not_worse": decisive_ok,
                "exact_paid_work_not_worse_when_decisive_equal": work_ok,
                "strict_improvement": strict,
            },
        },
        "slime_generation_ops": {
            "training_total": sum(row["slime_generation_ops"] for row in train_rows),
            "holdout_total": sum(row["slime_generation_ops"] for row in holdout_rows),
            "charged_separately_from_exact_solver_paid_work": True,
        },
        "claim_boundary": {
            "end_to_end_wall_clock_or_net_resource_speedup": False,
            "universal_sat_speedup": False,
            "Slime_order_is_proof": False,
            "P_VS_NP": "OPEN",
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
    return 0 if result["status"] == "PASS" or not args.require_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
