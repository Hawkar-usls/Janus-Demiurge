#!/usr/bin/env python3
"""Independent read-only JANUS Scout scheduled-Copilot canary witness.

Audits an immutable run-specific outbox already persisted by the Scout workflow.
Never calls Copilot, claims model consensus is truth, or writes to repositories.
Model synthesis means a structurally sourced response, NOT scientific validity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "janus.demiurge.scout_scheduled_canary_witness.v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID = re.compile(r"[0-9]{5,}\Z")
CANARY = "SCOUT_TERMINAL_07"


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(obj: dict) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_limited(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or not 1 <= path.stat().st_size <= 300_000:
        raise ValueError("CANARY_WITNESS_MISSING_OR_OVERSIZED_REPORT:" + path.name)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("CANARY_WITNESS_NOT_OBJECT")
    return obj


def verify_analysis(report: dict) -> bool:
    body = report.get("analysis")
    if (report.get("status") != "OBSERVED_REPOSITORY_STATE"
            or report.get("model_error") not in (None, "")
            or not isinstance(body, dict)
            or not isinstance(body.get("summary"), str)
            or not body["summary"].strip()
            or not isinstance(body.get("observations"), list)):
        return False
    commit = (report.get("repository_snapshot") or {}).get("target_commit")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        return False
    for observation in body["observations"]:
        if (not isinstance(observation, dict)
                or not isinstance(observation.get("claim"), str)
                or not observation["claim"].strip()
                or not isinstance(observation.get("support"), dict)
                or observation["support"].get("commit") != commit
                or not isinstance(observation["support"].get("path"), str)
                or not observation["support"]["path"].strip()):
            return False
    return True


def audit(root: Path, run_id: str, source_sha: str) -> dict:
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("CANARY_WITNESS_RUN_ID_INVALID")
    if not isinstance(source_sha, str) or not HEX40.fullmatch(source_sha):
        raise ValueError("CANARY_WITNESS_SOURCE_SHA_INVALID")
    manifest = load_limited(root / "scout_swarm/SCOUT_SWARM_MANIFEST-v1.json")
    agents = manifest.get("agents")
    if not isinstance(agents, list) or len(agents) != 17:
        raise ValueError("CANARY_WITNESS_EXPECTED_17_AGENTS")
    targets = {a["id"]: a for a in agents}
    if len(targets) != 17 or CANARY not in targets:
        raise ValueError("CANARY_WITNESS_AGENT_ID_MISMATCH")
    folder = root / "scout_swarm/outbox/runs" / run_id
    summary = load_limited(folder / "SWARM_SUMMARY.json")
    if (summary.get("run_id") != run_id
            or summary.get("control_sha") != source_sha
            or summary.get("agents_expected") != 17
            or summary.get("agents_received") != 17
            or summary.get("agents_snapshot_observed") != 17
            or summary.get("world_truth") is not False
            or summary.get("write_authority_over_targets") is not False):
        raise ValueError("CANARY_WITNESS_SUMMARY_SOURCE_OR_COMPLETENESS_HOLD")
    present = {p.stem for p in folder.glob("SCOUT_*.json")}
    if present != set(targets):
        raise ValueError("CANARY_WITNESS_MISSING_OR_EXTRA_AGENTS")
    outcomes = {}
    successes = []
    snapshots = 0
    for aid in sorted(targets):
        report = load_limited(folder / (aid + ".json"))
        target = report.get("target") if isinstance(report.get("target"), dict) else {}
        source = report.get("repository_snapshot") if isinstance(report.get("repository_snapshot"), dict) else {}
        auth = report.get("authority") if isinstance(report.get("authority"), dict) else {}
        gate = report.get("evidence_gate") if isinstance(report.get("evidence_gate"), dict) else {}
        if (report.get("agent_id") != aid
                or target.get("repository") != targets[aid]["target_repo"]
                or target.get("ref") != targets[aid]["target_ref"]
                or auth.get("target_repository_write") is not False
                or gate.get("world_truth") is not False
                or gate.get("model_output_is_independent_confirmation") is not False):
            raise ValueError("CANARY_WITNESS_AGENT_PROVENANCE_OR_AUTHORITY_HOLD:" + aid)
        commit = source.get("target_commit")
        if isinstance(commit, str) and HEX40.fullmatch(commit):
            snapshots += 1
        else:
            raise ValueError("CANARY_WITNESS_UNBOUND_SNAPSHOT:" + aid)
        success = verify_analysis(report)
        if report.get("status") == "OBSERVED_REPOSITORY_STATE" and not success:
            raise ValueError("CANARY_WITNESS_FABRICATED_MODEL_SUCCESS:" + aid)
        if success:
            successes.append(aid)
        outcomes[aid] = {
            "status": report.get("status"),
            "target_commit": commit,
            "synthesis_status": "STRUCTURAL_UNVERIFIED" if success else "NO_MODEL_SYNTHESIS",
            "failure_reason": report.get("synthesis_failure_reason"),
        }
    if any(aid != CANARY for aid in successes):
        raise ValueError("CANARY_WITNESS_UNAUTHORIZED_MODEL_FANOUT")
    if summary.get("agents_model_synthesis_ok") != len(successes):
        raise ValueError("CANARY_WITNESS_MODEL_HEALTH_COUNT_DRIFT")
    canary = outcomes[CANARY]
    result = {
        "schema": SCHEMA,
        "status": ("CANARY_MODEL_RESPONSE_STRUCTURALLY_VERIFIED_UNVERIFIED_TRUTH"
                   if successes else "CANARY_NO_MODEL_SYNTHESIS"),
        "run_id": run_id, "source_commit": source_sha,
        "scout_count": len(targets), "snapshots_observed": snapshots,
        "model_synthesis_count": len(successes),
        "canary_agent": CANARY, "canary_status": canary["status"],
        "canary_failure_reason": canary["failure_reason"],
        "unverified_model_response_not_world_truth": True,
        "independent_external_lab_validation": False,
        "owner_resources_modified": False,
        "copilot_calls_by_this_witness": 0,
        "paid_resources_requested": False,
        "authority_delta": 0,
    }
    result["receipt_sha256"] = digest(result)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--run-id", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.root, args.run_id, args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, sort_keys=True, indent=2)
        fp.write("\n")
    print("JANUS_SCOUT_SCHEDULE_CANARY_WITNESS=" + result["status"])
    print("JANUS_SCOUT_SCHEDULE_CANARY_SYNTHESIS_COUNT=" +
          str(result["model_synthesis_count"]))


if __name__ == "__main__":
    main()
