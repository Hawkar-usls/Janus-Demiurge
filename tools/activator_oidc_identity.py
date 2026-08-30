#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, Mapping

from tools.activator_dispatch_receiver import canonical_hash, verify_packet_hash_and_id

ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = "https://token.actions.githubusercontent.com/.well-known/jwks"
IDENTITY_SCHEMA = "janus.activator.github_actions_oidc_identity.v1.1"
REQUEST_SCHEMA = "janus.activator.mailbox_message.v1.1"
RESPONSE_SCHEMA = "janus.demiurge.mailbox_response.v1.1"
PROVENANCE_CLASS = "GITHUB_ACTIONS_OIDC_BIDIRECTIONAL_OBJECT_BOUND_IDENTITY"

HOME_REPOSITORY = "Hawkar-usls/Hawkar-usls"
HOME_REPOSITORY_ID = "1328314567"
TARGET_REPOSITORY = "Hawkar-usls/Janus-Demiurge"
TARGET_REPOSITORY_ID = "1188744620"
OWNER = "Hawkar-usls"
OWNER_ID = "242020399"
MAIN_REF = "refs/heads/main"
HOME_WORKFLOW_REFS = {
    "Hawkar-usls/Hawkar-usls/.github/workflows/janus-oidc-mailbox-roundtrip.yml@refs/heads/main",
}
TARGET_WORKFLOW_REFS = {
    "Hawkar-usls/Janus-Demiurge/.github/workflows/janus-activator-credentialless-mailbox.yml@refs/heads/main",
}
HOME_EVENTS = {"push", "workflow_dispatch"}
TARGET_EVENTS = {"push", "schedule", "workflow_dispatch"}
PACKET_ID_RE = re.compile(r"^dsp-[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")

Decoder = Callable[[str, str], Dict[str, Any]]


def request_audience(object_kind: str, object_id: str, object_hash: str) -> str:
    if object_kind != "DISPATCH_PACKET":
        raise ValueError("OIDC_V11_PACKET_ACK_STAGE_ONLY")
    if PACKET_ID_RE.fullmatch(str(object_id)) is None or HASH_RE.fullmatch(str(object_hash)) is None:
        raise ValueError("OIDC_REQUEST_OBJECT_ID_OR_HASH_INVALID")
    return f"urn:janus:mailbox-request:v1.1:{object_kind}:{object_id}:{object_hash}"


def response_audience(request_message_hash: str, response_core_hash: str) -> str:
    if HASH_RE.fullmatch(str(request_message_hash)) is None or HASH_RE.fullmatch(str(response_core_hash)) is None:
        raise ValueError("OIDC_RESPONSE_HASH_BINDING_INVALID")
    return f"urn:janus:mailbox-response:v1.1:{request_message_hash}:{response_core_hash}"


def _oidc_request(url: str, request_token: str, audience: str) -> urllib.request.Request:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("audience", audience))
    bound_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment))
    return urllib.request.Request(
        bound_url,
        headers={
            "Authorization": f"Bearer {request_token}",
            "Accept": "application/json",
            "User-Agent": "JANUS-Activator-OIDC/1.1",
        },
    )


def request_github_oidc_token(
    audience: str,
    *,
    request_url: str | None = None,
    request_token: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    url = str(request_url if request_url is not None else os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")).strip()
    token = str(request_token if request_token is not None else os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")).strip()
    if not url or not token:
        raise RuntimeError("GITHUB_ACTIONS_OIDC_REQUEST_ENV_MISSING")
    response = opener(_oidc_request(url, token, audience), timeout=20.0)
    value = json.loads(response.read().decode("utf-8"))
    jwt_value = value.get("value") if isinstance(value, dict) else None
    if not isinstance(jwt_value, str) or jwt_value.count(".") != 2:
        raise RuntimeError("GITHUB_ACTIONS_OIDC_RESPONSE_INVALID")
    return jwt_value


def issue_identity_assertion(
    audience: str,
    *,
    role: str,
    request_url: str | None = None,
    request_token: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
    now_fn: Callable[[], float] = time.time,
) -> Dict[str, Any]:
    jwt_value = request_github_oidc_token(
        audience,
        request_url=request_url,
        request_token=request_token,
        opener=opener,
    )
    return {
        "schema": IDENTITY_SCHEMA,
        "provider": "GITHUB_ACTIONS_OIDC",
        "role": str(role),
        "audience": audience,
        "bound_at": float(now_fn()),
        "jwt": jwt_value,
    }


_jwk_client = None


def _decode_signed_github_jwt(token: str, audience: str) -> Dict[str, Any]:
    # Lazy import keeps unit tests independent of the crypto dependency. The
    # actual GitHub Actions mailbox job installs PyJWT[crypto] before v1.1 use.
    import jwt  # type: ignore

    global _jwk_client
    if _jwk_client is None:
        _jwk_client = jwt.PyJWKClient(JWKS_URL)
    signing_key = _jwk_client.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=audience,
        issuer=ISSUER,
        options={
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
        },
    )
    if not isinstance(claims, dict):
        raise ValueError("OIDC_CLAIMS_NOT_OBJECT")
    return claims


def _audience_contains(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return expected in value
    return False


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _verification_failure(terminal: str, reason: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "identity_proof": False,
        "terminal": terminal,
        "reason": reason,
    }


def verify_identity_assertion(
    assertion: Dict[str, Any],
    *,
    expected_audience: str,
    expected_role: str,
    expected_repository: str,
    expected_repository_id: str,
    allowed_workflow_refs: Iterable[str],
    allowed_event_names: Iterable[str],
    decoder: Decoder | None = None,
) -> Dict[str, Any]:
    if not isinstance(assertion, dict):
        return _verification_failure("OIDC_ASSERTION_MISSING", "Identity assertion is not an object.")
    if assertion.get("schema") != IDENTITY_SCHEMA or assertion.get("provider") != "GITHUB_ACTIONS_OIDC":
        return _verification_failure("OIDC_ASSERTION_SCHEMA_REJECTED", "Identity assertion schema/provider mismatch.")
    if assertion.get("role") != expected_role:
        return _verification_failure("OIDC_ROLE_REJECTED", "Identity role mismatch.")
    if assertion.get("audience") != expected_audience:
        return _verification_failure("OIDC_AUDIENCE_REJECTED", "Assertion audience does not match exact object binding.")
    bound_at = _as_float(assertion.get("bound_at"))
    token = assertion.get("jwt")
    if bound_at is None or not isinstance(token, str) or token.count(".") != 2:
        return _verification_failure("OIDC_ASSERTION_MALFORMED", "bound_at or JWT is malformed.")

    try:
        claims = (decoder or _decode_signed_github_jwt)(token, expected_audience)
    except Exception as exc:
        return _verification_failure("OIDC_SIGNATURE_ISSUER_AUDIENCE_REJECTED", f"JWT verification failed with {type(exc).__name__}.")
    if not isinstance(claims, dict):
        return _verification_failure("OIDC_CLAIMS_REJECTED", "Decoded claims are not an object.")

    required = (
        "iss", "aud", "iat", "nbf", "exp", "repository", "repository_id",
        "repository_owner", "repository_owner_id", "ref", "event_name",
        "workflow_ref", "workflow_sha", "run_id", "run_attempt",
    )
    missing = [key for key in required if key not in claims]
    if missing:
        return _verification_failure("OIDC_REQUIRED_CLAIMS_MISSING", "Missing required claims: " + ",".join(missing))
    if claims.get("iss") != ISSUER or not _audience_contains(claims.get("aud"), expected_audience):
        return _verification_failure("OIDC_ISSUER_OR_AUDIENCE_REJECTED", "Issuer or token audience mismatch.")
    if str(claims.get("repository")) != expected_repository or str(claims.get("repository_id")) != str(expected_repository_id):
        return _verification_failure("OIDC_REPOSITORY_IDENTITY_REJECTED", "Repository name or immutable repository ID mismatch.")
    if str(claims.get("repository_owner")) != OWNER or str(claims.get("repository_owner_id")) != OWNER_ID:
        return _verification_failure("OIDC_OWNER_IDENTITY_REJECTED", "Repository owner name or immutable owner ID mismatch.")
    if str(claims.get("ref")) != MAIN_REF:
        return _verification_failure("OIDC_REF_REJECTED", "OIDC identity did not originate from refs/heads/main.")
    if str(claims.get("workflow_ref")) not in set(allowed_workflow_refs):
        return _verification_failure("OIDC_WORKFLOW_REF_REJECTED", "Workflow reference is not admitted by the identity constitution.")
    if str(claims.get("event_name")) not in set(allowed_event_names):
        return _verification_failure("OIDC_EVENT_REJECTED", "Workflow event is not admitted by the identity constitution.")
    if SHA_RE.fullmatch(str(claims.get("workflow_sha"))) is None:
        return _verification_failure("OIDC_WORKFLOW_SHA_REJECTED", "workflow_sha is not a 40-hex commit identity.")

    iat = _as_float(claims.get("iat"))
    nbf = _as_float(claims.get("nbf"))
    exp = _as_float(claims.get("exp"))
    if iat is None or nbf is None or exp is None or not (iat <= exp and nbf <= exp):
        return _verification_failure("OIDC_TIME_CLAIMS_REJECTED", "Token time claims are malformed.")
    if exp - iat > 900 or exp - iat <= 0:
        return _verification_failure("OIDC_TOKEN_LIFETIME_REJECTED", "Token lifetime exceeds the frozen historical-attestation bound.")
    if not (max(iat, nbf) <= bound_at <= exp):
        return _verification_failure("OIDC_BOUND_AT_REJECTED", "Identity bound_at is outside the signed token validity window.")

    public_claims = {
        key: claims.get(key)
        for key in (
            "repository", "repository_id", "repository_owner", "repository_owner_id",
            "ref", "event_name", "workflow_ref", "workflow_sha", "run_id", "run_attempt",
            "iat", "nbf", "exp",
        )
    }
    verification = {
        "ok": True,
        "identity_proof": True,
        "terminal": "OIDC_IDENTITY_VERIFIED_OBJECT_BOUND_HISTORICAL_ATTESTATION",
        "provider": "GITHUB_ACTIONS_OIDC",
        "role": expected_role,
        "audience": expected_audience,
        "bound_at": bound_at,
        "claims": public_claims,
        "subject_exact_match_required": False,
        "jwt_is_bearer_authorization": False,
    }
    verification["verification_hash"] = canonical_hash(verification)
    return verification


def verify_home_identity(assertion: Dict[str, Any], audience: str, *, decoder: Decoder | None = None) -> Dict[str, Any]:
    return verify_identity_assertion(
        assertion,
        expected_audience=audience,
        expected_role="HOME_REQUEST_SOURCE",
        expected_repository=HOME_REPOSITORY,
        expected_repository_id=HOME_REPOSITORY_ID,
        allowed_workflow_refs=HOME_WORKFLOW_REFS,
        allowed_event_names=HOME_EVENTS,
        decoder=decoder,
    )


def verify_target_identity(assertion: Dict[str, Any], audience: str, *, decoder: Decoder | None = None) -> Dict[str, Any]:
    return verify_identity_assertion(
        assertion,
        expected_audience=audience,
        expected_role="DEMIURGE_RESPONSE_SOURCE",
        expected_repository=TARGET_REPOSITORY,
        expected_repository_id=TARGET_REPOSITORY_ID,
        allowed_workflow_refs=TARGET_WORKFLOW_REFS,
        allowed_event_names=TARGET_EVENTS,
        decoder=decoder,
    )


def _authority_ceiling_false(row: Mapping[str, Any]) -> bool:
    return all(
        row.get(field) is False
        for field in (
            "command_authority_granted", "claim_authority_granted",
            "scientific_evidence_authority_granted", "external_effect_authorized",
            "physical_runtime_effect_authorized",
        )
    )


def verify_request_envelope(envelope: Dict[str, Any], *, decoder: Decoder | None = None) -> Dict[str, Any]:
    if not isinstance(envelope, dict) or envelope.get("schema") != REQUEST_SCHEMA:
        return _verification_failure("OIDC_REQUEST_SCHEMA_REJECTED", "Request envelope schema mismatch.")
    claimed = str(envelope.get("message_hash") or "")
    if HASH_RE.fullmatch(claimed) is None:
        return _verification_failure("OIDC_REQUEST_HASH_MISSING", "Request message hash is missing.")
    body = dict(envelope)
    body.pop("message_hash", None)
    if canonical_hash(body) != claimed:
        return _verification_failure("OIDC_REQUEST_HASH_REJECTED", "Request message hash mismatch.")
    if envelope.get("source_repository") != HOME_REPOSITORY or envelope.get("target_repository") != TARGET_REPOSITORY:
        return _verification_failure("OIDC_REQUEST_REPOSITORY_REJECTED", "Request repository binding mismatch.")
    if envelope.get("object_kind") != "DISPATCH_PACKET" or not _authority_ceiling_false(envelope):
        return _verification_failure("OIDC_REQUEST_AUTHORITY_OR_KIND_REJECTED", "v1.1 stage admits only authority-bounded dispatch packets.")

    obj = envelope.get("object")
    object_id = str(envelope.get("object_id") or "")
    object_hash = str(envelope.get("object_hash") or "")
    if not isinstance(obj, dict) or not verify_packet_hash_and_id(obj):
        return _verification_failure("OIDC_REQUEST_PACKET_REJECTED", "Dispatch packet deterministic integrity failed.")
    if object_id != obj.get("packet_id") or object_hash != obj.get("packet_hash"):
        return _verification_failure("OIDC_REQUEST_OBJECT_BINDING_REJECTED", "Envelope object identity does not match packet.")
    try:
        audience = request_audience("DISPATCH_PACKET", object_id, object_hash)
    except ValueError as exc:
        return _verification_failure("OIDC_REQUEST_AUDIENCE_BINDING_REJECTED", str(exc))
    identity = verify_home_identity(envelope.get("source_identity"), audience, decoder=decoder)
    if identity.get("ok") is not True:
        return identity
    result = {
        "ok": True,
        "identity_proof": True,
        "terminal": "OIDC_REQUEST_VERIFIED_HOME_OBJECT_BOUND_IDENTITY",
        "message_hash": claimed,
        "object_id": object_id,
        "object_hash": object_hash,
        "identity_verification": identity,
    }
    result["verification_hash"] = canonical_hash(result)
    return result


def finalize_signed_response(
    response_core: Dict[str, Any],
    *,
    request_message_hash: str,
    identity_issuer: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(response_core, dict):
        raise ValueError("OIDC_RESPONSE_CORE_REQUIRED")
    core_hash = canonical_hash(response_core)
    audience = response_audience(request_message_hash, core_hash)
    identity = identity_issuer(audience)
    response = {
        "schema": RESPONSE_SCHEMA,
        "response_core": response_core,
        "response_core_hash": core_hash,
        "target_identity": identity,
        "provenance_class": PROVENANCE_CLASS,
        "identity_proof": True,
    }
    response["response_hash"] = canonical_hash(response)
    return response


def verify_signed_response(
    response: Dict[str, Any],
    *,
    request_envelope: Dict[str, Any],
    decoder: Decoder | None = None,
) -> Dict[str, Any]:
    request_verification = verify_request_envelope(request_envelope, decoder=decoder)
    if request_verification.get("ok") is not True:
        return _verification_failure("OIDC_RESPONSE_REQUEST_NOT_VERIFIED", "Cannot verify response against an unauthenticated request.")
    if not isinstance(response, dict) or response.get("schema") != RESPONSE_SCHEMA:
        return _verification_failure("OIDC_RESPONSE_SCHEMA_REJECTED", "Response schema mismatch.")
    claimed = str(response.get("response_hash") or "")
    body = dict(response)
    body.pop("response_hash", None)
    if HASH_RE.fullmatch(claimed) is None or canonical_hash(body) != claimed:
        return _verification_failure("OIDC_RESPONSE_HASH_REJECTED", "Response outer hash mismatch.")
    core = response.get("response_core")
    core_hash = str(response.get("response_core_hash") or "")
    if not isinstance(core, dict) or HASH_RE.fullmatch(core_hash) is None or canonical_hash(core) != core_hash:
        return _verification_failure("OIDC_RESPONSE_CORE_HASH_REJECTED", "Response core hash mismatch.")
    if response.get("provenance_class") != PROVENANCE_CLASS or response.get("identity_proof") is not True:
        return _verification_failure("OIDC_RESPONSE_PROVENANCE_REJECTED", "Response did not declare the admitted bidirectional OIDC provenance class.")
    if core.get("request_message_hash") != request_envelope.get("message_hash"):
        return _verification_failure("OIDC_RESPONSE_REQUEST_BINDING_REJECTED", "Response core does not bind the exact request message hash.")
    if core.get("request_object_id") != request_envelope.get("object_id") or core.get("request_object_hash") != request_envelope.get("object_hash"):
        return _verification_failure("OIDC_RESPONSE_OBJECT_BINDING_REJECTED", "Response core object binding mismatch.")
    if not _authority_ceiling_false(core) or core.get("target_execution_authorized") is not False or core.get("target_execution_performed") is not False:
        return _verification_failure("OIDC_RESPONSE_AUTHORITY_REJECTED", "Response core exceeds packet/ACK-stage authority ceiling.")
    audience = response_audience(str(request_envelope["message_hash"]), core_hash)
    target_identity = verify_target_identity(response.get("target_identity"), audience, decoder=decoder)
    if target_identity.get("ok") is not True:
        return target_identity
    result = {
        "ok": True,
        "identity_proof": True,
        "terminal": "OIDC_RESPONSE_VERIFIED_BIDIRECTIONAL_OBJECT_BOUND_IDENTITY",
        "response_hash": claimed,
        "response_core_hash": core_hash,
        "target_identity_verification": target_identity,
    }
    result["verification_hash"] = canonical_hash(result)
    return result


__all__ = [
    "IDENTITY_SCHEMA", "REQUEST_SCHEMA", "RESPONSE_SCHEMA", "PROVENANCE_CLASS",
    "request_audience", "response_audience", "request_github_oidc_token",
    "issue_identity_assertion", "verify_identity_assertion", "verify_home_identity",
    "verify_target_identity", "verify_request_envelope", "finalize_signed_response",
    "verify_signed_response",
]
