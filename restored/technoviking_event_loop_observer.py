from __future__ import annotations

import hashlib
import json
import math
from statistics import median
from typing import Any, Iterable

SCHEMA = "janus.technoviking.event_loop_observer.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return x


def _percentile_nearest_rank(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def observe_lag(
    lag_samples_ms: Iterable[float],
    *,
    warn_ms: float = 100.0,
    severe_ms: float = 500.0,
) -> dict[str, Any]:
    warn = _finite_nonnegative("warn_ms", warn_ms)
    severe = _finite_nonnegative("severe_ms", severe_ms)
    if severe <= warn:
        raise ValueError("severe_ms must be greater than warn_ms")

    samples = [_finite_nonnegative("lag_sample_ms", x) for x in lag_samples_ms]
    if not samples:
        state = "NO_DATA"
        p50 = p95 = peak = 0.0
        warn_count = severe_count = 0
    else:
        p50 = float(median(samples))
        p95 = _percentile_nearest_rank(samples, 0.95)
        peak = max(samples)
        warn_count = sum(x >= warn for x in samples)
        severe_count = sum(x >= severe for x in samples)
        if severe_count or p95 >= severe:
            state = "SEVERE"
        elif warn_count or p95 >= warn:
            state = "WARN"
        else:
            state = "NORMAL"

    suggested_backoff_ms = 0.0
    if state == "WARN":
        suggested_backoff_ms = min(1000.0, max(warn, p95))
    elif state == "SEVERE":
        suggested_backoff_ms = min(5000.0, max(severe, p95))

    body = {
        "schema": SCHEMA,
        "state": state,
        "sample_count": len(samples),
        "p50_lag_ms": p50,
        "p95_lag_ms": p95,
        "peak_lag_ms": peak,
        "warn_threshold_ms": warn,
        "severe_threshold_ms": severe,
        "warn_or_worse_count": warn_count,
        "severe_count": severe_count,
        "suggested_backoff_ms": suggested_backoff_ms,
        "provenance": {
            "historical_role": "event_loop_monitor/stabilizer",
            "historical_canonical_md5_anchor": "22f0a0696a3c50b11793ffc9180b3d9e",
            "exact_historical_bytes_recovered": False,
            "runtime_marker": "TECHNOVIKING: Lag detected",
            "relationship": "ROLE_BACKED_RECONSTRUCTION_NOT_BYTE_DESCENDANT",
        },
        "authority": {
            "calls_gc_collect": False,
            "changes_mood": False,
            "changes_entropy": False,
            "sleeps_or_throttles": False,
            "starts_or_stops_services": False,
            "changes_event_loop": False,
        },
        "laws": [
            "LAG_OBSERVATION_NE_SCHEDULER_AUTHORITY",
            "RUNTIME_MARKER_NE_EXACT_SOURCE_RECOVERY",
            "ROLE_BACKED_RECONSTRUCTION_NE_BYTE_DESCENT",
            "GC_OR_SERVICE_CONTROL_REQUIRES_SEPARATE_AUTHORITY",
        ],
    }
    body["receipt_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
