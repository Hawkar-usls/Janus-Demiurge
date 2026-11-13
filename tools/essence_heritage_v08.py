#!/usr/bin/env python3
"""ESSENCE v0.8: LIVE *read-only* heritage operators over dated evidence.

Executes three audited modern, dependency-free operators:
  Trinity: three independent *roles*, synthesis, safety critic/veto.
  Slime: bounded utility-EMA metadata (never touches model weights).
  Spiral: append-only failure memory, preserving unsuccessful attempts.
Also validates historical source IDs, R0 13-role inheritance, present 6-role
root, v0.4 public donor snapshot, and real negative R2 evidence.
NO loading archived models, network, dynamic import, auto-write, or promotion.
Network is confined to a separate read-only public snapshot collector.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import re

from models.trinity.trinity_core import TrinityCouncil, TemporalTrinityCouncil
from models.slime.slime_quantization_kernel import SlimeQuantizationKernel
from spiral_evolution import SpiralLedger
from tools.essence_fitness_ledger_v06 import historical_r2

CATALOG_SCHEMA = "janus.essence.heritage_sources/0.8"
REPORT_SCHEMA = "janus.essence.heritage_research_report/0.8"
SNAPSHOT_SCHEMA = "janus.essence.collective_seed/0.4"
R0 = ("identity", "sensing", "memory", "planning", "verification", "recovery",
      "learning", "evolution", "routing", "resource", "governance",
      "transport", "coding")
BASE = ("sensing", "memory", "planning", "verification", "recovery", "coding")
ROUTING = {
    "identity": "memory", "learning": "memory", "evolution": "planning",
    "routing": "planning", "resource": "recovery",
    "governance": "verification", "transport": "sensing",
}
ALLOWED = frozenset(("modern_local_executable", "local_archive_metadata_only",
                     "cross_repo_reference_only"))
LOCAL_EXEC = {
    "TRINITY_TEMPORAL_COUNCIL", "SLIME_TRACE_QUANTIZATION",
    "SPIRAL_FAILURE_MEMORY",
}
ZERO = "0" * 64
MAX_BYTES = 1_000_000
MAX_SOURCES = 32
MAX_CANDIDATES = 32
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REPO = re.compile(r"^Hawkar-usls/[A-Za-z0-9_.-]{1,90}$")

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def load(path):
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValueError("INPUT_BYTES_EXCEEDED")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_INPUT")))

def valid_path(path):
    if (not isinstance(path, str) or not path or len(path) > 170
        or path.startswith("/") or "\\" in path
        or any(part in ("", ".", "..") for part in path.split("/"))):
        raise ValueError("UNSAFE_HERITAGE_PATH")
    return path

def validate_catalog(catalog, root):
    if not isinstance(catalog, dict) or catalog.get("schema") != CATALOG_SCHEMA:
        raise ValueError("INVALID_SOURCE_CATALOG")
    if tuple(catalog.get("canonical_13_roles", ())) != R0:
        raise ValueError("LEGACY_R0_ROLE_LOSS")
    if tuple(catalog.get("six_base_roles", ())) != BASE:
        raise ValueError("PARENT_SIX_ROLE_LOSS")
    if (catalog.get("runtime_mode") != "ISOLATED_READ_ONLY_RESEARCH"
        or catalog.get("scientific_status") != "NOT_PROVEN_AUTONOMOUS_IMPROVEMENT"):
        raise ValueError("CATALOG_AUTHORITY_UNSAFE")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not 13 <= len(entries) <= MAX_SOURCES:
        raise ValueError("INCOMPLETE_OR_OVERSIZED_LEGACY")
    seen, roles, verified = set(), set(), []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "id", "repository", "path", "git_blob_sha1", "role", "mechanic",
            "admission", "independent_performance_gain", "production_authority",
        }:
            raise ValueError("LEGACY_SOURCE_SHAPE")
        ident, repo, path = entry["id"], entry["repository"], valid_path(entry["path"])
        if (not isinstance(ident, str) or not re.fullmatch(r"[A-Z0-9_]{4,64}", ident)
            or ident in seen or not isinstance(repo, str) or not REPO.fullmatch(repo)
            or not isinstance(entry["git_blob_sha1"], str)
            or not SHA1.fullmatch(entry["git_blob_sha1"])
            or entry["role"] not in R0 or entry["admission"] not in ALLOWED
            or not isinstance(entry["mechanic"], str)
            or not 12 <= len(entry["mechanic"]) <= 180
            or entry["independent_performance_gain"] != "NOT_ESTABLISHED"
            or entry["production_authority"] is not False):
            raise ValueError("UNVERIFIED_OR_UNSAFE_GENE")
        if entry["admission"] == "modern_local_executable":
            if ident not in LOCAL_EXEC or repo != "Hawkar-usls/Janus-Demiurge":
                raise ValueError("EXECUTABLE_LEGACY_UNREVIEWED")
        seen.add(ident)
        roles.add(entry["role"])
        if repo == "Hawkar-usls/Janus-Demiurge":
            local = Path(root) / path
            if not local.is_file() or local.stat().st_size > MAX_BYTES:
                raise ValueError("MISSING_LOCAL_HERITAGE_SOURCE")
            if git_blob(local.read_bytes()) != entry["git_blob_sha1"]:
                raise ValueError("LOCAL_HERITAGE_SHA_MISMATCH:" + ident)
            verified.append(ident)
    if roles != set(R0) or seen.intersection(LOCAL_EXEC) != LOCAL_EXEC:
        raise ValueError("INCOMPLETE_13_ROLES_OR_EXECUTABLES")
    return sorted(verified)

def validate_root(manifest, repo="Hawkar-usls/Janus-Demiurge"):
    if (not isinstance(manifest, dict)
        or manifest.get("schema") != "janus.essence.microkernel/0.1"
        or manifest.get("repository") != repo
        or manifest.get("enabled") is not False
        or manifest.get("activation") != "EXPLICIT_READONLY_TEST_ONLY"
        or any(manifest.get("capabilities", {}).values())):
        raise ValueError("ROOT_AUTHORITY_DENIED")
    cells = manifest.get("microkernels")
    if (not isinstance(cells, list) or len(cells) != 6
        or set(x["role"] for x in cells) != set(BASE)):
        raise ValueError("ROOT_SIX_MICROCORES_REQUIRED")
    return True

def validate_snapshot(snapshot):
    if (not isinstance(snapshot, dict)
        or snapshot.get("schema") != SNAPSHOT_SCHEMA
        or snapshot.get("source") != "PUBLIC_REPO_DEFAULT_BRANCH_MANIFESTS"
        or snapshot.get("snapshot_sha256") != digest({
            k: v for k, v in snapshot.items() if k != "snapshot_sha256"})):
        raise ValueError("DONOR_SNAPSHOT_UNVERIFIED")
    donors = snapshot.get("donors")
    if (not isinstance(donors, list) or not 3 <= len(donors) <= 100
        or snapshot.get("verified_donor_count") != len(donors)
        or len({x["repo"] for x in donors}) != len(donors)
        or any(x.get("kernel_sha256") != snapshot.get("canonical_kernel_sha256")
               for x in donors)
        or set(snapshot.get("genes_by_role", {})) != set(BASE)
        or snapshot.get("automatic_replication_enabled") is not False
        or snapshot.get("source_code_and_weights_transplanted") is not False):
        raise ValueError("UNSAFE_DONOR_SNAPSHOT")
    innovations = snapshot.get("innovation_candidates")
    if not isinstance(innovations, list) or len(innovations) > MAX_CANDIDATES:
        raise ValueError("UNBOUNDED_DONOR_IDEAS")
    unique = set()
    for idea in innovations:
        if not isinstance(idea, dict) or not REPO.fullmatch(idea.get("repo", "")):
            raise ValueError("INVALID_REMOTE_IDEA")
        ident = (idea["repo"], idea.get("id"))
        if (ident in unique or idea["role"] not in BASE
            or idea.get("status") != "IDEA_NOT_PERFORMANCE_PROOF"
            or any(not isinstance(idea.get(k), str) or
                   not SHA256.fullmatch(idea[k])
                   for k in ("evidence_sha256", "precommit_sha256",
                             "origin_receipt_sha256"))):
            raise ValueError("BAD_IDEA_IDENTITY_OR_PROOF")
        unique.add(ident)
    return True

async def triadic_review(negative_evidence, candidates):
    async def runner(role, _):
        if role == "strategist_logic":
            return "HOLD_NEGATIVE_R2" if negative_evidence else "UNPROVEN_GAIN"
        if role == "seer_alternative":
            return "PRESERVE_RARE_IDEAS:" + str(len(candidates))
        if role == "doer_action":
            return "RESEARCH_ARTIFACTS_ONLY_NO_EXECUTION"
        raise ValueError("UNKNOWN_TRINITY_ROLE")

    async def synth(_, views):
        return "|".join(views[key] for key in ("father", "son", "spirit"))

    async def critic(_, proposal):
        if "RESEARCH_ARTIFACTS_ONLY_NO_EXECUTION" not in proposal:
            return False, "VETO_EXECUTION_RIGHTS"
        if negative_evidence or any(x["fitness_gate"] != "NOT_MEASURED"
                                    for x in candidates):
            return False, "VETO_NO_INDEPENDENT_POSITIVE_GAIN"
        return False, "VETO_UNAUTHENTICATED_PUBLIC_DONOR_IDEAS"

    council = TrinityCouncil(runner, synth, critic)
    return (await council.consult("HERITAGE_ESSENCE_V08")).receipt()

def run(catalog, manifest, snapshot, real_r2, *, root):
    verified = validate_catalog(catalog, root)
    validate_root(manifest)
    validate_snapshot(snapshot)
    evidence = historical_r2(real_r2)
    if evidence["source_repository"] != "Hawkar-usls/Janus-Demiurge":
        raise ValueError("R2_WRONG_HISTORICAL_ORIGIN")
    if evidence["relative_gain"] >= 0 or evidence["research_gate"] != "HOLD_NO_INDEPENDENT_GAIN":
        raise ValueError("R2_NEGATIVE_CONTROL_CHANGED")
    candidates = []
    for idea in snapshot["innovation_candidates"]:
        candidates.append({
            "repository": idea["repo"], "id": idea["id"], "role": idea["role"],
            "origin_receipt_sha256": idea["origin_receipt_sha256"],
            "source_ideas_sha256": idea["source_ideas_sha256"],
            "fitness_gate": "NOT_MEASURED",
            "authorization": "CATALOG_REVIEW_ONLY",
        })
    # Exact modern Trinity method, not an approximation of its neural system.
    council = asyncio.run(triadic_review(True, candidates))
    if council["accepted"] or not str(council["final"]).startswith("VETO_"):
        raise ValueError("TRINITY_SAFETY_VETO_MISSING")
    # Existing temporal 2-of-3 operator is an advisory policy shadow,
    # NOT physical future prediction or an independent verifier.
    risk = {"past": (1.0, -1.0), "present": (1.0, -1.0),
            "future": (1.0, -1.0)}
    temporal = TemporalTrinityCouncil.decide(risk).receipt()
    if temporal["consensus"] != "stabilize":
        raise ValueError("TEMPORAL_RESEARCH_GUARD_FAILED")
    # Numeric importance trace derived ONLY from the completed failed trial.
    # It is not a neuron, trained tensor, or model-quality estimate.
    trace = SlimeQuantizationKernel().update_trace(0.5, 1.0)
    if not math.isfinite(trace) or not 0 <= trace <= 1:
        raise ValueError("TRACE_BOUND_FAILED")
    # The canonical SpiralLedger records the failure as a new immutable turn.
    memory = SpiralLedger("ESSENCE_HERITAGE_RESEARCH")
    base = {"phase": "BASELINE_FROZEN", "authority": False}
    memory.ascend(state_before=None, candidate_state=base,
                  active_state_after=base, promoted=False,
                  lessons=["CANONICAL_13_ROLE_LINEAGE_IMPORTED_AS_REFERENCES"])
    failed = {"phase": "R2_FAILED_TO_IMPROVE", "sha256": evidence["source_record_sha256"]}
    memory.ascend(state_before=base, candidate_state=failed,
                  active_state_after=base, promoted=False,
                  score_before=evidence["baseline_mae_s"],
                  score_candidate=evidence["candidate_mae_s"],
                  lessons=["NO_IMPROVEMENT_DO_NOT_REPEAT_WITHOUT_NEW_DATA"],
                  constraints=["FUTURE_INDEPENDENT_REPLICATION_REQUIRED"])
    assert memory.turns[1].parent_fingerprint == memory.turns[0].fingerprint
    assert memory.turns[1].active_state_after == base
    roles = {role: {"parent_base_role": ROUTING.get(role, role),
                    "role_kind": "BASE_MICROCORE" if role in BASE
                                 else "LEGACY_ADVISORY_ONLY",
                    "matched_sources": sorted(s["id"] for s in catalog["entries"]
                                              if s["role"] == role)}
             for role in R0}
    result = {
        "schema": REPORT_SCHEMA, "catalog_sha256": digest(catalog),
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "real_r2_record_sha256": evidence["source_record_sha256"],
        "source_class": "LIVE_PUBLIC_DONOR_INVENTORY_PLUS_REAL_RETROSPECTIVE_R2",
        "operators_exercised": [
            "MODERN_TRINITY_THREE_ROLE_CRITIC_VETO",
            "MODERN_TRINITY_PAST_PRESENT_FUTURE_GUARD",
            "MODERN_SLIME_BOUNDED_UTILITY_TRACE",
            "CANONICAL_SPIRAL_APPEND_ONLY_FAILURE_MEMORY",
            "R0_THIRTEEN_ROLE_MAPPING",
            "V04_PUBLIC_DONOR_GENE_CATALOG",
        ],
        "historical_sources_in_gene_pool": len(catalog["entries"]),
        "source_repositories": len(set(s["repository"] for s in catalog["entries"])),
        "local_sources_git_blob_verified": verified,
        "historical_roles": roles, "base_microcores": list(BASE),
        "verified_public_donors_reported_by_collector": snapshot["verified_donor_count"],
        "proposed_rare_ideas": candidates,
        "triadic_council": council, "temporal_advisory": temporal,
        "completed_r2_relative_gain": evidence["relative_gain"],
        "slime_reference_trace": round(trace, 8),
        "spiral_turns": [x.to_dict() for x in memory.turns],
        "research_gate": "HOLD_UNVERIFIED_PERFORMANCE_AND_R2_NEGATIVE",
        "report_kind": "READ_ONLY_LIVE_RESEARCH_ADVISORY_NOT_MODEL_TRAINING",
        "independent_external_authentication": False,
        "automatic_offspring": False,
        "production_authority": False,
        "model_weights_modified": False,
        "original_six_role_kernel_unchanged": True,
    }
    result["report_sha256"] = digest(result)
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("audit", "run"))
    p.add_argument("--catalog", default="research/essence/v08/heritage_sources.json")
    p.add_argument("--manifest", default=".janus/essence/manifest.json")
    p.add_argument("--snapshot")
    p.add_argument("--r2", default="tests/fixtures/essence_r2_real_duration_20261113.json")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog = load(args.catalog)
    verified = validate_catalog(catalog, root)
    manifest = load(args.manifest)
    validate_root(manifest)
    if args.mode == "run":
        if not args.snapshot:
            p.error("--snapshot required")
        report = run(catalog, manifest, load(args.snapshot), load(args.r2), root=root)
    else:
        report = {
            "schema": REPORT_SCHEMA,
            "catalog_sha256": digest(catalog),
            "source_repositories": len(set(s["repository"] for s in catalog["entries"])),
            "local_sources_git_blob_verified": verified,
            "canonical_13_roles": list(R0),
            "research_gate": "CATALOG_AUDITED_DONORS_NOT_YET_COLLECTED",
            "production_authority": False,
            "model_weights_modified": False,
        }
        report["report_sha256"] = digest(report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"source_repositories": report["source_repositories"],
                      "research_gate": report["research_gate"],
                      "production_authority": False}))
if __name__ == "__main__":
    main()
