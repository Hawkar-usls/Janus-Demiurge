"""Safe, PURE snapshot admissibility from legacy All Star Genesis helpers.

Provenance: local All Star/genesis_protocol.py
SHA256: 03a495bded40e1a01c51738946fd0312f03a921afcd8002fe8adc821ca0544f1
Original is_valid_metrics() accepts NaN score; original is_unstable()
does not reject NaN/-inf grad maximum. This sidecar rejects both.

No imports of Genesis, torch, numpy, config, system metrics, local files or
network. Not a claim about stability, training quality, P=NP or TOPA review.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

SCHEMA = "janus.demiurge.legacy_genesis_metric_admissibility.v1"
REQUIRED_FIELDS = (
    "score", "loss", "val_loss", "diversity",
    "mutual_information", "grad_mean", "grad_max"
)
GRADIENT_FIELDS = ("grad_mean", "grad_max")

def assess_legacy_metric_frame(frame: Mapping, *, gradient_ceiling: float = 100.0):
    """Classify only input validity and one LEGACY heuristic gradient threshold.

    Does not inspect or return any raw telemetry values. Unknown input fields
    (including names, locations, device identifiers and labels) are ignored.
    """
    if not isinstance(frame, Mapping):
        raise TypeError("METRICS_OBJECT_REQUIRED")
    if isinstance(gradient_ceiling, bool) or not isinstance(gradient_ceiling, (int, float)):
        raise ValueError("FINITE_POSITIVE_GRADIENT_CEILING_REQUIRED")
    if not math.isfinite(gradient_ceiling) or gradient_ceiling <= 0:
        raise ValueError("FINITE_POSITIVE_GRADIENT_CEILING_REQUIRED")

    reasons = []
    values = {}
    for field in REQUIRED_FIELDS:
        value = frame.get(field)
        if type(value) not in (int, float):
            reasons.append(field.upper() + "_MISSING_OR_NON_NUMERIC")
        else:
            try:
                f = float(value)
                if not math.isfinite(f):
                    reasons.append(field.upper() + "_NON_FINITE")
                else:
                    values[field] = f
            except (OverflowError, ValueError):
                reasons.append(field.upper() + "_NON_FINITE")
    for field in GRADIENT_FIELDS:
        if field in values and values[field] < 0:
            reasons.append(field.upper() + "_NEGATIVE")
    if "grad_max" in values and "grad_mean" in values:
        if values["grad_mean"] > values["grad_max"]:
            reasons.append("GRADIENT_MEAN_EXCEEDS_MAX")

    if reasons:
        status = "INVALID_METRIC_FRAME"
    elif values["grad_max"] > gradient_ceiling:
        reasons.append("LEGACY_GRADIENT_CEILING_EXCEEDED")
        status = "HEURISTIC_GRADIENT_ALERT"
    else:
        status = "FINITE_VALUES_ONLY"

    return {
        "schema": SCHEMA,
        "status": status,
        "reasonCodes": reasons,
        "metricValuesExported": False,
        "hypothesis": "UNTESTED_HEURISTIC_ONLY",
        "scientificVerdict": "NOT_TOPA_ADJUDICATED",
        "pEqualsNpProof": False,
        "autonomousGraphMutationAllowed": False,
        "externalProviderRequestsAllowed": False,
    }
