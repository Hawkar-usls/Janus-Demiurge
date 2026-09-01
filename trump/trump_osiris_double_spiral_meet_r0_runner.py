#!/usr/bin/env python3
"""Frozen holdout runner for TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R0."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
from typing import List

from trump_osiris_double_spiral_meet_r0 import (
    dense_control_formula,
    double_spiral_meet,
    exact_search,
    formula_digest,
    structured_holdout_formula,
    verify_root_sat,
)

SAT_SEEDS = [7101, 7102, 7103, 7104, 7105, 7106]
UNSAT_SEEDS = [7201, 7202, 7203, 7204, 7205, 7206]
DENSE_SEEDS = [7301, 7302, 7303, 7304, 7305, 7306]


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run_one(case_id: str, family: str, seed: int, clauses) -> dict:
    baseline_terminal, baseline_witness, baseline_work = exact_search(clauses)
    candidate = double_spiral_meet(clauses, max_separator_size=2)

    terminal_match = candidate.terminal == baseline_terminal
    candidate_sat_replay = True
    baseline_sat_replay = True
    if candidate.terminal == "SAT":
        candidate_sat_replay = verify_root_sat(clauses, candidate.witness)
    if baseline_terminal == "SAT":
        baseline_sat_replay = verify_root_sat(clauses, baseline_witness)

    return {
        "case_id": case_id,
        "family": family,
        "seed": seed,
        "formula_sha256": formula_digest(clauses),
        "variables": len({abs(lit) for clause in clauses for lit in clause}),
        "clauses": len(clauses),
        "baseline": {
            "terminal": baseline_terminal,
            "root_replay": baseline_sat_replay,
            "exact_nodes": baseline_work.nodes,
            "prunes": baseline_work.prunes,
            "leaves": baseline_work.leaves,
        },
        "candidate": candidate.as_dict(),
        "checks": {
            "terminal_match": terminal_match,
            "candidate_sat_root_replay": candidate_sat_replay,
            "baseline_sat_root_replay": baseline_sat_replay,
            "truth_contradiction": not terminal_match,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--receipt",
        default="trump/TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R0_RECEIPT.json",
    )
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    core_path = here / "trump_osiris_double_spiral_meet_r0.py"
    spec_path = here / "TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R0_FROZEN_SPEC.json"
    runner_path = Path(__file__).resolve()

    rows: List[dict] = []
    for seed in SAT_SEEDS:
        rows.append(run_one(f"STRUCTURED_SAT_{seed}", "STRUCTURED_SAT", seed, structured_holdout_formula(seed, "SAT")))
    for seed in UNSAT_SEEDS:
        rows.append(run_one(f"STRUCTURED_UNSAT_{seed}", "STRUCTURED_UNSAT", seed, structured_holdout_formula(seed, "UNSAT")))
    for seed in DENSE_SEEDS:
        rows.append(run_one(f"DENSE_CONTROL_{seed}", "DENSE_CONTROL", seed, dense_control_formula(seed)))

    terminal_matches = sum(1 for row in rows if row["checks"]["terminal_match"])
    truth_contradictions = sum(1 for row in rows if row["checks"]["truth_contradiction"])
    sat_replay_failures = sum(
        1 for row in rows
        if row["candidate"]["terminal"] == "SAT" and not row["checks"]["candidate_sat_root_replay"]
    )
    structured_rows = [row for row in rows if row["family"].startswith("STRUCTURED_")]
    structured_meet_exposure = sum(
        1 for row in structured_rows if row["candidate"]["mode"] == "EXACT_DOUBLE_SPIRAL_MEET"
    )
    dense_rows = [row for row in rows if row["family"] == "DENSE_CONTROL"]
    dense_fallbacks = sum(
        1 for row in dense_rows if row["candidate"]["mode"] == "NO_MEET_EXACT_FALLBACK"
    )

    baseline_total = sum(row["baseline"]["exact_nodes"] for row in rows)
    candidate_total = sum(row["candidate"]["work"]["charged_abstract_ops"] for row in rows)
    structured_baseline = sum(row["baseline"]["exact_nodes"] for row in structured_rows)
    structured_candidate = sum(row["candidate"]["work"]["charged_abstract_ops"] for row in structured_rows)
    dense_baseline = sum(row["baseline"]["exact_nodes"] for row in dense_rows)
    dense_candidate = sum(row["candidate"]["work"]["charged_abstract_ops"] for row in dense_rows)

    primary_pass = (
        terminal_matches == len(rows)
        and truth_contradictions == 0
        and sat_replay_failures == 0
        and structured_meet_exposure == len(structured_rows)
    )
    secondary_work_pass = candidate_total < baseline_total

    receipt = {
        "schema": "JANUS/TRUMP/OSIRIS-DOUBLE-SPIRAL-MEET-R0-RECEIPT/v1.0",
        "experiment_id": "TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R0",
        "status": (
            "PRIMARY_EXACT_MEET_PASS__SECONDARY_WORK_PASS__P_VS_NP_OPEN"
            if primary_pass and secondary_work_pass
            else "PRIMARY_EXACT_MEET_PASS__SECONDARY_WORK_FAIL__P_VS_NP_OPEN"
            if primary_pass
            else "PRIMARY_EXACT_MEET_FAIL__P_VS_NP_OPEN"
        ),
        "frozen_meta_prereg_commit": "7a74da731c948e6ef663877c9b4f940201ede3ea",
        "runtime": {
            "repository": "Hawkar-usls/Janus-Demiurge",
            "branch": "research/trump-osiris-double-spiral-meet-r0",
            "github_sha": os.environ.get("GITHUB_SHA"),
            "python": sys.version,
            "platform": platform.platform(),
            "source_sha256": {
                "core": file_sha256(core_path),
                "runner": file_sha256(runner_path),
                "frozen_spec": file_sha256(spec_path),
            },
        },
        "frozen_holdout": {
            "structured_sat_seeds": SAT_SEEDS,
            "structured_unsat_seeds": UNSAT_SEEDS,
            "dense_control_seeds": DENSE_SEEDS,
            "case_count": len(rows),
            "same_holdout_learning": False,
        },
        "primary_gate": {
            "pass": primary_pass,
            "terminal_matches": terminal_matches,
            "required_terminal_matches": len(rows),
            "truth_contradictions": truth_contradictions,
            "sat_root_replay_failures": sat_replay_failures,
            "structured_meet_exposure": structured_meet_exposure,
            "required_structured_meet_exposure": len(structured_rows),
        },
        "secondary_work_gate": {
            "pass": secondary_work_pass,
            "metric": "charged_abstract_ops_not_wall_clock",
            "baseline_exact_nodes_total": baseline_total,
            "candidate_charged_ops_total": candidate_total,
            "saved_abstract_ops": baseline_total - candidate_total,
            "saved_fraction": 0.0 if baseline_total == 0 else (baseline_total - candidate_total) / baseline_total,
            "structured": {
                "baseline_exact_nodes": structured_baseline,
                "candidate_charged_ops": structured_candidate,
                "saved": structured_baseline - structured_candidate,
            },
            "dense_controls": {
                "baseline_exact_nodes": dense_baseline,
                "candidate_charged_ops": dense_candidate,
                "overhead": dense_candidate - dense_baseline,
                "exact_fallbacks": dense_fallbacks,
                "case_count": len(dense_rows),
            },
            "claim_ceiling": "finite frozen abstract-work comparison only; not runtime speedup, asymptotic complexity, or generalization",
        },
        "mechanism_observation": {
            "law_tested": "FORWARD_BUILDS_THE_BOUNDARY || REVERSE_BUILDS_THE_OBLIGATION -> MEET_ONLY_ON_EXACT_WITNESS",
            "actual_meet_definition": "left and right exact feasibility relations intersect on the same canonical separator assignment S",
            "prior_bidirectional_schedule_reused_as_authority": False,
            "R5_C025_authority_changed": False,
            "R6_router_changed": False,
        },
        "rows": rows,
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "polynomial_time_SAT_proved": False,
            "general_solver_speedup_established": False,
            "natural_TRUMP_residual_generalization_established": False,
            "canonical_runtime_promotion_authorized": False,
        },
        "next_gate_if_primary_passes": "R1_SHADOW_ONLY_ON_FRESH_NATURAL_UNENRICHED_TRUMP_RESIDUALS_WITH_UNCHANGED_R5_C025_REPLAY",
    }

    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=False))
    return 0 if primary_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
