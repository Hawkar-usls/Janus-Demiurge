#!/usr/bin/env python3
"""JANUS-RETRO-PHYSICAL-005 — preregistration and fail-closed QPU score.

The IBM Quantum QPU is *real independent hardware*, but a mid-circuit
choice on one QPU is NOT a spacelike-separated late free choice, and
provider job-level timestamps are NOT per-shot independent time tags.
No experiment is claimed to demonstrate backwards-in-time messaging.

Fixed gates (real QPU requested only by a separate manual workflow):
  H(A), CX(A,B), measure A -> EARLY,
  H(C), measure C -> SETTING (after EARLY in circuit program),
  if SETTING == 1: H(B), measure B -> LATE.
The setting C is random during the run, after the early A readout.
The predeclared PRIMARY is whether A's unconditional marginal depends
on C (Fisher exact two-sided 2x2 test, no selection on LATE).
The Bell-pair Z/Z vs Z/X correlations are diagnostic controls only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "janus.ocean.physical_qpu_delayed_choice_v1"
EXPERIMENT_ID = "JANUS-RETRO-PHYSICAL-005"
SHOTS = 4096
SIGNIFICANCE_THRESHOLD = .001
PRIMARY = "EARLY_A_VS_LATER_RANDOM_SETTING_C_UNCONDITIONED"
CONTROL = "Z_Z_BELL_CORRELATION_AND_Z_X_DECORRELATION_DIAGNOSTIC_ONLY"
REGISTERS = ("early", "setting", "late")


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(obj):
    return hashlib.sha256(canon(obj)).hexdigest()


def plan():
    proposal = {
        "schema": SCHEMA,
        "phase": "FROZEN_BEFORE_ANY_QPU_JOB",
        "experiment_id": EXPERIMENT_ID,
        "shots": SHOTS,
        "circuit_version": "BELL_EARLY_A_THEN_RANDOM_C_THEN_CONDITIONAL_B_V1",
        "register_order": list(REGISTERS),
        "first_qubit": "A: early Z measurement",
        "second_qubit": "B: basis Z if C=0, basis X if C=1",
        "third_qubit": "C: later H and random Z measurement setting",
        "temporal_program_order": [
            "prepare Bell pair A,B",
            "barrier",
            "measure A into EARLY",
            "barrier",
            "H on setting qubit C then measure C",
            "barrier",
            "if C==1 apply H to B",
            "measure B into LATE",
        ],
        "primary_hypothesis_null": "A and C independent, no backwards-signalling",
        "primary_predeclared_statistic": PRIMARY,
        "primary_test": "FISHER_EXACT_TWO_SIDED_CONDITIONAL_ON_MARGINS",
        "fixed_nominal_significance_threshold": SIGNIFICANCE_THRESHOLD,
        "multiple_hardware_jobs_per_confirmation": 1,
        "all_shots_included": True,
        "drop_zero_postselected_cohorts": False,
        "select_shots_by_late_B": False,
        "positive_control": CONTROL,
        "observed_conditions": [
            "PROVIDER_JOB_ID_AND_BACKEND",
            "COMPILED_CIRCUIT_AND_ITS_SHA256",
            "ALL_SHOT_VALUES_OF_A_C_B",
        ],
        "platform": "IBM_QUANTUM_PHYSICAL_QPU_MANUAL_TRIGGER_ONLY",
        "hardware_job_submitted_by_this_plan": False,
        "spacelike_separation_claimed": False,
        "late_choice_from_external_separated_lab": False,
        "late_choice_from_QPU_ANCILLA": True,
        "independent_physical_lab_replication": False,
        "physical_retrocausality_proven": False,
        "production_model_modified": False,
    }
    proposal["preregistered_sha256"] = digest(proposal)
    return proposal


def verify_plan(item):
    if not isinstance(item, dict) or item.get("schema") != SCHEMA:
        raise ValueError("PLAN_SCHEMA_INVALID")
    if item != plan():
        raise ValueError("FROZEN_PLAN_TAMPERED")
    return item["preregistered_sha256"]


def _single_bit(v):
    if type(v) is bool:
        return int(v)
    if type(v) is int and v in (0, 1):
        return v
    if isinstance(v, str) and v in ("0", "1"):
        return int(v)
    raise ValueError("INVALID_SHOT_BIT")


def _log_choose(n, k):
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n-k + 1)


def fisher_exact_two_sided(a0_s0, a1_s0, a0_s1, a1_s1):
    """Fixed two-sided hypergeometric probability of equally/extremely unlikely tables."""
    cells = (a0_s0, a1_s0, a0_s1, a1_s1)
    if any(type(v) is not int or v < 0 for v in cells):
        raise ValueError("FISHER_BAD_TABLE")
    n = sum(cells)
    if n == 0:
        raise ValueError("FISHER_EMPTY_TABLE")
    group_0 = a0_s0 + a1_s0
    a1_total = a1_s0 + a1_s1
    observed = a1_s0
    lo = max(0, group_0 - (n - a1_total))
    hi = min(group_0, a1_total)
    denominator = _log_choose(n, group_0)
    def lp(x):
        return (_log_choose(a1_total, x)
                + _log_choose(n-a1_total, group_0-x)
                - denominator)
    observed_lp = lp(observed)
    selected = [lp(k) for k in range(lo, hi+1)
                if lp(k) <= observed_lp + 1e-10]
    return min(1.0, math.fsum(math.exp(x) for x in selected))


def assess(plan_data, records, job_meta):
    precommit = verify_plan(plan_data)
    if not isinstance(records, list) or len(records) != SHOTS:
        raise ValueError("ALL_SHOTS_REQUIRED_NO_SUBSAMPLING")
    if not isinstance(job_meta, dict):
        raise ValueError("JOB_METADATA_REQUIRED")
    if (job_meta.get("provider") != "IBM_QUANTUM" or
        job_meta.get("backend_simulator") is not False or
        not isinstance(job_meta.get("job_id"), str) or
        not job_meta.get("job_id") or
        not isinstance(job_meta.get("backend_name"), str) or
        not job_meta.get("backend_name") or
        not isinstance(job_meta.get("compiled_circuit_sha256"), str) or
        len(job_meta["compiled_circuit_sha256"]) != 64):
        raise ValueError("REAL_QPU_JOB_AND_CIRCUIT_PROVENANCE_REQUIRED")
    counts = {(s, a): 0 for s in (0, 1) for a in (0, 1)}
    corr = {0: [0, 0], 1: [0, 0]}
    raw = []
    for row in records:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError("SHOT_ROW_MALFORMED")
        a, setting, b = map(_single_bit, row)
        raw.append([a, setting, b])
        counts[(setting, a)] += 1
        corr[setting][int(a == b)] += 1
    s0 = counts[(0, 0)] + counts[(0, 1)]
    s1 = counts[(1, 0)] + counts[(1, 1)]
    quality = min(s0, s1) >= SHOTS // 4
    # All rows stay in the report EVEN if hardware performance is poor.
    p0 = counts[(0, 1)]/s0 if s0 else None
    p1 = counts[(1, 1)]/s1 if s1 else None
    difference = p1-p0 if quality else None
    p_fisher = fisher_exact_two_sided(
        counts[(0, 0)], counts[(0, 1)], counts[(1, 0)], counts[(1, 1)])
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "phase": "PHYSICAL_QPU_HARDWARE_SCORING",
        "status": ("REAL_QPU_EXPLORATORY_DATA_SCORED"
                   if quality else "REAL_QPU_SETTING_QUALITY_HOLD"),
        "precommit_sha256": precommit,
        "provider": "IBM_QUANTUM",
        "backend_name": job_meta["backend_name"],
        "job_id": job_meta["job_id"],
        "compiled_circuit_sha256": job_meta["compiled_circuit_sha256"],
        "shot_count": SHOTS,
        "raw_shots_sha256": digest(raw),
        "raw_shots_included": True,
        "all_raw_shots": raw,
        "primary": {
            "definition": PRIMARY,
            "a1_given_setting0": p0,
            "a1_given_setting1": p1,
            "difference_setting1_minus_setting0": difference,
            "fisher_exact_two_sided_p": p_fisher,
            "predeclared_alpha": SIGNIFICANCE_THRESHOLD,
            "threshold_crossed": bool(quality and p_fisher < SIGNIFICANCE_THRESHOLD),
            "threshold_crossing_not_proof_of_retrocausality": True,
            "setting0_shots": s0,
            "setting1_shots": s1,
            "all_shots_included_no_late_postselection": True,
        },
        "diagnostics_not_primary": {
            "p_a_equals_b_setting_z": corr[0][1]/s0 if s0 else None,
            "p_a_equals_b_setting_x": corr[1][1]/s1 if s1 else None,
            "z_z_entanglement_control_expected_high": True,
            "z_x_control_expected_about_half": True,
        },
        "limitations": {
            "late_choice_after_early_in_circuit_program": True,
            "per_shot_time_tags_independently_verified": False,
            "spacelike_separation_proven": False,
            "QPU_provider_is_external_to_JANUS": True,
            "independent_human_laboratory_custodian": False,
            "possible_hardware_crosstalk_or_drift": True,
            "no_backward_communication_channel_demonstrated": True,
            "physical_retrocausality_proven": False,
            "production_model_changed": False,
        },
    }


def write_once(path, item):
    output = Path(path)
    if output.exists():
        raise ValueError("REFUSE_OVERWRITE_EXPERIMENT_EVIDENCE")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(item, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("plan", "score"))
    ap.add_argument("--input")
    ap.add_argument("--plan")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.mode == "plan":
        out = plan()
    else:
        if not args.input or not args.plan:
            ap.error("--input and --plan required")
        bundle = json.loads(Path(args.input).read_text())
        frozen = json.loads(Path(args.plan).read_text())
        out = assess(frozen, bundle["records"], bundle["job_metadata"])
    write_once(args.output, out)
    print(json.dumps({"status": out["phase"], "sha256": digest(out),
                      "real_qpu_job_submitted_by_this_process": False,
                      "physical_retrocausality_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
