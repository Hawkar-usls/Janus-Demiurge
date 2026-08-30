from __future__ import annotations

import base64
import json
import urllib.error

import pytest

from tools.activator_mailbox_poller import (
    HOME_REPOSITORY,
    TARGET_REPOSITORY,
    canonical_hash,
    iter_home_envelopes,
    poll,
    verify_message,
)
from tools.activator_mailbox_worker import build_response


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self._body = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body

    def read(self):
        return self._body


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


def unauthenticated_grant_envelope() -> dict:
    grant_id = "xg-" + "b" * 64
    grant = {
        "schema": "janus.activator.execution_grant.v0.7",
        "grant_id": grant_id,
        "grant_hash": "c" * 64,
        "target_organ": TARGET_REPOSITORY,
        "operation": "READ_ONLY_ORIENTATION_SNAPSHOT",
        "target_execution_authorized": True,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    row = {
        "schema": "janus.activator.mailbox_message.v1.0",
        "created_at": 2.5,
        "source_repository": HOME_REPOSITORY,
        "target_repository": TARGET_REPOSITORY,
        "object_kind": "EXECUTION_GRANT",
        "object_id": grant_id,
        "object_hash": grant["grant_hash"],
        "object": grant,
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


def test_credentialless_v1_grant_is_rejected_before_worker_or_claim(tmp_path):
    env = unauthenticated_grant_envelope()
    # Even a correctly hash-sealed public mailbox envelope cannot create P12
    # execution authority without authenticated source identity.
    assert verify_message(env) is False
    with pytest.raises(PermissionError, match="IDENTITY_GATE_REQUIRED"):
        build_response(env, repo_root=tmp_path, target_head_sha="9" * 40)


def test_authority_escalation_invalidates_mailbox_message():
    env = envelope()
    env["external_effect_authorized"] = True
    env["message_hash"] = canonical_hash({k: v for k, v in env.items() if k != "message_hash"})
    assert verify_message(env) is False


def test_object_tamper_invalidates_envelope_even_with_old_hash():
    env = envelope()
    env["object"]["operation"] = "DO_SOMETHING_ELSE"
    assert verify_message(env) is False


def test_path_like_object_id_is_rejected_even_when_envelope_rehashed():
    env = envelope()
    unsafe = "../../poison"
    env["object_id"] = unsafe
    env["object"]["packet_id"] = unsafe
    env["object"]["packet_hash"] = canonical_hash({k: v for k, v in env["object"].items() if k != "packet_hash"})
    env["object_hash"] = env["object"]["packet_hash"]
    env["message_hash"] = canonical_hash({k: v for k, v in env.items() if k != "message_hash"})
    assert verify_message(env) is False


def test_tree_discovery_reads_blob_without_contents_directory_listing():
    env = envelope()
    commit_sha = "1" * 40
    blob_url = f"https://api.github.com/repos/{HOME_REPOSITORY}/git/blobs/abc123"
    encoded = base64.b64encode(json.dumps(env).encode("utf-8")).decode("ascii")
    seen = []

    def opener(request, timeout=20.0):
        url = request.full_url
        seen.append(url)
        if "/branches/" in url:
            return Response({"commit": {"sha": commit_sha}})
        if f"/git/trees/{commit_sha}" in url:
            return Response({
                "truncated": False,
                "tree": [{
                    "path": ".janus/mailbox/outbox/example.json",
                    "type": "blob",
                    "url": blob_url,
                }],
            })
        if url == blob_url:
            return Response({"encoding": "base64", "content": encoded})
        raise AssertionError(url)

    rows = list(iter_home_envelopes(opener=opener))
    assert rows == [env]
    assert all("/contents/.janus/mailbox/outbox" not in url for url in seen)


def test_truncated_tree_is_unknown_resource_limit_not_empty_mailbox():
    commit_sha = "2" * 40

    def opener(request, timeout=20.0):
        url = request.full_url
        if "/branches/" in url:
            return Response({"commit": {"sha": commit_sha}})
        if f"/git/trees/{commit_sha}" in url:
            return Response({"truncated": True, "tree": []})
        raise AssertionError(url)

    with pytest.raises(RuntimeError, match="UNKNOWN_RESOURCE_LIMIT"):
        list(iter_home_envelopes(opener=opener))


def test_missing_home_mailbox_is_noop_not_negative_evidence(tmp_path):
    def missing(_request, timeout=20.0):
        raise urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)

    manifest = poll(tmp_path, opener=missing)
    assert manifest["accepted"] == []
    assert manifest["rejected_invalid"] == 0
    assert manifest["blocked_execution_identity_required"] == 0
    assert manifest["credentialless_execution_enabled"] is False
    assert manifest["execution_claim_allowed_before_identity_verification"] is False
    assert manifest["silence_interpretation"] == "NOOP_NOT_NEGATIVE_EVIDENCE"
    assert manifest["cross_repository_write_performed"] is False
