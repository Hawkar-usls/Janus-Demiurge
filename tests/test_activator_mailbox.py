from __future__ import annotations

import json
import urllib.error

from tools.activator_mailbox_poller import (
    HOME_REPOSITORY,
    TARGET_REPOSITORY,
    canonical_hash,
    poll,
    verify_message,
)
from tools.activator_mailbox_worker import build_response


def packet() -> dict:
    body = {
        "schema": "janus.activator.dispatch_packet.v0.3",
        "created_at": 1.0,
        "activation_receipt_hash": "a" * 64,
        "target_organ": TARGET_REPOSITORY,
        "operation": "WAKE_ORGAN_READ_ONLY",
        "risk_class": "R0_INTERNAL_READ_ONLY_ORGAN_WAKE",
        "effect_scope": "GITHUB_INTERNAL_READ_ONLY_ANALYSIS",
        "dispatch_authorized": True,
        "external_effect_authorized": False,
        "claim_authority_granted": False,
        "command_authority_granted": False,
    }
    body["packet_id"] = "dsp-" + canonical_hash({
        "activation_receipt_hash": body["activation_receipt_hash"],
        "target_organ": body["target_organ"],
        "operation": body["operation"],
    })
    body["packet_hash"] = canonical_hash(body)
    return body


def envelope() -> dict:
    obj = packet()
    row = {
        "schema": "janus.activator.mailbox_message.v1.0",
        "created_at": 2.0,
        "source_repository": HOME_REPOSITORY,
        "target_repository": TARGET_REPOSITORY,
        "object_kind": "DISPATCH_PACKET",
        "object_id": obj["packet_id"],
        "object_hash": obj["packet_hash"],
        "object": obj,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    row["message_hash"] = canonical_hash(row)
    return row


def test_valid_hash_bound_packet_envelope_emits_delivery_ack(tmp_path):
    env = envelope()
    assert verify_message(env) is True
    response = build_response(env, repo_root=tmp_path, target_head_sha="9" * 40)
    assert response["response_kind"] == "DELIVERY_ACK"
    assert response["payload"]["ack"]["accepted"] is True
    assert response["payload"]["ack"]["execution_authorized"] is False
    assert response["payload"]["ack"]["execution_performed"] is False
    assert response["identity_proof"] is False
    assert response["external_effect_authorized"] is False


def test_authority_escalation_invalidates_mailbox_message():
    env = envelope()
    env["external_effect_authorized"] = True
    env["message_hash"] = canonical_hash({k: v for k, v in env.items() if k != "message_hash"})
    assert verify_message(env) is False


def test_object_tamper_invalidates_envelope_even_with_old_hash():
    env = envelope()
    env["object"]["operation"] = "DO_SOMETHING_ELSE"
    assert verify_message(env) is False


def test_missing_home_mailbox_is_noop_not_negative_evidence(tmp_path):
    def missing(_request, timeout=20.0):
        raise urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)

    manifest = poll(tmp_path, opener=missing)
    assert manifest["accepted"] == []
    assert manifest["rejected_invalid"] == 0
    assert manifest["silence_interpretation"] == "NOOP_NOT_NEGATIVE_EVIDENCE"
    assert manifest["cross_repository_write_performed"] is False
