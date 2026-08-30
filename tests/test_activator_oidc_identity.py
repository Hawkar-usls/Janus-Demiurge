from __future__ import annotations

import json

from tools.activator_dispatch_receiver import canonical_hash
from tools.activator_oidc_identity import (
    HOME_REPOSITORY,
    HOME_REPOSITORY_ID,
    HOME_WORKFLOW_REFS,
    IDENTITY_SCHEMA,
    ISSUER,
    OWNER,
    OWNER_ID,
    PROVENANCE_CLASS,
    REQUEST_SCHEMA,
    TARGET_REPOSITORY,
    TARGET_REPOSITORY_ID,
    TARGET_WORKFLOW_REFS,
    finalize_signed_response,
    request_audience,
    verify_home_identity,
    verify_request_envelope,
    verify_signed_response,
)


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


def claims(*, target=False, **overrides) -> dict:
    row = {
        "iss": ISSUER,
        "aud": "",
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
        "run_id": "9002" if target else "9001",
        "run_attempt": "1",
    }
    row.update(overrides)
    return row


def decoder_factory(*, home_overrides=None, target_overrides=None):
    home_overrides = dict(home_overrides or {})
    target_overrides = dict(target_overrides or {})

    def decode(token: str, audience: str) -> dict:
        if token.startswith("home."):
            return claims(aud=audience, **home_overrides)
        if token.startswith("target."):
            return claims(target=True, aud=audience, **target_overrides)
        raise ValueError("unknown fake token")

    return decode


def home_assertion(audience: str, *, bound_at=150.0) -> dict:
    return {
        "schema": IDENTITY_SCHEMA,
        "provider": "GITHUB_ACTIONS_OIDC",
        "role": "HOME_REQUEST_SOURCE",
        "audience": audience,
        "bound_at": bound_at,
        "jwt": "home.fake.jwt",
    }


def target_assertion(audience: str, *, bound_at=160.0) -> dict:
    return {
        "schema": IDENTITY_SCHEMA,
        "provider": "GITHUB_ACTIONS_OIDC",
        "role": "DEMIURGE_RESPONSE_SOURCE",
        "audience": audience,
        "bound_at": bound_at,
        "jwt": "target.fake.jwt",
    }


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
        "source_identity": home_assertion(audience),
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }
    row["message_hash"] = canonical_hash(row)
    return row


def response_core(request: dict) -> dict:
    ack = {
        "schema": "janus.demiurge.activator_dispatch_ack.v0.1",
        "created_at": 155.0,
        "packet_id": request["object_id"],
        "packet_hash": request["object_hash"],
        "accepted": True,
        "terminal": "ACK_ACCEPTED_NO_EXECUTION",
        "reasons": ["OIDC test ACK"],
        "execution_authorized": False,
        "execution_performed": False,
        "claim_authority_granted": False,
        "external_effect_authorized": False,
    }
    ack["ack_hash"] = canonical_hash(ack)
    return {
        "schema": "janus.demiurge.mailbox_response_core.v1.1",
        "created_at": 155.0,
        "source_repository": TARGET_REPOSITORY,
        "target_repository": HOME_REPOSITORY,
        "request_message_hash": request["message_hash"],
        "request_object_kind": request["object_kind"],
        "request_object_id": request["object_id"],
        "request_object_hash": request["object_hash"],
        "response_kind": "DELIVERY_ACK",
        "payload": {"ack": ack},
        "source_identity_verified": True,
        "source_identity_verification_hash": "f" * 64,
        "target_execution_authorized": False,
        "target_execution_performed": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "OIDC_MAILBOX_DELIVERY_ACK_CORE_READY",
    }


def test_valid_home_identity_is_object_bound_without_exact_subject_dependency():
    req = request_envelope()
    audience = req["source_identity"]["audience"]
    verified = verify_home_identity(req["source_identity"], audience, decoder=decoder_factory())
    assert verified["ok"] is True
    assert verified["identity_proof"] is True
    assert verified["subject_exact_match_required"] is False
    assert verified["claims"]["repository_id"] == HOME_REPOSITORY_ID


def test_wrong_assertion_audience_is_rejected_before_decode():
    req = request_envelope()
    expected = req["source_identity"]["audience"]
    req["source_identity"]["audience"] = expected + ":wrong"
    req["message_hash"] = canonical_hash({k: v for k, v in req.items() if k != "message_hash"})
    result = verify_request_envelope(req, decoder=decoder_factory())
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_AUDIENCE_REJECTED"


def test_wrong_repository_id_is_rejected():
    result = verify_request_envelope(
        request_envelope(),
        decoder=decoder_factory(home_overrides={"repository_id": "999"}),
    )
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_REPOSITORY_IDENTITY_REJECTED"


def test_wrong_workflow_ref_is_rejected():
    result = verify_request_envelope(
        request_envelope(),
        decoder=decoder_factory(home_overrides={"workflow_ref": "Hawkar-usls/Hawkar-usls/.github/workflows/other.yml@refs/heads/main"}),
    )
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_WORKFLOW_REF_REJECTED"


def test_wrong_ref_is_rejected():
    result = verify_request_envelope(
        request_envelope(),
        decoder=decoder_factory(home_overrides={"ref": "refs/heads/evil"}),
    )
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_REF_REJECTED"


def test_bound_at_outside_signed_window_is_rejected():
    req = request_envelope()
    req["source_identity"]["bound_at"] = 999.0
    req["message_hash"] = canonical_hash({k: v for k, v in req.items() if k != "message_hash"})
    result = verify_request_envelope(req, decoder=decoder_factory())
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_BOUND_AT_REJECTED"


def test_bidirectional_signed_response_verifies_both_workflow_identities():
    req = request_envelope()
    core = response_core(req)
    response = finalize_signed_response(
        core,
        request_message_hash=req["message_hash"],
        identity_issuer=lambda audience: target_assertion(audience),
    )
    assert response["provenance_class"] == PROVENANCE_CLASS
    result = verify_signed_response(response, request_envelope=req, decoder=decoder_factory())
    assert result["ok"] is True
    assert result["identity_proof"] is True
    assert result["target_identity_verification"]["claims"]["repository_id"] == TARGET_REPOSITORY_ID


def test_tampered_response_core_fails_before_target_identity_trust():
    req = request_envelope()
    response = finalize_signed_response(
        response_core(req),
        request_message_hash=req["message_hash"],
        identity_issuer=lambda audience: target_assertion(audience),
    )
    response["response_core"]["target_execution_performed"] = True
    result = verify_signed_response(response, request_envelope=req, decoder=decoder_factory())
    assert result["ok"] is False
    assert result["terminal"] == "OIDC_RESPONSE_HASH_REJECTED"


def test_source_verified_but_target_unsigned_never_becomes_bidirectional_identity():
    req = request_envelope()
    core = response_core(req)
    response = {
        "schema": "janus.demiurge.mailbox_response.v1.1",
        "response_core": core,
        "response_core_hash": canonical_hash(core),
        "target_identity": None,
        "provenance_class": PROVENANCE_CLASS,
        "identity_proof": True,
    }
    response["response_hash"] = canonical_hash(response)
    result = verify_signed_response(response, request_envelope=req, decoder=decoder_factory())
    assert result["ok"] is False
    assert result["identity_proof"] is False
