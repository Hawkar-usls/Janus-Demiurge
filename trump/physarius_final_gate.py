#!/usr/bin/env python3
"""TRUMP final admission gate for the JANUS Physarius/HRaiN pipeline.

Candidate-only. It may block or admit to a next review stage, but it never
promotes a scientific claim, proof theorem, external effect, or physical action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(obj: object) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_true(v: object) -> bool:
    return v is True


def gate(manifest: dict, contract: dict, packet: dict) -> dict:
    stage = packet.get("stage")
    stages = contract.get("stages", {})
    receipt = {
        "schema": "janus.trump.physarius_final_admission.receipt.v1",
        "component": "TRUMP",
        "stage": stage,
        "packet_sha256": sha256_obj(packet),
        "contract_sha256": sha256_obj(contract),
        "manifest_sha256": sha256_obj(manifest),
        "candidate_only": True,
        "scientific_claim_promoted": False,
        "proof_promoted": False,
        "external_effect_authorized": False,
        "physical_effect_authorized": False,
        "missing": [],
        "unknown": [],
        "violations": [],
    }

    activation = manifest.get("activation", {})
    if activation.get("scientific_claim_promotion_authority") is not False:
        receipt["violations"].append("TRUMP_AUTHORITY_CEILING_NOT_FAIL_CLOSED")
    if activation.get("external_effect_authority") is not False:
        receipt["violations"].append("EXTERNAL_EFFECT_AUTHORITY_MUST_BE_FALSE")
    if activation.get("physical_runtime_effect_authority") is not False:
        receipt["violations"].append("PHYSICAL_EFFECT_AUTHORITY_MUST_BE_FALSE")

    if stage not in stages:
        receipt["violations"].append("UNKNOWN_STAGE")
        receipt["verdict"] = "BLOCKED_UNKNOWN_STAGE"
        receipt["admitted"] = False
        return receipt

    required = stages[stage].get("required", [])
    for key in required:
        if key not in packet:
            receipt["missing"].append(key)
        elif packet[key] is None or packet[key] == "UNKNOWN":
            receipt["unknown"].append(key)

    if stage == "DISCOVERY_ONLY":
        if packet.get("content_exposed") is not False:
            receipt["violations"].append("CONTENT_EXPOSED_DURING_DISCOVERY")
        if packet.get("source_read_only") is not True:
            receipt["violations"].append("SOURCE_NOT_READ_ONLY")
        if packet.get("lineage_roles_preserved") is not True:
            receipt["violations"].append("LINEAGE_ROLES_NOT_PRESERVED")

    elif stage == "CONTENT_PULL_CANDIDATE":
        for key in (
            "selector_frozen", "feature_frozen", "score_frozen", "split_frozen",
            "holdout_clean", "lineage_independence_audited", "member_id_bound"
        ):
            if key in packet and not is_true(packet[key]):
                receipt["violations"].append(f"{key.upper()}_NOT_TRUE")

    elif stage == "DOMAIN_EVIDENCE_CANDIDATE":
        for key in (
            "timing_classified", "claim_ceiling_frozen", "human_translation_blocked",
            "independent_replication_not_inflated", "source_read_only", "lineage_roles_preserved"
        ):
            if key in packet and not is_true(packet[key]):
                receipt["violations"].append(f"{key.upper()}_NOT_TRUE")

    elif stage == "SCIENTIFIC_PROMOTION_CANDIDATE":
        for key in (
            "prefrozen_quantitative_claim", "raw_or_new_data_result", "independent_replication",
            "negative_control_pass", "post_result_prior_art_null", "replayable_provenance",
            "mad_lab_survived", "lineage_independence_audited"
        ):
            if key in packet and not is_true(packet[key]):
                receipt["violations"].append(f"{key.upper()}_NOT_TRUE")

    if receipt["violations"]:
        if "CONTENT_EXPOSED_DURING_DISCOVERY" in receipt["violations"]:
            verdict = "BLOCKED_HOLDOUT_CONTAMINATION"
        else:
            verdict = "BLOCKED_AUTHORITY_OR_GATE_VIOLATION"
        admitted = False
    elif receipt["missing"]:
        verdict = "BLOCKED_MISSING_RECEIPT"
        admitted = False
    elif receipt["unknown"]:
        verdict = "BLOCKED_UNKNOWN_RECEIPT"
        admitted = False
    else:
        verdict = stages[stage]["success_verdict"]
        admitted = True

    receipt["verdict"] = verdict
    receipt["admitted"] = admitted
    receipt["next_authority"] = (
        "SEARCH_PIPELINE_ONLY" if stage == "DISCOVERY_ONLY" and admitted else
        "FROZEN_CONTENT_PULL_REVIEW" if stage == "CONTENT_PULL_CANDIDATE" and admitted else
        "JANUS_GENESIS_DOMAIN_LANE_ONLY" if stage == "DOMAIN_EVIDENCE_CANDIDATE" and admitted else
        "JANUS_FUNDAMENTUM_SCIENTIFIC_PROMOTION_GATE" if stage == "SCIENTIFIC_PROMOTION_CANDIDATE" and admitted else
        "NONE"
    )
    receipt["receipt_sha256"] = sha256_obj({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="trump/TRUMP_MANIFEST.json")
    ap.add_argument("--contract", default="trump/PHYSARIUS_FINAL_ADMISSION_CONTRACT_v1.json")
    ap.add_argument("--packet", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    receipt = gate(load(args.manifest), load(args.contract), load(args.packet))
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if receipt["admitted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
