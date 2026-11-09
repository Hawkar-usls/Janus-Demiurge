#!/usr/bin/env python3
"""JANUS Ocean: preregistered, video-context measurement calibration (CPU).

The VIDEO is provenance for research *questions*, not a source of training
labels or proof of backwards-time communication. Here we calibrate
ordinary Born-rule measurement probabilities of JanusTinyTransformer.

Disjoint historical-looking synthetic samples:
- train: fit model weights
- validation: select ONE global temperature on fixed grid
- test: final read-only evaluation, never used for calibration
- independent future randomness: negative control, not a training target

No quantum hardware, operational collapse control, tachyon or CTC device.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

SCHEMA = "janus.ocean.video_measurement_calibration.v1"
VIDEO_ID = "KkKMZLvlmKA"
VIDEO_URL = "https://youtu.be/KkKMZLvlmKA"
TEMPERATURES = (0.5, 0.65, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
EPS = 1e-8

# The statements were extracted from the video's Russian-language transcript.
# Times refer to topic boundaries, NOT an independent physical experiment.
VIDEO_POINTS = (
    {"second": 1355, "topic": "wheeler_one_electron", "class": "INTERPRETIVE_SPECULATION",
     "test": "No unique electron/worldline or tachyon inference from these data"},
    {"second": 1401, "topic": "positron_time_reversal_picture", "class": "QFT_INTERPRETATION",
     "test": "Do not relabel electron rest mass as a tachyon"},
    {"second": 1505, "topic": "cramer_transactional_interpretation", "class": "INTERPRETATION",
     "test": "Compare standard Born predictions; no raw future-message access"},
    {"second": 1537, "topic": "offer_confirmation_wave_metaphor", "class": "INTERPRETATION",
     "test": "Late choice does not change unconditional earlier marginals"},
    {"second": 1585, "topic": "double_slit_measurement", "class": "ESTABLISHED_MEASUREMENT_PHENOMENON",
     "test": "Which-path decoherence attenuates interference in a fixed basis"},
    {"second": 1664, "topic": "retrocausal_claim", "class": "UNPROVEN_OPERATIONAL_CLAIM",
     "test": "Requires independent blinded precommit data, not postselection"},
)


def video_card():
    return {
        "schema": "janus.ocean.video_source_classification.v1",
        "source": {"url": VIDEO_URL, "video_id": VIDEO_ID,
                   "transcript_language": "ru", "source_type": "PUBLIC_VIDEO"},
        "extracted_topics": list(VIDEO_POINTS),
        "reference_physics": [
            "John Cramer, Rev Mod Phys 58, 647 (1986), DOI 10.1103/RevModPhys.58.647",
            "Standard Born rule and quantum dephasing; Bell no-signalling",
        ],
        "label_provenance": "SYNTHETIC_BORN_RULE_ONLY_NOT_VIDEO_CLAIMS",
        "physical_retrocausality_proven": False,
        "electron_tachyon_identity_proven": False,
        "trained_on_video_speech_as_measurement_outcomes": False,
    }


def card_sha256():
    return hashlib.sha256(json.dumps(
        video_card(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


def _validate(probabilities, labels):
    if len(probabilities) != len(labels) or len(labels) < 1:
        raise ValueError("MISSING_OR_MISMATCHED_CALIBRATION_ROWS")
    for p, y in zip(probabilities, labels):
        if type(y) not in (int, bool) or y not in (0, 1):
            raise ValueError("LABEL_MUST_BE_BINARY")
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("PROBABILITY_OUTSIDE_UNIT_INTERVAL")


def temperature_probability(p, temperature):
    if type(temperature) not in (int, float) or temperature <= 0 or not math.isfinite(temperature):
        raise ValueError("INVALID_TEMPERATURE")
    p = min(1 - EPS, max(EPS, float(p)))
    z = math.log(p / (1 - p)) / temperature
    if z < 0:
        e = math.exp(z)
        return e / (1 + e)
    return 1 / (1 + math.exp(-z))


def metrics(probabilities, labels):
    probabilities = list(probabilities)
    labels = list(labels)
    _validate(probabilities, labels)
    n = len(labels)
    loss = 0.0
    brier = 0.0
    correct = 0
    ece = 0.0
    bins = [[] for _ in range(10)]
    for p, y in zip(probabilities, labels):
        q = min(1-EPS, max(EPS, p))
        loss += -(y * math.log(q) + (1-y)*math.log(1-q))
        brier += (p-y)**2
        pred = int(p >= 0.5)
        correct += (pred == y)
        confidence = max(p, 1-p)
        bin_id = min(9, int((confidence-0.5)/0.05))
        bins[bin_id].append((confidence, pred == y))
    for bucket in bins:
        if bucket:
            ece += len(bucket) / n * abs(
                sum(c for c, _ in bucket)/len(bucket)
                - sum(int(ok) for _, ok in bucket)/len(bucket)
            )
    return {
        "n": n,
        "nll": round(loss/n, 7),
        "brier": round(brier/n, 7),
        "accuracy": round(correct/n, 7),
        "ece10": round(ece, 7),
    }


def calibrate(validation_probs, validation_y, test_probs, test_y, oracle_test_probs):
    """Choose T from VALIDATION only. Evaluate TEST exactly once with frozen T.

    The test is not sampled by or optimized inside this function. Externally
    enforce disjoint source seeds and no overlap of training examples.
    """
    vp = list(validation_probs)
    vy = list(validation_y)
    tp = list(test_probs)
    ty = list(test_y)
    oracle = list(oracle_test_probs)
    _validate(vp, vy)
    _validate(tp, ty)
    _validate(oracle, ty)
    if len(vy) < 1024 or len(ty) < 1024:
        raise ValueError("INSUFFICIENT_INDEPENDENT_HOLDOUT")
    # Fixed grid with an explicit identity candidate; deterministic tie break.
    val_losses = {
        t: metrics((temperature_probability(p, t) for p in vp), vy)["nll"]
        for t in TEMPERATURES
    }
    best = min(TEMPERATURES, key=lambda t: (val_losses[t], abs(t-1)))
    frozen = [temperature_probability(p, best) for p in tp]
    uncalibrated = metrics(tp, ty)
    calibrated = metrics(frozen, ty)
    born = metrics(oracle, ty)
    return {
        "schema": SCHEMA,
        "video_card_sha256": card_sha256(),
        "chosen_temperature": best,
        "allowed_temperatures": list(TEMPERATURES),
        "calibration_rows": len(vy),
        "test_rows": len(ty),
        "validation_nll_raw": val_losses[1.0],
        "validation_nll_calibrated": val_losses[best],
        "test_raw": uncalibrated,
        "test_calibrated": calibrated,
        "test_analytic_born": born,
        "test_brier_gain_over_uncalibrated": round(
            uncalibrated["brier"] - calibrated["brier"], 7),
        "calibration_selection_used_test_labels": False,
        "hypothesis_training_labels_from_video": False,
        "source": "SYNTHETIC_BORN_RULE_WITH_INDEPENDENT_SPLITS",
        "future_signal_or_quantum_collapse_proven": False,
        "status": (
            "TEMPERATURE_CALIBRATION_IMPROVED_HELDOUT_NLL_ONLY"
            if calibrated["nll"] < uncalibrated["nll"]
            else "HOLD_NO_HELDOUT_CALIBRATION_NLL_GAIN"
        ),
    }


def save_card(path):
    p = Path(path)
    if p.exists():
        raise RuntimeError("REFUSE_OVERWRITE_VIDEO_HYPOTHESIS_CARD")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(video_card(), ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                 encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", required=True)
    args = parser.parse_args()
    save_card(args.card)
    print(json.dumps({"video_id": VIDEO_ID, "card_sha256": card_sha256(),
                      "claim_class": "UNVERIFIED_INTERPRETATION_NOT_PHYSICAL_SIGNAL"}))
