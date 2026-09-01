#!/usr/bin/env python3
"""Frozen fresh-holdout runner for TRUMP OSIRIS double-spiral R1."""

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
    exact_search,
    formula_digest,
    structured_holdout_formula,
    verify_root_sat,
)
from trump_osiris_double_spiral_meet_r1_advisory import double_spiral_meet_r1

SAT_SEEDS = [8101,8102,8103,8104,8105,8106,8107,8108]
UNSAT_SEEDS = [8201,8202,8203,8204,8205,8206,8207,8208]
DENSE_SEEDS = [8301,8302,8303,8304,8305,8306,8307,8308]


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run_one(case_id: str, family: str, seed: int, clauses) -> dict:
    baseline_terminal, baseline_witness, baseline_work = exact_search(clauses)
    candidate = double_spiral_meet_r1(clauses)
    terminal_match = candidate.terminal == baseline_terminal
    candidate_replay = candidate.terminal != "SAT" or verify_root_sat(clauses, candidate.witness)
    baseline_replay = baseline_terminal != "SAT" or verify_root_sat(clauses, baseline_witness)
    return {
        "case_id": case_id,
        "family": family,
        "seed": seed,
        "formula_sha256": formula_digest(clauses),
        "baseline": {
            "terminal": baseline_terminal,
            "exact_nodes": baseline_work.nodes,
            "root_replay": baseline_replay,
        },
        "candidate": candidate.as_dict(),
        "checks": {
            "terminal_match": terminal_match,
            "candidate_sat_root_replay": candidate_replay,
            "truth_contradiction": not terminal_match,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default="trump/TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R1_RECEIPT.json")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    rows: List[dict] = []
    for seed in SAT_SEEDS:
        rows.append(run_one(f"STRUCTURED_SAT_{seed}", "STRUCTURED_SAT", seed, structured_holdout_formula(seed, "SAT")))
    for seed in UNSAT_SEEDS:
        rows.append(run_one(f"STRUCTURED_UNSAT_{seed}", "STRUCTURED_UNSAT", seed, structured_holdout_formula(seed, "UNSAT")))
    for seed in DENSE_SEEDS:
        rows.append(run_one(f"DENSE_CONTROL_{seed}", "DENSE_CONTROL", seed, dense_control_formula(seed)))

    structured = [r for r in rows if r["family"].startswith("STRUCTURED_")]
    dense = [r for r in rows if r["family"] == "DENSE_CONTROL"]
    terminal_matches = sum(r["checks"]["terminal_match"] for r in rows)
    contradictions = sum(r["checks"]["truth_contradiction"] for r in rows)
    replay_failures = sum(
        1 for r in rows if r["candidate"]["terminal"] == "SAT" and not r["checks"]["candidate_sat_root_replay"]
    )
    meet_exposure = sum(
        1 for r in structured if r["candidate"]["mode"] == "ADVISORY_PROPOSAL_EXACT_DOUBLE_SPIRAL_MEET"
    )
    dense_skips = sum(
        1 for r in dense if r["candidate"]["advisory"]["decision"] == "DENSITY_SKIP_TO_EXACT_FALLBACK"
    )
    baseline_total = sum(r["baseline"]["exact_nodes"] for r in rows)
    candidate_total = sum(r["candidate"]["work"]["charged_abstract_ops"] for r in rows)
    structured_baseline = sum(r["baseline"]["exact_nodes"] for r in structured)
    structured_candidate = sum(r["candidate"]["work"]["charged_abstract_ops"] for r in structured)
    dense_baseline = sum(r["baseline"]["exact_nodes"] for r in dense)
    dense_candidate = sum(r["candidate"]["work"]["charged_abstract_ops"] for r in dense)
    proposal_ranks = [r["candidate"]["advisory"].get("proposal_rank") for r in structured]

    primary_pass = (
        terminal_matches == len(rows)
        and contradictions == 0
        and replay_failures == 0
        and meet_exposure == len(structured)
    )
    secondary_pass = candidate_total < baseline_total

    receipt = {
        "schema": "JANUS/TRUMP/OSIRIS-DOUBLE-SPIRAL-MEET-R1-RECEIPT/v1.0",
        "experiment_id": "TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R1_ADVISORY",
        "status": (
            "PRIMARY_PASS__SECONDARY_WORK_PASS__SAME_FAMILY_ONLY__P_VS_NP_OPEN"
            if primary_pass and secondary_pass
            else "PRIMARY_PASS__SECONDARY_WORK_FAIL__P_VS_NP_OPEN"
            if primary_pass
            else "PRIMARY_FAIL__P_VS_NP_OPEN"
        ),
        "frozen_meta_prereg_commit": "9ac877d1dce2073f6a468c7a596c3382c89e3a7a",
        "runtime": {
            "repository": "Hawkar-usls/Janus-Demiurge",
            "branch": "research/trump-osiris-double-spiral-meet-r1-advisory",
            "github_sha": os.environ.get("GITHUB_SHA"),
            "python": sys.version,
            "platform": platform.platform(),
            "source_sha256": {
                "R0_exact_core": file_sha256(here / "trump_osiris_double_spiral_meet_r0.py"),
                "R1_advisory_core": file_sha256(here / "trump_osiris_double_spiral_meet_r1_advisory.py"),
                "R1_runner": file_sha256(Path(__file__).resolve()),
                "R1_frozen_spec": file_sha256(here / "TRUMP_OSIRIS_DOUBLE_SPIRAL_MEET_R1_ADVISORY_FROZEN_SPEC.json"),
            },
        },
        "fresh_holdout": {
            "structured_sat_seeds": SAT_SEEDS,
            "structured_unsat_seeds": UNSAT_SEEDS,
            "dense_control_seeds": DENSE_SEEDS,
            "case_count": len(rows),
            "R0_validation_seeds_reused": False,
            "same_holdout_learning": False,
        },
        "primary_gate": {
            "pass": primary_pass,
            "terminal_matches": terminal_matches,
            "required": len(rows),
            "truth_contradictions": contradictions,
            "sat_root_replay_failures": replay_failures,
            "structured_meet_exposure": meet_exposure,
            "required_structured_meet_exposure": len(structured),
        },
        "advisory_behavior": {
            "dense_density_skips": dense_skips,
            "dense_case_count": len(dense),
            "structured_proposal_ranks": proposal_ranks,
            "max_structured_proposal_rank": max(x for x in proposal_ranks if x is not None),
        },
        "secondary_work_gate": {
            "pass": secondary_pass,
            "metric": "charged_abstract_ops_not_wall_clock",
            "baseline_exact_nodes_total": baseline_total,
            "candidate_charged_ops_total": candidate_total,
            "saved_abstract_ops": baseline_total - candidate_total,
            "saved_fraction": 0.0 if baseline_total == 0 else (baseline_total - candidate_total) / baseline_total,
            "structured": {
                "baseline": structured_baseline,
                "candidate": structured_candidate,
                "saved": structured_baseline - structured_candidate,
            },
            "dense": {
                "baseline": dense_baseline,
                "candidate": dense_candidate,
                "overhead": dense_candidate - dense_baseline,
            },
            "claim_ceiling": "fresh same-generator-family discovery-policy result only; not wall-clock speedup or general solver speedup",
        },
        "rows": rows,
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "polynomial_time_SAT_proved": False,
            "general_solver_speedup_established": False,
            "natural_TRUMP_residual_generalization_established": False,
            "R5_C025_authority_changed": False,
            "R6_authority_changed": False,
        },
        "next_gate_if_both_pass": "R2_NATURAL_UNENRICHED_TRUMP_RESIDUAL_SHADOW_WITH_EXACT_R5_C025_REPLAY",
    }

    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if primary_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
