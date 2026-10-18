"""Seal R2 paired questions for external review without inventing judgments.

This gives a checkable commitment to arm assignment and submitted questions.
Only arm *labels* are blinded, not the recognizable substance of algorithms.
No reviewer identity/independence is authenticated by this module.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from janus_model.divergent_mind import _canonical


CONTRACT = Path(__file__).resolve().parent / "eval" / "DIVERGENT_MIND_R2_HOLDOUT_CONTRACT.json"
TRIAL_SCHEMA = "janus.divergent_mind.r2.blinded_trial.v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def validate_contract(contract: dict) -> None:
    if (not isinstance(contract, dict) or
            contract.get("schema") != "janus.divergent_mind.r2.external_holdout_contract.v1" or
            contract.get("registration_status") !=
            "DESIGN_FROZEN__FUTURE_CASES_NOT_YET_COLLECTED" or
            contract.get("external_judge", {}).get("assigned") is not False or
            contract.get("scientific_gate") != "OPEN__EXTERNAL_REVIEW_REQUIRED"):
        raise ValueError("untrusted or non-open holdout contract")
    plan = contract.get("comparison", {})
    if (plan.get("arms") != 2 or plan.get("questions_per_arm") != 4 or
            plan.get("same_source_commit_triplet_required") is not True or
            plan.get("zero_scientific_promotion") is not True or
            plan.get("zero_independence_automatic_verified") is not True or
            plan.get("arm_label_blinding") is not True or
            plan.get("full_algorithm_blinding_claimed") is not False):
        raise ValueError("invalid comparison constraints")


def seal_trial(capture: dict, contract: dict, *, nonce: str) -> tuple[dict, dict]:
    validate_contract(contract)
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32,128}", nonce):
        raise ValueError("private nonce must be hex and supplied by reviewer/submitter")
    if (not isinstance(capture, dict) or
            capture.get("status") != "READ_ONLY_QUESTIONS_READY__NOT_RUNTIME_INTEGRATION" or
            capture.get("whole_blobs_verified") != 6 or
            capture.get("origin_path_at_commit_checked_via_github_contents_api") is not True or
            capture.get("source_writeback") is not False or
            capture.get("scientific_claim_promotion") is not False or
            capture.get("authority_delta") != 0):
        raise ValueError("holdout cannot use unverified or action-authoritative source capture")
    packet = capture.get("packet", {})
    source = packet.get("questions_by_arm", {})
    if set(source) != {"native_baseline", "divergent_r1"}:
        raise ValueError("two actual comparison arms are required")
    for arm, questions in source.items():
        if (not isinstance(questions, list) or len(questions) != 4 or
                any(q.get("claim_promotion") is not False or
                    q.get("independence_verified") is not False or
                    q.get("effect_authority") is not False for q in questions)):
            raise ValueError("unsafe or unbalanced questions")
    # Deterministic after nonce choice, but opaque before private reveal.
    flip = int(digest({"nonce": nonce, "source": capture["source_pack_sha256"]})[0], 16) % 2
    mapping = {"arm_a": "divergent_r1" if flip else "native_baseline",
               "arm_b": "native_baseline" if flip else "divergent_r1"}
    blinded = {
        label: [{
            "question": q["question"],
            "source_refs": q["source_refs"],
            "required_falsifier": q["required_falsifier"],
            "epistemic_status": "QUESTION_ONLY__UNVERIFIED",
        } for q in source[arm]]
        for label, arm in mapping.items()
    }
    public = {
        "schema": TRIAL_SCHEMA,
        "contract_sha256": digest(contract),
        "source_pack_sha256": capture["source_pack_sha256"],
        "question_budget_per_arm": 4,
        "blinded_arms": blinded,
        "reviewer_assignment": "OPEN__NO_INDEPENDENT_JUDGE_ASSIGNED",
        "scientific_status": "OPEN",
    }
    public["submission_sha256"] = digest(public)
    private = {
        "schema": "janus.divergent_mind.r2.private_arm_mapping.v1",
        "submission_sha256": public["submission_sha256"],
        "nonce": nonce,
        "mapping": mapping,
        "commitment_sha256": digest({"nonce": nonce, "mapping": mapping,
                                    "submission_sha256": public["submission_sha256"]}),
        "instruction": "DO_NOT_DISCLOSE_MAPPING_UNTIL_EXTERNAL_RATINGS_FROZEN",
    }
    return public, private


def verify_reveal(public: dict, private: dict, contract: dict) -> bool:
    validate_contract(contract)
    if not isinstance(public, dict) or not isinstance(private, dict):
        return False
    if (public.get("schema") != TRIAL_SCHEMA or private.get("schema") !=
            "janus.divergent_mind.r2.private_arm_mapping.v1"):
        return False
    copy = dict(public)
    published = copy.pop("submission_sha256", None)
    if not isinstance(published, str) or not HEX64.fullmatch(published) or digest(copy) != published:
        return False
    mapping = private.get("mapping")
    if (public.get("contract_sha256") != digest(contract) or
            private.get("submission_sha256") != published or
            not isinstance(mapping, dict) or
            set(mapping) != {"arm_a", "arm_b"} or
            set(mapping.values()) != {"native_baseline", "divergent_r1"}):
        return False
    if not isinstance(private.get("nonce"), str) or not re.fullmatch(
            r"[0-9a-f]{32,128}", private["nonce"]):
        return False
    return private.get("commitment_sha256") == digest({
        "nonce": private["nonce"], "mapping": private["mapping"], "submission_sha256": published,
    })


def load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))
