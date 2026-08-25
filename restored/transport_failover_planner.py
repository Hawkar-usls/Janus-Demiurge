from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

SCHEMA = "janus.transport_failover_plan.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _clean_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("target URL must be non-empty text")
    return value.strip().rstrip("/")


def build_plan(active_target: str | None, candidates: Iterable[str], event_type: str, data: Any, device_id: str) -> dict[str, Any]:
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be non-empty text")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be non-empty text")

    ordered: list[str] = []
    raw_targets = ([] if active_target is None else [active_target]) + list(candidates)
    for raw in raw_targets:
        try:
            clean = _clean_url(raw)
        except ValueError:
            continue
        if clean not in ordered:
            ordered.append(clean)
    if not ordered:
        raise ValueError("at least one valid target is required")

    payload = {
        "device_id": device_id.strip(),
        "type": event_type.strip(),
        "data": data,
    }
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "TRANSPORT_PLAN_ONLY",
        "targets": ordered,
        "request": {
            "method": "POST",
            "path": "/api/device/data",
            "payload": payload,
        },
        "policy": {
            "ack": "HTTP_2XX",
            "terminal_reject": "HTTP_4XX",
            "retry_or_failover": "HTTP_5XX_OR_NETWORK_ERROR",
        },
        "authority": {
            "opens_socket": False,
            "sends_network_request": False,
            "changes_active_target": False,
            "retries_automatically": False,
        },
        "laws": [
            "PLAN_NE_TRANSPORT_AUTHORITY",
            "HTTP_LT_500_NE_SUCCESS",
            "ACK_REQUIRES_2XX",
            "CLIENT_REJECTION_NE_RETRY_LOOP",
            "NETWORK_FAILURE_MAY_SUGGEST_NEXT_TARGET",
        ],
    }
    body["plan_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def classify_attempt(plan: dict[str, Any], target: str, http_status: int | None = None, network_error: str | None = None) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise ValueError("plan must be a transport failover plan")
    target = _clean_url(target)
    targets = plan.get("targets") or []
    if target not in targets:
        raise ValueError("target is not part of the plan")

    if network_error:
        outcome = "RETRY_OR_FAILOVER"
    else:
        if not isinstance(http_status, int):
            raise ValueError("http_status is required when network_error is absent")
        if 200 <= http_status < 300:
            outcome = "ACK"
        elif 400 <= http_status < 500:
            outcome = "TERMINAL_REJECT"
        else:
            outcome = "RETRY_OR_FAILOVER"

    idx = targets.index(target)
    next_target = targets[idx + 1] if outcome == "RETRY_OR_FAILOVER" and idx + 1 < len(targets) else None
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ATTEMPT_RECEIPT",
        "plan_sha256": plan.get("plan_sha256"),
        "target": target,
        "http_status": http_status,
        "network_error": network_error,
        "outcome": outcome,
        "next_target": next_target,
        "authority": {
            "sends_network_request": False,
            "switches_target": False,
        },
    }
    body["attempt_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
