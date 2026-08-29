#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

TARGET_ORGAN = "Hawkar-usls/Janus-Demiurge"
PACKET_SCHEMA = "janus.activator.dispatch_packet.v0.3"
OPERATION = "WAKE_ORGAN_READ_ONLY"
RISK_CLASS = "R0_INTERNAL_READ_ONLY_ORGAN_WAKE"
EFFECT_SCOPE = "GITHUB_INTERNAL_READ_ONLY_ANALYSIS"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_packet_hash_and_id(packet: Dict[str, Any]) -> bool:
    if not isinstance(packet, dict):
        return False
    claimed_hash = str(packet.get("packet_hash") or "")
    if len(claimed_hash) != 64:
        return False
    body = dict(packet)
    body.pop("packet_hash", None)
    if canonical_hash(body) != claimed_hash:
        return False
    expected_id = "dsp-" + canonical_hash({
        "activation_receipt_hash": packet.get("activation_receipt_hash"),
        "target_organ": packet.get("target_organ"),
        "operation": packet.get("operation"),
    })
    return packet.get("packet_id") == expected_id


def receive(packet: Dict[str, Any]) -> Dict[str, Any]:
    packet_id = str(packet.get("packet_id") or "UNKNOWN") if isinstance(packet, dict) else "UNKNOWN"
    packet_hash = str(packet.get("packet_hash") or "") if isinstance(packet, dict) else ""
    reasons: list[str] = []
    terminal = "ACK_ACCEPTED_NO_EXECUTION"
    accepted = True

    if not verify_packet_hash_and_id(packet):
        accepted = False
        terminal = "ACK_REJECTED_INVALID_PACKET"
        reasons.append("Packet hash or deterministic packet identity failed verification.")
    elif packet.get("schema") != PACKET_SCHEMA:
        accepted = False
        terminal = "ACK_REJECTED_INVALID_PACKET"
        reasons.append("Packet schema is not the admitted Activator dispatch schema.")
    elif packet.get("target_organ") != TARGET_ORGAN:
        accepted = False
        terminal = "ACK_REJECTED_WRONG_TARGET"
        reasons.append("Packet target is not Janus-Demiurge.")
    elif packet.get("operation") != OPERATION or packet.get("risk_class") != RISK_CLASS or packet.get("effect_scope") != EFFECT_SCOPE:
        accepted = False
        terminal = "ACK_REJECTED_AUTHORITY_ESCALATION"
        reasons.append("Packet requested an operation/risk/effect scope outside the read-only receiver contract.")
    elif (
        packet.get("dispatch_authorized") is not True
        or packet.get("external_effect_authorized") is not False
        or packet.get("claim_authority_granted") is not False
        or packet.get("command_authority_granted") is not False
    ):
        accepted = False
        terminal = "ACK_REJECTED_AUTHORITY_ESCALATION"
        reasons.append("Packet authority flags violate the fail-closed receiver contract.")
    else:
        reasons.extend([
            "Packet integrity and deterministic identity verified.",
            "Target and low-risk read-only scope matched receiver contract.",
            "Receiver acknowledges delivery only; no target execution was authorized or performed.",
        ])

    ack = {
        "schema": "janus.demiurge.activator_dispatch_ack.v0.1",
        "created_at": time.time(),
        "packet_id": packet_id,
        "packet_hash": packet_hash if len(packet_hash) == 64 else canonical_hash(packet if isinstance(packet, dict) else {}),
        "accepted": accepted,
        "terminal": terminal,
        "reasons": reasons,
        "execution_authorized": False,
        "execution_performed": False,
        "claim_authority_granted": False,
        "external_effect_authorized": False,
    }
    ack["ack_hash"] = canonical_hash(ack)
    return ack


def verify_ack(ack: Dict[str, Any]) -> bool:
    if not isinstance(ack, dict):
        return False
    claimed = str(ack.get("ack_hash") or "")
    if len(claimed) != 64:
        return False
    body = dict(ack)
    body.pop("ack_hash", None)
    return canonical_hash(body) == claimed


def main() -> None:
    parser = argparse.ArgumentParser(description="JANUS Demiurge Activator dispatch receiver")
    parser.add_argument("--packet", required=True, help="Activator dispatch packet JSON")
    parser.add_argument("--output", help="Optional ACK output path")
    args = parser.parse_args()

    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    ack = receive(packet)
    if not verify_ack(ack):
        raise SystemExit("ACK_INTEGRITY_FAILURE")
    text = json.dumps(ack, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
