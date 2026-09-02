from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from janus_model.decision import NO_ACTION_ID, SCHEMA as DECISION_CANDIDATE_SET_SCHEMA, _validate_candidate_set

INDEX_SCHEMA = "janus.native_repair_candidates.index.v1"
REJECTION_SCHEMA = "janus.native_repair_candidate_rejections.v1"


def _module_by_repo(organ_context: dict) -> dict[str, dict]:
    modules = organ_context.get("repository_modules") or {}
    return {
        str(module.get("repository")): module
        for module in modules.values()
        if isinstance(module, dict) and isinstance(module.get("repository"), str)
    }


def prevalidate_candidate_index(index_obj: dict, organ_context: dict, self_memory_digest: str) -> tuple[dict, dict]:
    """Turn raw self-memory candidates into a truly scout-bound candidate set.

    The strict decision validator remains authoritative. Every candidate is run
    through it in isolation together with NO_ACTION. The *only* neutralizable
    failure is an exact target-commit mismatch against an otherwise observed
    module. Malformed, unknown-target, risk, verifier, proposal, and all other
    failures remain fatal.
    """
    if index_obj.get("schema") != INDEX_SCHEMA:
        raise RuntimeError("JANUS_REPAIR_CANDIDATE_INDEX_SCHEMA_FAIL")
    raw_candidates = index_obj.get("candidates")
    if not isinstance(raw_candidates, list):
        raise RuntimeError("JANUS_REPAIR_CANDIDATE_INDEX_LIST_FAIL")
    if index_obj.get("candidate_count") != len(raw_candidates):
        raise RuntimeError("JANUS_REPAIR_CANDIDATE_INDEX_COUNT_FAIL")
    if not isinstance(self_memory_digest, str) or len(self_memory_digest) != 64:
        raise RuntimeError("JANUS_REPAIR_SELF_MEMORY_DIGEST_REJECTED")

    no_action = {"candidate_id": NO_ACTION_ID, "action": "NO_ACTION", "score_text": "NO_ACTION"}
    modules = _module_by_repo(organ_context)
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise RuntimeError("DECISION_CANDIDATE_OBJECT_REQUIRED")
        probe = {
            "schema": DECISION_CANDIDATE_SET_SCHEMA,
            "status": "BOUNDED_PREVALIDATED_CANDIDATES",
            "source_self_memory_digest": self_memory_digest,
            "candidates": [no_action, raw],
        }
        try:
            validated = _validate_candidate_set(probe, organ_context)
        except RuntimeError as exc:
            message = str(exc)
            prefix = "DECISION_TARGET_COMMIT_NOT_SCOUT_BOUND:"
            if not message.startswith(prefix):
                raise
            candidate_id = message[len(prefix):]
            target = raw.get("target") or {}
            repository = target.get("repository")
            module = modules.get(repository)
            if module is None:
                # Defensive: exact-commit mismatch is neutral only when the
                # repository is positively observed in this organ context.
                raise RuntimeError(f"PREFLIGHT_STALE_TARGET_MODULE_DISAPPEARED:{candidate_id}")
            rejected.append({
                "candidate_id": candidate_id,
                "status": "REJECTED_STALE_TARGET",
                "reason": "STALE_TARGET_NOT_SCOUT_BOUND",
                "target_repository": repository,
                "candidate_expected_target_commit": target.get("expected_target_commit"),
                "scout_bound_target_commit": module.get("target_commit"),
                "negative_evidence": False,
                "verification_failure": False,
                "mutation_attempted": False,
                "authority_delta": 0,
            })
            continue
        # position zero is NO_ACTION; the strict validator normalizes the row.
        admitted.append(validated[1])

    candidate_set = {
        "schema": DECISION_CANDIDATE_SET_SCHEMA,
        "status": "BOUNDED_PREVALIDATED_CANDIDATES",
        "source_self_memory_digest": self_memory_digest,
        "candidates": [no_action, *admitted],
    }
    # Final aggregate validation remains strict. This catches duplicate IDs and
    # any cross-row issue before the neural selector ever sees the set.
    validated_set = _validate_candidate_set(candidate_set, organ_context)
    candidate_set["candidates"] = validated_set

    receipt = {
        "schema": REJECTION_SCHEMA,
        "status": "CANDIDATE_PREFLIGHT_COMPLETE",
        "raw_external_candidate_count": len(raw_candidates),
        "admitted_external_candidate_count": len(admitted),
        "rejected_stale_candidate_count": len(rejected),
        "rejections": rejected,
        "laws": [
            "STALE_CANDIDATE != NEGATIVE_EVIDENCE",
            "STALE_CANDIDATE != VERIFICATION_FAILURE",
            "STALE_CANDIDATE != APPLY",
            "NO_VALID_ACTION => NO_ACTION_REMAINS_AVAILABLE",
            "MALFORMED_OR_UNOBSERVED_CANDIDATE => FAIL_CLOSED",
        ],
        "authority_delta": 0,
    }
    return candidate_set, receipt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--organ-context", required=True)
    ap.add_argument("--candidates-out", required=True)
    ap.add_argument("--rejections-out", required=True)
    args = ap.parse_args()

    index_obj = json.loads(Path(args.index).read_text(encoding="utf-8"))
    organ_context = json.loads(Path(args.organ_context).read_text(encoding="utf-8"))
    self_memory_digest = ((organ_context.get("self_memory") or {}).get("digest_sha256"))
    candidate_set, receipt = prevalidate_candidate_index(index_obj, organ_context, self_memory_digest)
    Path(args.candidates_out).write_text(json.dumps(candidate_set, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.rejections_out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "raw_external_candidate_count": receipt["raw_external_candidate_count"],
        "admitted_external_candidate_count": receipt["admitted_external_candidate_count"],
        "rejected_stale_candidate_count": receipt["rejected_stale_candidate_count"],
        "total_decision_candidates": len(candidate_set["candidates"]),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
