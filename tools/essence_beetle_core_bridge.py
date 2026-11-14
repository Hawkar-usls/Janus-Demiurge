#!/usr/bin/env python3
"""ESSENCE v2.9 -> Universal Beetle: provenance-bound research steering organ.

Reads only explicit public GitHub source files from four ESSENCE core repos,
the frozen neural research state and Beetle's own direction contract.
It NEVER grants evidence, learning, training, code execution, Git write,
network-wide discovery, or production authority. Input data are NOT prompts.
The downstream Demiurge director must independently validate this receipt.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA = "janus.essence.beetle_core_bridge/2.9"
REPO_PREFIX = "Hawkar-usls/"
MAX_BYTES = 600_000
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
SOURCES = (
    ("genesis", "Janus_Genesis", "main",
     "research/essence/module_organogenesis_v13/generation_0002.json",
     "janus.essence.module_governor/1.3"),
    ("demiurge", "Janus-Demiurge", "main",
     "rex/candidates/rex_lifecycle_heartbeat_ledger_health/fitness.json",
     "janus.rex.module_functional_gain/2.4"),
    ("swarm", "janus-distributed-ai-swarm", "main",
     "research/essence/peer_v13/source_ledger.json",
     "janus.essence.github_peer_lineage/1.3"),
    ("demi_head", "Demi_Head", "main",
     "research/essence/peer_v13/source_ledger.json",
     "janus.essence.github_peer_lineage/1.3"),
    ("neural", "Janus-Demiurge", "research/essence-neural-state",
     "research/essence/neural_duration/state.json",
     "janus.essence.github_future_weights/2.6"),
    ("beetle", "janus-lapis", "main",
     "data/beetle/directions.json", None),
)
MAX_AD_HOC = 2
# Only deterministic source categories -> approved research topics.
QUESTIONS = (
    {
        "id": "essence_independent_core_tests",
        "title": "Independent tests of inherited JANUS microkernels",
        "keywords": [
            "modular neural evolution", "independent benchmark",
            "software agent reliability", "formal counterexample",
            "multi agent verification", "unseen tasks",
        ],
        "target_repositories": [
            "Hawkar-usls/Janus_Genesis",
            "Hawkar-usls/janus-distributed-ai-swarm",
            "Hawkar-usls/Demi_Head",
        ],
        "priority": 82,
    },
    {
        "id": "essence_prospective_weight_gain",
        "title": "Prospective neural model generalization controls",
        "keywords": [
            "prospective validation", "time series concept drift",
            "grouped cross validation", "neural weight adaptation",
            "holdout contamination", "model rollback",
        ],
        "target_repositories": [
            "Hawkar-usls/janus-meta-registry",
            "Hawkar-usls/Janus_Genesis",
            "Hawkar-usls/janus-distributed-ai-swarm",
        ],
        "priority": 78,
    },
)

def canon(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def sha(data: object) -> str:
    return hashlib.sha256(canon(data)).hexdigest()

def safe_object(raw: bytes, expected: str | None, source: str) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("CORE_SOURCE_OVERSIZE")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("CORE_SOURCE_NOT_JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("CORE_SOURCE_NOT_OBJECT")
    if expected and obj.get("schema") != expected:
        raise ValueError("CORE_SCHEMA_MISMATCH:" + source)
    if obj.get("production_authority") is True:
        raise ValueError("CORE_PRODUCTION_AUTHORITY_NOT_ACCEPTED")
    return obj

def classify(role: str, obj: dict) -> dict:
    """Never copy untrusted key values, instructions, labels or model weights."""
    if role == "genesis":
        if obj.get("repository") != "Hawkar-usls/Janus_Genesis":
            raise ValueError("GENESIS_REPOSITORY_UNBOUND")
        return {"research_generation": min(10, max(0, int(obj.get("research_generation", 0)))),
                "status": "HOLD" if str(obj.get("research_status", "")).startswith("HOLD_") else "RESEARCH_ONLY"}
    if role in ("swarm", "demi_head"):
        rows = obj.get("peers")
        if not isinstance(rows, list) or len(rows) > 20:
            raise ValueError("PEER_LEDGER_UNTRUSTED")
        repo = "Hawkar-usls/janus-distributed-ai-swarm" if role == "swarm" else "Hawkar-usls/Demi_Head"
        if not any(isinstance(row, dict) and row.get("repository") == repo for row in rows):
            raise ValueError("PEER_SELF_MISSING")
        return {"peer_count": len(rows), "status": "PEER_RESEARCH_ONLY"}
    if role == "demiurge":
        if obj.get("candidate_module") != "rex_lifecycle_heartbeat_ledger_health":
            raise ValueError("DEMIURGE_ORGAN_ID_UNBOUND")
        return {"functional_gain": obj.get("new_functional_capability_proven") is True,
                "status": "RETROSPECTIVE_RESEARCH_ONLY"}
    if role == "neural":
        if (type(obj.get("generation")) is not int or
            not 0 <= obj["generation"] <= 4 or
            obj.get("research_only") is not True or
            obj.get("production_authority") is not False or
            obj.get("state_sha256") != sha({k:v for k,v in obj.items() if k != "state_sha256"})):
            raise ValueError("NEURAL_STATE_NOT_SEALED")
        hist = obj.get("history")
        if not isinstance(hist, list) or len(hist) > 24:
            raise ValueError("NEURAL_HISTORY_UNTRUSTED")
        return {"accepted_generations": obj["generation"],
                "pending_future_exam": isinstance(obj.get("pending"), dict),
                "status": "PROSPECTIVE_PROOF_PENDING" if obj["generation"] == 0 else "RESEARCH_ONLY"}
    if role == "beetle":
        if not isinstance(obj.get("directions"), list) or not obj["directions"]:
            raise ValueError("BEETLE_DIRECTION_CONTRACT_MISSING")
        return {"status": "BEETLE_SEARCH_CONTRACT_PRESENT"}
    raise ValueError("UNKNOWN_CORE_ROLE")

def git_blob(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()

def validate_source(role: str, repo: str, ref: str, path: str,
                    schema: str | None, commit: str, blob: str, raw: bytes) -> dict:
    if not SHA40.fullmatch(commit) or not SHA40.fullmatch(blob):
        raise ValueError("CORE_SOURCE_UNPINNED")
    if git_blob(raw) != blob:
        raise ValueError("CORE_GIT_BLOB_MISMATCH")
    obj = safe_object(raw, schema, role)
    summary = classify(role, obj)
    return {
        "role": role, "repository": REPO_PREFIX+repo, "ref": ref,
        "path": path, "commit_sha": commit, "git_blob_sha1": blob,
        "json_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": summary,
        "scientific_evidence": False,
        "production_authority": False,
    }

def build(evidence: list[dict], *, eligible_roles: set[str] | None = None) -> dict:
    roles = {item["role"] for item in evidence}
    valid = (roles == {x[0] for x in SOURCES})
    if eligible_roles is not None:
        valid = valid and roles == eligible_roles
    if len(evidence) != len(SOURCES):
        valid = False
    state = "CORE_LINKED_SEARCH_STEERING_ONLY" if valid else "HOLD_INCOMPLETE_CORE_SOURCES"
    # Sorted, deterministic and repeatable, no timestamps or fabricated hits.
    receipt = {
        "schema": SCHEMA,
        "status": state,
        "sources": sorted(evidence, key=lambda x: x["role"]),
        "source_count": len(evidence),
        "search_questions": [dict(x) for x in QUESTIONS] if valid else [],
        "beetle_receiver": "Hawkar-usls/janus-lapis::Universal Beetle",
        "transport": "DEMIURGE_LIVE_PRIORITIES_READ_BY_LAPIS",
        "science_claim": "RESEARCH_STEERING_NOT_INDEPENDENT_EVIDENCE",
        "producer_can_modify_model_weights": False,
        "producer_can_write_other_repositories": False,
        "automatic_production_promotion": False,
        "authority_delta": 0,
    }
    receipt["receipt_sha256"] = sha(receipt)
    return receipt

def github_json(endpoint: str, token: str) -> dict:
    if not token or len(token) > 4096:
        raise ValueError("GITHUB_TOKEN_REQUIRED")
    request = Request(
        "https://api.github.com/" + endpoint,
        headers={"Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "JANUS-ESSENCE-Beetle-Bridge/2.9",
                 "Authorization": "Bearer " + token})
    with urlopen(request, timeout=20) as stream:
        raw = stream.read(MAX_BYTES * 2 + 1)
    if len(raw) > MAX_BYTES * 2:
        raise ValueError("GITHUB_RESPONSE_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("GITHUB_RESPONSE_NOT_OBJECT")
    return obj

def online(token: str) -> dict:
    sources = []
    for role, repo, ref, path, schema in SOURCES:
        pinned = github_json("repos/" + REPO_PREFIX + repo + "/commits/" + quote(ref, safe="/"), token)
        commit = pinned.get("sha")
        if not isinstance(commit, str) or not SHA40.fullmatch(commit):
            raise ValueError("MISSING_CORE_COMMIT:" + role)
        item = github_json("repos/" + REPO_PREFIX + repo + "/contents/" +
                           quote(path, safe="/") + "?ref=" + commit, token)
        if item.get("type") != "file" or item.get("encoding") != "base64":
            raise ValueError("CORE_CONTENT_TYPE_REJECTED:" + role)
        encoded = item.get("content")
        if not isinstance(encoded, str) or len(encoded) > MAX_BYTES * 2:
            raise ValueError("CORE_CONTENT_INVALID:" + role)
        try:
            raw = base64.b64decode(encoded, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("CORE_BASE64_INVALID") from exc
        sources.append(validate_source(role, repo, ref, path, schema,
                                       commit, item.get("sha"), raw))
    return build(sources)

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    doc = online(os.environ.get("GH_TOKEN", ""))
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if not dest.exists() or dest.read_text() != raw:
        dest.write_text(raw)
    print(json.dumps({"status": doc["status"], "sources": doc["source_count"],
                      "search_questions": len(doc["search_questions"]),
                      "authority_delta": 0}, sort_keys=True))

if __name__ == "__main__":
    main()
