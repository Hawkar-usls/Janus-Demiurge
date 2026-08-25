from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA = "janus.sender_request_envelope.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash64(name: str, value: Any) -> str:
    text = str(value or "").lower()
    if not HEX64.fullmatch(text):
        raise ValueError(f"{name} must be a 64-char lowercase SHA-256 hex string")
    return text


def bind_send_request(outbox_record: dict[str, Any], transport_plan: dict[str, Any], target: str) -> dict[str, Any]:
    if not isinstance(outbox_record, dict):
        raise ValueError("outbox_record must be a dict")
    if not isinstance(transport_plan, dict) or transport_plan.get("schema") != "janus.transport_failover_plan.v1":
        raise ValueError("transport_plan must be janus.transport_failover_plan.v1")

    record_sha = _hash64("record_sha256", outbox_record.get("record_sha256"))
    plan_sha = _hash64("plan_sha256", transport_plan.get("plan_sha256"))
    event_id = _hash64("event_id", outbox_record.get("event_id"))

    targets = transport_plan.get("targets") or []
    if target not in targets:
        raise ValueError("target must belong to transport plan")
    request = transport_plan.get("request") or {}
    method = str(request.get("method") or "").upper()
    path = str(request.get("path") or "")
    if method != "POST":
        raise ValueError("only POST plans are supported by this envelope version")
    if not path.startswith("/"):
        raise ValueError("request path must be absolute-path form")

    payload = request.get("payload")
    payload_sha = hashlib.sha256(_canon(payload)).hexdigest()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "NETWORK_SEND_REQUEST_UNAUTHORIZED",
        "bindings": {
            "outbox_record_sha256": record_sha,
            "event_id": event_id,
            "transport_plan_sha256": plan_sha,
            "target": target,
            "method": method,
            "path": path,
            "payload_sha256": payload_sha,
        },
        "limits": {
            "max_attempts_under_this_envelope": 1,
            "target_switch_allowed": False,
            "method_change_allowed": False,
            "path_change_allowed": False,
            "payload_change_allowed": False,
        },
        "authorization_requirement": {
            "required": True,
            "approval_must_bind_to": "envelope_sha256",
            "approval_verifier": "EXTERNAL_SOVEREIGN_LOCK_OR_EQUIVALENT",
            "approval_receipt_present": False,
        },
        "authority": {
            "authorized": False,
            "opens_socket": False,
            "sends_network_request": False,
            "acknowledges_outbox_event": False,
            "switches_target": False,
        },
        "laws": [
            "REQUEST_ENVELOPE_NE_NETWORK_AUTHORITY",
            "APPROVAL_MUST_BIND_TO_EXACT_ENVELOPE_HASH",
            "ONE_ENVELOPE_ONE_TARGET_ONE_ATTEMPT",
            "OUTBOX_ACK_REQUIRES_VERIFIED_TRANSPORT_ACK",
            "PAYLOAD_HASH_MISMATCH_REQUIRES_NEW_ENVELOPE",
            "FAILOVER_REQUIRES_NEW_TARGET_BOUND_ENVELOPE",
        ],
    }
    body["envelope_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
