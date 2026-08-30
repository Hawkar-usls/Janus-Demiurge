#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict

from tools.activator_dispatch_receiver import canonical_hash, receive, verify_ack
from tools.activator_mailbox_poller import HOME_REPOSITORY, MESSAGE_SCHEMA, TARGET_REPOSITORY, verify_message
from tools.activator_oidc_identity import (
    REQUEST_SCHEMA as OIDC_REQUEST_SCHEMA,
    finalize_signed_response,
    issue_identity_assertion,
    verify_request_envelope,
)

LEGACY_RESPONSE_SCHEMA = "janus.demiurge.mailbox_response.v1.0"
LEGACY_PROVENANCE_CLASS = "PUBLIC_REPOSITORY_ORIGIN_HASH_BOUND_NOT_IDENTITY_PROOF"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _legacy_response(envelope: Dict[str, Any]) -> Dict[str, Any]:
    if not verify_message(envelope):
        raise ValueError("MAILBOX_MESSAGE_INVALID")
    obj = dict(envelope["object"])
    ack = receive(obj)
    if not verify_ack(ack):
        raise RuntimeError("MAILBOX_ACK_INTEGRITY_FAILURE")
    response: Dict[str, Any] = {
        "schema": LEGACY_RESPONSE_SCHEMA,
        "created_at": time.time(),
        "source_repository": TARGET_REPOSITORY,
        "target_repository": HOME_REPOSITORY,
        "request_message_hash": envelope["message_hash"],
        "request_object_kind": "DISPATCH_PACKET",
        "request_object_id": envelope["object_id"],
        "request_object_hash": envelope["object_hash"],
        "provenance_class": LEGACY_PROVENANCE_CLASS,
        "identity_proof": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "response_kind": "DELIVERY_ACK",
        "payload": {"ack": ack},
        "terminal": "MAILBOX_DELIVERY_ACK_EMITTED" if ack.get("accepted") else "MAILBOX_DELIVERY_ACK_REJECTED",
    }
    response["response_hash"] = canonical_hash(response)
    return response


def _oidc_response(
    envelope: Dict[str, Any],
    *,
    target_head_sha: str,
    oidc_decoder=None,
    identity_issuer: Callable[[str], Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if SHA_RE.fullmatch(str(target_head_sha)) is None:
        raise ValueError("OIDC_TARGET_HEAD_SHA_INVALID")

    source_verification = verify_request_envelope(envelope, decoder=oidc_decoder)
    if source_verification.get("ok") is not True or source_verification.get("identity_proof") is not True:
        raise PermissionError("OIDC_HOME_SOURCE_IDENTITY_NOT_VERIFIED")

    obj = dict(envelope["object"])
    ack = receive(obj)
    if not verify_ack(ack):
        raise RuntimeError("OIDC_MAILBOX_ACK_INTEGRITY_FAILURE")

    core = {
        "schema": "janus.demiurge.mailbox_response_core.v1.1",
        "created_at": time.time(),
        "source_repository": TARGET_REPOSITORY,
        "target_repository": HOME_REPOSITORY,
        "target_head_sha": target_head_sha,
        "request_message_hash": envelope["message_hash"],
        "request_object_kind": "DISPATCH_PACKET",
        "request_object_id": envelope["object_id"],
        "request_object_hash": envelope["object_hash"],
        "response_kind": "DELIVERY_ACK",
        "payload": {"ack": ack},
        "source_identity_verified": True,
        "source_identity_verification_hash": source_verification["verification_hash"],
        "source_identity_verification": source_verification,
        "target_execution_authorized": False,
        "target_execution_performed": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "world_truth_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "OIDC_MAILBOX_DELIVERY_ACK_CORE_READY" if ack.get("accepted") else "OIDC_MAILBOX_DELIVERY_REJECT_CORE_READY",
    }

    issuer = identity_issuer or (
        lambda audience: issue_identity_assertion(
            audience,
            role="DEMIURGE_RESPONSE_SOURCE",
        )
    )
    return finalize_signed_response(
        core,
        request_message_hash=str(envelope["message_hash"]),
        identity_issuer=issuer,
    )


def build_response(
    envelope: Dict[str, Any],
    *,
    repo_root: str | Path,
    target_head_sha: str,
    oidc_decoder=None,
    identity_issuer: Callable[[str], Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if str(envelope.get("object_kind") or "") == "EXECUTION_GRANT":
        # Preserve the original identity-gate diagnostic while recording that
        # v1.1 is still packet/ACK stage even after identity infrastructure exists.
        raise PermissionError("MAILBOX_EXECUTION_IDENTITY_GATE_REQUIRED_V11_PACKET_STAGE")
    if envelope.get("object_kind") != "DISPATCH_PACKET":
        raise ValueError("MAILBOX_OBJECT_KIND_UNSUPPORTED")

    if envelope.get("schema") == MESSAGE_SCHEMA:
        return _legacy_response(envelope)
    if envelope.get("schema") == OIDC_REQUEST_SCHEMA:
        return _oidc_response(
            envelope,
            target_head_sha=target_head_sha,
            oidc_decoder=oidc_decoder,
            identity_issuer=identity_issuer,
        )
    raise ValueError("MAILBOX_MESSAGE_SCHEMA_UNSUPPORTED")


def response_filename(response: Dict[str, Any]) -> str:
    if response.get("schema") == LEGACY_RESPONSE_SCHEMA:
        if response.get("response_kind") != "DELIVERY_ACK":
            raise ValueError("MAILBOX_V1_RESPONSE_KIND_NOT_ALLOWED")
        return f"{response['request_object_id']}.ack.json"
    if response.get("schema") == "janus.demiurge.mailbox_response.v1.1":
        core = response.get("response_core")
        if not isinstance(core, dict) or core.get("response_kind") != "DELIVERY_ACK":
            raise ValueError("MAILBOX_V11_RESPONSE_KIND_NOT_ALLOWED")
        return f"{core['request_object_id']}.oidc-ack.json"
    raise ValueError("MAILBOX_RESPONSE_SCHEMA_UNSUPPORTED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one pulled JANUS mailbox dispatch request with optional OIDC identity")
    parser.add_argument("--envelope", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-head-sha", required=True)
    parser.add_argument("--out-dir", default="runtime/activator-mailbox/responses")
    args = parser.parse_args()

    envelope = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
    response = build_response(
        envelope,
        repo_root=args.repo_root,
        target_head_sha=args.target_head_sha,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / response_filename(response)
    out.write_text(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
