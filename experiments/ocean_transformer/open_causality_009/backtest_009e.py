#!/usr/bin/env python3
"""JANUS OPEN-009E: retrospective pseudo-prospective NOAA and simulated late-choice diagnostics.

Additive controls only. This does not change any sealed OPEN-009A/B/C/D source,
predictor, checkpoint, target time, future artifact, or Meta Registry preregistration.
Backtest is retrospective with chronological holdout, NOT a new prospective trial.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import random
import secrets
import statistics

import noaa_009a as noaa

TARGETS = [dt.date(2025, 11, d) for d in range(1, 9)]
N_BITS = 1024
TRAIN_SEED = 0x4A414E5553
SIM_POS_SEED = 0xC001D00D
SIM_LEAK_SEED = 0xABCD
TRIAL_MODEL_P_SAME = 0.72


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def write_once(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def exact_binom_upper(n, k):
    return sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n)


def historic_backtest(outdir):
    # Original OPEN-009A rule: forecast on target-minus-2, four training
    # days on prepare-minus-7, -6, -5, -4 == target-minus-9..-6.
    memo = {}
    def load(d):
        key = d.isoformat()
        if key not in memo:
            memo[key] = noaa.fetch(d)
        return memo[key]

    frozen = []
    for target in TARGETS:
        days = [target - dt.timedelta(days=ago) for ago in (9, 8, 7, 6)]
        history = [load(d) for d in days]
        prediction, baselines = noaa.forecast(history, target)
        frozen.append({
            "target": target.isoformat(),
            "training_dates": [d.isoformat() for d in days],
            "training_file_sha256": [r["raw_sha256"] for r in history],
            "predictions_w_m2": prediction,
            "baselines_w_m2": baselines,
        })
    # Nothing from target date has been fetched yet in this program.
    early = {
        "schema": "janus.open009e.historical_holdout.v1",
        "source": "NOAA_SURFRAD_BONDVILLE",
        "phase": "PSEUDO_PROSPECTIVE_HISTORICAL_ONLY",
        "purpose": "diagnostic historical backtest; NOT external early timestamp",
        "target_dates": [d.isoformat() for d in TARGETS],
        "targets_accessed_before_forecast_freeze": False,
        "source_model": "existing unmodified noaa_009a.forecast",
        "fixed_predictions": frozen
    }
    write_once(outdir / "noaa_early_hist_009e.json", early)
    early_sha = digest(early)
    results = []
    for pred in frozen:
        day = load(dt.date.fromisoformat(pred["target"]))  # Only after early file was closed.
        measured = day["hourly_ghi"]
        row = {"target": pred["target"], "target_raw_sha256": day["raw_sha256"],
               "valid_hours": sum(v is not None for v in measured),
               "early_forecast_sha256": early_sha}
        if len(measured) != 24 or any(v is None or not math.isfinite(v) for v in measured):
            row["status"] = "INCOMPLETE_NO_SCORE"
        else:
            row["status"] = "SCORED"
            y = measured
            forecasts = {"JANUS_PHYSICS_HEURISTIC": pred["predictions_w_m2"], **pred["baselines_w_m2"]}
            row["mae_w_m2"] = {name: round(sum(abs(a - b) for a, b in zip(values, y)) / 24, 6)
                               for name, values in forecasts.items()}
        results.append(row)
        print("NOAA_HOLDOUT " + json.dumps(row, sort_keys=True), flush=True)

    complete = all(row["status"] == "SCORED" for row in results)
    report = {"schema": "janus.open009e.noaa_backtest.v1",
              "kind": "RETROSPECTIVE_PSEUDO_PROSPECTIVE",
              "target_policy": "fixed 2025-11-01 through 2025-11-08, no replacements",
              "early_forecast_sha256": early_sha,
              "original_OPEN009_frozen_files_modified": False,
              "results": results,
              "status": "COMPLETE_8_OF_8" if complete else "INCOMPLETE_NO_POOLED_CLAIM",
              "retrocausality_proven": False}
    if complete:
        names = list(results[0]["mae_w_m2"])
        pooled = {name: round(sum(row["mae_w_m2"][name] for row in results) / len(results), 6)
                  for name in names}
        report["pooled_mae_w_m2"] = pooled
        report["janus_beats_every_baseline"] = all(pooled["JANUS_PHYSICS_HEURISTIC"] < v
                     for k, v in pooled.items() if k != "JANUS_PHYSICS_HEURISTIC")
        print("NOAA_POOLED " + json.dumps(pooled, sort_keys=True), flush=True)
    else:
        print("NOAA_POOLED NOT_SCORED_INCOMPLETE", flush=True)
    write_once(outdir / "noaa_backtest_result_009e.json", report)
    return report


def calibrator_controls(outdir):
    # Phase 1: learn a simple order/persistence statistic from the past only.
    rng = random.Random(TRAIN_SEED)
    history = []
    state = 0
    for _ in range(4096):
        state = state if rng.random() < TRIAL_MODEL_P_SAME else 1 - state
        history.append(state)
    same = sum(a == b for a, b in zip(history[:-1], history[1:]))
    p_stay = (same + 1) / (len(history) + 1)  # Beta(1,1) smoothing on 4095 transitions
    contexts = [rng.randrange(2) for _ in range(N_BITS)]
    predictions = list(contexts)
    probs = [p_stay if b else 1 - p_stay for b in contexts]
    early = {"schema": "janus.open009e.two_phase_early.v1",
             "trained_p_stay": p_stay, "training_n_transitions": len(history) - 1,
             "n": N_BITS, "predicted_bits": predictions, "p_one": probs,
             "late_random_choice_generated": False, "frozen_model": "Beta-smoothed Markov persistence"}
    write_once(outdir / "calibrator_early_009e.json", early)
    early_sha = digest(early)

    # Phase 2: late independent random bits are first obtained AFTER early file fsync.
    late_bytes = secrets.token_bytes(N_BITS // 8)
    late = [(byte >> i) & 1 for byte in late_bytes for i in range(7, -1, -1)]
    ctrl_rng = random.Random(SIM_POS_SEED)
    predictable = [v if ctrl_rng.random() < TRIAL_MODEL_P_SAME else 1 - v for v in contexts]
    leak_rng = random.Random(SIM_LEAK_SEED)
    injected = [v if leak_rng.random() < 0.56 else 1 - v for v in contexts]

    def score(bits):
        correct = sum(p == y for p, y in zip(predictions, bits))
        return {"matches": correct, "accuracy": round(correct / N_BITS, 8),
                "one_sided_exact_binom_p": exact_binom_upper(N_BITS, correct),
                "brier": round(statistics.mean((p - y) ** 2 for p, y in zip(probs, bits)), 8)}
    report = {"schema": "janus.open009e.two_phase_control.v1",
              "early_sha256": early_sha,
              "early_fsynced_before_late_choice": True,
              "independent_late_choice": score(late),
              "causally_predictable_markov_control": score(predictable),
              "deliberately_injected_dependency_control": score(injected),
              "late_random_bytes_hex": late_bytes.hex(),
              "simulation_limit": "Local OS randomness and one software process; no external late free choice, timestamp witness or physical retrocausal channel",
              "real_transformer_was_evaluated": False,
              "retrocausality_proven": False}
    write_once(outdir / "calibrator_control_result_009e.json", report)
    print("CALIBRATOR_RESULT " + json.dumps({k: v for k, v in report.items()
                  if k.endswith("_control") or k == "independent_late_choice"}, sort_keys=True), flush=True)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--calibrator-only", action="store_true")
    args = ap.parse_args()
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    calibrator_controls(outdir)
    if not args.calibrator_only:
        historic_backtest(outdir)


if __name__ == "__main__":
    main()
