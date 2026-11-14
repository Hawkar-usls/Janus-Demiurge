"""Ocean's inbound read-only view of a Tachyon 009B shadow review.

Consumes only a hash-bound research receipt, not arbitrary instructions,
gradients, drand labels, physics authority or changes to live Ocean models.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

SOURCE_SCHEMA = "janus.tachyon.ocean_shadow_bridge.v1"
WRAPPER_SCHEMA = "janus.tachyon.ocean_009b.real_early_witness.v1"
FEEDBACK_SCHEMA = "janus.ocean.tachyon_research_feedback.v1"
OUTPUT_SCHEMA = "janus.ocean.tachyon_research_context.v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES = 100_000


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def consume(record):
    if not isinstance(record, dict):
        raise ValueError("RECORD_OBJECT_REQUIRED")
    wrapped = record.get("schema") == WRAPPER_SCHEMA
    review = record.get("tachyon_shadow_review") if wrapped else record
    if not isinstance(review, dict) or review.get("schema") != SOURCE_SCHEMA:
        raise ValueError("TACHYON_REVIEW_SCHEMA_REJECTED")
    found_sha = review.get("receipt_sha256")
    body = dict(review)
    body.pop("receipt_sha256", None)
    if not isinstance(found_sha, str) or not HEX.fullmatch(found_sha) or digest(body) != found_sha:
        raise ValueError("TACHYON_REVIEW_TAMPERED")
    src = review.get("ocean_source")
    if not isinstance(src, dict) or src.get("repository") != "Hawkar-usls/Janus-Demiurge" or src.get("lane") != "OPEN-FUTURE-009B":
        raise ValueError("WRONG_OCEAN_SOURCE_OR_LANE")
    commit = src.get("commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError("OCEAN_SOURCE_COMMIT_REQUIRED")
    early = review.get("early")
    if not isinstance(early, dict):
        raise ValueError("EARLY_RECEIPT_MISSING")
    try:
        dt = date.fromisoformat(early["target_date"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("TARGET_DATE_MISSING") from exc
    if not date(2026,11,12) <= dt <= date(2026,11,19):
        raise ValueError("FROZEN_COHORT_VIOLATION")
    if not isinstance(early.get("precommit_sha256"), str) or not HEX.fullmatch(early["precommit_sha256"]):
        raise ValueError("PRECOMMIT_HASH_MISSING")
    if early.get("witness_timestamp_supplied") is not True:
        raise ValueError("UNWITNESSED_PRECOMMIT_NOT_IMPORTABLE")
    if review.get("authority_delta") != 0 or review.get("automatic_deployment") is not False or review.get("physical_retrocausality_established") is not False:
        raise ValueError("REVIEW_AUTHORITY_OR_CLAIM_ESCALATION")
    tachyon = review.get("tachyon")
    if not isinstance(tachyon, dict) or tachyon.get("learned_training_signal") is not False or tachyon.get("semantic_classifier_used_for_truth") is not False or tachyon.get("numeric_lorentz_head_used_on_drand") is not False:
        raise ValueError("ILLEGAL_LEARNED_GRADIENT_OR_INVALID_DOMAIN")
    feedback = review.get("feedback")
    if (not isinstance(feedback, dict) or feedback.get("schema") != FEEDBACK_SCHEMA or
        feedback.get("eligible_as_gradient_label") is not False or
        feedback.get("may_revise_frozen_early_forecast") is not False or
        feedback.get("may_trigger_automatic_training") is not False or
        feedback.get("authority_delta") != 0):
        raise ValueError("FEEDBACK_RETRAINING_OR_AUTHORITY_REJECTED")
    questions = feedback.get("candidate_questions")
    if (not isinstance(questions, list) or len(questions)>4 or any(not isinstance(x,str) or not 1<=len(x)<=300 for x in questions)):
        raise ValueError("QUESTION_WINDOW_UNBOUNDED")
    topa = review.get("topa")
    envelope = topa.get("envelope") if isinstance(topa, dict) else None
    if (not isinstance(envelope, dict) or envelope.get("evidence_class") != "HYPOTHESIS_ONLY" or
        envelope.get("status") != "HYPOTHESIS_ONLY" or
        topa.get("provider_admission") not in ("NOT_EXECUTED", "HYPOTHESIS_ONLY_ACCEPTED")):
        raise ValueError("TOPA_CLAIM_ESCALATION_REJECTED")
    late = review.get("late")
    allowed_late = {"PENDING_FUTURE_OUTCOMES", "UPSTREAM_REPORT_ONLY_NO_INDEPENDENT_RECALC", "SIGNATURE_DIGESTS_AND_SCORE_RECOMPUTED"}
    if not isinstance(late, dict) or late.get("status") not in allowed_late:
        raise ValueError("UNKNOWN_LATE_SCORE_STATE")
    if late.get("retrocausality_proven") is True:
        raise ValueError("NO_PROOF_OF_RETROCAUSALITY")
    if wrapped:
        if (record.get("original_source_commit") != commit or record.get("precommit_target_date_utc") != str(dt) or
            record.get("n_distinct_future_rounds") != 128 or
            record.get("ocean_canonical_precommit_sha256") != early["precommit_sha256"] or
            record.get("github_artifact_server_digest_matches_download") is not True):
            raise ValueError("ORIGINAL_ARCHIVE_LINEAGE_REJECTED")
    result = {
        "schema": OUTPUT_SCHEMA,
        "status": "RESEARCH_CONTEXT_ONLY_NOT_TRAINING",
        "target_date": str(dt),
        "source": {"repo": src["repository"], "ocean_commit": commit,
                    "tachyon_review_sha256": found_sha,
                    "ocean_precommit_sha256": early["precommit_sha256"],
                    "witness_wrapper_supplied": wrapped},
        "research_questions": questions,
        "topa_status": topa["provider_admission"],
        "outcome_state": late["status"],
        "model": {"ocean_weights_modified": False,
                  "tachyon_weights_inherited": False,
                  "auto_training_triggered": False,
                  "direct_training_signal": False},
        "rights": {"may_create_read_only_research_tasks": True,
                   "may_modify_ocean_forecast": False,
                   "may_modify_existing_ocean_workflows": False,
                   "may_promote_scientific_claim": False,
                   "may_mutate_other_repositories": False,
                   "authority_delta": 0},
        "physical_retrocausality_established": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tachyon-review", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    raw = args.tachyon_review.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("UNBOUNDED_TACHYON_REVIEW")
    record = consume(json.loads(raw))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
    print(json.dumps({"status":record["status"], "receipt_sha256": record["receipt_sha256"]}))

if __name__=="__main__":
    main()
