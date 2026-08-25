from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCHEMA = "janus.numerical_divergence_guard.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def sanitize_state(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    input_keys = payload.get("input_keys") if isinstance(payload.get("input_keys"), list) else []
    clean_weights: dict[str, float] = {}
    raw_weights = payload.get("weights") if isinstance(payload.get("weights"), dict) else {}
    for key, value in raw_weights.items():
        try:
            fv = float(value)
        except Exception:
            continue
        if not math.isfinite(fv):
            continue
        clean_weights[str(key)] = _clip(fv, -10.0, 10.0)

    try:
        bias = float(payload.get("bias", 0.0))
    except Exception:
        bias = 0.0
    if not math.isfinite(bias):
        bias = 0.0
    bias = _clip(bias, -10.0, 10.0)

    try:
        best_score = float(payload.get("best_score", -1e9))
    except Exception:
        best_score = -1e9
    if not math.isfinite(best_score):
        best_score = -1e9

    history = payload.get("history_tail") if isinstance(payload.get("history_tail"), list) else []
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "SANITIZED_STATE_CANDIDATE",
        "input_keys": [str(x) for x in input_keys[:64]],
        "weights": clean_weights,
        "bias": bias,
        "best_score": best_score,
        "history_tail": history[-64:],
        "authority": {
            "writes_model_state": False,
            "loads_model_state": False,
            "changes_learning_rate": False,
        },
        "laws": [
            "SANITIZED_STATE_NE_APPLIED_STATE",
            "NONFINITE_PARAMETER_MUST_NOT_ENTER_ACTIVE_STATE",
            "STATE_REPAIR_REQUIRES_SEPARATE_APPLY_GATE",
        ],
    }
    body["state_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def assess(weights: dict[str, Any], bias: Any, current_lr_scale: float = 1.0) -> dict[str, Any]:
    if not isinstance(weights, dict):
        raise ValueError("weights must be a dict")
    try:
        lr_scale = float(current_lr_scale)
    except Exception as exc:
        raise ValueError("current_lr_scale must be numeric") from exc
    if not math.isfinite(lr_scale):
        raise ValueError("current_lr_scale must be finite")

    parsed: dict[str, float] = {}
    nonfinite_keys: list[str] = []
    invalid_keys: list[str] = []
    for key, value in weights.items():
        try:
            fv = float(value)
        except Exception:
            invalid_keys.append(str(key))
            continue
        if not math.isfinite(fv):
            nonfinite_keys.append(str(key))
            continue
        parsed[str(key)] = fv

    try:
        bias_f = float(bias)
    except Exception:
        bias_f = float("nan")
    bias_nonfinite = not math.isfinite(bias_f)
    max_abs = max((abs(v) for v in parsed.values()), default=0.0)
    magnitude_trigger = max_abs > 25.0
    trigger = bool(nonfinite_keys or invalid_keys or bias_nonfinite or magnitude_trigger)

    if trigger:
        candidate_weights = {k: _clip(v, -3.0, 3.0) for k, v in parsed.items()}
        candidate_bias = 0.0 if bias_nonfinite else _clip(bias_f, -3.0, 3.0)
        proposed_lr_scale = 0.6
        status = "STABILIZATION_PROPOSAL"
    else:
        candidate_weights = dict(parsed)
        candidate_bias = bias_f
        proposed_lr_scale = min(1.2, 0.99 * lr_scale + 0.01)
        status = "STABLE_OBSERVATION"

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "observed": {
            "max_abs_weight": max_abs,
            "bias_nonfinite": bias_nonfinite,
            "nonfinite_weight_keys": sorted(nonfinite_keys),
            "invalid_weight_keys": sorted(invalid_keys),
            "magnitude_trigger_gt_25": magnitude_trigger,
            "current_lr_scale": lr_scale,
        },
        "candidate": {
            "weights": candidate_weights,
            "bias": candidate_bias,
            "lr_scale": proposed_lr_scale,
        },
        "authority": {
            "mutates_weights": False,
            "mutates_bias": False,
            "changes_learning_rate": False,
            "loads_or_saves_model": False,
        },
        "laws": [
            "DIVERGENCE_DETECTION_NE_MODEL_MUTATION",
            "BLACKHOLE_PROPOSAL_NE_AUTOMATIC_APPLY",
            "NONFINITE_WEIGHT_IS_EXPLICIT_TRIGGER",
            "GREEN_LOCAL_OBJECTIVE_DOES_NOT_OVERRIDE_RETURN_PATH_FAILURE",
        ],
    }
    body["guard_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
