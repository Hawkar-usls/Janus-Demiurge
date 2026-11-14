#!/usr/bin/env python3
"""ESSENCE v3.3 proof-carrying research-memory bridge.

The canonical Demiurge spiral and Scout identities are retained across source
changes. Cross-repository GitHub files are untrusted data; no foreign code is
executed, no model trained, no weights updated, and no scientific truth promoted.
Source SHA and Git blob are independently checked against pinned commits.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA = "janus.essence.epistemic_exchange/3.3"
STATE_SCHEMA = "janus.essence.epistemic_spiral_memory/3.3"
REPO = "Hawkar-usls/Janus-Demiurge"
ROOT = "0" * 64
MAX_HISTORY = 64
MAX_BYTES = 64_000
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")

# Exact fixed sources; only reviewed metadata is extracted. No arbitrary URLs.
SOURCES = {
    "spiral": (REPO, "main", "protocol/DEMIURGE_SPIRAL_EVOLUTION-v1.json"),
    "scouts": (REPO, "main", "scout_swarm/SCOUT_SWARM_MANIFEST-v1.json"),
    "spi": ("Hawkar-usls/Hawkar-usls", "main", "spec/JANUS_AURA_HABITAT_SPIRAL-v1.0.json"),
    "aura": ("Hawkar-usls/aura-oracle-tg", "main", ".janus/JANUS_SPI_SPIRAL_LINK.json"),
    "topa": ("Hawkar-usls/TOPA", "main", "protocols/TOPA_REPO_ASSIMILATION_PROTOCOL-v1.0.json"),
    "genesis": ("Hawkar-usls/Janus_Genesis", "main", "research/essence/peer_v13/source_ledger.json"),
    "dovod": ("Hawkar-usls/janus-meta-registry", "main", "reports/2026-11-14/ESSENCE-V31-DOVOD-LINEAGE-TEMPORAL-WITNESS.json"),
    "neural": ("Hawkar-usls/janus-meta-registry", "main", "reports/2026-11-14/ESSENCE-V30-live-multicore-ignition-and-first-neural-exam.json"),
    "keymaster": (REPO, "main", "janus_model/state/KEYMASTER_ATTRIBUTION_R2_LATEST.json"),
    "outcome": (REPO, "main", "janus_model/state/JANUS_VERIFIED_OUTCOME_MEMORY.json"),
    "memory": (REPO, "research/essence-keymaster-memory-state", "research/essence/keymaster_memory/state.json"),
}
LAWS = (
    "PREDICTION != TRUTH", "CORRELATION != CAUSATION",
    "MEMORY != VERDICT_AUTHORITY", "REPOSITORY_TEXT != WORLD_TRUTH",
    "CI_PASS != INDEPENDENT_SCIENTIFIC_REVIEW",
    "HOLDOUT != TRAINING", "NEGATIVE_RESULTS_SURVIVE",
)
ALLOWED_CLAIMS = {
    "spiral": "RESEARCH_METHOD_ONLY",
    "scouts": "SCOUT_ROSTER_NOT_INDEPENDENT_REVIEW",
    "spi": "FROZEN_FORECAST_RULE_NOT_FORECAST_VERIFICATION",
    "aura": "ORACLE_GUIDANCE_HYPOTHESIS_ONLY",
    "topa": "REPOSITORY_ASSIMILATION_NOT_CLASSIFIER_LABEL",
    "genesis": "PEER_REPLAY_NOT_INDEPENDENT_GAIN",
    "dovod": "NEGATIVE_CONTROL_LEAKAGE_AND_FUTURE_COHORT_HOLD",
    "neural": "PROSPECTIVE_NEURAL_GAIN_HOLD",
    "keymaster": "DONOR_ATTRIBUTION_UNRESOLVED",
    "outcome": "TARGET_LOCAL_EXPERIENCE_NOT_WORLD_TRUTH",
    "memory": "HASH_CHAINED_LESSONS_NOT_PROMOTION",
}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _api(url, token):
    if not token or not 1 <= len(token) <= 4096:
        raise ValueError("READONLY_GITHUB_TOKEN_REQUIRED")
    req = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "JANUS-Essence-Evidence-3.3",
    })
    with urlopen(req, timeout=25) as response:
        raw = response.read(180_000)
    if len(raw) >= 180_000:
        raise ValueError("GITHUB_API_RESPONSE_TOO_LARGE")
    return json.loads(raw)


def fetch_snapshot(token, current_main_sha):
    if not SHA40.fullmatch(str(current_main_sha)):
        raise ValueError("DEMIURGE_COMMIT_NOT_PINNED")
    roots, records = {}, {}
    for role, (repo, branch, path) in SOURCES.items():
        name = (repo, branch)
        if name not in roots:
            if repo == REPO and branch == "main":
                roots[name] = current_main_sha
            else:
                ref = quote(branch, safe="")
                meta = _api("https://api.github.com/repos/" + repo + "/commits/" + ref, token)
                sha = meta.get("sha") if isinstance(meta, dict) else None
                if not SHA40.fullmatch(str(sha)):
                    raise ValueError("SOURCE_COMMIT_UNVERIFIED")
                roots[name] = sha
        commit = roots[name]
        url = ("https://api.github.com/repos/" + repo + "/contents/"
               + quote(path, safe="/") + "?ref=" + commit)
        response = _api(url, token)
        if (not isinstance(response, dict)
            or response.get("type") != "file"
            or response.get("encoding") != "base64"):
            raise ValueError("SOURCE_OBJECT_NOT_CONTENTS_BLOB")
        encoded = response.get("content")
        if not isinstance(encoded, str) or len(encoded) > MAX_BYTES * 2:
            raise ValueError("SOURCE_CONTENT_UNBOUNDED")
        try:
            raw = base64.b64decode(encoded, validate=False)
        except Exception as exc:
            raise ValueError("SOURCE_BASE64_INVALID") from exc
        if not 2 <= len(raw) <= MAX_BYTES:
            raise ValueError("SOURCE_BYTES_UNBOUNDED")
        if response.get("sha") != git_blob(raw):
            raise ValueError("SOURCE_GIT_BLOB_MISMATCH")
        try:
            doc = json.loads(raw.decode("utf-8"),
                             parse_constant=lambda _: (_ for _ in ()).throw(
                                 ValueError("SOURCE_NONFINITE_JSON")))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("SOURCE_JSON_INVALID") from exc
        records[role] = {
            "repository": repo, "path": path, "source_commit": commit,
            "source_blob_sha1": response["sha"],
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "canonical_sha256": seal(doc), "payload": doc,
        }
    return records


def require(condition, code):
    if not condition:
        raise ValueError(code)


def check_sources(records):
    require(isinstance(records, dict) and set(records) == set(SOURCES),
            "EVIDENCE_ROSTER_INCOMPLETE")
    payload = {}
    refs = {}
    for role, (repo, branch, path) in SOURCES.items():
        row = records[role]
        require(isinstance(row, dict) and row.get("repository") == repo
                and row.get("path") == path
                and SHA40.fullmatch(str(row.get("source_commit", "")))
                and SHA40.fullmatch(str(row.get("source_blob_sha1", "")))
                and SHA64.fullmatch(str(row.get("source_sha256", "")))
                and SHA64.fullmatch(str(row.get("canonical_sha256", ""))),
                "UNPINNED_SOURCE_PROVENANCE")
        p = row.get("payload")
        require(isinstance(p, dict), "INVALID_SOURCE_PAYLOAD")
        # Test fixtures and GitHub live responses share this byte/content seal.
        raw = canonical(p)
        require(row.get("canonical_sha256") == seal(p),
                "SOURCE_CANONICAL_DIGEST_MISMATCH")
        require(len(raw) <= MAX_BYTES, "SOURCE_CANONICAL_SIZE_EXCEEDED")
        payload[role] = p
        refs[role] = {
            "repository": repo, "path": path,
            "source_commit": row["source_commit"],
            "source_sha256": row["source_sha256"],
            "canonical_sha256": row["canonical_sha256"],
            "source_blob_sha1": row["source_blob_sha1"],
            "claim_ceiling": ALLOWED_CLAIMS[role],
        }
    # The remote raw bytes may have whitespace: canonical hash is a separate
    # assertion; the original git object is checked at fetch_snapshot().
    spiral = payload["spiral"]
    require(spiral.get("schema") == "janus.demiurge.spiral_evolution.protocol.v1"
            and spiral.get("status") == "CANONICAL"
            and "NO_LEARNING_ENTITY_DELETION" in spiral.get("laws", [])
            and "FAILURE_BECOMES_LESSON" in spiral.get("laws", [])
            and "EXACT_REPEAT_WITHOUT_NEW_INFORMATION_IS_NO_ASCENT" in spiral.get("laws", [])
            and spiral.get("admission", {}).get("INTEGRATED_LESSON") is not None,
            "SPIRAL_INHERITANCE_CONTRACT_HOLD")
    scouts = payload["scouts"]
    roster = scouts.get("agents")
    require(scouts.get("schema") == "janus.demiurge.scout_swarm.manifest.v2.spiral.strict_science"
            and scouts.get("agent_count") == 17
            and isinstance(roster, list) and len(roster) == 17
            and len({r.get("id") for r in roster if isinstance(r, dict)}) == 17
            and all(isinstance(r, dict) and isinstance(r.get("id"), str)
                    and r["id"].startswith("SCOUT_")
                    and r.get("target_repo", "").startswith("Hawkar-usls/")
                    for r in roster)
            and "PREVIOUS_SCOUT_REPORT_IS_MEMORY_NOT_EVIDENCE" in scouts.get("invariants", [])
            and "FAILED_RUNS_AND_NEGATIVE_RESULTS_MUST_SURVIVE" in scouts.get("invariants", []),
            "SCOUT_INHERITED_IDENTITY_CONTRACT_HOLD")
    spi = payload["spi"]
    require(spi.get("schema_id") == "janus.aura_spi.habitat_spiral.v1"
            and spi.get("spi_contract", {}).get("semantic_synthesis_is_evidence") is False
            and "MEMORY != VERDICT_AUTHORITY" in spi.get("scientific_firewall", [])
            and spi.get("generation_semantics", {}).get("origin_prime_requires") == "VERIFIED_RETURN",
            "SPI_FORECAST_AND_VERDICT_BOUNDARY_HOLD")
    aura = payload["aura"]
    require(aura.get("schema") == "janus.aura_spi.repository_link.v2"
            and aura.get("prediction_authority") is False
            and aura.get("scientific_evidence_authority") is False
            and aura.get("may_resolve_own_forecast") is False
            and aura.get("write_back_default") == "DENY",
            "AURA_ORACLE_AUTHORITY_HOLD")
    topa = payload["topa"]
    require(topa.get("schema") == "hawkar.topa.repo_assimilation_protocol.v1"
            and "NEGATIVE_RESULTS_AND_FAILED_RUNS_REMAIN_SEARCHABLE" in topa.get("core_rules", [])
            and "REPO_TEXT_TO_ARTIFACT_LABEL" in topa.get("forbidden_automatic_promotions", [])
            and topa.get("required_receipt_boundaries", {}).get("repository_corpus_is_supervised_artifact_truth") is False,
            "TOPA_LABEL_CONTAMINATION_HOLD")
    genesis = payload["genesis"]
    gp = genesis.get("policy") or {}
    require(genesis.get("schema") == "janus.essence.github_peer_lineage/1.3"
            and genesis.get("benchmarks_not_independently_blinded") is True
            and isinstance(genesis.get("peers"), list)
            and len(genesis["peers"]) == 6
            and gp.get("automatic_code_import") is False
            and gp.get("automatic_merge") is False
            and gp.get("independent_new_gain_proven") is False,
            "GENESIS_PEER_AUTHORITY_HOLD")
    dovod = payload["dovod"]
    negative = (dovod.get("experiment_lineage") or {}).get("negative_control") or {}
    require(dovod.get("status") == "DOVOD_TEMPORAL_WITNESS_LIVE_PASS_HOLD_INSUFFICIENT_FUTURE_COHORT"
            and negative.get("identical_train_test_sequences") == 25
            and negative.get("test_sequences") == 50
            and (dovod.get("provenance_and_admission") or {}).get("independent_neural_improvement_proven") is False,
            "DOVOD_NEGATIVE_CONTROL_LOST")
    neural = payload["neural"].get("first_real_prospective_neural_exam") or {}
    require(neural.get("verdict") == "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"
            and neural.get("accepted_generations") == 0
            and neural.get("independent_future_advantage_proven") is False
            and neural.get("no_auto_production_weight_change") is True,
            "NEURAL_UNPROVEN_GAIN_MUST_REMAIN_HOLD")
    km = payload["keymaster"]
    require(km.get("schema") == "janus.keymaster.attribution_r2_summary.v1"
            and km.get("status") == "REPLICATED_EVIDENCE_READY"
            and isinstance(km.get("attribution"), list)
            and len(km["attribution"]) == 8
            and all(r.get("class") == "UNRESOLVED" for r in km["attribution"])
            and km.get("claim_ceiling", {}).get("authority_delta") == 0
            and km.get("claim_ceiling", {}).get("automatic_weighting_change") is False,
            "KEYMASTER_UNRESOLVED_NEEDS_REVIEW")
    outcome = payload["outcome"]
    require(outcome.get("schema") == "janus.verified_outcome_memory.v1"
            and outcome.get("policy", {}).get("feedback_grants_mutation_authority") is False
            and outcome.get("policy", {}).get("target_local_reverification_still_required") is True,
            "OUTCOME_MEMORY_AUTHORITY_HOLD")
    # Reuse the existing *real* memory guardian; not the hardware legacy files.
    from tools.essence_v32_keymaster_memory import verify_state, check_outcomes
    verify_state(payload["memory"])
    lessons = check_outcomes(outcome)
    require(payload["memory"].get("operational_authority") is False,
            "MEMORY_WITNESS_HAS_NO_OPERATIONAL_AUTHORITY")
    return refs, {
        "roster_ids": sorted(x["id"] for x in roster),
        "negative_evidence": [
            {"id": "DOVOD_SHA_25_OF_50_TEST_LEAKAGE", "status": "NEGATIVE_CONTROL_CONTAMINATED"},
            {"id": "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114",
             "status": "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"},
            {"id": "KEYMASTER_R2_REPLICATED_ABLATIONS",
             "status": "UNRESOLVED_EIGHT_CONTRIBUTORS"},
        ],
        "local_verified_lesson_count": len(lessons),
        "peer_count": len(genesis["peers"]),
    }


def empty_state():
    body = {
        "schema": STATE_SCHEMA, "repository": REPO, "history": [],
        "production_authority": False,
    }
    return dict(body, state_sha256=seal(body))


def verify_state(state):
    require(isinstance(state, dict)
            and state.get("schema") == STATE_SCHEMA
            and state.get("repository") == REPO
            and state.get("production_authority") is False
            and state.get("state_sha256") == seal({
                k: v for k, v in state.items() if k != "state_sha256"}),
            "EVIDENCE_STATE_HASH_OR_SCHEMA")
    history = state.get("history")
    require(isinstance(history, list) and len(history) <= MAX_HISTORY,
            "EVIDENCE_HISTORY_LIMIT")
    last = ROOT
    ids = set()
    prev_turn = 0
    initial_scouts = None
    for item in history:
        require(isinstance(item, dict) and item.get("previous_sha256") == last
                and type(item.get("turn")) is int and item["turn"] == prev_turn + 1
                and item.get("receipt_sha256") == seal({
                    k: v for k, v in item.items() if k != "receipt_sha256"})
                and SHA64.fullmatch(str(item.get("source_fingerprint_sha256", "")))
                and item["source_fingerprint_sha256"] not in ids
                and item.get("decision") == "INTEGRATED_LESSON_NOT_ASCENDED"
                and item.get("production_authority") is False,
                "EVIDENCE_SPIRAL_CHAIN_BROKEN")
        require(len(item.get("scout_identities", [])) == 17
                and isinstance(item.get("negative_evidence"), list)
                and len(item["negative_evidence"]) >= 3,
                "EVIDENCE_HISTORY_LOSS")
        current_scouts = item["scout_identities"]
        require(isinstance(current_scouts, list)
                and len(set(current_scouts)) == 17
                and all(isinstance(x, str) and x.startswith("SCOUT_")
                        for x in current_scouts),
                "EVIDENCE_SCOUT_IDENTITY_INVALID")
        if initial_scouts is None:
            initial_scouts = current_scouts
        else:
            require(current_scouts == initial_scouts,
                    "EVIDENCE_SCOUT_LINEAGE_REPLACED")
        ids.add(item["source_fingerprint_sha256"])
        last = item["receipt_sha256"]
        prev_turn = item["turn"]
    return last


def integrate(records, previous):
    refs, facts = check_sources(records)
    tail = verify_state(previous)
    # Commits advance for unrelated code changes. A new commit pointing to
    # identical verified JSON blob bytes is NOT a new source/lesson turn.
    # Keep commit hashes in the receipt for traceability, not in novelty ID.
    fingerprint = seal({role: {
        "repository": row["repository"], "path": row["path"],
        "source_sha256": row["source_sha256"]}
        for role, row in sorted(refs.items())})
    if previous["history"]:
        require(previous["history"][-1]["scout_identities"] == facts["roster_ids"],
                "EVIDENCE_SCOUT_LINEAGE_REPLACED")
    already = {x["source_fingerprint_sha256"] for x in previous["history"]}
    new_information = fingerprint not in already
    require(not (new_information and len(previous["history"]) >= MAX_HISTORY),
            "EVIDENCE_SPIRAL_ARCHIVE_REQUIRED")
    state = {k: v for k, v in previous.items() if k != "state_sha256"}
    if new_information:
        turn = len(state["history"]) + 1
        item = {
            "turn": turn, "entity": "JANUS_ESSENCE_EPISTEMIC_EXCHANGE",
            "previous_sha256": tail, "source_fingerprint_sha256": fingerprint,
            "scout_identities": facts["roster_ids"],
            "negative_evidence": facts["negative_evidence"],
            "constraints_inherited": list(LAWS),
            "decision": "INTEGRATED_LESSON_NOT_ASCENDED",
            "production_authority": False,
        }
        item["receipt_sha256"] = seal(item)
        state["history"] = list(state["history"]) + [item]
    state["state_sha256"] = seal(state)
    verify_state(state)
    report = {
        "schema": SCHEMA,
        "status": "INTEGRATED_LESSON_NO_PROMOTION" if new_information else "NO_ASCENT_NO_NEW_INFORMATION",
        "canonical_spiral": "ENTITY_n+EXPERIENCE_n+FAILED_ATTEMPTS_n+CONSTRAINTS_n->INTEGRATE->ENTITY_n+1",
        "source_fingerprint_sha256": fingerprint,
        "source_references": refs, "cross_repo_evidence_policies": list(LAWS),
        "scout_identity_count": len(facts["roster_ids"]),
        "historical_negative_results": facts["negative_evidence"],
        "keymaster_verified_local_lessons": facts["local_verified_lesson_count"],
        "genesis_peer_count": facts["peer_count"],
        "memory_state_sha256": state["state_sha256"],
        "memory_turn": len(state["history"]),
        "memory_changed": new_information,
        "forecast_resolved": False, "independent_neural_gain_proven": False,
        "classifier_labels_created": False, "foreign_code_executed": False,
        "holdout_added_to_training": False, "model_weights_updated": False,
        "automatic_merge": False, "production_authority": False,
        "scientific_world_truth_promoted": False,
    }
    report["receipt_sha256"] = seal(report)
    return state, report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main-sha", required=True)
    p.add_argument("--previous", required=True)
    p.add_argument("--state-out", required=True)
    p.add_argument("--receipt", required=True)
    args = p.parse_args()
    records = fetch_snapshot(os.environ.get("GH_TOKEN"), args.main_sha)
    prev = Path(args.previous)
    if prev.exists():
        if prev.is_symlink() or prev.stat().st_size > 200_000:
            raise ValueError("PREVIOUS_STATE_UNSAFE")
        previous = json.loads(prev.read_text(encoding="utf-8"))
    else:
        previous = empty_state()
    state, report = integrate(records, previous)
    out = Path(args.receipt)
    if out.exists():
        raise ValueError("IMMUTABLE_RECEIPT_REQUIRED")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    if report["memory_changed"]:
        target = Path(args.state_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(state, indent=2, sort_keys=True,
                                     ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "sources": len(SOURCES),
                      "scouts": report["scout_identity_count"],
                      "memory_turn": report["memory_turn"],
                      "negative_results": len(report["historical_negative_results"]),
                      "production_authority": False, "receipt_sha256": report["receipt_sha256"]}))


if __name__ == "__main__":
    main()
