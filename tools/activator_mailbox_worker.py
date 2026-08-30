#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

from tools.activator_dispatch_receiver import receive, verify_ack
from tools.activator_readonly_execution import orientation_snapshot, verify_grant
from tools.activator_mailbox_poller import (
    HOME_REPOSITORY,
    MESSAGE_SCHEMA,
    TARGET_REPOSITORY,
    canonical_hash,
    verify_message,
)

RESPONSE_SCHEMA = "janus.demiurge.mailbox_response.v1.0"
PROVENANCE_CLASS = "PUBLIC_REPOSITORY_ORIGIN_HASH_BOUND_NOT_IDENTITY_PROOF"


def _execution_receipt(grant: Dict[str, Any], *, repo_root: str | Path, target_head_sha: str) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    grant_hash = str(grant.get("grant_hash") or "")
    grant_id = str(grant.get("grant_id") or "")
    execution_id = "exec-mailbox-" + canonical_hash({
        "grant_id": grant_id,
        "grant_hash": grant_hash,
        "target_head_sha": target_head_sha,
        "transport": "CREDENTIALLESS_PULL_MAILBOX",
    })
    valid = verify_grant(grant)
    snapshot = orientation_snapshot(repo_root, target_head_sha) if valid else None
    receipt = {
        "schema": "janus.demiurge.activator_execution_receipt.v0.1",
        "execution_id": execution_id,
        "created_at": time.time(),
        "source_actor": HOME_REPOSITORY,
        "source_actor_trust_model": PROVENANCE_CLASS,
        "grant_id": grant_id,
        "grant_hash": grant_hash if len(grant_hash) == 64 else canonical_hash(grant),
        "target_repository": TARGET_REPOSITORY,
        "target_head_sha": str(target_head_sha),
        "operation": "READ_ONLY_ORIENTATION_SNAPSHOT",
        "risk_class": "R0_INTERNAL_READ_ONLY_ORIENTATION",
        "execution_scope": "TARGET_REPOSITORY_LOCAL_READ_ONLY_METADATA",
        "execution_authorized": bool(valid),
        "execution_performed": bool(valid),
        "snapshot_hash": snapshot.get("snapshot_hash") if snapshot else None,
        "target_process_network_access": False,
        "model_access": False,
        "repository_write_performed": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "external_effect_performed": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "EXECUTED_READ_ONLY_ORIENTATION" if valid else "EXECUTION_BLOCKED_INVALID_GRANT",
        "reasons": [
            "Credentialless mailbox request was hash-bound to the canonical HOME repository origin.",
            "Mailbox v1.0 provenance is not yet identity-equivalent to pinned GitHub Actions provenance.",
            "Only checked-out repository metadata was read; no model, target-process network, repository mutation, or external effect was permitted.",
        ] if valid else ["Execution grant failed the existing P12 grant verifier."],
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt, snapshot


def build_response(envelope: Dict[str, Any], *, repo_root: str | Path, target_head_sha: str) -> Dict[str, Any]:
    if not verify_message(envelope):
        raise ValueError("MAILBOX_MESSAGE_INVALID")
    kind = str(envelope["object_kind"])
    obj = dict(envelope["object"])

    response: Dict[str, Any] = {
        "schema": RESPONSE_SCHEMA,
        "created_at": time.time(),
        "source_repository": TARGET_REPOSITORY,
        "target_repository": HOME_REPOSITORY,
        "request_message_hash": envelope["message_hash"],
        "request_object_kind": kind,
        "request_object_id": envelope["object_id"],
        "request_object_hash": envelope["object_hash"],
        "provenance_class": PROVENANCE_CLASS,
        "identity_proof": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
    }

    if kind == "DISPATCH_PACKET":
        ack = receive(obj)
        if not verify_ack(ack):
            raise RuntimeError("MAILBOX_ACK_INTEGRITY_FAILURE")
        response.update({
            "response_kind": "DELIVERY_ACK",
            "payload": {"ack": ack},
            "terminal": "MAILBOX_DELIVERY_ACK_EMITTED" if ack.get("accepted") else "MAILBOX_DELIVERY_ACK_REJECTED",
        })
    elif kind == "EXECUTION_GRANT":
        receipt, snapshot = _execution_receipt(obj, repo_root=repo_root, target_head_sha=target_head_sha)
        response.update({
            "response_kind": "EXECUTION_RESULT",
            "payload": {"receipt": receipt, "snapshot": snapshot},
            "terminal": "MAILBOX_EXECUTION_RESULT_EMITTED" if receipt.get("execution_performed") else "MAILBOX_EXECUTION_BLOCKED",
        })
    else:
        raise ValueError("MAILBOX_OBJECT_KIND_UNSUPPORTED")

    response["response_hash"] = canonical_hash(response)
    return response


def response_filename(response: Dict[str, Any]) -> str:
    object_id = str(response["request_object_id"])
    suffix = "ack" if response["response_kind"] == "DELIVERY_ACK" else "execution"
    return f"{object_id}.{suffix}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one already-pulled credentialless JANUS mailbox request")
    parser.add_argument("--envelope", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-head-sha", required=True)
    parser.add_argument("--out-dir", default="runtime/activator-mailbox/responses")
    args = parser.parse_args()

    envelope = json.loads(Path(args.envelope).read_text(encoding="utf-8"))
    response = build_response(envelope, repo_root=args.repo_root, target_head_sha=args.target_head_sha)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / response_filename(response)
    out.write_text(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
