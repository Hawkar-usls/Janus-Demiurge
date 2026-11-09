#!/usr/bin/env python3
"""JANUS Ocean LIGHT-007: reproducible, offline light-to-causality controls.

All "light" and "photon" observations are seeded SYNTHETIC fixtures.
No physical photon detection, IBM service, QPU simulation, or future-to-past
communication is claimed. Original QPU-005 and 006 protocols are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
OCEAN = HERE.parent
sys.path.insert(0, str(OCEAN / "causality_controls"))
import controls_006 as ctrl006

ID = "JANUS-OCEAN-LIGHT-CAUSALITY-CONTROLS-007"
SCHEMA = "janus.ocean.light_causality_controls_007.v1"
SEED = 20261109
BINS = 2048
LENGTH = 1024
TRAIN_END = 512
TEST_START = 640
DELAY = 3
LIGHT_ORIGINAL_BLOB = "d86db6212d62b23621fb023c0317f38b94c21ef4"
LIGHT_NORMALIZED_BLOB = "901f0f094cf078115ad6b1b64f2cf6de639a4ff8"
QPU_SHOTS = 4096


def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def write_once(path, obj):
    p = Path(path)
    if p.exists():
        raise ValueError("LIGHT007_REFUSE_OVERWRITE")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")


def poisson(lambda_value, rng):
    """Knuth's sampler for small synthetic Poisson rates; not a light detector."""
    if not 0 < lambda_value <= 20:
        raise ValueError("POISSON_RATE_OUT_OF_RANGE")
    threshold = math.exp(-lambda_value)
    product = 1.0
    k = 0
    while product > threshold:
        k += 1
        product *= rng.random()
    return k - 1


def count_streams():
    rng = random.Random(SEED + 7)
    return {
        "low": [poisson(4.0, rng) for _ in range(BINS)],
        "high": [poisson(12.0, rng) for _ in range(BINS)],
    }


def summarize_stream(xs):
    n = len(xs)
    mean = sum(xs) / n
    variance = math.fsum((x - mean) ** 2 for x in xs) / (n - 1)
    return {"n_bins": n, "mean": round(mean, 7),
            "sample_variance": round(variance, 7),
            "fano_sample": round(variance / mean, 7)}


def shot_noise_control():
    streams = count_streams()
    low = summarize_stream(streams["low"])
    high = summarize_stream(streams["high"])
    for item in (low, high):
        if not 0.8 < item["fano_sample"] < 1.2:
            raise AssertionError("SYNTHETIC_POISSON_COUNT_VARIANCE_FAILED")
    if not high["mean"] > 2 * low["mean"]:
        raise AssertionError("SYNTHETIC_INTENSITY_NOT_RECOVERED")
    return {
        "control": "LIGHT-CTRL-01-COUNTING-NOISE",
        "status": "PASS_SYNTHETIC_ONLY",
        "source_model": "IDEAL_POISSON_COUNT_PROCESS",
        "low_nominal_counts_per_bin": 4.0,
        "high_nominal_counts_per_bin": 12.0,
        "low": low,
        "high": high,
        "stream_hashes": {k: digest(v) for k, v in streams.items()},
        "actual_photon_counts_collected": 0,
        "not_a_test_of_quantum_light_statistics": True,
        "note": "This is a toy independent-arrival process, not a universal optical-statistics law.",
    }


def light_timeline():
    rng = random.Random(SEED + 13)
    src = [1 if rng.random() < .22 else 0 for _ in range(LENGTH)]
    # A delayed classical detector response: only past source bits influence t.
    detector = [
        round(max(0.0, .4 + 4.0 * (src[t - DELAY] if t >= DELAY else 0)
                  + .55 * (src[t - DELAY - 1] if t >= DELAY + 1 else 0)
                  + rng.uniform(-.11, .11)), 8)
        for t in range(LENGTH)
    ]
    return {"source": src, "detector": detector}


def separation_score(source, detector, lag, train_until=TRAIN_END):
    """Positive lag uses source in the past; negative lag is diagnostic only."""
    if not -8 <= lag <= 8:
        raise ValueError("LAG_OUT_OF_RANGE")
    pairs = [(source[t - lag], detector[t])
             for t in range(16, train_until)
             if 0 <= t - lag < train_until]
    seen_0 = [y for x, y in pairs if x == 0]
    seen_1 = [y for x, y in pairs if x == 1]
    if not seen_0 or not seen_1:
        raise ValueError("EMPTY_TRAINING_GROUP")
    return sum(seen_1) / len(seen_1) - sum(seen_0) / len(seen_0)


def fit_forward_lag(timeline):
    source, detector = timeline["source"], timeline["detector"]
    candidates = {lag: separation_score(source, detector, lag)
                  for lag in range(9)}
    lag = max(candidates, key=candidates.get)
    if lag != DELAY:
        raise AssertionError("FORWARD_LAG_NOT_RECOVERED")
    levels = []
    for bit in (0, 1):
        ys = [detector[t] for t in range(16, TRAIN_END)
              if source[t - lag] == bit]
        levels.append(sum(ys) / len(ys))
    acausal_diagnostics = {str(lag): separation_score(source, detector, lag)
                           for lag in range(-8, 0)}
    if not candidates[lag] > 2 * max(acausal_diagnostics.values()):
        raise AssertionError("ACausal_CORRELATION_TOO_STRONG")
    return {
        "estimated_positive_delay_bins": lag,
        "train_ends_before": TRAIN_END,
        "mean_level_by_past_source": [round(x, 10) for x in levels],
        "forward_scores": {str(k): round(v, 8) for k, v in candidates.items()},
        "negative_lags_diagnostic_only": {
            str(k): round(v, 8) for k, v in acausal_diagnostics.items()
        },
    }


def forward_prediction(source, t, source_t, lag, learned_levels):
    if lag < 0 or source_t > t or source_t != t - lag:
        raise ValueError("FUTURE_OR_MISALIGNED_LIGHT_INPUT_REFUSED")
    if not 0 <= source_t < len(source):
        raise ValueError("SOURCE_OUTSIDE_OBSERVED_WINDOW")
    return learned_levels[source[source_t]]


def prepare_forecasts():
    timeline = light_timeline()
    fit = fit_forward_lag(timeline)
    lag = fit["estimated_positive_delay_bins"]
    levels = fit["mean_level_by_past_source"]
    precommit = {
        "schema": SCHEMA,
        "id": ID,
        "phase": "SYNTHETIC_LIGHT_FORECAST_PRECOMMIT",
        "source_seed": SEED + 13,
        "train_range_t": [16, TRAIN_END - 1],
        "unused_gap_t": [TRAIN_END, TEST_START - 1],
        "test_range_t": [TEST_START, LENGTH - 1],
        "model": fit,
        "predictions": [
            {"t": t, "source_t": t - lag,
             "prediction": round(forward_prediction(
                 timeline["source"], t, t - lag, lag, levels), 8)}
            for t in range(TEST_START, LENGTH)
        ],
        "labels_in_precommit": False,
        "real_detector_data": False,
    }
    return {
        "schema": SCHEMA,
        "payload": precommit,
        "payload_sha256": digest(precommit),
        "independent_timestamp_attestation": False,
    }


def score_forecasts(commit):
    if commit != prepare_forecasts() or digest(commit.get("payload")) != commit.get("payload_sha256"):
        raise ValueError("LIGHT_FORECAST_PRECOMMIT_MUTATED")
    timeline = light_timeline()
    train_mean = sum(timeline["detector"][16:TRAIN_END]) / (TRAIN_END - 16)
    predictions = commit["payload"]["predictions"]
    mae = sum(abs(row["prediction"] - timeline["detector"][row["t"]])
              for row in predictions) / len(predictions)
    baseline = sum(abs(train_mean - timeline["detector"][row["t"]])
                   for row in predictions) / len(predictions)
    if not mae < baseline:
        raise AssertionError("SYNTHETIC_FORWARD_TIMING_BASELINE_NOT_BEATEN")
    return {
        "control": "LIGHT-CTRL-02-FORWARD-DELAYS",
        "status": "PASS_SYNTHETIC_ONLY",
        "precommit_sha256": commit["payload_sha256"],
        "test_windows": len(predictions),
        "recovered_delay_bins": commit["payload"]["model"]["estimated_positive_delay_bins"],
        "causal_test_mae": round(mae, 8),
        "constant_train_mean_baseline_mae": round(baseline, 8),
        "future_source_access_denied": True,
        "observed_arrival_times_independently_verified": False,
        "physical_speed_of_light_measured": False,
        "note": "Known simulated forward delay, not evidence of quantum retrocausality.",
    }


def postselection_rows():
    rows = []
    # A and setting C are strictly independent unconditionally.
    # A late selection on B creates a FALSE A-C association (collider bias).
    for c in (0, 1):
        for a in (0, 1):
            selected = 900 if a == c else 100
            rows += [[a, c, 1 if i < selected else 0] for i in range(1024)]
    random.Random(SEED + 41).shuffle(rows)
    return rows


def postselection_control():
    rows = postselection_rows()
    full = ctrl006.score_qpu_fixture(rows)
    if full["table"] != [[1024, 1024], [1024, 1024]]:
        raise AssertionError("UNCONDITIONAL_COUNTS_CHANGED")
    if full["primary_fisher_two_sided_p"] != 1:
        raise AssertionError("FALSE_UNCONDITIONAL_SIGNALLING")
    # This calculation is for an ANTI-PATTERN DEMONSTRATION ONLY.
    selected = [r for r in rows if r[2] == 1]
    counts = [[0, 0], [0, 0]]
    for a, c, b in selected:
        counts[c][a] += 1
    p_bad = ctrl006.qpu005.fisher_exact_two_sided(
        counts[0][0], counts[0][1], counts[1][0], counts[1][1])
    if len(selected) != 2000 or counts != [[900, 100], [100, 900]]:
        raise AssertionError("INTENTIONAL_SELECTION_BIAS_FIXTURE_CHANGED")
    if not p_bad < 1e-20:
        raise AssertionError("FALSE_SIGNIFICANCE_NOT_DEMONSTRATED")
    reversed_b = ctrl006.score_qpu_fixture([[a, c, 1 - b] for a, c, b in rows])
    if (reversed_b["table"] != full["table"] or
            reversed_b["primary_fisher_two_sided_p"] != full["primary_fisher_two_sided_p"]):
        raise AssertionError("QPU005_PRIMARY_DEPENDS_ON_LATE_B")
    return {
        "control": "LIGHT-CTRL-03-NO-POSTSELECTION",
        "status": "PASS_SYNTHETIC_ONLY",
        "total_raw_shots": len(rows),
        "raw_sha256": digest(rows),
        "predeclared_unselected_table": full["table"],
        "unselected_fisher_p": full["primary_fisher_two_sided_p"],
        "forbidden_selected_table_for_demonstration_only": counts,
        "forbidden_selected_p": p_bad,
        "primary_ignores_late_B": True,
        "qpu005_original_statistic_reused": True,
        "provider_job_id": None,
        "real_qpu_shots": 0,
        "note": "Late-outcome conditioning creates a false apparent early/late signal; only unselected primary counts are admissible.",
    }


def provenance_control():
    files = {
        "light_20260127_original_with_fence.json": LIGHT_ORIGINAL_BLOB,
        "light_current_normalized.json": LIGHT_NORMALIZED_BLOB,
    }
    found = {}
    for file, expected in files.items():
        data = (HERE / "fixtures" / file).read_bytes()
        observed = ctrl006.git_blob_sha(data)
        if observed != expected:
            raise ValueError("LIGHT_ORIGINAL_OR_NORMALIZED_SHA_MISMATCH:" + file)
        found[file] = observed
    original = (HERE / "fixtures" / "light_20260127_original_with_fence.json").read_text()
    current = (HERE / "fixtures" / "light_current_normalized.json").read_text()
    if not original.startswith(""+chr(96)*3+"json\n") or not original.endswith(chr(96)*3):
        raise ValueError("LIGHT_ORIGINAL_MARKDOWN_FENCE_CHANGED")
    historical = json.loads(original[len(chr(96)*3+"json\n"):-3].strip())
    normalized = json.loads(current)
    if historical != normalized:
        raise ValueError("LIGHT_CURRENT_SEMANTICS_DIFFER_FROM_ORIGINAL")
    if historical.get("artifact_type") != "PHYSICAL_UNIT_TEST":
        raise ValueError("HISTORICAL_LIGHT_CLASS_CHANGED")
    if "NOISE_JITTER_AND_DECOHERENCE" not in historical:
        raise ValueError("LIGHT_JITTER_RESEARCH_MISSING")
    if "STOCHASTIC_SCHEDULER" not in historical:
        raise ValueError("LIGHT_STOCHASTIC_RESEARCH_MISSING")
    prior = ctrl006.provenance_control()
    return {
        "control": "LIGHT-CTRL-04-HISTORICAL-PROVENANCE",
        "status": "PASS_GIT_BLOB_SNAPSHOTS_AND_PRIOR_CAUSAL_CHAIN",
        "git_blobs": found,
        "light_original_creation_commit": "8fa51d5ec7b79a67f473613552e5740293857511",
        "light_original_committed_at_utc": "2026-01-27T03:15:14Z",
        "light_json_embedded_timestamp": historical.get("timestamp"),
        "original_wrapped_in_markdown_code_fence": True,
        "normalized_semantic_content_equal": True,
        "banana_qpu006_provenance_status": prior["status"],
        "historical_timestamps_not_independent_physical_time_tags": True,
    }


def combined_report():
    forecast = prepare_forecasts()
    controls = [
        shot_noise_control(),
        score_forecasts(forecast),
        postselection_control(),
        provenance_control(),
    ]
    return {
        "schema": SCHEMA,
        "id": ID,
        "status": "OFFLINE_SYNTHETIC_LIGHT_CONTROLS_PASS",
        "forecast_precommit": forecast,
        "controls": controls,
        "all_controls_pass": all(x["status"].startswith("PASS") for x in controls),
        "original_light_file_modified": False,
        "original_banana_file_modified": False,
        "original_qpu005_modified": False,
        "original_ctrl006_modified": False,
        "IBM_provider_called": False,
        "QPU_time_used_minutes": 0,
        "actual_photon_measurements": 0,
        "retrocausality_proven": False,
        "evidence_class": "DETERMINISTIC_SYNTHETIC_CONTROLS_NOT_PHYSICAL_EVIDENCE",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("prepare", "score", "counts", "selection", "provenance", "all"))
    ap.add_argument("--input")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.mode == "prepare":
        output = prepare_forecasts()
    elif args.mode == "score":
        if not args.input:
            ap.error("--input forecast precommit is required")
        output = score_forecasts(json.loads(Path(args.input).read_text()))
    elif args.mode == "counts":
        output = shot_noise_control()
    elif args.mode == "selection":
        output = postselection_control()
    elif args.mode == "provenance":
        output = provenance_control()
    else:
        output = combined_report()
    write_once(args.output, output)
    print(json.dumps({"mode": args.mode, "status": output.get("status", "PRECOMMIT"),
                      "output_sha256": digest(output), "actual_qpu_used": False}, sort_keys=True))


if __name__ == "__main__":
    main()
