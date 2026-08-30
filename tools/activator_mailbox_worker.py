#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

from tools.activator_dispatch_receiver import receive, verify_ack
from tools.activator_mailbox_poller import (
    HOME_REPOSITORY,
    TARGET_REPOSITORY,
    canonical_hash,
    verify_message,
)

RESPONSE_SCHEMA = "janus.demiurge.mailbox_response.v1.0"
PROVENANCE_CLASS = "PUBLIC_REPOSITORY_ORIGIN_HASH_BOUND_NOT_IDENTITY_PROOF"


def build_response(envelope: Dict[str, Any], *, repo_root: str | Path, target_head_sha: str) -> Dict[str, Any]:
    # Defense in depth: v1.0 ingress already rejects execution grants. The
    # worker independently refuses every non-dispatch object so a hand-crafted
    # local file cannot bypass the identity gate.
    if str(envelope.get("object_kind") or "") == "EXECUTION_GRANT":
        raise PermissionError("MAILBOX_EXECUTION_IDENTITY_GATE_REQUIRED")
    if not verify_message(envelope):
        raise ValueError("MAILBOX_MESSAGE_INVALID")
    if envelope.get("object_kind") != "DISPATCH_PACKET":
        raise ValueError("MAILBOX_OBJECT_KIND_UNSUPPORTED")

    obj = dict(envelope["object"])
    ack = receive(obj)
    if not verify_ack(ack):
        raise RuntimeError("MAILBOX_ACK_INTEGRITY_FAILURE")

    response: Dict[str, Any] = {
        "schema": RESPONSE_SCHEMA,
        "created_at": time.time(),
        "source_repository": TARGET_REPOSITORY,
        "target_repository": HOME_REPOSITORY,
        "request_message_hash": envelope["message_hash"],
        "request_object_kind": "DISPATCH_PACKET",
        "request_object_id": envelope["object_id"],
        "request_object_hash": envelope["object_hash"],
        "provenance_class": PROVENANCE_CLASS,
        "identity_proof": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "response_kind": "DELIVERY_ACK",
        "payload": {"ack": ack},
        "terminal": "MAILBOX_DELIVERY_ACK_EMITTED" if ack.get("accepted") else "MAILBOX_DELIVERY_ACK_REJECTED",
    }
    response["response_hash"] = canonical_hash(response)
    return response


def response_filename(response: Dict[str, Any]) -> str:
    if response.get("response_kind") != "DELIVERY_ACK":
        raise ValueError("MAILBOX_V1_RESPONSE_KIND_NOT_ALLOWED")
    return f"{response['request_object_id']}.ack.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute one already-pulled credentialless JANUS mailbox dispatch request")
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
