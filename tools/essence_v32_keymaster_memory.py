#!/usr/bin/env python3
"""ESSENCE v3.2 Keymaster + EvolutionaryMemory: bounded executable evidence bridge.

Uses existing Keymaster v2 provenance and verified outcome-memory contracts.
The original hardware Keymaster (root/keymaster.py) and EvolutionaryMemory
(root/memory.py) are *historical design sources*, NEVER imported or executed.
No serial/ArtMoney, subprocess, secrets, model training, selection or promotion.
Only hash-bound source metadata and target-local verified lessons are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "janus.essence.keymaster_memory_bridge/3.2"
STATE_SCHEMA = "janus.essence.keymaster_memory_state/3.2"
REPOSITORY = "Hawkar-usls/Janus-Demiurge"
CONFIG_SCHEMA = "janus.keymaster.primary_learning_contributors.v2"
ATTRIBUTION_SCHEMA = "janus.keymaster.attribution_r2_summary.v1"
OUTCOME_SCHEMA = "janus.verified_outcome_memory.v1"
MAX_SOURCE_BYTES = 90000
MAX_STATE_BYTES = 120000
MAX_HISTORY = 32
MAX_LESSONS = 30
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
REPO = re.compile(r"^Hawkar-usls/[A-Za-z0-9_.-]+$")
EXPECTED_IDS = frozenset((
    "TOPA", "TRANCEPTION", "LAPIS", "IO_PUBLIC", "FAST_CAT_SHAITAN",
    "FUNDAMENTUM", "DEMI_HEAD", "AURA_ORACLE"
))
PATHS = {
    "keymaster": "janus_model/keymaster/PRIMARY_REPOSITORY_CONTRIBUTORS-v2.json",
    "attribution": "janus_model/state/KEYMASTER_ATTRIBUTION_R2_LATEST.json",
    "outcomes": "janus_model/state/JANUS_VERIFIED_OUTCOME_MEMORY.json",
}
LEGACY_REFERENCES = ("keymaster.py", "memory.py")
ROOT = "0" * 64


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def checked_json(root, relative):
    root = Path(root).resolve(strict=True)
    p = root / relative
    if p.is_symlink() or not p.resolve(strict=True).is_relative_to(root):
        raise ValueError("SOURCE_PATH_ESCAPE")
    if not 2 <= p.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("SOURCE_SIZE_HOLD")
    raw = p.read_bytes()
    obj = json.loads(raw.decode("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(
        ValueError("NONFINITE_JSON")))
    if not isinstance(obj, dict):
        raise ValueError("SOURCE_OBJECT_REQUIRED")
    return obj, hashlib.sha256(raw).hexdigest()


def check_keymaster(config):
    if (config.get("schema") != CONFIG_SCHEMA
        or config.get("status") != "ACTIVE_REQUIRED_8_OF_8"
        or config.get("contributor_count") != 8):
        raise ValueError("KEYMASTER_SOURCE_CONTRACT")
    sources = config.get("contributors")
    if not isinstance(sources, list) or len(sources) != 8:
        raise ValueError("KEYMASTER_CONTRIBUTOR_SET")
    ids = set()
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("KEYMASTER_ENTRY")
        if item.get("id") in ids or item.get("id") not in EXPECTED_IDS:
            raise ValueError("KEYMASTER_ID_MISMATCH")
        if not isinstance(item.get("repository"), str) or not REPO.fullmatch(item["repository"]):
            raise ValueError("KEYMASTER_UNTRUSTED_REPOSITORY")
        if item.get("cohort") not in ("CORE_5", "EXTENDED_3"):
            raise ValueError("KEYMASTER_COHORT")
        ids.add(item["id"])
    if ids != EXPECTED_IDS:
        raise ValueError("KEYMASTER_INCOMPLETE_8")
    if (sum(x["cohort"] == "CORE_5" for x in sources) != 5
        or sum(x["cohort"] == "EXTENDED_3" for x in sources) != 3):
        raise ValueError("KEYMASTER_COHORT_SIZES")
    select = config.get("selection") or {}
    learn = config.get("learning") or {}
    fire = config.get("firewalls") or {}
    required_true = (select.get("tracked_files_only"),
                     select.get("semantic_text_only"),
                     select.get("token_like_text_scrubbed"))
    required_false = (select.get("execute_source"),
                      select.get("secretish_paths_allowed"),
                      select.get("generated_state_is_training_source"),
                      learn.get("adaptive_holdout_inclusion"),
                      learn.get("frozen_anchor_inclusion"),
                      learn.get("training_material_is_truth"),
                      learn.get("contribution_grants_authority"),
                      fire.get("source_execution"),
                      fire.get("cross_repository_write"))
    if not all(x is True for x in required_true) or any(x is not False for x in required_false):
        raise ValueError("KEYMASTER_LEARNING_FIREWALL")
    if learn.get("lane") != "TRAIN_ONLY":
        raise ValueError("KEYMASTER_LANE_NOT_TRAIN_ONLY")
    return tuple(sorted((x["id"], x["repository"]) for x in sources))


def check_attribution(attr, contributors):
    if attr.get("schema") != ATTRIBUTION_SCHEMA or attr.get("status") != "REPLICATED_EVIDENCE_READY":
        raise ValueError("ATTRIBUTION_CONTRACT")
    ceiling = attr.get("claim_ceiling") or {}
    for key in ("automatic_contributor_removal", "automatic_weighting_change",
                "r2_class_grants_authority", "r2_class_is_world_causality",
                "r2_class_is_world_truth", "failed_or_missing_run_is_negative_evidence"):
        if ceiling.get(key) is not False:
            raise ValueError("ATTRIBUTION_AUTHORITY_FIREWALL")
    if ceiling.get("authority_delta") != 0:
        raise ValueError("ATTRIBUTION_AUTHORITY_CHANGED")
    rows = attr.get("attribution")
    if not isinstance(rows, list) or len(rows) != 8:
        raise ValueError("ATTRIBUTION_RECORD_COUNT")
    ids = []
    unresolved = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("class") not in (
            "UNRESOLVED", "REPRODUCIBLE_SUPPORT", "REPRODUCIBLE_ADVERSE"
        ):
            raise ValueError("ATTRIBUTION_UNKNOWN_CLASS")
        if not SHA40.fullmatch(str(row.get("latest_head_sha", ""))):
            raise ValueError("ATTRIBUTION_MISSING_PROVENANCE")
        ids.append((row.get("id"), row.get("repository")))
        unresolved += row["class"] == "UNRESOLVED"
    if tuple(sorted(ids)) != contributors:
        raise ValueError("ATTRIBUTION_DONOR_BINDING_MISMATCH")
    return {"donors_verified": len(ids), "unresolved_donors": unresolved,
            "class_counts": {k: sum(x["class"] == k for x in rows)
                             for k in ("UNRESOLVED", "REPRODUCIBLE_SUPPORT", "REPRODUCIBLE_ADVERSE")}}


def check_outcomes(mem):
    if mem.get("schema") != OUTCOME_SCHEMA or mem.get("status") != "VERIFIED_OUTCOME_MEMORY_READY":
        raise ValueError("OUTCOME_MEMORY_SCHEMA")
    policy = mem.get("policy") or {}
    for key in ("feedback_grants_mutation_authority", "historical_verify_pass_is_world_truth",
                "silence_is_negative_evidence", "rejected_provenance_is_negative_evidence"):
        if policy.get(key) is not False:
            raise ValueError("OUTCOME_MEMORY_AUTHORITY")
    for key in ("only_target_local_verify_pass_is_positive_feedback",
                "native_model_selected_required_for_training_prior",
                "target_local_reverification_still_required",
                "clean_patch_lineage_required_for_training_prior"):
        if policy.get(key) is not True:
            raise ValueError("OUTCOME_MEMORY_VERIFIER_REQUIRED")
    rows = mem.get("records")
    if (not isinstance(rows, list) or len(rows) > 64
        or mem.get("record_count") != len(rows)):
        raise ValueError("OUTCOME_RECORD_COUNT")
    seen = set()
    lessons = []
    for row in rows:
        if not isinstance(row, dict) or not SHA64.fullmatch(str(row.get("record_sha256", ""))):
            raise ValueError("OUTCOME_RECORD_UNSEALED")
        if row["record_sha256"] != seal({k: v for k, v in row.items() if k != "record_sha256"}):
            raise ValueError("OUTCOME_RECORD_DIGEST_MISMATCH")
        ident = row.get("proposal_id")
        if not isinstance(ident, str) or not 1 <= len(ident) <= 96 or ident in seen:
            raise ValueError("OUTCOME_DUPLICATE_PROPOSAL")
        seen.add(ident)
        if (row.get("positive_feedback") is True
            and row.get("status") == "VERIFY_PASS"
            and row.get("lineage_verified") is True
            and row.get("terminal_authority") == "TARGET_LOCAL_VERIFIER"
            and row.get("native_model_selected") is True
            and row.get("training_eligible") is True
            and row.get("mutation_authority_granted") is False
            and row.get("main_mutated") is False
            and row.get("truth_claim") is False):
            # EvolutionaryMemory's lesson bank: provenance-only, not a score
            # and never used to re-fit or choose production weights.
            lessons.append({
                "proposal_sha256": str(row.get("proposal_sha256")),
                "record_sha256": row["record_sha256"],
                "target_repository": str(row.get("target_repository")),
                "lesson": "TARGET_LOCAL_VERIFIED_EXPERIENCE_NOT_GENERALIZATION",
            })
    if mem.get("training_eligible_count") != len(lessons):
        raise ValueError("OUTCOME_ELIGIBLE_COUNT_MISMATCH")
    return sorted(lessons, key=lambda x: x["record_sha256"])[:MAX_LESSONS]


def empty_state():
    raw = {"schema": STATE_SCHEMA, "repository": REPOSITORY,
           "history": [], "operational_authority": False}
    return dict(raw, state_sha256=seal(raw))


def verify_state(state):
    if (not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA
        or state.get("repository") != REPOSITORY
        or state.get("operational_authority") is not False
        or state.get("state_sha256") != seal({
            k: v for k, v in state.items() if k != "state_sha256"})):
        raise ValueError("MEMORY_STATE_TAMPERED")
    chain = ROOT
    history = state.get("history")
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError("MEMORY_HISTORY_UNBOUNDED")
    fingerprints = set()
    for index, row in enumerate(history):
        if (not isinstance(row, dict) or row.get("sequence") != index
            or row.get("previous_sha256") != chain
            or not SHA64.fullmatch(str(row.get("evidence_sha256", "")))
            or row.get("evidence_sha256") in fingerprints
            or row.get("receipt_sha256") != seal({
                k: v for k, v in row.items() if k != "receipt_sha256"})):
            raise ValueError("MEMORY_HISTORY_CHAIN_BROKEN")
        if row.get("training_admission") is not False or row.get("authority_delta") != 0:
            raise ValueError("MEMORY_HISTORY_AUTHORITY_CHANGED")
        fingerprints.add(row["evidence_sha256"])
        chain = row["receipt_sha256"]
    return chain


def evaluate(config, attribution, outcomes, previous, *, source_hashes, source_commit):
    if not SHA40.fullmatch(str(source_commit)):
        raise ValueError("SOURCE_COMMIT_NOT_PINNED")
    for path in PATHS:
        if not SHA64.fullmatch(str(source_hashes.get(path, ""))):
            raise ValueError("SOURCE_HASH_REQUIRED")
    donors = check_keymaster(config)
    evidence = check_attribution(attribution, donors)
    lessons = check_outcomes(outcomes)
    tail = verify_state(previous)
    fingerprint = seal({"sources": source_hashes})
    seen = {x["evidence_sha256"] for x in previous["history"]}
    novel = fingerprint not in seen
    # Keymaster's defensive state machine: unresolved donor contribution
    # cannot automatically change weights or remove a donor.
    mode = "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION" if evidence["unresolved_donors"] else "REVIEW_ONLY"
    if novel and len(previous["history"]) >= MAX_HISTORY:
        raise ValueError("MEMORY_HISTORY_FULL_REQUIRES_REVIEW")
    base = {k: v for k, v in previous.items() if k != "state_sha256"}
    if novel:
        row = {
            "sequence": len(base["history"]),
            "evidence_sha256": fingerprint,
            "source_commit": source_commit,
            "previous_sha256": tail,
            "donor_count": evidence["donors_verified"],
            "verified_local_lessons": len(lessons),
            "keymaster_guard": mode,
            "authority_delta": 0,
            "training_admission": False,
        }
        row["receipt_sha256"] = seal(row)
        base["history"] = list(base["history"]) + [row]
    new_state = dict(base, state_sha256=seal(base))
    verify_state(new_state)
    report = {
        "schema": SCHEMA, "repository": REPOSITORY,
        "source_commit": source_commit, "source_sha256": dict(sorted(source_hashes.items())),
        "source_fingerprint_sha256": fingerprint,
        "legacy_design_sources_not_executed": list(LEGACY_REFERENCES),
        "microkernels": [
            {"id": "keymaster_provenance_guard", "state": mode,
             "source_contributors": evidence["donors_verified"],
             "unresolved_contributors": evidence["unresolved_donors"],
             "classes": evidence["class_counts"]},
            {"id": "evolutionary_verified_memory", "state": "LOCAL_LESSONS_VERIFIED",
             "lesson_count": len(lessons), "lessons": lessons},
        ],
        "memory_added_new_evidence": novel, "previous_state_sha256": previous["state_sha256"],
        "next_state_sha256": new_state["state_sha256"],
        "memory_generations_recorded": len(new_state["history"]),
        "cross_run_memory_persistable_to_research_branch": True,
        "keymaster_can_touch_secrets": False,
        "keymaster_can_control_hardware": False,
        "keymaster_can_remove_contributors": False,
        "historical_python_executed": False,
        "raw_memory_text_exported": False,
        "scientific_generalization_proven": False,
        "neural_weights_changed": False,
        "automatic_module_activation": False,
        "automatic_production_promotion": False,
        "training_data_modified": False,
        "status": "RESEARCH_LESSONS_BOUND_NO_MODEL_ADMISSION",
    }
    report["receipt_sha256"] = seal(report)
    return new_state, report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--previous", required=True)
    p.add_argument("--state-out", required=True)
    p.add_argument("--receipt", required=True)
    a = p.parse_args()
    config, h1 = checked_json(a.source_root, PATHS["keymaster"])
    attribution, h2 = checked_json(a.source_root, PATHS["attribution"])
    outcomes, h3 = checked_json(a.source_root, PATHS["outcomes"])
    previous_path = Path(a.previous)
    if previous_path.exists():
        if previous_path.is_symlink() or previous_path.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("PREVIOUS_STATE_SIZE_OR_SYMLINK")
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
    else:
        previous = empty_state()
    new_state, report = evaluate(
        config, attribution, outcomes, previous,
        source_hashes={"keymaster": h1, "attribution": h2, "outcomes": h3},
        source_commit=a.source_commit)
    out = Path(a.receipt)
    if out.exists():
        raise ValueError("RECEIPT_IS_IMMUTABLE")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    if new_state["state_sha256"] != previous["state_sha256"]:
        state_path = Path(a.state_out)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2,
                                         sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "donors": 8,
        "verified_lessons": report["microkernels"][1]["lesson_count"],
        "memory_new": report["memory_added_new_evidence"],
        "memory_history": report["memory_generations_recorded"],
        "weights_changed": False, "authority": False,
        "receipt_sha256": report["receipt_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
