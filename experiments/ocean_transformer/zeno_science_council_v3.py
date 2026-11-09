#!/usr/bin/env python3
"""JANUS Ocean V3: blinded-by-construction CPU physics reference council.

This is a preregistered *synthetic* computation suite for:
- quantum Zeno chain probability vs unconditional final measurement;
- a local qubit marginal before and after a later choice of basis on B;
- conditional (heralded) correlations that MUST NOT be interpreted as signals.

No hardware measurement, new training target, W|A network query, or
independent retrocausal physical effect is represented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import zeno_temporal_001 as zeno

SCHEMA = "janus.ocean.zeno_council_v3.v1"
EXPERIMENT = "JANUS-ZENO-TEMPORAL-002"
ANGLES = (0.0, math.pi / 8, math.pi / 4, math.pi / 2)
MAX_ERROR = 1e-12

# Three nonidentical physical quantities. All values are generated from
# independently stated analytic expressions and separately verified against
# the established CPU reference. No provider math has been run for these.
CHECKS = (
    ("zeno_n4_unconditional", "(1+cos(pi/4)^4)/2",
     "probability of A=0 at final Z readout ignoring earlier measurements"),
    ("zeno_n4_all_zero", "cos(pi/8)^8",
     "probability of ALL four Z measurement outcomes being zero"),
    ("bell_early_marginal", "1/2",
     "early P(A=0) ignoring later basis and outcomes"),
)


def bell_late_measurement(theta: float) -> dict:
    """Bell Phi+ with later B-only basis rotation, enumerated via amplitudes.

    Amplitudes in basis A,B:
       a00=cos(theta)/sqrt(2); a01=sin(theta)/sqrt(2)
       a10=-sin(theta)/sqrt(2); a11=cos(theta)/sqrt(2).
    Conditional quantities can vary, unconditioned A marginal cannot.
    """
    if type(theta) not in (int, float) or not math.isfinite(theta) or not 0 <= theta <= math.pi:
        raise ValueError("INVALID_LATE_BASIS")
    c, s = math.cos(theta), math.sin(theta)
    a00, a01, a10, a11 = c / math.sqrt(2), s / math.sqrt(2), -s / math.sqrt(2), c / math.sqrt(2)
    p00, p01, p10, p11 = (a00*a00, a01*a01, a10*a10, a11*a11)
    early = p00 + p01
    later_b0 = p00 + p10
    if abs(sum((p00, p01, p10, p11)) - 1) > MAX_ERROR:
        raise ArithmeticError("BELL_NORMALIZATION_BROKEN")
    if abs(early - .5) > MAX_ERROR or abs(later_b0 - .5) > MAX_ERROR:
        raise ArithmeticError("BELL_NO_SIGNALLING_VIOLATED")
    return {
        "late_basis_theta_radians": theta,
        "early_p_a0_before_late_choice": .5,
        "early_p_a0_unconditioned_after_late_choice": early,
        "late_p_b0": later_b0,
        "postselected_p_a0_given_b0": p00 / later_b0,
        "postselected_fraction": later_b0,
        "raw_four_joint_probabilities": [p00, p01, p10, p11],
        "independent_early_marginal_check": True,
    }


def reference_cases() -> list[dict]:
    n4 = zeno.probabilities(math.pi, 4)
    reference = (
        (1 + math.cos(math.pi / 4)**4) / 2,
        math.cos(math.pi / 8)**8,
        .5,
    )
    expected_from_cpu = (
        n4["unconditional_final_p0"],
        n4["all_zero_measurement_record_probability"],
        bell_late_measurement(math.pi/4)["early_p_a0_unconditioned_after_late_choice"],
    )
    result = []
    for (name, expression, definition), value, cpu in zip(CHECKS, reference, expected_from_cpu):
        if abs(value-cpu) > MAX_ERROR:
            raise ArithmeticError("ANALYTIC_AND_CPU_REFERENCE_DISAGREE")
        result.append({
            "case_id": name,
            "public_wolfram_expression": expression,
            "physical_event": definition,
            "analytical_reference": value,
            "cpu_reference": cpu,
            "reference_consistent": True,
            "remote_wolfram_checked_for_this_case": False,
        })
    return result


def build_report() -> dict:
    cases = reference_cases()
    rows = [bell_late_measurement(theta) for theta in ANGLES]
    unconditioned = [r["early_p_a0_unconditioned_after_late_choice"] for r in rows]
    heralded = [r["postselected_p_a0_given_b0"] for r in rows]
    if max(unconditioned)-min(unconditioned) > MAX_ERROR:
        raise ArithmeticError("RAW_EARLY_MARGINAL_CHANGED_BY_LATE_CHOICE")
    if max(heralded)-min(heralded) < .9:
        raise ArithmeticError("POSTSELECTION_CONTROL_NOT_DISCRIMINATING")
    report = {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT,
        "lineage": "JANUS-ZENO-TEMPORAL-001",
        "benchmark_scope": "SYNTHETIC_STANDARD_QUANTUM_MECHANICS_CPU_ONLY",
        "source_hypothesis": "https://youtu.be/e4k4kHzbYyU?t=837",
        "predeclared_case_ids": [name for name, _, _ in CHECKS],
        "analytic_crosschecks": cases,
        "late_basis_choices_radians": list(ANGLES),
        "full_joint_probability_controls": rows,
        "unconditional_max_min_difference": max(unconditioned)-min(unconditioned),
        "postselection_conditional_range": max(heralded)-min(heralded),
        "logic": {
            "no_signalling": "PASS_UNCONDITIONAL_EQUAL_0_5",
            "postselection_trap": "CONDITIONAL_VARIATION_NOT_SIGNAL",
            "future_choice_bits_used_in_early_training": False,
            "postselected_records_used_for_primary_test": False,
            "unconditional_outcomes_relabelled_as_heralded": False,
        },
        "wolfram": {
            "prior_one_live_math_match_zeno_n2": "SOURCE_BOUND_V2_REGISTRY_RECORD_SEPARATE",
            "new_cases_remote_checked": 0,
            "live_wolfram_queries_in_this_process": 0,
            "provider_key_or_login_used": False,
            "allowed_future_remote_checks": "MANUAL_REVIEW_ONLY_ONE_APPROVED_CASE_AT_A_TIME",
        },
        "claims": {
            "physical_retrocausality_proven": False,
            "electron_as_tachyon_proven": False,
            "physical_quantum_collapse_forced": False,
            "independent_lab_data_ingested": False,
            "models_or_production_weights_modified": False,
        },
    }
    return report


def immutable_json(path: str, obj: dict) -> str:
    dst = Path(path)
    if dst.exists():
        raise RuntimeError("REFUSE_OVERWRITE_SCIENCE_EVIDENCE")
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args=parser.parse_args()
    report=build_report()
    digest=immutable_json(args.output,report)
    print(json.dumps({"experiment":EXPERIMENT, "status": "STANDARD_QM_CPU_CONTROL_PASS",
                      "source_sha256":digest,"live_wolfram_calls":0,
                      "physical_retrocausality_proven":False},sort_keys=True))


if __name__ == "__main__":
    main()
