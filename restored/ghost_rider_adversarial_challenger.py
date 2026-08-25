from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "janus.ghost_rider_adversarial_challenge.v1"
LANES = (
    "DIRECT_NEGATION",
    "ASSUMPTION_ATTACK",
    "ALTERNATIVE_CAUSAL_STORY",
    "MISSING_EVIDENCE",
)


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _clean_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def prepare_challenge(claim: str, source_ref: str | None = None) -> dict[str, Any]:
    claim = _clean_text("claim", claim)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ADVERSARIAL_TASK",
        "claim": claim,
        "source_ref": source_ref,
        "lanes": list(LANES),
        "instructions": {
            "DIRECT_NEGATION": "Construct the strongest plausible case that the claim is false.",
            "ASSUMPTION_ATTACK": "Identify a hidden assumption whose failure would break the claim.",
            "ALTERNATIVE_CAUSAL_STORY": "Construct a materially different explanation for the same observations.",
            "MISSING_EVIDENCE": "State what observation would discriminate the claim from its alternatives.",
        },
        "authority": {
            "synthetic_output_is_evidence": False,
            "writes_truth_memory": False,
            "changes_runtime": False,
            "chooses_conclusion": False,
        },
        "laws": [
            "ADVERSARIAL_GENERATION_NE_EVIDENCE",
            "COUNTERHYPOTHESIS_MUST_BE_TESTABLE",
            "SOURCE_CLAIM_AND_SYNTHETIC_ATTACK_MUST_REMAIN_SEPARATE",
            "NO_TRUTH_DB_PROMOTION_WITHOUT_INDEPENDENT_EVIDENCE",
        ],
    }
    body["challenge_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def seal_candidate(challenge: dict[str, Any], lane: str, candidate_text: str) -> dict[str, Any]:
    if not isinstance(challenge, dict) or challenge.get("schema") != SCHEMA:
        raise ValueError("challenge must be a Ghost Rider challenge receipt")
    if lane not in LANES:
        raise ValueError("unknown adversarial lane")
    candidate_text = _clean_text("candidate_text", candidate_text)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ADVERSARIAL_CANDIDATE_NOT_EVIDENCE",
        "challenge_sha256": challenge.get("challenge_sha256"),
        "claim": challenge.get("claim"),
        "lane": lane,
        "candidate_text": candidate_text,
        "authority": {
            "candidate_is_fact": False,
            "candidate_is_refutation": False,
            "writes_truth_memory": False,
            "changes_runtime": False,
        },
        "next_gate": "TEST_CANDIDATE_AGAINST_INDEPENDENT_EVIDENCE",
    }
    body["candidate_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
