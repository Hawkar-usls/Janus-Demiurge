#!/usr/bin/env python3
"""Source-bound Ocean/Wolfram science council, inspired by the Rowan research gate.

Binds the exact offline quantum dataset, trusted status-only external arithmetic
verification, and existing native Ocean transformer benchmark. A pass is
scientific *research admission* only; physical retrocausality is never inferred.
No remote network, credential, provider text, or production model writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import measurement_priors as physics
import wolfram_alpha_bridge as wolfram
import ocean_video_calibration as video

SCHEMA = "janus.ocean.wolfram_source_bound_council.v1"
MEASUREMENT_SCHEMA = physics.SCHEMA
TRAIN_SCHEMA = "janus.ocean.measurement_transformer_benchmark.v1"
QUERY_IDS = tuple(name for name, _, _ in wolfram.CASES)


class CouncilHold(ValueError):
    pass


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


def read_json(path):
    p = Path(path)
    if p.stat().st_size > 1500000:
        raise CouncilHold("INPUT_OVERSIZED")
    return json.loads(p.read_text(encoding="utf-8"))


def validate_priors(priors):
    if priors.get("schema") != MEASUREMENT_SCHEMA:
        raise CouncilHold("PRIOR_SCHEMA_DRIFT")
    expected = physics.report()
    if priors != expected:
        raise CouncilHold("PRIOR_GRID_OR_BELL_CONTROL_DRIFT")
    return canonical_sha256(priors)


def validate_wolfram(bridge, priors_digest):
    if bridge.get("schema") != wolfram.SCHEMA:
        raise CouncilHold("WOLFRAM_BRIDGE_SCHEMA_DRIFT")
    provenance = bridge.get("source_binding", {})
    if provenance.get("canonical_dataset_sha256") != priors_digest:
        raise CouncilHold("WOLFRAM_SOURCE_BINDING_DRIFT")
    if provenance.get("dataset_schema") != MEASUREMENT_SCHEMA:
        raise CouncilHold("WOLFRAM_DATASET_SCHEMA_DRIFT")
    if bridge.get("evidence_of_retrocausality") is not False:
        raise CouncilHold("WOLFRAM_PHYSICAL_CLAIM_ESCALATION")
    if bridge.get("model_weights_updated") is not False:
        raise CouncilHold("WOLFRAM_MAY_NOT_UPDATE_MODEL")
    if bridge.get("secret_emitted") is not False:
        raise CouncilHold("WOLFRAM_SECRET_GATE_FAILED")
    mode = bridge.get("mode")
    status = bridge.get("status")
    if (mode, status) not in (
        ("OFFLINE_REFERENCE_ONLY", "NO_EXTERNAL_QUERY_PERFORMED"),
        ("LIVE_READ_ONLY_WOLFRAM_ALPHA", "EXTERNAL_ARITHMETIC_CHECK_PASS"),
    ):
        raise CouncilHold("WOLFRAM_MODE_STATUS_INCONSISTENT")
    remote = mode == "LIVE_READ_ONLY_WOLFRAM_ALPHA"
    if bridge.get("upstream", {}).get("authenticated") is not remote:
        raise CouncilHold("WOLFRAM_AUTHENTICATION_STATUS_DRIFT")
    entries = bridge.get("queries")
    if not isinstance(entries, list) or len(entries) != len(QUERY_IDS):
        raise CouncilHold("WOLFRAM_QUERY_COUNT_CHANGED")
    for row, (query_id, expression, expected) in zip(entries, wolfram.CASES):
        if row.get("id") != query_id or row.get("public_expression") != expression:
            raise CouncilHold("UNAPPROVED_WOLFRAM_QUERY")
        if type(row.get("analytical_expected")) not in (int, float):
            raise CouncilHold("NONNUMERIC_REFERENCE")
        if abs(row["analytical_expected"] - expected) > 1e-12:
            raise CouncilHold("WOLFRAM_BASELINE_TAMPERING")
        if row.get("external_checked") is not remote:
            raise CouncilHold("WOLFRAM_REMOTE_CHECK_STATUS_DRIFT")
        if "wolfram_numeric_result" in row or "provider_response" in row:
            raise CouncilHold("WOLFRAM_PROVIDER_CONTENT_MUST_NOT_BE_CACHED")
        if remote and row.get("agrees_with_standard_arithmetic") is not True:
            raise CouncilHold("WOLFRAM_EXTERNAL_MATH_NOT_CONFIRMED")
        if not remote and "agrees_with_standard_arithmetic" in row:
            raise CouncilHold("WOLFRAM_OFFLINE_FALSE_CONFIRMATION")
    return remote


def validate_training(train):
    if train is None:
        return "NOT_RUN", None
    if train.get("schema") != TRAIN_SCHEMA or train.get("model") != "JanusTinyTransformer":
        raise CouncilHold("TRANSFORMER_SOURCE_OR_SCHEMA_DRIFT")
    for key in ("production_checkpoint_changed", "future_labels_seen_at_training",
                "postselection_on_test_results", "physically_triggered_wavefunction_collapse",
                "proven_tachyons_or_retrocausal_communication"):
        if train.get(key) is not False:
            raise CouncilHold("TRAINING_SAFETY_BOUNDARY_VIOLATION_" + key)
    if train.get("dataset_type") != "SYNTHETIC_STANDARD_QUANTUM_MEASUREMENT":
        raise CouncilHold("TRANSFORMER_DATASET_CLASS_DRIFT")
    # Every video-linked calibration claim is checked against this
    # repository's fixed source card. No video narration may become a target.
    if train.get("video_source") != video.VIDEO_URL:
        raise CouncilHold("VIDEO_PROVENANCE_CHANGED")
    if train.get("video_hypothesis_card_sha256") != video.card_sha256():
        raise CouncilHold("VIDEO_HYPOTHESIS_CARD_DRIFT")
    if train.get("calibration_training_test_seeds_disjoint") is not True:
        raise CouncilHold("TRAIN_VAL_TEST_SPLIT_ASSERTION_MISSING")
    seeds = [train.get("independent_validation_seed"),
             train.get("independent_test_seed")]
    if not all(type(s) is int for s in seeds) or seeds[0] == seeds[1]:
        raise CouncilHold("CALIBRATION_TEST_SEED_COLLISION")
    card = train.get("video_measurement_calibration")
    if not isinstance(card, dict) or card.get("schema") != video.SCHEMA:
        raise CouncilHold("VIDEO_CALIBRATION_SCHEMA_MISSING")
    if card.get("video_card_sha256") != video.card_sha256():
        raise CouncilHold("VIDEO_CALIBRATION_SOURCE_CHANGED")
    if card.get("allowed_temperatures") != list(video.TEMPERATURES) or (
        card.get("chosen_temperature") not in video.TEMPERATURES
    ):
        raise CouncilHold("TEMPERATURE_GRID_FROZEN_SELECTION_DRIFT")
    if (card.get("calibration_selection_used_test_labels") is not False or
        card.get("hypothesis_training_labels_from_video") is not False or
        card.get("future_signal_or_quantum_collapse_proven") is not False):
        raise CouncilHold("VIDEO_CALIBRATION_AUTHORITY_ESCALATION")
    if (card.get("calibration_rows", 0) < 1024 or
        card.get("test_rows", 0) < 1024):
        raise CouncilHold("CALIBRATION_NOT_ENOUGH_DATA")
    if card.get("source") != "SYNTHETIC_BORN_RULE_WITH_INDEPENDENT_SPLITS":
        raise CouncilHold("CALIBRATION_INPUT_CLASS_CHANGED")
    if card.get("validation_nll_calibrated", float("inf")) > (
        card.get("validation_nll_raw", float("-inf")) + 1e-6
    ):
        raise CouncilHold("CALIBRATION_VALIDATION_DETERIORATED")
    before, after = train.get("untrained_holdout"), train.get("trained_holdout")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise CouncilHold("TRAINING_HOLDOUT_MISSING")
    if before.get("cases") != after.get("cases") or after.get("cases", 0) < 1000:
        raise CouncilHold("INDEPENDENT_HOLDOUT_TOO_SMALL")
    for metrics in (before, after):
        for key in ("brier", "analytic_born_oracle_brier", "logloss"):
            value = metrics.get(key)
            if not isinstance(value, (float, int)) or not math.isfinite(value):
                raise CouncilHold("TRAINING_NONFINITE_METRIC")
            if key.endswith("brier") and not 0 <= value <= 1:
                raise CouncilHold("TRAINING_BRIER_OUTSIDE_RANGE")
    raw = card.get("test_raw", {})
    calibrated = card.get("test_calibrated", {})
    born = card.get("test_analytic_born", {})
    if any(item.get("n") != after["cases"] for item in (raw, calibrated, born)):
        raise CouncilHold("VIDEO_TEST_ROW_ALIGNMENT_FAILED")
    if (abs(raw.get("brier", -10)-after["brier"]) > 5e-6 or
        abs(born.get("brier", -10)-after["analytic_born_oracle_brier"]) > 5e-6):
        raise CouncilHold("VIDEO_CALIBRATION_NOT_BOUND_TO_OCEAN_TEST")
    if (not all(math.isfinite(v) for v in (
        calibrated.get("nll", float("nan")),
        calibrated.get("brier", float("nan")),
        raw.get("nll", float("nan")),
    )) or not 0 <= calibrated["brier"] <= 1):
        raise CouncilHold("VIDEO_CALIBRATION_INVALID_METRICS")
    expected_status = ("TEMPERATURE_CALIBRATION_IMPROVED_HELDOUT_NLL_ONLY"
                       if calibrated["nll"] < raw["nll"]
                       else "HOLD_NO_HELDOUT_CALIBRATION_NLL_GAIN")
    if card.get("status") != expected_status:
        raise CouncilHold("VIDEO_CALIBRATION_OUTCOME_CONTRADICTS_METRICS")
    control = train.get("independent_future_random_negative_control")
    if not isinstance(control, dict) or control.get("cases") != after["cases"]:
        raise CouncilHold("FUTURE_RANDOM_CONTROL_MISSING")
    if train.get("assessment") not in (
        "SYNTHETIC_BORN_RULE_LEARNING_GAIN_ONLY", "HOLD_NO_MEASURED_SYNTHETIC_GAIN"
    ):
        raise CouncilHold("TRANSFORMER_INVALID_ASSESSMENT")
    measured_gain = before["brier"] - after["brier"]
    if train["assessment"] == "SYNTHETIC_BORN_RULE_LEARNING_GAIN_ONLY" and measured_gain <= 0.01:
        raise CouncilHold("SYNTHETIC_GAIN_NOT_SUPPORTED")
    if train["assessment"] == "HOLD_NO_MEASURED_SYNTHETIC_GAIN" and measured_gain > 0.01:
        raise CouncilHold("SYNTHETIC_GAIN_CONTRADICTS_METRICS")
    return train["assessment"], measured_gain


def council(priors, bridge, training=None):
    digest = validate_priors(priors)
    remote = validate_wolfram(bridge, digest)
    train_status, gain = validate_training(training)
    research_admission = "EXTERNAL_MATH_CHECKED" if remote else "OFFLINE_MATH_ONLY"
    return {
        "schema": SCHEMA,
        "source_binding": {
            "repository": "Hawkar-usls/Janus-Demiurge",
            "prior_grid_sha256": digest,
            "provider_receipt_sha256": canonical_sha256(bridge),
            "training_report_sha256": canonical_sha256(training) if training else None,
        },
        "conceptual_roles": {
            "SENSE": "CPU Born-rule simulation, no-signalling test and source hashes",
            "VERIFY": "Wolfram Alpha public arithmetic checks on live manual opt-in only",
            "THINK": "Native JanusTinyTransformer trained on synthetic measurement samples",
            "CHALLENGE": "Born oracle, untrained baseline, future random control, source integrity",
            "REMEMBER": "GitHub Actions run artifact; never provider response text",
        },
        "research_admission": research_admission,
        "training_assessment": train_status,
        "video_research_source": video.VIDEO_URL,
        "video_hypothesis_card_sha256": video.card_sha256(),
        "video_calibration_status": (
            training["video_measurement_calibration"]["status"] if training else "NOT_RUN"
        ),
        "video_calibrated_holdout": (
            training["video_measurement_calibration"]["test_calibrated"]
            if training else None
        ),
        "measured_synthetic_brier_gain": round(gain, 6) if gain is not None else None,
        "verified_external_provider": remote,
        "raw_future_signal_deductible": False,
        "claims": {
            "cpu_quantum_simulation": True,
            "physical_quantum_collapse_proven": False,
            "electron_tachyon_identity_proven": False,
            "physical_retrocausal_communication_proven": False,
            "independent_physics_experiment_run": False,
        },
        "authority": {
            "edit_production_weights": False,
            "run_rowan_jobs": False,
            "spend_wolfram_credits_automatically": False,
            "promote_physical_claim": False,
            "external_wolfram_calls_in_this_process": 0,
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--priors", required=True)
    p.add_argument("--wolfram", required=True)
    p.add_argument("--training")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    out = Path(args.output)
    if out.exists():
        raise CouncilHold("REFUSE_REWRITE_RESEARCH_LEDGER")
    record = council(read_json(args.priors), read_json(args.wolfram),
                     read_json(args.training) if args.training else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "research_admission": record["research_admission"],
        "training_assessment": record["training_assessment"],
        "physical_retrocausality_proven": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
