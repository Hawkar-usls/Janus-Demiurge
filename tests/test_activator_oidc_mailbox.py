from __future__ import annotations

import base64
import json
import urllib.error
from pathlib import Path

from tools.activator_dispatch_receiver import canonical_hash
from tools.activator_mailbox_poller import HOME_REPOSITORY, TARGET_REPOSITORY, poll
from tools.activator_mailbox_worker import build_response, response_filename
from tools.activator_oidc_identity import (
    HOME_REPOSITORY_ID,
    HOME_WORKFLOW_REFS,
    IDENTITY_SCHEMA,
    ISSUER,
    OWNER,
    OWNER_ID,
    REQUEST_SCHEMA,
    TARGET_REPOSITORY_ID,
    TARGET_WORKFLOW_REFS,
    request_audience,
    verify_signed_response,
)


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self._body = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body

    def read(self):
        return self._body


def packet() -> dict:
    row = {
        "schema": "janus.activator.dispatch_packet.v0.3",
        "created_at": 10.0,
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
    row["packet_id"] = "dsp-" + canonical_hash({
        "activation_receipt_hash": row["activation_receipt_hash"],
        "target_organ": row["target_organ"],
        "operation": row["operation"],
    })
    row["packet_hash"] = canonical_hash(row)
    return row


def request_envelope() -> dict:
    obj = packet()
    audience = request_audience("DISPATCH_PACKET", obj["packet_id"], obj["packet_hash"])
    row = {
        "schema": REQUEST_SCHEMA,
        "created_at": obj["created_at"],
        "source_repository": HOME_REPOSITORY,
        "target_repository": TARGET_REPOSITORY,
        "object_kind": "DISPATCH_PACKET",
        "object_id": obj["packet_id"],
        "object_hash": obj["packet_hash"],
        "object": obj,
        "source_identity": {
            "schema": IDENTITY_SCHEMA,
            "provider": "GITHUB_ACTIONS_OIDC",
            "role": "HOME_REQUEST_SOURCE",
            "audience": audience,
            "bound_at": 150.0,
            "jwt": "home.fake.jwt",
        },
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    row["message_hash"] = canonical_hash(row)
    return row


def claims(*, target: bool, audience: str) -> dict:
    return {
        "iss": ISSUER,
        "aud": audience,
        "iat": 100,
        "nbf": 100,
        "exp": 700,
        "repository": TARGET_REPOSITORY if target else HOME_REPOSITORY,
        "repository_id": TARGET_REPOSITORY_ID if target else HOME_REPOSITORY_ID,
        "repository_owner": OWNER,
        "repository_owner_id": OWNER_ID,
        "ref": "refs/heads/main",
        "event_name": "schedule" if target else "push",
        "workflow_ref": next(iter(TARGET_WORKFLOW_REFS if target else HOME_WORKFLOW_REFS)),
        "workflow_sha": ("2" if target else "1") * 40,
        "run_id": "2" if target else "1",
        "run_attempt": "1",
    }


def decoder(token: str, audience: str) -> dict:
    if token.startswith("home."):
        return claims(target=False, audience=audience)
    if token.startswith("target."):
        return claims(target=True, audience=audience)
    raise ValueError("unknown fake token")


def target_issuer(audience: str) -> dict:
    return {
        "schema": IDENTITY_SCHEMA,
        "provider": "GITHUB_ACTIONS_OIDC",
        "role": "DEMIURGE_RESPONSE_SOURCE",
        "audience": audience,
        "bound_at": 160.0,
        "jwt": "target.fake.jwt",
    }


def test_poller_materializes_oidc_packet_only_after_home_identity_verifies(tmp_path):
    env = request_envelope()
    commit_sha = "3" * 40
    blob_url = f"https://api.github.com/repos/{HOME_REPOSITORY}/git/blobs/oidcpacket"
    encoded = base64.b64encode(json.dumps(env).encode("utf-8")).decode("ascii")

    def opener(request, timeout=20.0):
        url = request.full_url
        if "/branches/" in url:
            return Response({"commit": {"sha": commit_sha}})
        if f"/git/trees/{commit_sha}" in url:
            return Response({
                "truncated": False,
                "tree": [{
                    "path": f".janus/mailbox/outbox/{env['object_id']}.oidc-packet.json",
                    "type": "blob",
                    "url": blob_url,
                }],
            })
        if url == blob_url:
            return Response({"encoding": "base64", "content": encoded})
        if url.endswith(f"/{env['object_id']}.oidc-ack.json"):
            raise urllib.error.HTTPError(url, 404, "missing", {}, None)
        raise AssertionError(url)

    manifest = poll(tmp_path, opener=opener, oidc_decoder=decoder)
    assert manifest["rejected_oidc_identity"] == 0
    assert len(manifest["accepted"]) == 1
    accepted = manifest["accepted"][0]
    assert accepted["protocol"] == "OIDC_V1_1"
    assert accepted["identity_proof"] is True
    assert Path(accepted["path"]).is_file()
    assert Path(accepted["identity_verification_path"]).is_file()


def test_worker_reverifies_home_and_emits_target_signed_oidc_ack(tmp_path):
    env = request_envelope()
    response = build_response(
        env,
        repo_root=tmp_path,
        target_head_sha="9" * 40,
        oidc_decoder=decoder,
        identity_issuer=target_issuer,
    )
    assert response_filename(response) == f"{env['object_id']}.oidc-ack.json"
    assert response["identity_proof"] is True
    core = response["response_core"]
    assert core["source_identity_verified"] is True
    assert core["target_execution_authorized"] is False
    assert core["target_execution_performed"] is False
    assert core["world_truth_authority_granted"] is False
    assert core["payload"]["ack"]["execution_performed"] is False

    verified = verify_signed_response(response, request_envelope=env, decoder=decoder)
    assert verified["ok"] is True
    assert verified["identity_proof"] is True


def test_worker_never_accepts_execution_grant_in_oidc_packet_stage(tmp_path):
    env = request_envelope()
    env["object_kind"] = "EXECUTION_GRANT"
    try:
        build_response(
            env,
            repo_root=tmp_path,
            target_head_sha="9" * 40,
            oidc_decoder=decoder,
            identity_issuer=target_issuer,
        )
    except PermissionError as exc:
        assert "STAGE_GATE_REQUIRED" in str(exc)
    else:
        raise AssertionError("OIDC execution grant unexpectedly reached worker")
