"""Inference-only, exact-checkpoint output calibration admitted by a native auditor.

The adapter is bounded numeric data. It cannot replace weights, execute code,
change training gates, choose tools or authorize repository mutations.
"""
from __future__ import annotations
import hashlib
import json
import math

VOCAB = 258
MAX_ABS = 0.25
MAX_NORM = 2.0
SCHEMA = "janus.helios.native_calibration.v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def validate_bias(value):
    if not isinstance(value, list) or len(value) != VOCAB:
        raise ValueError("CALIBRATION_SHAPE_REJECTED")
    if any(type(x) not in (float, int) or not math.isfinite(x) or abs(x) > MAX_ABS for x in value):
        raise ValueError("CALIBRATION_VALUE_REJECTED")
    if sum(x*x for x in value) > MAX_NORM**2 or abs(sum(value)/VOCAB) > 1e-5:
        raise ValueError("CALIBRATION_BUDGET_REJECTED")
    return [float(x) for x in value]


def validate_admission(receipt, checkpoint_sha256):
    if (not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA or
            receipt.get("status") != "ADMITTED_NATIVE_CALIBRATION" or
            receipt.get("checkpoint_sha256") != checkpoint_sha256 or
            receipt.get("scope") != "INFERENCE_LOGIT_CALIBRATION_ONLY" or
            receipt.get("native_auditor_passed") is not True):
        raise ValueError("CALIBRATION_ADMISSION_REJECTED")
    bias = validate_bias(receipt.get("bias"))
    log_scale = receipt.get("log_scale")
    if type(log_scale) not in (int,float) or not math.isfinite(log_scale) or abs(log_scale) > 0.05:
        raise ValueError("CALIBRATION_SCALE_REJECTED")
    if receipt.get("calibration_sha256") != hashlib.sha256(canonical({"bias":bias,"log_scale":log_scale})).hexdigest():
        raise ValueError("CALIBRATION_DIGEST_REJECTED")
    metrics = receipt.get("metrics") or {}
    from janus_model.eval_contract import MIN_MEANINGFUL_IMPROVEMENT_FRACTION, VERIFIED_NONREGRESSION_NOISE_FRACTION
    fractions = []
    for name in ("adaptive", "anchor"):
        row = metrics.get(name) or {}
        if row.get("batches") != 24 or row.get("batch_size") != 8 or row.get("context_length") != 128:
            raise ValueError("CALIBRATION_EVALUATION_BUDGET_REJECTED")
        before, after = row.get("before"), row.get("after")
        if (type(before) not in (int, float) or type(after) not in (int, float) or
                not math.isfinite(before) or not math.isfinite(after) or before <= 0 or after < 0):
            raise ValueError("CALIBRATION_METRICS_REJECTED")
        fractions.append((before-after)/before)
    if min(fractions) < -VERIFIED_NONREGRESSION_NOISE_FRACTION or max(fractions) < MIN_MEANINGFUL_IMPROVEMENT_FRACTION:
        raise ValueError("CALIBRATION_REGRESSION_REJECTED")
    return bias


def attach_calibration(model, receipt, checkpoint_sha256):
    import torch
    import torch.nn.functional as functional
    bias = validate_admission(receipt, checkpoint_sha256)
    if model.config.vocab_size != VOCAB:
        raise ValueError("CALIBRATION_VOCAB_REJECTED")
    vector = torch.tensor(bias, dtype=next(model.parameters()).dtype,
                          device=next(model.parameters()).device)

    def calibrated_output(module, args, kwargs, output):
        if module.training:
            raise RuntimeError("CALIBRATION_IS_INFERENCE_ONLY")
        logits, loss = output
        logits = logits * math.exp(receipt["log_scale"]) + vector
        targets = args[1] if len(args) > 1 else kwargs.get("targets")
        if targets is not None:
            targets = targets[:, -logits.shape[1]:]
            loss = functional.cross_entropy(logits.reshape(-1, VOCAB), targets.reshape(-1))
        return logits, loss

    return model.register_forward_hook(calibrated_output, with_kwargs=True)
