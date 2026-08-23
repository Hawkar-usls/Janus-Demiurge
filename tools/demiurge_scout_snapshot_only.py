#!/usr/bin/env python3
"""Deterministic JANUS Scout fallback when the shared model preflight is unavailable.

This is not a second Scout implementation. It reuses the canonical Scout engine's
manifest, Git snapshot, spiral context and ascent classifier, but deliberately
skips model synthesis after a run-level preflight has already established that
calling the model would fail (for example, monthly quota exhaustion).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import demiurge_scout_swarm as engine


def build_report(
    agent: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    snapshot: Dict[str, Any],
    *,
    model_status: str,
    token_fp: str,
) -> Dict[str, Any]:
    spiral_context = engine.inherited_spiral_context(previous)
    target_available = bool(snapshot.get("target_commit")) and not snapshot.get("snapshot_error")

    if target_available:
        normalized_status = str(model_status or "UNAVAILABLE").upper()
        status = (
            "DEGRADED_MODEL_QUOTA_EXHAUSTED"
            if normalized_status == "QUOTA_EXHAUSTED"
            else "DEGRADED_MODEL_PRECHECK_UNAVAILABLE"
        )
        analysis = {
            "summary": "Model synthesis skipped by the shared run-level preflight; deterministic repository snapshot remains available.",
            "observations": [],
            "risks": [],
            "open_questions": [],
            "next_checks": [],
            "lessons": [
                "Shared model preflight blocked synthesis without erasing repository evidence or Scout identity."
            ],
            "oracle_guidance": None,
        }
        model_error = f"MODEL_PREFLIGHT:{normalized_status}"
    else:
        status = "DEGRADED_TARGET_UNAVAILABLE"
        analysis = {
            "summary": "Target repository could not be observed in this turn.",
            "observations": [],
            "risks": [],
            "open_questions": [],
            "next_checks": ["Retry target observation on the next spiral turn."],
            "lessons": ["Transport failure is a retained constraint, not evidence about target state."],
            "oracle_guidance": None,
        }
        model_error = str(snapshot.get("snapshot_error") or "TARGET_UNAVAILABLE")[:2000]

    ascent_status = engine.classify_ascent(previous, snapshot, analysis)
    return {
        "schema": "janus.demiurge.scout_agent.report.v2.spiral",
        "agent_id": agent["id"],
        "role": agent["role"],
        "created_at_utc": engine.utc_now(),
        "status": status,
        "target": {"repository": agent["target_repo"], "ref": agent["target_ref"]},
        "focus": agent["focus"],
        "repository_snapshot": snapshot,
        "analysis": analysis,
        "spiral": {
            "turn": spiral_context["next_turn"],
            "parent_report_sha256": spiral_context["parent_report_sha256"],
            "previous_target_commit": spiral_context["previous_target_commit"],
            "identity_persistent": True,
            "previous_report_is_evidence": False,
            "retained_lessons": spiral_context["retained_lessons"],
            "retained_constraints": spiral_context["retained_constraints"],
            "new_lessons": analysis["lessons"],
            "ascent_status": ascent_status,
            "logical_ring": False,
        },
        "model_error": model_error,
        "model_preflight": {
            "status": str(model_status or "UNAVAILABLE").upper(),
            "scope": "ONE_SHARED_CHECK_PER_SWARM_RUN",
            "model_call_attempted_by_this_scout": False,
            "snapshot_survives_model_unavailability": True,
        },
        "janus_agent_token": {
            "scope": "EPHEMERAL_GITHUB_RUN_AGENT",
            "fingerprint": token_fp,
            "raw_token_persisted": False,
        },
        "evidence_gate": {
            "repository_observation_bound_to_commit": target_available,
            "model_output_is_independent_confirmation": False,
            "previous_scout_report_is_independent_confirmation": False,
            "world_truth": False,
        },
        "authority": {"target_repository_write": False, "demiurge_report_write": True},
    }


def run_snapshot_only(agent_id: str, output: Path, model_status: str) -> None:
    agents = engine.agent_map()
    if agent_id not in agents:
        raise SystemExit(f"UNKNOWN_AGENT:{agent_id}")
    agent = agents[agent_id]
    previous = engine.load_previous_agent_state(agent_id)
    token = secrets.token_urlsafe(48)
    token_fp = hashlib.sha256(token.encode()).hexdigest()[:16]

    with tempfile.TemporaryDirectory(prefix=f"{agent_id.lower()}-snapshot-") as td:
        repo = Path(td) / "target"
        clone_url = f"https://github.com/{agent['target_repo']}.git"
        try:
            engine.run(["git", "clone", "--depth", "20", "--branch", agent["target_ref"], clone_url, str(repo)], timeout=180)
            snapshot = engine.repository_snapshot(repo, agent)
        except Exception as exc:
            snapshot = {
                "target_repo": agent["target_repo"],
                "target_ref": agent["target_ref"],
                "snapshot_error": f"{type(exc).__name__}:{exc}"[:2000],
            }

    report = build_report(agent, previous, snapshot, model_status=model_status, token_fp=token_fp)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"{agent_id}={report['status']} spiral_turn={report['spiral']['turn']} "
        f"ascent={report['spiral']['ascent_status']} model_call=SKIPPED"
    )


def self_test() -> None:
    agent = {
        "id": "SCOUT_TEST",
        "role": "TEST",
        "target_repo": "owner/repo",
        "target_ref": "main",
        "focus": "test",
    }
    snapshot = {"target_commit": "abc", "target_repo": "owner/repo", "target_ref": "main"}
    report = build_report(agent, None, snapshot, model_status="QUOTA_EXHAUSTED", token_fp="deadbeef")
    assert report["status"] == "DEGRADED_MODEL_QUOTA_EXHAUSTED"
    assert report["model_preflight"]["model_call_attempted_by_this_scout"] is False
    assert report["evidence_gate"]["repository_observation_bound_to_commit"] is True
    assert report["spiral"]["identity_persistent"] is True
    print("JANUS_SCOUT_SNAPSHOT_ONLY_PREFLIGHT_FALLBACK_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-agent")
    parser.add_argument("--output")
    parser.add_argument("--model-status", default="UNAVAILABLE")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.run_agent or not args.output:
        parser.error("--run-agent and --output are required")
    run_snapshot_only(args.run_agent, Path(args.output), args.model_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
