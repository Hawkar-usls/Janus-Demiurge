from __future__ import annotations

import base64
import json
import urllib.error

from tools.activator_execution_claim import acquire
from tools.activator_mailbox_poller import canonical_hash


class Response:
    def __init__(self, status=201, body=b"{}"):
        self.status = status
        self._body = body

    def read(self):
        return self._body


def grant() -> dict:
    row = {
        "schema": "janus.activator.execution_grant.v0.7",
        "created_at": 1.0,
        "parent_grant_hash": None,
        "authenticated_final_receipt_hash": "a" * 64,
        "finalization_id": "ackf-" + "b" * 64,
        "packet_id": "dsp-" + "c" * 64,
        "packet_hash": "d" * 64,
        "target_organ": "Hawkar-usls/Janus-Demiurge",
        "operation": "READ_ONLY_ORIENTATION_SNAPSHOT",
        "risk_class": "R0_INTERNAL_READ_ONLY_ORIENTATION",
        "execution_scope": "TARGET_REPOSITORY_LOCAL_READ_ONLY_METADATA",
        "target_execution_authorized": True,
        "repository_write_authorized": False,
        "network_access_authorized": False,
        "model_access_authorized": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "EXECUTION_GRANT_ISSUED_READ_ONLY_ORIENTATION",
        "reasons": ["test grant"],
    }
    row["grant_id"] = "xg-" + canonical_hash({
        "authenticated_final_receipt_hash": row["authenticated_final_receipt_hash"],
        "packet_id": row["packet_id"],
        "packet_hash": row["packet_hash"],
        "target_organ": row["target_organ"],
        "operation": row["operation"],
    })
    row["grant_hash"] = canonical_hash(row)
    return row


def test_first_lane_acquires_claim():
    g = grant()
    result = acquire(
        g,
        token="local-target-token",
        transport_lane="SECRET_PUSH",
        workflow_run_id="1",
        opener=lambda request, timeout=20.0: Response(201),
    )
    assert result["terminal"] == "CLAIM_ACQUIRED"
    assert result["execution_permitted"] is True
    assert result["grant_id"] == g["grant_id"]


def test_second_lane_is_suppressed_by_existing_same_hash_claim():
    g = grant()
    stored = {}

    def opener(request, timeout=20.0):
        if request.get_method() == "PUT":
            # GitHub Contents create-only semantics: a second create attempt does
            # not overwrite the object that already won the claim race.
            if stored.get("put_seen"):
                raise urllib.error.HTTPError(request.full_url, 422, "exists", {}, None)
            payload = json.loads(request.data.decode("utf-8"))
            stored["claim"] = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
            stored["put_seen"] = True
            return Response(201)
        return Response(200, json.dumps(stored["claim"]).encode("utf-8"))

    first = acquire(g, token="local-target-token", transport_lane="SECRET_PUSH", workflow_run_id="1", opener=opener)
    second = acquire(g, token="local-target-token", transport_lane="CREDENTIALLESS_PULL", workflow_run_id="2", opener=opener)
    assert first["execution_permitted"] is True
    assert second["terminal"] == "CLAIM_ALREADY_HELD"
    assert second["execution_permitted"] is False
    assert second["existing_transport_lane"] == "SECRET_PUSH"


def test_missing_local_target_token_never_executes():
    result = acquire(grant(), token="", transport_lane="CREDENTIALLESS_PULL", workflow_run_id="3")
    assert result["terminal"] == "CLAIM_BLOCKED_NO_LOCAL_REPOSITORY_TOKEN"
    assert result["execution_permitted"] is False
