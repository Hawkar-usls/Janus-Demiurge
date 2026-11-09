#!/usr/bin/env python3
"""JANUS Ocean CTRL-006: reproducible offline causal-control demonstrations.

All plant and QPU observations here are SYNTHETIC fixtures, not real measurements.
No IBM imports, QPU connections, provider credentials, internet, or model changes.
This is not an amendment of preregistered JANUS-RETRO-PHYSICAL-005.
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
sys.path.insert(0, str(OCEAN))
import physical_qpu_005_protocol as qpu005

SCHEMA = "janus.ocean.causality_controls_006.v1"
ID = "BANANA-TO-JANUS-CAUSALITY-CONTROLS-006"
SEED = 20261109
SHOTS = 4096
EPISODES = 40
STEPS = 12
TRAIN_END = 24
VALID_END = 32
FORECAST_ALLOWED_FIELDS = frozenset(("episode", "t", "maturity", "ethylene", "temperature"))
EXPECTED_BLOBS = {
    "banana_20260126_original.json": "a83a3df5188717dbfd761f59b9c004b8425503d8",
    "qpu005_20261109_prereg.json": "42d0053c15f7c7e0032538cce45b0564686aca86",
    "banana_qpu005_bridge_20261109.json": "6b5b823a7333c9cc08e84a657d5c43781935e54b",
    "physical_qpu_005_protocol.py": "09448c98ef0321660e739a558d0e43ab55ae5289",
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def write_once(path, value):
    dest = Path(path)
    if dest.exists():
        raise ValueError("REFUSE_TO_OVERWRITE_SCIENTIFIC_EVIDENCE")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def synthetic_ripening():
    """Episodes share a synthetic forward-time law; splits are by episode."""
    rng = random.Random(SEED)
    rows = []
    for ep in range(EPISODES):
        maturity = .08 + .014 * (ep % 7)
        for step in range(STEPS):
            temperature = round(rng.uniform(19, 26), 6)
            ethylene = round(rng.choice((0.0, 0.25, 0.5, 1.0)), 6)
            noise = rng.uniform(-.003, .003)
            delta = .018 + .046 * ethylene + .006 * (temperature - 22) + noise
            target = round(min(.98, max(maturity, maturity + delta)), 6)
            rows.append({
                "episode": ep,
                "t": step,
                "maturity": round(maturity, 6),
                "temperature": temperature,
                "ethylene": ethylene,
                "target_t": step + 1,
                "target": target,
                "synthetic": True,
            })
            maturity = target
    return rows


def solve_three_by_three(a, b):
    aug = [list(a[i]) + [b[i]] for i in range(3)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda j: abs(aug[j][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("SINGULAR_TRAINING_MATRIX")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        fac = aug[col][col]
        aug[col] = [v / fac for v in aug[col]]
        for other in range(3):
            if other == col:
                continue
            factor = aug[other][col]
            aug[other] = [x - factor * y for x, y in zip(aug[other], aug[col])]
    return [row[3] for row in aug]


def fit_forward_model(rows):
    train = [r for r in rows if r["episode"] < TRAIN_END]
    assert len(train) == TRAIN_END * STEPS
    matrix = [[0.0] * 3 for _ in range(3)]
    rhs = [0.0] * 3
    for row in train:
        x = [1.0, row["ethylene"], row["temperature"] - 22.0]
        y = row["target"] - row["maturity"]
        for i in range(3):
            rhs[i] += x[i] * y
            for j in range(3):
                matrix[i][j] += x[i] * x[j]
    for i in range(3):
        matrix[i][i] += 1e-7
    return solve_three_by_three(matrix, rhs)


def predict_next(observed, coefficients):
    if set(observed) != FORECAST_ALLOWED_FIELDS:
        raise ValueError("FUTURE_OR_UNDECLARED_FEATURE_REFUSED")
    if any(not isinstance(observed[k], (int, float)) for k in FORECAST_ALLOWED_FIELDS):
        raise ValueError("NONNUMERIC_OBSERVATION")
    prediction = observed["maturity"] + (
        coefficients[0] + coefficients[1] * observed["ethylene"]
        + coefficients[2] * (observed["temperature"] - 22))
    return round(min(.98, max(0.0, prediction)), 6)


def observation(row):
    return {k: row[k] for k in FORECAST_ALLOWED_FIELDS}


def make_forecast_commit():
    rows = synthetic_ripening()
    coefficients = fit_forward_model(rows)
    # Validation episodes 24..31 are intentionally not tuned on or evaluated.
    test = [row for row in rows if row["episode"] >= VALID_END]
    assert len(test) == (EPISODES - VALID_END) * STEPS
    predictions = [
        {"episode": r["episode"], "t": r["t"], "target_t": r["target_t"],
         "prediction": predict_next(observation(r), coefficients),
         "persistence_baseline": r["maturity"]}
        for r in test
    ]
    payload = {
        "id": ID,
        "status": "SYNTHETIC_FORECAST_COMMIT_NOT_AN_EXTERNAL_TIMESTAMP",
        "seed": SEED,
        "train_episodes": [0, TRAIN_END - 1],
        "unused_validation_episodes": [TRAIN_END, VALID_END - 1],
        "test_episodes": [VALID_END, EPISODES - 1],
        "input_features": sorted(FORECAST_ALLOWED_FIELDS),
        "model_coefficients": [round(x, 12) for x in coefficients],
        "predictions": predictions,
    }
    return {"schema": SCHEMA, "phase": "FORECAST_PRECOMMIT",
            "payload": payload, "payload_sha256": sha256(payload),
            "external_independent_witness": False}


def score_forecast_commit(commit):
    expected = make_forecast_commit()
    if commit != expected or sha256(commit.get("payload")) != commit.get("payload_sha256"):
        raise ValueError("FORECAST_PRECOMMIT_OR_SCIENTIFIC_PLAN_CHANGED")
    rows = synthetic_ripening()
    truth = {(r["episode"], r["t"]): r for r in rows if r["episode"] >= VALID_END}
    predictions = commit["payload"]["predictions"]
    model_error = math.fsum(abs(item["prediction"] -
                                truth[item["episode"], item["t"]]["target"])
                            for item in predictions) / len(predictions)
    baseline_error = math.fsum(abs(item["persistence_baseline"] -
                                   truth[item["episode"], item["t"]]["target"])
                               for item in predictions) / len(predictions)
    if not (model_error < baseline_error):
        raise AssertionError("FORWARD_CAUSAL_SYNTHETIC_CONTROL_FAILED")
    return {
        "control": "BRIDGE-CTRL-01-FORWARD-BANANA",
        "status": "PASS_SYNTHETIC_ONLY",
        "forecast_commit_sha256": commit["payload_sha256"],
        "test_rows": len(predictions),
        "model_mae": round(model_error, 9),
        "persistence_mae": round(baseline_error, 9),
        "forward_improvement_over_persistence": True,
        "training_target_used_only_from_earlier_episodes": True,
        "late_test_target_was_not_a_predictor_feature": True,
        "true_future_measurements_collected": False,
        "scientific_note": "Synthetic maturation is predictable from current conditions. It is NOT retrocausal information transfer.",
    }


def make_qpu_fixture(injected=False):
    # Exactly 4096 labelled synthetic observations; no device or simulated Qiskit calls.
    rows = []
    for setting in (0, 1):
        a0 = 1024 if not injected or setting == 0 else 768
        a1 = 2048 - a0
        for a, count in ((0, a0), (1, a1)):
            for i in range(count):
                b = a if setting == 0 else (i % 2)
                rows.append([a, setting, b])
    random.Random(SEED + int(injected)).shuffle(rows)
    assert len(rows) == SHOTS
    return rows


def score_qpu_fixture(rows):
    if not isinstance(rows, list) or len(rows) != SHOTS:
        raise ValueError("ALL_4096_RAW_SHOTS_REQUIRED")
    counts = [[0, 0], [0, 0]]
    diagnostics = [[0, 0], [0, 0]]
    for row in rows:
        if (not isinstance(row, list) or len(row) != 3
                or any(type(x) is not int or x not in (0, 1) for x in row)):
            raise ValueError("INVALID_RAW_SHOT")
        a, c, b = row
        counts[c][a] += 1
        diagnostics[c][int(a == b)] += 1
    s0 = sum(counts[0])
    s1 = sum(counts[1])
    if min(s0, s1) < SHOTS // 4:
        raise ValueError("SETTING_QUALITY_HOLD_KEEP_ALL_ORIGINAL_SHOTS")
    p_value = qpu005.fisher_exact_two_sided(
        counts[0][0], counts[0][1], counts[1][0], counts[1][1])
    delta = counts[1][1] / s1 - counts[0][1] / s0
    return {
        "raw_shots_sha256": sha256(rows),
        "table": counts,
        "number_of_shots": len(rows),
        "primary_fisher_two_sided_p": round(p_value, 16),
        "primary_delta_a1_c1_minus_c0": round(delta, 9),
        "threshold_crossed": p_value < qpu005.SIGNIFICANCE_THRESHOLD,
        "diagnostic_a_equal_b_if_c0": round(diagnostics[0][1] / s0, 9),
        "diagnostic_a_equal_b_if_c1": round(diagnostics[1][1] / s1, 9),
        "synthetic": True,
    }


def qpu_offline_control():
    null_rows = make_qpu_fixture(False)
    injected_rows = make_qpu_fixture(True)
    null = score_qpu_fixture(null_rows)
    alternative = score_qpu_fixture(injected_rows)
    # The primary statistic cannot depend on the later B result.
    b_mutated = [[a, c, 1 - b] for a, c, b in null_rows]
    b_counterfactual = score_qpu_fixture(b_mutated)
    if null["table"] != [[1024, 1024], [1024, 1024]]:
        raise AssertionError("NO_SIGNALLING_NULL_FIXTURE_CHANGED")
    if null["threshold_crossed"] or null["primary_fisher_two_sided_p"] != 1:
        raise AssertionError("FALSE_POSITIVE_ON_NULL")
    if not alternative["threshold_crossed"]:
        raise AssertionError("INJECTED_ASSOCIATION_NOT_DETECTED")
    if (b_counterfactual["table"] != null["table"]
            or b_counterfactual["primary_fisher_two_sided_p"] !=
            null["primary_fisher_two_sided_p"]):
        raise AssertionError("LATE_B_POSTSELECTION_OR_LEAKAGE")
    return {
        "control": "BRIDGE-CTRL-02-QPU005",
        "status": "PASS_SYNTHETIC_ONLY",
        "frozen_qpu005_fisher_method_reused": True,
        "raw_sample_count_each_fixture": SHOTS,
        "null": null,
        "deliberately_injected_association": alternative,
        "counterfactual_late_B_does_not_change_primary": True,
        "real_ibm_job_id": None,
        "real_qpu_shots": 0,
        "device_timing_and_spacelike_separation_verified": False,
        "scientific_note": "Injected A-C association proves test sensitivity only. It does not imply a physical or retrocausal signal.",
    }


def provenance_control():
    fixtures = HERE / "fixtures"
    checked = {}
    for name in ("banana_20260126_original.json",
                 "qpu005_20261109_prereg.json",
                 "banana_qpu005_bridge_20261109.json"):
        raw = (fixtures / name).read_bytes()
        blob = git_blob_sha(raw)
        if blob != EXPECTED_BLOBS[name]:
            raise ValueError("HISTORICAL_GIT_BLOB_MISMATCH:" + name)
        checked[name] = blob
    frozen_raw = (OCEAN / "physical_qpu_005_protocol.py").read_bytes()
    frozen_hash = git_blob_sha(frozen_raw)
    if frozen_hash != EXPECTED_BLOBS["physical_qpu_005_protocol.py"]:
        raise ValueError("FROZEN_QPU005_PROTOCOL_CHANGED")
    checked["physical_qpu_005_protocol.py"] = frozen_hash

    banana = json.loads((fixtures / "banana_20260126_original.json").read_text())
    prereg = json.loads((fixtures / "qpu005_20261109_prereg.json").read_text())
    bridge = json.loads((fixtures / "banana_qpu005_bridge_20261109.json").read_text())
    if banana.get("artifact_type") != "BIOLOGICAL_UNIT_TEST":
        raise ValueError("BANANA_ORIGIN_NOT_UNIT_TEST")
    if banana.get("version") != "1.0-UNICODE":
        raise ValueError("BANANA_ORIGINAL_VERSION_MISMATCH")
    if prereg.get("experiment_id") != "JANUS-RETRO-PHYSICAL-005":
        raise ValueError("PHYSICAL_PROTOCOL_ID_CHANGED")
    if prereg["predeclared_hardware_design"]["shots_one_provider_job"] != SHOTS:
        raise ValueError("SHOT_COUNT_CHANGED")
    if prereg["predeclared_hardware_design"]["primary_alpha"] != .001:
        raise ValueError("PRIMARY_ALPHA_CHANGED")
    sources = {s["source_id"]: s for s in bridge["original_sources"]}
    if (sources["BANANA_DNA_DECODER_ORIGINAL"]["original_git_blob_sha"]
            != checked["banana_20260126_original.json"]):
        raise ValueError("BRIDGE_BANANA_REFERENCE_TAMPERED")
    if (sources["QPU005_PREREGISTRATION"]["git_blob_sha"]
            != checked["qpu005_20261109_prereg.json"]):
        raise ValueError("BRIDGE_QPU_REFERENCE_TAMPERED")
    if bridge["status"] != "RESEARCH_HYPOTHESIS_REGISTERED__NO_NEW_PHYSICAL_MEASUREMENTS":
        raise ValueError("FALSE_PHYSICAL_EVIDENCE_CLAIM")
    if any(bridge["safety"][key] for key in (
        "original_banana_json_modified",
        "original_qpu005_code_modified",
        "IBM_provider_called_by_this_record",
    )):
        raise ValueError("BRIDGE_FALSE_PROVENANCE")
    if len(bridge["proposed_controls"]) != 3:
        raise ValueError("BRIDGE_CONTROL_COUNT_CHANGED")
    return {
        "control": "BRIDGE-CTRL-03-TRACEABILITY",
        "status": "PASS_HISTORICAL_SNAPSHOTS_AND_CURRENT_QPU_SOURCE",
        "verified_git_blob_sha": checked,
        "original_banana_commit": "05af9149c4d8f94bba56c740194760d8f5353221",
        "original_qpu005_merge_commit": "8fa54f25c5bf3f5593db6b7ddc2a3a8da5f78f19",
        "bridge_reference_pr": "https://github.com/Hawkar-usls/janus-meta-registry/pull/477",
        "evidence_scope": "Pinned Git blobs and offline provenance; not independent chronological notarization",
        "no_external_git_or_ibm_requests": True,
    }


def run_all():
    forecast_commit = make_forecast_commit()
    return {
        "schema": SCHEMA,
        "experiment_id": ID,
        "status": "OFFLINE_CONTROLS_PASS__SYNTHETIC_ONLY",
        "seed": SEED,
        "source_experiment_preserved": "JANUS-RETRO-PHYSICAL-005",
        "forecast_precommit": forecast_commit,
        "controls": [
            score_forecast_commit(forecast_commit),
            qpu_offline_control(),
            provenance_control(),
        ],
        "new_physical_qpu_results": False,
        "qpu_time_used_minutes": 0,
        "hardware_provider_called": False,
        "real_banana_measurements": False,
        "retrocausality_proven": False,
        "publication_limit": "Reproducible unit tests of procedures, not real biological or quantum outcomes",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "score", "qpu", "provenance", "all"))
    p.add_argument("--input")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.mode == "prepare":
        result = make_forecast_commit()
    elif args.mode == "score":
        if not args.input:
            p.error("--input forecast precommit is required")
        result = score_forecast_commit(json.loads(Path(args.input).read_text()))
    elif args.mode == "qpu":
        result = qpu_offline_control()
    elif args.mode == "provenance":
        result = provenance_control()
    else:
        result = run_all()
    write_once(args.output, result)
    print(json.dumps({
        "mode": args.mode, "status": result.get("status", result.get("phase")),
        "sha256": sha256(result), "real_qpu_job_submitted": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
