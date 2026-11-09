#!/usr/bin/env python3
"""JANUS LIGHT-008: prospective real-light capture analysis, no hardware invocation.

Physical input MUST arrive separately from a real collection device; this module
does not synthesize or fabricate observations. Synthetic input is accepted
exclusively for explicit unit tests and remains visibly marked synthetic.

Protocol: schedule -> TRAIN physical capture -> prediction precommit ->
external GitHub/witness publication -> TEST physical capture -> score.
The local commit hash or local UTC clock is NOT an independent time witness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import secrets

SCHEMA = "janus.ocean.light_physical_008.v1"
EXPERIMENT = "JANUS-LIGHT-PHYSICAL-008"
N = 256
PERIOD_MS = 50
SETTLE_MS = 5
LAGS = tuple(range(5))
REAL = "ESP32_USB_CAPTURE"
SYNTHETIC = "SYNTHETIC_UNIT_TEST"


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(v):
    if not isinstance(v, str) or not v.endswith("Z"):
        raise ValueError("UTC_TIMESTAMP_WITH_Z_REQUIRED")
    try:
        d = datetime.fromisoformat(v[:-1] + "+00:00")
    except ValueError:
        raise ValueError("INVALID_UTC_TIMESTAMP") from None
    if d.utcoffset().total_seconds() != 0:
        raise ValueError("NON_UTC_CLOCK")
    return d


def atomic_new(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, indent=2,
                         sort_keys=True, allow_nan=False) + "\n"
    with p.open("x", encoding="utf-8") as f:
        f.write(payload)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def shuffled_balanced_bits(rng):
    bits = [0] * (N // 2) + [1] * (N // 2)
    rng.shuffle(bits)
    return bits


def make_schedule(rng=None, timestamp=None, plan_id=None):
    # Production CLI uses SystemRandom; deterministic RNG only in unit tests.
    rng = rng if rng is not None else secrets.SystemRandom()
    payload = {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "type": "PROSPECTIVE_SOURCE_SCHEDULE",
        "plan_id": plan_id if plan_id is not None else secrets.token_hex(16),
        "created_utc": timestamp if timestamp is not None else utc_now(),
        "sampling_period_ms": PERIOD_MS,
        "settle_ms": SETTLE_MS,
        "samples_per_phase": N,
        "train_bits": shuffled_balanced_bits(rng),
        "test_bits": shuffled_balanced_bits(rng),
        "source_class": "PLANNED_LED_MODULATION_NOT_PHYSICAL_DATA",
    }
    return {"payload": payload, "payload_sha256": sha(payload)}


def validate_schedule(schedule):
    if (not isinstance(schedule, dict) or
            sha(schedule.get("payload")) != schedule.get("payload_sha256")):
        raise ValueError("SOURCE_SCHEDULE_SHA_MISMATCH")
    p = schedule["payload"]
    if (p.get("schema") != SCHEMA or p.get("experiment") != EXPERIMENT or
            p.get("type") != "PROSPECTIVE_SOURCE_SCHEDULE" or
            p.get("samples_per_phase") != N or
            p.get("sampling_period_ms") != PERIOD_MS or
            p.get("settle_ms") != SETTLE_MS or
            p.get("source_class") != "PLANNED_LED_MODULATION_NOT_PHYSICAL_DATA"):
        raise ValueError("SOURCE_SCHEDULE_PROTOCOL_DRIFT")
    parse_utc(p.get("created_utc"))
    if not isinstance(p.get("plan_id"), str) or len(p["plan_id"]) < 16:
        raise ValueError("INVALID_PLAN_ID")
    for phase in ("train", "test"):
        bits = p.get(phase + "_bits")
        if (not isinstance(bits, list) or len(bits) != N or
                any(type(x) is not int or x not in (0, 1) for x in bits) or
                sum(bits) != N // 2):
            raise ValueError("SOURCE_SCHEDULE_NOT_BALANCED_AND_COMPLETE")
    return p


def validate_capture(capture, schedule, phase, source_class=None):
    p = validate_schedule(schedule)
    if phase not in ("train", "test"):
        raise ValueError("UNEXPECTED_CAPTURE_PHASE")
    if not isinstance(capture, dict):
        raise ValueError("INVALID_CAPTURE")
    if (capture.get("schema") != SCHEMA or capture.get("phase") != phase or
            capture.get("plan_sha256") != schedule["payload_sha256"] or
            capture.get("plan_id") != p["plan_id"]):
        raise ValueError("CAPTURE_PLAN_OR_PHASE_MISMATCH")
    cls = capture.get("source_class")
    if cls not in (REAL, SYNTHETIC):
        raise ValueError("SOURCE_CLASS_MUST_BE_EXPLICIT")
    if source_class is not None and cls != source_class:
        raise ValueError("MIXED_REAL_AND_SYNTHETIC_DATA_REFUSED")
    rows = capture.get("rows")
    if not isinstance(rows, list) or len(rows) != N:
        raise ValueError("ALL_256_UNFILTERED_SAMPLES_REQUIRED")
    last_monotonic = -1
    last_elapsed = -1
    last_utc = None
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("INVALID_CAPTURE_ROW")
        if (type(row.get("seq")) is not int or row["seq"] != i or
                type(row.get("led")) is not int or row["led"] != p[phase+"_bits"][i]):
            raise ValueError("ROW_ORDER_OR_LED_SCHEDULE_MISMATCH")
        if type(row.get("adc_u16")) is not int or not 0 <= row["adc_u16"] <= 65535:
            raise ValueError("INVALID_ADC_U16")
        elapsed = row.get("esp_elapsed_us")
        monotonic = row.get("host_monotonic_ns")
        if (type(elapsed) is not int or type(monotonic) is not int or
                elapsed < 0 or monotonic <= last_monotonic or
                elapsed <= last_elapsed):
            raise ValueError("NONMONOTONIC_DEVICE_OR_HOST_CLOCK")
        last_elapsed, last_monotonic = elapsed, monotonic
        stamp = parse_utc(row.get("host_received_utc"))
        if last_utc is not None and stamp < last_utc:
            raise ValueError("UTC_CLOCK_MOVED_BACKWARDS")
        last_utc = stamp
    if capture.get("total_samples") != N:
        raise ValueError("INCOMPLETE_COUNT_CLAIM")
    return rows


def fit_model(train, schedule):
    rows = validate_capture(train, schedule, "train")
    bits = schedule["payload"]["train_bits"]
    # Do not use the first MAX_LAG samples; the preceding LED state is unknown.
    models = []
    for lag in LAGS:
        pairs = [(bits[i - lag], rows[i]["adc_u16"]) for i in range(max(LAGS), N)]
        zero = [value for bit, value in pairs if bit == 0]
        one = [value for bit, value in pairs if bit == 1]
        if len(zero) < 40 or len(one) < 40:
            raise ValueError("INSUFFICIENT_TREATMENT_BALANCE")
        mu0, mu1 = sum(zero) / len(zero), sum(one) / len(one)
        mse = math.fsum((v - (mu1 if bit else mu0))**2 for bit, v in pairs)/len(pairs)
        models.append({"lag_bins": lag, "mu_off": mu0, "mu_on": mu1, "train_mse": mse})
    winner = min(models, key=lambda x: (x["train_mse"], x["lag_bins"]))
    return {
        "lag_bins": winner["lag_bins"],
        "mu_off": round(winner["mu_off"], 8),
        "mu_on": round(winner["mu_on"], 8),
        "train_mse": round(winner["train_mse"], 8),
        "baseline_mean_adc": round(sum(r["adc_u16"] for r in rows) / N, 8),
        "fit_max_lag_bins": max(LAGS),
        "train_saturation_fraction": round(sum(
            r["adc_u16"] in (0, 65535) for r in rows) / N, 7),
    }


def make_precommit(schedule, train, timestamp=None):
    p = validate_schedule(schedule)
    rows = validate_capture(train, schedule, "train")
    model = fit_model(train, schedule)
    lag = model["lag_bins"]
    bits = p["test_bits"]
    predictions = []
    for i in range(N):
        # Each independent phase begins with LED physically LOW; no lookahead.
        source = bits[i - lag] if i >= lag else 0
        level = model["mu_on"] if source else model["mu_off"]
        predictions.append({"seq": i, "adc_prediction": round(level, 6),
                            "constant_baseline": model["baseline_mean_adc"]})
    payload = {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "phase": "FORECAST_PRECOMMIT_BEFORE_TEST_CAPTURE",
        "plan_sha256": schedule["payload_sha256"],
        "train_capture_sha256": sha(train),
        "source_class": train["source_class"],
        "model": model,
        "predictions": predictions,
        "n_predictions": N,
        "real_test_measurements_accessed": False,
    }
    return {
        "payload": payload,
        "payload_sha256": sha(payload),
        "prepared_utc_self_reported": timestamp if timestamp else utc_now(),
        "external_precommit_witness_verified": False,
    }


def score(schedule, train, precommit, test):
    validate_schedule(schedule)
    source_class = train.get("source_class")
    train_rows = validate_capture(train, schedule, "train")
    test_rows = validate_capture(test, schedule, "test", source_class)
    if (not isinstance(precommit, dict) or
            sha(precommit.get("payload")) != precommit.get("payload_sha256")):
        raise ValueError("PRECOMMIT_HASH_INVALID")
    parse_utc(precommit.get("prepared_utc_self_reported"))
    expected = make_precommit(schedule, train,
                              timestamp=precommit["prepared_utc_self_reported"])
    if expected != precommit:
        raise ValueError("PRECOMMIT_CHANGED_AFTER_CALIBRATION")
    if train_rows[-1]["host_received_utc"] >= precommit["prepared_utc_self_reported"]:
        raise ValueError("FORECAST_WAS_NOT_AFTER_CALIBRATION")
    if test_rows[0]["host_received_utc"] <= precommit["prepared_utc_self_reported"]:
        raise ValueError("FORECAST_WAS_NOT_BEFORE_TEST_CAPTURE")
    predictions = precommit["payload"]["predictions"]
    mae = math.fsum(abs(row["adc_prediction"] - observed["adc_u16"])
                    for row, observed in zip(predictions, test_rows))/N
    baseline = math.fsum(abs(row["constant_baseline"] - observed["adc_u16"])
                         for row, observed in zip(predictions, test_rows))/N
    adc_max = max(r["adc_u16"] for r in test_rows)
    adc_min = min(r["adc_u16"] for r in test_rows)
    return {
        "schema": SCHEMA,
        "experiment": EXPERIMENT,
        "status": ("REAL_RECORDING_SCORED_WITH_SELF_REPORTED_TIMES"
                   if source_class == REAL else "SYNTHETIC_TEST_ONLY"),
        "source_class": source_class,
        "run_plan_sha256": schedule["payload_sha256"],
        "train_capture_sha256": sha(train),
        "test_capture_sha256": sha(test),
        "forecast_precommit_sha256": precommit["payload_sha256"],
        "n_unfiltered_samples": N,
        "mae_forecast_adc": round(mae, 6),
        "mae_constant_baseline_adc": round(baseline, 6),
        "beats_baseline": mae < baseline,
        "selected_lag_bins_from_train_only": precommit["payload"]["model"]["lag_bins"],
        "bin_period_ms": PERIOD_MS,
        "adc_observed_range": [adc_min, adc_max],
        "sensor_saturation_fraction": round(
            sum(r["adc_u16"] in (0, 65535) for r in test_rows)/N, 7),
        "host_clock_sequence_check": "PASS_SELF_REPORTED_UTC_AND_MONOTONIC",
        "time_sync_verified_by_independent_custodian": False,
        "precommit_preceded_test_verified_externally": False,
        "optical_propagation_time_measured": False,
        "hardware_lineage_independently_verified": False,
        "physical_retrocausality_proven": False,
        "IBM_provider_called": False,
        "QPU_minutes_used": 0,
        "limitations": [
            "ESP32 ADC latency, firmware and USB transmission dominate nanosecond optical flight-time",
            "Local UTC timestamps may drift or be manipulated; these are receive times, not photon-event times",
            "External GitHub timestamp/witness review must occur before any scientific promotion",
            "Forward prediction given a predetermined LED schedule is conventional causation, never retrocausality",
            "A real physical claim requires verification of sensor identity, calibration and raw provenance",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    for action in ("schedule", "prepare", "score"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--output", required=True)
        if action != "schedule":
            cmd.add_argument("--plan", required=True)
            cmd.add_argument("--train", required=True)
        if action == "score":
            cmd.add_argument("--precommit", required=True)
            cmd.add_argument("--test", required=True)
    args = ap.parse_args()
    if args.mode == "schedule":
        output = make_schedule()
    elif args.mode == "prepare":
        output = make_precommit(read_json(args.plan), read_json(args.train))
    else:
        output = score(read_json(args.plan), read_json(args.train),
                       read_json(args.precommit), read_json(args.test))
    atomic_new(args.output, output)
    print(json.dumps({
        "experiment": EXPERIMENT, "mode": args.mode,
        "record_sha256": sha(output), "QPU_time_used_minutes": 0,
        "actual_physical_capture_performed_by_this_command": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
