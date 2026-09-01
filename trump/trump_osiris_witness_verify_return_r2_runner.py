#!/usr/bin/env python3
"""Frozen prospective runner for the R2 witness/verify/return shadow overlay."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
from typing import List

from trump_osiris_double_spiral_meet_r0 import dense_control_formula, structured_holdout_formula
from trump_osiris_witness_verify_return_r2_shadow import (
    RULE_ID,
    prospective_pattern_admission_gate,
    witness_verify_return_r2_shadow,
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case_id: str, family: str, seed: int, clauses) -> dict:
    result = witness_verify_return_r2_shadow(clauses).as_dict()
    return {
        "case_id": case_id,
        "family": family,
        "seed": seed,
        **result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default="trump/TRUMP_OSIRIS_WITNESS_VERIFY_RETURN_R2_RECEIPT.json")
    parser.add_argument("--spec", default="trump/TRUMP_OSIRIS_WITNESS_VERIFY_RETURN_R2_FROZEN_SPEC.json")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    spec_path = Path(args.spec)
    spec = load_spec(spec_path)
    frozen = spec["fresh_holdout"]

    rows: List[dict] = []
    for seed in frozen["structured_sat_seeds"]:
        rows.append(run_case(f"STRUCTURED_SAT_{seed}", "STRUCTURED_SAT", seed, structured_holdout_formula(seed, "SAT")))
    for seed in frozen["structured_unsat_seeds"]:
        rows.append(run_case(f"STRUCTURED_UNSAT_{seed}", "STRUCTURED_UNSAT", seed, structured_holdout_formula(seed, "UNSAT")))
    for seed in frozen["dense_control_seeds"]:
        rows.append(run_case(f"DENSE_CONTROL_{seed}", "DENSE_CONTROL", seed, dense_control_formula(seed)))

    unique_witnesses = len({r["pre_verification_witness"]["witness_sha256"] for r in rows})
    preserved_pretruth = sum(
        r["pre_verification_witness"]["payload"]["stage"] == "PRESERVED_BEFORE_TRUTH_VERIFICATION"
        and r["pre_verification_witness"]["payload"]["truth"] is None
        for r in rows
    )
    verification_passes = sum(r["independent_verification"]["verification_pass"] for r in rows)
    terminal_matches = sum(r["independent_verification"]["terminal_match"] for r in rows)
    replay_failures = sum(
        not r["independent_verification"]["candidate_sat_root_replay"]
        or not r["independent_verification"]["baseline_sat_root_replay"]
        for r in rows
    )
    experience_eligible = sum(r["return_higher"]["experience_eligible"] for r in rows)
    pattern_support = sum(r["return_higher"]["pattern_support"] for r in rows)

    gate = prospective_pattern_admission_gate(rows, rule_frozen_before_holdout=True)
    primary_pass = (
        len(rows) == frozen["case_count"]
        and unique_witnesses == len(rows)
        and preserved_pretruth == len(rows)
        and verification_passes == len(rows)
        and terminal_matches == len(rows)
        and replay_failures == 0
        and experience_eligible == len(rows)
    )

    receipt = {
        "schema": "JANUS/TRUMP/OSIRIS-WITNESS-VERIFY-RETURN-R2-RECEIPT/v1.0",
        "experiment_id": "TRUMP_OSIRIS_WITNESS_VERIFY_RETURN_R2_SHADOW",
        "status": (
            "PRIMARY_EPISTEMIC_AUTOMATON_PASS__PATTERN_GATE_PASS__SHADOW_ONLY__P_VS_NP_OPEN"
            if primary_pass and gate["pass"]
            else "PRIMARY_EPISTEMIC_AUTOMATON_PASS__PATTERN_GATE_FAIL__SHADOW_ONLY__P_VS_NP_OPEN"
            if primary_pass
            else "PRIMARY_FAIL__SHADOW_ONLY__P_VS_NP_OPEN"
        ),
        "runtime": {
            "repository": "Hawkar-usls/Janus-Demiurge",
            "branch": "research/trump-osiris-witness-verify-return-r2-shadow",
            "github_sha": os.environ.get("GITHUB_SHA"),
            "python": sys.version,
            "platform": platform.platform(),
            "source_sha256": {
                "R2_shadow_core": file_sha256(here / "trump_osiris_witness_verify_return_r2_shadow.py"),
                "R2_runner": file_sha256(Path(__file__).resolve()),
                "R2_frozen_spec": file_sha256(spec_path),
            },
        },
        "frozen_rule": {
            "rule_id": RULE_ID,
            "spec_sha256": file_sha256(spec_path),
            "frozen_before_holdout": True,
            "same_holdout_learning": False,
        },
        "primary_gate": {
            "pass": primary_pass,
            "cases": len(rows),
            "required_cases": frozen["case_count"],
            "unique_preverification_witnesses": unique_witnesses,
            "preserved_before_truth_verification": preserved_pretruth,
            "independent_verification_passes": verification_passes,
            "terminal_matches": terminal_matches,
            "root_replay_failures": replay_failures,
            "verified_experience_records": experience_eligible,
        },
        "pattern_admission_gate": gate,
        "observed_pattern_support": {
            "support_cases": pattern_support,
            "total_cases": len(rows),
            "fraction": 0.0 if not rows else pattern_support / len(rows),
        },
        "authority_firewall": {
            "pattern_proof_authority": False,
            "witness_proof_authority": False,
            "verified_experience_proof_authority": False,
            "current_holdout_routing_authority": False,
            "future_routing_memory_eligible_if_pattern_gate_passes": bool(gate["pass"]),
            "SAT_UNSAT_authority": "INDEPENDENT_EXACT_ROOT_SEARCH_AND_ROOT_REPLAY_ONLY",
        },
        "rows": rows,
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "polynomial_time_SAT_proved": False,
            "general_solver_speedup_established": False,
            "natural_TRUMP_residual_generalization_established": False,
            "claim": "fresh same-generator-family prospective validation of OBSERVE->PRESERVE->VERIFY->RETURN_HIGHER shadow semantics only",
        },
        "next_gate": "R3_NATURAL_UNENRICHED_TRUMP_RESIDUALS_WITH_R2_MEMORY_SHADOW_AND_EXACT_R5_C025_REPLAY",
        "law": "PATTERN_IS_NOT_TRUTH__WITNESS_IS_NOT_ANSWER__PRESERVE_THEN_VERIFY__ONLY_VERIFIED_EXPERIENCE_RETURNS_HIGHER",
    }

    out = Path(args.receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if primary_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
