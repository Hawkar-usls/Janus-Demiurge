from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

SCHEMA = "janus.chronosync.batch_plan.v1"
PRIORITY = {"CRITICAL": 0, "NORMAL": 1, "COLD": 2}


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return x


def _payload_size_hint(value: Any) -> int:
    try:
        return len(_canon(value))
    except (TypeError, ValueError):
        return len(repr(value).encode("utf-8", errors="replace"))


def normalize_packets(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    packets = []
    for seq, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError("packet must be a mapping")
        source = str(raw.get("source") or "").strip()
        if not source:
            raise ValueError("packet source is required")
        timestamp = _finite_nonnegative("timestamp", raw.get("timestamp"))
        explicit = raw.get("priority")
        if explicit is None:
            if raw.get("critical") is True:
                priority = "CRITICAL"
            elif _payload_size_hint(raw.get("data")) > 5000:
                priority = "COLD"
            else:
                priority = "NORMAL"
        else:
            priority = str(explicit).strip().upper()
            if priority not in PRIORITY:
                raise ValueError(f"unsupported priority: {priority}")
        packet = {
            "sequence": seq,
            "source": source,
            "timestamp": timestamp,
            "priority": priority,
            "data": raw.get("data"),
            "conflict_key": raw.get("conflict_key"),
        }
        packet["packet_sha256"] = hashlib.sha256(_canon(packet)).hexdigest()
        packets.append(packet)
    return packets


def plan_batch(
    items: Iterable[dict[str, Any]],
    *,
    current_interval_s: float = 1.0,
    max_batch: int = 50,
) -> dict[str, Any]:
    interval = _finite_nonnegative("current_interval_s", current_interval_s)
    if interval == 0:
        raise ValueError("current_interval_s must be > 0")
    if isinstance(max_batch, bool) or not isinstance(max_batch, int) or max_batch < 1 or max_batch > 1000:
        raise ValueError("max_batch must be an integer in 1..1000")

    packets = normalize_packets(items)
    ordered = sorted(packets, key=lambda p: (PRIORITY[p["priority"]], p["sequence"]))
    selected = ordered[:max_batch]
    deferred = ordered[max_batch:]

    depth = len(packets)
    if depth > 10:
        next_interval = max(0.1, interval * 0.8)
        rate_state = "ACCELERATE"
    elif depth == 0:
        next_interval = min(5.0, interval * 1.2)
        rate_state = "IDLE_BACKOFF"
    else:
        next_interval = interval
        rate_state = "HOLD"

    conflict_counts: dict[str, int] = {}
    for p in selected:
        key = p.get("conflict_key")
        if key is not None:
            k = str(key)
            conflict_counts[k] = conflict_counts.get(k, 0) + 1
    unresolved = sorted(k for k, n in conflict_counts.items() if n > 1)

    body = {
        "schema": SCHEMA,
        "status": "BATCH_PLAN_ONLY",
        "input_count": depth,
        "selected_count": len(selected),
        "deferred_count": len(deferred),
        "rate_state": rate_state,
        "current_interval_s": interval,
        "suggested_next_interval_s": next_interval,
        "selected": selected,
        "deferred_packet_sha256": [p["packet_sha256"] for p in deferred],
        "unresolved_conflict_keys": unresolved,
        "authority": {
            "writes_memory": False,
            "writes_files": False,
            "writes_database": False,
            "resolves_conflicts": False,
            "drops_packets": False,
            "starts_background_task": False,
        },
        "provenance": {
            "historical_source": "chronosync.py",
            "historical_source_sha256": "8d400a6ae43f9800cf419ac357433ac7bf8209867c5f6a3d4efbe7316a965c2b",
            "relationship": "SAFE_SUBFUNCTION_RESTORATION_NOT_RUNTIME_EQUIVALENCE",
            "historical_conflict_resolver": "DEFINED_BUT_UNCALLED_IN_RECOVERED_SOURCE",
        },
        "laws": [
            "PRIORITY_PLAN_NE_WRITE_AUTHORITY",
            "CONFLICT_DETECTION_NE_CONFLICT_RESOLUTION",
            "CORE_NAME_NE_SOURCE_AUTHORITY",
            "FIFO_WITHIN_PRIORITY_REQUIRES_EXPLICIT_SEQUENCE",
            "DEFERRED_NE_DROPPED",
        ],
    }
    body["plan_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
