"""JANUS R1: offline read-only adapter for pinned HRAiN / iNaiHR / EYE excerpts.

This consumes explicitly selected fields of real *repository state artifacts*;
it does not instantiate or call their runtimes. A Git blob SHA identifies the
originating complete file, but an excerpt alone is not cryptographic proof of
its own extraction. Capture verification is a separate source-audit gate.

The standard arm and divergent arm see the SAME sources and emit the SAME
number of question-only suggestions. Neither arm may promote claims or act.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from janus_model.divergent_mind import _digest


SCHEMA = "janus.divergent_mind.organ_snapshot.r1"
REPORT_SCHEMA = "janus.divergent_mind.organ_questions.r1"
CAPTURE_KIND = "PINNED_EXCERPTS_FROM_NATIVE_GITHUB_FILES__NOT_LIVE_RUNTIME"
FIELD_NAMES = {
    "hrain_head": ("Hawkar-usls/Hrain", "state/neural-link/HEAD.json",
                   "janus.neural_link.archive_head.v1"),
    "hrain_manifest": ("Hawkar-usls/Hrain", "state/neural-link/MANIFEST.json",
                       "janus.neural_link.archive_manifest.v1"),
    "hrain_provenance": ("Hawkar-usls/Hrain", "state/neural-link/PROVENANCE.json",
                         "janus.hrain.neural_link_memory_provenance.v1"),
    "inaihr_state": ("Hawkar-usls/iNaiHR", "janus-synth/state/JANUS_SYNTH_LATEST.json",
                     "janus.inaihr.semantic_evolution.v2"),
    "eye_next_tests": ("Hawkar-usls/janus-meta-registry",
                        "EYE/r4_7_rt/generated/next_best_tests.json",
                        "janus.eye.r4_1.next_best_tests.v1"),
    "eye_independence": ("Hawkar-usls/janus-meta-registry",
                         "EYE/r4_7_rt/generated/independence_matrix.json",
                         "janus.eye.r4_1.independence_matrix.v1"),
}
KEYS = {
    "hrain_head": {"schema", "status", "event_object_count", "latest_event_count",
                   "append_only_event_objects", "mutable_head_is_authority",
                   "cross_repo_write_credential_used"},
    "hrain_manifest": {"schema", "status", "authority"},
    "hrain_provenance": {"schema", "status", "read_only_mirror",
                         "cross_repository_write", "source_repository", "source_commit"},
    "inaihr_state": {"schema", "status", "generated_at", "candidate_count",
                      "registry", "attention", "recent_candidates"},
    "eye_next_tests": {"schema", "available_ranked", "unavailable_counterfactual_value_ranked",
                        "warning"},
    "eye_independence": {"schema", "unknown_independence_conflicts", "pair_count",
                          "pairs_sample"},
}
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
TEST_ID = re.compile(r"TOPA-RT-H[1-9][0-9]*\Z")
SYNTH_ID = re.compile(r"syn:[a-f0-9]{20}\Z")
OBJ_ID = re.compile(r"obj:[a-f0-9]{20}\Z")
MAX_QUESTIONS = 4


def _exact(value: dict, keys: set[str], description: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{description}: missing, extra, or instruction-like fields")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and HEX40.fullmatch(value) is not None


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 1_000_000


def _parse_time(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid snapshot UTC timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("timestamp must be explicit UTC")
    return timestamp


def validate(pack: dict[str, Any]) -> dict[str, dict]:
    _exact(pack, {"schema", "pack_id", "capture_kind", "sources"}, "pack")
    if pack["schema"] != SCHEMA or pack["capture_kind"] != CAPTURE_KIND:
        raise ValueError("unsupported or misleading live-capture claim")
    if not isinstance(pack["pack_id"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", pack["pack_id"]):
        raise ValueError("bad pack id")
    sources = pack["sources"]
    _exact(sources, set(FIELD_NAMES), "organ source set")
    out = {}
    for key, (repo, path, schema) in FIELD_NAMES.items():
        source = sources[key]
        _exact(source, {"origin", "excerpt"}, key)
        ref = source["origin"]
        _exact(ref, {"repository", "commit", "path", "blob_sha"}, key + " origin")
        if ref["repository"] != repo or ref["path"] != path or not _sha(ref["commit"]) or not _sha(ref["blob_sha"]):
            raise ValueError("source origin must be an exact immutable approved file")
        entry = source["excerpt"]
        _exact(entry, KEYS[key], key + " excerpt")
        if entry["schema"] != schema:
            raise ValueError("native organ schema mismatch")
        out[key] = entry
    # Cross-file pin consistency proves *identity of references*, not truth.
    h = out["hrain_head"]
    m = out["hrain_manifest"]
    p = out["hrain_provenance"]
    if (h["status"] != "ARCHIVE_SYNCED" or m["status"] != "ACTIVE_APPEND_ONLY_CHAT_MEMORY" or
            p["status"] != "VERIFIED_READ_ONLY_MIRROR" or
            not h["append_only_event_objects"] or h["mutable_head_is_authority"] is not False or
            h["cross_repo_write_credential_used"] is not False or
            p["read_only_mirror"] is not True or p["cross_repository_write"] is not False):
        raise ValueError("unsafe or unsupported structural HRAiN state")
    if (not _nonnegative_int(h["event_object_count"]) or not _nonnegative_int(h["latest_event_count"]) or
            h["latest_event_count"] > h["event_object_count"]):
        raise ValueError("incoherent archive counts")
    _exact(m["authority"], {"chat_event_is_command", "archive_is_world_truth",
                            "archive_is_scientific_evidence",
                            "archive_grants_external_effect_authority",
                            "archive_grants_repository_write_authority"}, "HRAiN authority")
    if any(type(v) is not bool or v for v in m["authority"].values()):
        raise ValueError("HRAiN mirror cannot confer authority")
    if p["source_repository"] != "Hawkar-usls/janus-meta-registry" or not _sha(p["source_commit"]):
        raise ValueError("invalid structural source pin")
    if len({sources[k]["origin"]["commit"] for k in ("hrain_head", "hrain_manifest", "hrain_provenance")}) != 1:
        raise ValueError("HRAiN source files are not same-commit snapshots")
    i = out["inaihr_state"]
    if i["status"] != "ACTIVE_AUTONOMOUS_CANDIDATE_EVOLUTION":
        raise ValueError("unsupported iNaiHR mode")
    _parse_time(i["generated_at"])
    _exact(i["registry"], {"repository", "source_commit"}, "iNaiHR registry")
    if i["registry"]["repository"] != "Hawkar-usls/janus-meta-registry" or not _sha(i["registry"]["source_commit"]):
        raise ValueError("unbound iNaiHR registry")
    _exact(i["attention"], {"focus_key", "focus_age", "attention_weight_is_evidence_weight",
                            "no_fixed_hypothesis_center"}, "iNaiHR attention")
    if (i["attention"]["attention_weight_is_evidence_weight"] is not False or
            i["attention"]["no_fixed_hypothesis_center"] is not True or
            not isinstance(i["attention"]["focus_key"], str) or
            not 1 <= len(i["attention"]["focus_key"]) <= 100 or
            not _nonnegative_int(i["attention"]["focus_age"])):
        raise ValueError("invalid attention authority")
    if (not _nonnegative_int(i["candidate_count"]) or
            not isinstance(i["recent_candidates"], list) or
            not 1 <= len(i["recent_candidates"]) <= 8 or
            len(i["recent_candidates"]) > i["candidate_count"]):
        raise ValueError("invalid sampled synthesis size")
    seen = set()
    for candidate in i["recent_candidates"]:
        _exact(candidate, {"id", "status", "attention_score", "focus_key", "source_ids",
                           "prior_candidate_id", "independent_replication_established",
                           "authority"}, "iNaiHR candidate")
        if (not isinstance(candidate["id"], str) or not SYNTH_ID.fullmatch(candidate["id"]) or
                candidate["id"] in seen or
                candidate["status"] != "CANDIDATE_AWAITING_CORROBORATION" or
                not isinstance(candidate["focus_key"], str) or
                type(candidate["attention_score"]) not in (int, float) or
                not 0 <= candidate["attention_score"] <= 1000 or
                not isinstance(candidate["source_ids"], list) or
                len(candidate["source_ids"]) != 2 or
                not all(isinstance(v, str) and OBJ_ID.fullmatch(v) for v in candidate["source_ids"]) or
                not isinstance(candidate["prior_candidate_id"], str) or
                not SYNTH_ID.fullmatch(candidate["prior_candidate_id"]) or
                candidate["independent_replication_established"] is not False):
            raise ValueError("candidate cannot become evidence or executable instruction")
        seen.add(candidate["id"])
        _exact(candidate["authority"], {"automatic_promotion", "causal", "mutation", "proof", "truth"},
               "iNaiHR claim authority")
        if any(type(v) is not bool or v for v in candidate["authority"].values()):
            raise ValueError("unsafe candidate authority")
    eye = out["eye_next_tests"]
    if (not isinstance(eye["available_ranked"], list) or
            not isinstance(eye["unavailable_counterfactual_value_ranked"], list) or
            not 1 <= len(eye["available_ranked"]) + len(eye["unavailable_counterfactual_value_ranked"]) <= 16 or
            eye["warning"] != "Unavailable test value is counterfactual planning information only."):
        raise ValueError("unsupported EYE next-test receipt")
    tests_seen = set()
    for available, group in ((True, eye["available_ranked"]),
                             (False, eye["unavailable_counterfactual_value_ranked"])):
        for test in group:
            _exact(test, {"test_id", "available", "gain_per_cost"}, "EYE test")
            if (not isinstance(test["test_id"], str) or not TEST_ID.fullmatch(test["test_id"]) or
                    test["test_id"] in tests_seen or test["available"] is not available or
                    type(test["gain_per_cost"]) not in (int, float) or
                    not 0 <= test["gain_per_cost"] <= 1000):
                raise ValueError("invalid test route or impossible availability")
            tests_seen.add(test["test_id"])
    eye_ind = out["eye_independence"]
    if type(eye_ind["unknown_independence_conflicts"]) is not bool:
        raise ValueError("invalid independence uncertainty")
    if (not _nonnegative_int(eye_ind["pair_count"]) or
            not isinstance(eye_ind["pairs_sample"], list) or
            len(eye_ind["pairs_sample"]) > min(20, eye_ind["pair_count"])):
        raise ValueError("independence excerpt must be bounded")
    for pair in eye_ind["pairs_sample"]:
        _exact(pair, {"a", "b", "independent_under_model", "shared_failure_domains"},
               "under-model pair")
        if (not isinstance(pair["a"], str) or not TEST_ID.fullmatch(pair["a"]) or
                not isinstance(pair["b"], str) or not TEST_ID.fullmatch(pair["b"]) or
                pair["a"] == pair["b"] or type(pair["independent_under_model"]) is not bool or
                not isinstance(pair["shared_failure_domains"], list) or
                len(pair["shared_failure_domains"]) > 8 or
                not all(isinstance(v, str) and len(v) <= 80 for v in pair["shared_failure_domains"])):
            raise ValueError("bad independence pair")
    if sources["eye_next_tests"]["origin"]["commit"] != sources["eye_independence"]["origin"]["commit"]:
        raise ValueError("EYE test and independence data from different source commits")
    return out


def run(pack: dict[str, Any], arm: str = "divergent_r1") -> dict[str, Any]:
    if arm not in ("native_baseline", "divergent_r1"):
        raise ValueError("unknown comparison arm")
    state = validate(pack)
    sources = pack["sources"]
    def source_refs(*keys: str) -> list[dict[str, str]]:
        return [{"organ_file": key, **sources[key]["origin"]} for key in keys]

    def question(kind: str, body: str, refs: list[str], required: str) -> dict:
        return {
            "question_id": "jdm-r1-" + _digest({"kind": kind, "pack": pack["pack_id"]})[:16],
            "kind": kind,
            "question": body,
            "source_refs": source_refs(*refs),
            "required_falsifier": required,
            "epistemic_status": "QUESTION_ONLY__UNVERIFIED",
            "independence_verified": False,
            "claim_promotion": False,
            "effect_authority": False,
        }

    head = state["hrain_head"]
    ini = state["inaihr_state"]
    eye = state["eye_next_tests"]
    independent = state["eye_independence"]
    first = max(eye["available_ranked"], key=lambda x: (x["gain_per_cost"], -int(x["test_id"].split("H")[-1])),
                default=None)
    candidate = max(ini["recent_candidates"], key=lambda x: (x["attention_score"], x["id"]))

    native_questions = [
        question("ARCHIVE_PROVENANCE_CHECK",
                 f"Can the HRAiN archive head ({head['event_object_count']} immutable event objects) be replayed from its pinned origin?",
                 ["hrain_head", "hrain_provenance"], "INDEPENDENT_REPLAY_OF_PINNED_ARCHIVE"),
        question("SEMANTIC_CANDIDATE_REVIEW",
                 f"Which target-local observation would refute iNaiHR candidate {candidate['id']}?",
                 ["inaihr_state"], "TARGET_LOCAL_CORROBORATION_OR_REFUTATION"),
        question("EYE_AVAILABLE_TEST",
                 f"Does EYE's best currently available test {first['test_id'] if first else 'NONE'} distinguish alternatives under independent execution?",
                 ["eye_next_tests"], "DOMAIN_NATIVE_TEST_REPLAY__NOT_EXECUTED"),
        question("EYE_MODEL_INDEPENDENCE",
                 "Do EYE's modeled independent test pairs remain distinct under a real failure-domain audit?",
                 ["eye_independence"], "INDEPENDENT_FAILURE_DOMAIN_AUDIT"),
    ]
    difference = (state["hrain_provenance"]["source_commit"] != ini["registry"]["source_commit"])
    if difference:
        pin_question = question(
            "CROSS_ORGAN_SOURCE_PIN_DRIFT",
            "Why does a recent iNaiHR candidate snapshot cite a different registry source commit than HRAiN's structural mirror? Re-acquire both before treating agreement as fresh.",
            ["hrain_provenance", "inaihr_state"], "MATCHED_REGISTRY_PIN_REPLAY")
    else:
        pin_question = question(
            "CROSS_ORGAN_PIN_ALIGNMENT",
            "The two registry commit labels agree; do their source-file digests and lineage still match?",
            ["hrain_provenance", "inaihr_state"], "INDEPENDENT_FILE_DIGEST_REPLAY")
    r1_questions = [
        pin_question,
        question("MODEL_PAIR_NE_INDEPENDENT_WITNESS",
                 f"EYE models {independent['pair_count']} test pairs but unknown conflicts are {independent['unknown_independence_conflicts']}; can unrelated failure domains be established outside the model?",
                 ["eye_independence", "inaihr_state"], "EXTERNAL_FAILURE_DOMAIN_AUDIT_WITH_BLIND_REPLAY"),
        question("FOCUS_AND_CANDIDATE_COUNT_NE_EVIDENCE",
                 f"Why do {ini['candidate_count']} semantic candidate records and attention focus {ini['attention']['focus_key']} not by themselves prove any claim, even with a synced HRAiN archive?",
                 ["hrain_manifest", "inaihr_state"], "SOURCE_ORIGIN_AND_TARGET_LOCAL_FALSIFICATION"),
        question("UNAVAILABLE_TEST_NE_NEGATIVE_RESULT",
                 "Would a missing EYE test be misreported as a negative result or an available route? Check availability before proposed execution.",
                 ["eye_next_tests", "eye_independence"], "TEST_AVAILABILITY_REPLAY_AND_NEGATIVE_CONTROL"),
    ]
    selected = (native_questions if arm == "native_baseline" else r1_questions)[:MAX_QUESTIONS]
    return {
        "schema": REPORT_SCHEMA,
        "arm": arm,
        "source_pack_id": pack["pack_id"],
        "source_pack_sha256": _digest(pack),
        "capture_kind": CAPTURE_KIND,
        "question_budget": MAX_QUESTIONS,
        "questions": selected,
        "attention_flags": {
            "cross_organ_registry_pin_differs": difference,
            "eye_independence_conflicts_unknown": independent["unknown_independence_conflicts"],
            "inaihr_candidate_count": ini["candidate_count"],
            "sampled_inaihr_candidate_status": "CANDIDATE_AWAITING_CORROBORATION",
            "eye_available_test_count": len(eye["available_ranked"]),
            "eye_unavailable_test_count": len(eye["unavailable_counterfactual_value_ranked"]),
        },
        "guardrails": {
            "runtime_invoked": False,
            "complete_origin_file_hashes_reverified_at_run_time": False,
            "direct_eye_to_inaihr_bypass": False,
            "read_only": True,
            "independent_evaluator_executed": False,
            "scientific_claim_promotion": False,
            "repository_writeback": False,
            "cross_repo_mutation": False,
            "authority_delta": 0,
        },
        "scientific_status": "OPEN__QUESTIONS_ONLY__REQUIRES_INDEPENDENT_VERIFICATION",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline JANUS R1 pinned organ question proposer")
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--arm", default="divergent_r1", choices=["native_baseline", "divergent_r1"])
    args = parser.parse_args()
    report = run(json.loads(args.pack.read_text(encoding="utf-8")), args.arm)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
