import hashlib
import json

from restored.sender_request_envelope import bind_send_request


def _canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _record():
    event_id = hashlib.sha256(b"event").hexdigest()
    body = {"event_id": event_id, "record_sha256": hashlib.sha256(b"record").hexdigest()}
    return body


def _plan(payload=None):
    if payload is None:
        payload = {"device_id": "node", "type": "heartbeat", "data": {"ok": True}}
    body = {
        "schema": "janus.transport_failover_plan.v1",
        "targets": ["http://a", "http://b"],
        "request": {"method": "POST", "path": "/api/device/data", "payload": payload},
    }
    body["plan_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def test_envelope_binds_exact_record_plan_target_and_payload_without_authority():
    r = bind_send_request(_record(), _plan(), "http://a")
    assert r["status"] == "NETWORK_SEND_REQUEST_UNAUTHORIZED"
    assert r["bindings"]["target"] == "http://a"
    assert r["limits"]["max_attempts_under_this_envelope"] == 1
    assert r["authority"]["authorized"] is False
    assert r["authority"]["sends_network_request"] is False
    assert r["authorization_requirement"]["approval_must_bind_to"] == "envelope_sha256"


def test_payload_change_changes_envelope_identity():
    a = bind_send_request(_record(), _plan({"x": 1}), "http://a")
    b = bind_send_request(_record(), _plan({"x": 2}), "http://a")
    assert a["bindings"]["payload_sha256"] != b["bindings"]["payload_sha256"]
    assert a["envelope_sha256"] != b["envelope_sha256"]


def test_failover_target_requires_distinct_envelope():
    a = bind_send_request(_record(), _plan(), "http://a")
    b = bind_send_request(_record(), _plan(), "http://b")
    assert a["envelope_sha256"] != b["envelope_sha256"]
    assert a["limits"]["target_switch_allowed"] is False
    assert "FAILOVER_REQUIRES_NEW_TARGET_BOUND_ENVELOPE" in a["laws"]
