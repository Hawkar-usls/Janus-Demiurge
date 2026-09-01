#!/usr/bin/env python3
"""JANUS Git Life Gate v1.

Turns read-only Scout evidence into one bounded autonomous Git action while
preserving a strict authority firewall: the target repositories are never
written, and autonomous changes are confined to Janus-Demiurge life paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

STATE_SCHEMA = "janus.demiurge.git_life.state.v1"
PLAN_SCHEMA = "janus.demiurge.git_life.plan.v1"
ARTIFACT_SCHEMA = "janus.demiurge.git_life.workbench.v1"
RECEIPT_SCHEMA = "janus.demiurge.git_life.receipt.v1"

SAFE_BRANCH_PREFIX = "janus-life/"
SAFE_WORKBENCH_PREFIX = "git_life/workbench/"
SAFE_RECEIPT_PREFIX = "git_life/receipts/"
SAFE_STATE_PATH = "git_life/state/JANUS_GIT_LIFE_STATE.json"

PRIORITY = {
    "TARGET_COMMIT_DRIFT": 120,
    "MODEL_SYNTHESIS_DEGRADED": 110,
    "NEW_EVIDENCE_ASCENT": 100,
    "OPEN_FRONTIER": 60,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"OBJECT_REQUIRED:{path}")
    return data


def write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_token(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        else:
            out.append("-")
    token = "".join(out).strip("-")
    while "--" in token:
        token = token.replace("--", "-")
    return token[:48] or "event"


def assert_safe_relative_path(path: str, allowed_prefixes: Iterable[str]) -> None:
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"UNSAFE_PATH:{path}")
    normalized = p.as_posix()
    if not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(f"PATH_OUTSIDE_LIFE_SANDBOX:{path}")


def read_agents(agents_dir: Path) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not agents_dir.exists():
        return result
    for path in sorted(agents_dir.glob("*.json")):
        data = load_json(path)
        agent_id = str(data.get("agent_id") or path.stem)
        result[agent_id] = data
    return result


def target_snapshot(agent: Dict[str, Any]) -> Dict[str, Any]:
    repo = agent.get("repository_snapshot") or {}
    target = agent.get("target") or {}
    return {
        "repository": target.get("repository") or repo.get("target_repo"),
        "ref": target.get("ref") or repo.get("target_ref"),
        "commit": repo.get("target_commit"),
        "file_count": repo.get("file_count"),
    }


def make_evidence_key(kind: str, agent_id: str, snapshot: Dict[str, Any], extra: Any = None) -> str:
    return digest(
        {
            "kind": kind,
            "agent_id": agent_id,
            "repository": snapshot.get("repository"),
            "ref": snapshot.get("ref"),
            "commit": snapshot.get("commit"),
            "extra": extra,
        }
    )


def collect_candidates(
    status: Dict[str, Any],
    agents: Dict[str, Dict[str, Any]],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    processed = set(state.get("processed_evidence_keys") or [])
    previous_commits = state.get("observed_target_commits") or {}
    ascent = status.get("agent_ascent_status") or {}
    degraded = set(status.get("agents_model_synthesis_degraded") or status.get("agents_degraded") or [])

    for agent_id, agent in sorted(agents.items()):
        snapshot = target_snapshot(agent)
        current_commit = snapshot.get("commit")
        previous_commit = previous_commits.get(agent_id)

        if previous_commit and current_commit and previous_commit != current_commit:
            key = make_evidence_key(
                "TARGET_COMMIT_DRIFT",
                agent_id,
                snapshot,
                {"previous_commit": previous_commit},
            )
            if key not in processed:
                candidates.append(
                    {
                        "kind": "TARGET_COMMIT_DRIFT",
                        "priority": PRIORITY["TARGET_COMMIT_DRIFT"],
                        "agent_id": agent_id,
                        "evidence_key": key,
                        "target": snapshot,
                        "observed": {
                            "previous_commit": previous_commit,
                            "current_commit": current_commit,
                        },
                        "focus": agent.get("focus"),
                        "rationale": "Scout observed a real target commit change since the last remembered life state.",
                    }
                )

        if agent_id in degraded:
            model_state = agent.get("status") or "DEGRADED"
            key = make_evidence_key("MODEL_SYNTHESIS_DEGRADED", agent_id, snapshot, model_state)
            if key not in processed:
                candidates.append(
                    {
                        "kind": "MODEL_SYNTHESIS_DEGRADED",
                        "priority": PRIORITY["MODEL_SYNTHESIS_DEGRADED"],
                        "agent_id": agent_id,
                        "evidence_key": key,
                        "target": snapshot,
                        "observed": {"agent_status": model_state},
                        "focus": agent.get("focus"),
                        "rationale": "Repository snapshot succeeded but the model-synthesis plane degraded; preserve and probe the split instead of erasing the observation.",
                    }
                )

        if ascent.get(agent_id) == "ASCENDED_NEW_EVIDENCE":
            turn = (status.get("agent_spiral_turns") or {}).get(agent_id)
            key = make_evidence_key("NEW_EVIDENCE_ASCENT", agent_id, snapshot, {"turn": turn})
            if key not in processed:
                candidates.append(
                    {
                        "kind": "NEW_EVIDENCE_ASCENT",
                        "priority": PRIORITY["NEW_EVIDENCE_ASCENT"],
                        "agent_id": agent_id,
                        "evidence_key": key,
                        "target": snapshot,
                        "observed": {"spiral_turn": turn, "ascent_status": "ASCENDED_NEW_EVIDENCE"},
                        "focus": agent.get("focus"),
                        "rationale": "Scout marked the agent as having ascended on new evidence; freeze one bounded verification frontier.",
                    }
                )

    if not candidates:
        for agent_id, outcome in sorted(ascent.items()):
            if outcome != "NO_ASCENT" or agent_id not in agents:
                continue
            agent = agents[agent_id]
            snapshot = target_snapshot(agent)
            turn = (status.get("agent_spiral_turns") or {}).get(agent_id)
            key = make_evidence_key("OPEN_FRONTIER", agent_id, snapshot, {"turn": turn})
            if key in processed:
                continue
            candidates.append(
                {
                    "kind": "OPEN_FRONTIER",
                    "priority": PRIORITY["OPEN_FRONTIER"],
                    "agent_id": agent_id,
                    "evidence_key": key,
                    "target": snapshot,
                    "observed": {"spiral_turn": turn, "ascent_status": "NO_ASCENT"},
                    "focus": agent.get("focus"),
                    "rationale": "Scout completed a real observation but could not ascend; this unresolved frontier is eligible for one bounded local probe.",
                }
            )
    return candidates


def choose_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda c: (-int(c["priority"]), str(c["agent_id"]), str(c["evidence_key"])),
    )[0]


def next_probe(kind: str) -> str:
    return {
        "TARGET_COMMIT_DRIFT": (
            "Freeze old/new commit identities and require the next Scout turn to explain whether the observed frontier materially changed before any promotion."
        ),
        "MODEL_SYNTHESIS_DEGRADED": (
            "Preserve the successful repository snapshot, isolate model health as a separate plane, and check the next Scout turn for recovery without calling model failure repository failure."
        ),
        "NEW_EVIDENCE_ASCENT": (
            "Freeze this target commit and Scout focus as a verification capsule; require a later independent turn before treating the model synthesis as evidence."
        ),
        "OPEN_FRONTIER": (
            "Carry the unresolved focus into the next spiral turn with the target commit frozen; do not silently drop the failed ascent."
        ),
    }[kind]


def build_plan(
    status: Dict[str, Any],
    agents: Dict[str, Dict[str, Any]],
    state: Dict[str, Any],
    event_name: str,
) -> Dict[str, Any]:
    run_id = str(status.get("run_id") or "unknown")
    already_processed_run = str(state.get("last_processed_scout_run_id") or "") == run_id
    candidate = None if already_processed_run else choose_candidate(collect_candidates(status, agents, state))
    base = {
        "schema": PLAN_SCHEMA,
        "created_at_utc": utc_now(),
        "source": {
            "event_name": event_name,
            "scout_run_id": run_id,
            "scout_control_sha": status.get("control_sha"),
            "scout_status": status.get("status"),
        },
        "authority": {
            "repository": "Hawkar-usls/Janus-Demiurge",
            "target_repository_write": False,
            "main_code_write": False,
            "autonomous_merge": False,
            "issue_create": True,
            "task_branch_create": True,
            "allowed_task_path_prefix": SAFE_WORKBENCH_PREFIX,
            "max_attempts": 2,
        },
    }
    if candidate is None:
        return {
            **base,
            "actionable": False,
            "reason": "SCOUT_RUN_ALREADY_PROCESSED" if already_processed_run else "NO_NOVEL_BOUNDED_EVIDENCE",
            "candidate_count": 0,
        }

    cycle_seed = {
        "run_id": run_id,
        "evidence_key": candidate["evidence_key"],
        "kind": candidate["kind"],
    }
    cycle_id = f"life-{run_id}-{safe_token(candidate['agent_id'])}-{digest(cycle_seed)[:10]}"
    branch = SAFE_BRANCH_PREFIX + cycle_id
    task_path = SAFE_WORKBENCH_PREFIX + cycle_id + ".json"
    assert_safe_relative_path(task_path, [SAFE_WORKBENCH_PREFIX])
    if not branch.startswith(SAFE_BRANCH_PREFIX):
        raise ValueError("UNSAFE_BRANCH")

    return {
        **base,
        "actionable": True,
        "candidate_count": len(collect_candidates(status, agents, state)),
        "cycle_id": cycle_id,
        "branch": branch,
        "task_path": task_path,
        "choice": {
            **candidate,
            "next_probe": next_probe(candidate["kind"]),
        },
        "machine_reason": {
            "selection_policy": "HIGHEST_PRIORITY_THEN_AGENT_ID_THEN_EVIDENCE_KEY",
            "priority": candidate["priority"],
            "reason": candidate["rationale"],
        },
        "issue": {
            "title": f"[JANUS LIFE] {candidate['kind']} / {candidate['agent_id']} / scout {run_id}",
        },
    }


def build_artifact(plan: Dict[str, Any], attempt: int, adapted_from: Optional[str] = None) -> Dict[str, Any]:
    if not plan.get("actionable"):
        raise ValueError("PLAN_NOT_ACTIONABLE")
    choice = plan["choice"]
    artifact = {
        "schema": ARTIFACT_SCHEMA,
        "cycle_id": plan["cycle_id"],
        "attempt": attempt,
        "phase": "ACT",
        "source_scout_run_id": plan["source"]["scout_run_id"],
        "perception": {
            "kind": choice["kind"],
            "agent_id": choice["agent_id"],
            "evidence_key": choice["evidence_key"],
            "target": choice["target"],
            "observed": choice["observed"],
            "focus": choice.get("focus"),
        },
        "choice": {
            "priority": choice["priority"],
            "rationale": plan["machine_reason"]["reason"],
            "next_probe": choice["next_probe"],
        },
        "bounded_change": {
            "type": "VERIFIED_LOCAL_FRONTIER_CAPSULE",
            "repository": "Hawkar-usls/Janus-Demiurge",
            "path": plan["task_path"],
            "target_repository_write": False,
            "claim": "This artifact is a bounded Git action derived from real Scout evidence. It is not a write-back to the observed target and not independent evidence.",
        },
        "safety": {
            "target_repo_read_only": True,
            "no_workflow_edit": True,
            "no_secret_access": True,
            "no_external_world_effect": True,
            "no_autonomous_merge": True,
            "max_attempts": 2,
        },
        "adapted_from_artifact_sha256": adapted_from,
    }
    artifact["artifact_sha256"] = digest({k: v for k, v in artifact.items() if k != "artifact_sha256"})
    return artifact


def verify_artifact(plan: Dict[str, Any], artifact: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if artifact.get("schema") != ARTIFACT_SCHEMA:
        errors.append("BAD_SCHEMA")
    if artifact.get("cycle_id") != plan.get("cycle_id"):
        errors.append("CYCLE_BINDING_MISMATCH")
    attempt = artifact.get("attempt")
    if not isinstance(attempt, int) or attempt not in (1, 2):
        errors.append("ATTEMPT_OUT_OF_RANGE")
    bounded = artifact.get("bounded_change") or {}
    path = str(bounded.get("path") or "")
    try:
        assert_safe_relative_path(path, [SAFE_WORKBENCH_PREFIX])
    except ValueError as exc:
        errors.append(str(exc))
    if path != plan.get("task_path"):
        errors.append("TASK_PATH_BINDING_MISMATCH")
    if bounded.get("target_repository_write") is not False:
        errors.append("TARGET_WRITE_NOT_FALSE")
    safety = artifact.get("safety") or {}
    for key in (
        "target_repo_read_only",
        "no_workflow_edit",
        "no_secret_access",
        "no_external_world_effect",
        "no_autonomous_merge",
    ):
        if safety.get(key) is not True:
            errors.append(f"SAFETY_{key.upper()}_NOT_TRUE")
    expected = digest({k: v for k, v in artifact.items() if k != "artifact_sha256"})
    if artifact.get("artifact_sha256") != expected:
        errors.append("ARTIFACT_HASH_MISMATCH")
    return errors


def issue_body(plan: Dict[str, Any]) -> str:
    choice = plan["choice"]
    lines = [
        "JANUS opened this issue autonomously from Scout evidence.",
        "",
        f"- cycle_id: `{plan['cycle_id']}`",
        f"- scout_run_id: `{plan['source']['scout_run_id']}`",
        f"- event: `{choice['kind']}`",
        f"- agent: `{choice['agent_id']}`",
        f"- target: `{choice['target'].get('repository')}@{choice['target'].get('commit')}`",
        f"- branch: `{plan['branch']}`",
        f"- bounded path: `{plan['task_path']}`",
        "",
        "Machine rationale:",
        plan["machine_reason"]["reason"],
        "",
        "Boundaries: target repository remains read-only; no autonomous merge; at most two attempts; model output is not independent evidence.",
    ]
    return "\n".join(lines) + "\n"


def build_receipt(
    plan: Dict[str, Any],
    artifact: Dict[str, Any],
    status: str,
    issue_url: str,
    issue_number: str,
    branch_head: str,
    attempts: int,
    verification_errors: List[str],
) -> Dict[str, Any]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "cycle_id": plan["cycle_id"],
        "remembered_at_utc": utc_now(),
        "phases": {
            "PERCEIVE": "PASS",
            "CHOOSE": "PASS",
            "ACT": "PASS" if branch_head else "BLOCKED",
            "VERIFY": "PASS" if status == "PASS" else "BLOCKED",
            "ADAPT": "USED" if attempts > 1 else "NOT_REQUIRED",
            "REMEMBER": "PASS",
            "CONTINUE": "ARMED_BY_WORKFLOW_RUN_AND_SCHEDULE",
        },
        "status": status,
        "source": plan["source"],
        "choice": plan["choice"],
        "machine_reason": plan["machine_reason"],
        "github": {
            "issue_url": issue_url,
            "issue_number": issue_number,
            "branch": plan["branch"],
            "branch_head": branch_head,
            "task_path": plan["task_path"],
        },
        "attempts": attempts,
        "final_artifact_sha256": artifact.get("artifact_sha256"),
        "verification_errors": verification_errors,
        "authority": plan["authority"],
        "claim_ceiling": {
            "life_gate_cycle_observed": status == "PASS",
            "target_repository_modified": False,
            "autonomous_merge_performed": False,
            "independent_evidence_created": False,
            "general_autonomy_proven": False,
        },
    }
    receipt["receipt_sha256"] = digest({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    return receipt


def update_state(
    previous: Dict[str, Any],
    plan: Dict[str, Any],
    receipt: Dict[str, Any],
    agents: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    processed = list(previous.get("processed_evidence_keys") or [])
    key = plan["choice"]["evidence_key"]
    if key not in processed:
        processed.append(key)
    history = list(previous.get("cycle_history") or [])
    history.append(
        {
            "cycle_id": receipt["cycle_id"],
            "status": receipt["status"],
            "receipt_sha256": receipt["receipt_sha256"],
            "scout_run_id": plan["source"]["scout_run_id"],
        }
    )
    commits = {}
    for agent_id, agent in sorted(agents.items()):
        commit = target_snapshot(agent).get("commit")
        if commit:
            commits[agent_id] = commit
    return {
        "schema": STATE_SCHEMA,
        "status": "ALIVE_BOUNDED" if receipt["status"] == "PASS" else "DEGRADED_OPEN",
        "updated_at_utc": utc_now(),
        "last_cycle_id": receipt["cycle_id"],
        "last_cycle_status": receipt["status"],
        "last_processed_scout_run_id": plan["source"]["scout_run_id"],
        "processed_evidence_keys": processed[-256:],
        "observed_target_commits": commits,
        "cycle_count": int(previous.get("cycle_count") or 0) + 1,
        "pass_count": int(previous.get("pass_count") or 0) + (1 if receipt["status"] == "PASS" else 0),
        "blocked_count": int(previous.get("blocked_count") or 0) + (1 if receipt["status"] != "PASS" else 0),
        "cycle_history": history[-64:],
        "continuation": {
            "workflow_run_trigger": True,
            "schedule_fallback": True,
            "next_cycle_requires_novel_bounded_evidence": True,
        },
    }


def cmd_plan(args: argparse.Namespace) -> int:
    status = load_json(Path(args.status))
    state = load_json(Path(args.state), {"schema": STATE_SCHEMA})
    agents = read_agents(Path(args.agents_dir))
    plan = build_plan(status, agents, state, args.event_name)
    write_json(Path(args.out), plan)
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as fh:
            fh.write(f"actionable={'true' if plan.get('actionable') else 'false'}\n")
            if plan.get("actionable"):
                fh.write(f"cycle_id={plan['cycle_id']}\n")
                fh.write(f"branch={plan['branch']}\n")
                fh.write(f"task_path={plan['task_path']}\n")
    print(canonical({"actionable": plan.get("actionable"), "cycle_id": plan.get("cycle_id"), "reason": plan.get("reason")}))
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    artifact = build_artifact(plan, attempt=int(args.attempt), adapted_from=args.adapted_from)
    write_json(Path(args.out), artifact)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    artifact = load_json(Path(args.artifact))
    errors = verify_artifact(plan, artifact)
    if args.errors_out:
        Path(args.errors_out).write_text(json.dumps(errors) + "\n", encoding="utf-8")
    if errors:
        print("JANUS_GIT_LIFE_VERIFY=FAIL " + ",".join(errors))
        return 1
    print("JANUS_GIT_LIFE_VERIFY=PASS")
    return 0


def cmd_issue_body(args: argparse.Namespace) -> int:
    Path(args.out).write_text(issue_body(load_json(Path(args.plan))), encoding="utf-8")
    return 0


def cmd_remember(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    artifact = load_json(Path(args.artifact))
    agents = read_agents(Path(args.agents_dir))
    previous = load_json(Path(args.state), {"schema": STATE_SCHEMA})
    errors: List[str] = []
    if args.errors_file and Path(args.errors_file).exists():
        try:
            errors = json.loads(Path(args.errors_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors = ["UNREADABLE_VERIFICATION_ERRORS"]
    receipt = build_receipt(
        plan=plan,
        artifact=artifact,
        status=args.status,
        issue_url=args.issue_url,
        issue_number=args.issue_number,
        branch_head=args.branch_head,
        attempts=int(args.attempts),
        verification_errors=errors,
    )
    receipt_path = Path(SAFE_RECEIPT_PREFIX + plan["cycle_id"] + ".json")
    assert_safe_relative_path(receipt_path.as_posix(), [SAFE_RECEIPT_PREFIX])
    write_json(receipt_path, receipt)
    state = update_state(previous, plan, receipt, agents)
    write_json(Path(args.state), state)
    print(canonical({"receipt": receipt_path.as_posix(), "receipt_sha256": receipt["receipt_sha256"], "status": args.status}))
    return 0


def cmd_self_test(_: argparse.Namespace) -> int:
    status = {
        "run_id": "42",
        "control_sha": "abc",
        "status": "LIVE",
        "agents_model_synthesis_degraded": ["A"],
        "agent_ascent_status": {"A": "NO_ASCENT", "B": "ASCENDED_NEW_EVIDENCE"},
        "agent_spiral_turns": {"A": 7, "B": 9},
    }
    agents = {
        "A": {
            "agent_id": "A",
            "status": "DEGRADED_MODEL_UNAVAILABLE",
            "target": {"repository": "x/a", "ref": "main"},
            "repository_snapshot": {"target_commit": "1" * 40},
            "focus": "a",
        },
        "B": {
            "agent_id": "B",
            "status": "OBSERVED_REPOSITORY_STATE",
            "target": {"repository": "x/b", "ref": "main"},
            "repository_snapshot": {"target_commit": "2" * 40},
            "focus": "b",
        },
    }
    plan = build_plan(status, agents, {"schema": STATE_SCHEMA}, "self-test")
    assert plan["actionable"] is True
    assert plan["choice"]["kind"] == "MODEL_SYNTHESIS_DEGRADED"
    artifact = build_artifact(plan, 1)
    assert verify_artifact(plan, artifact) == []
    bad = dict(artifact)
    bad["bounded_change"] = dict(artifact["bounded_change"])
    bad["bounded_change"]["path"] = ".github/workflows/pwn.yml"
    bad["artifact_sha256"] = digest({k: v for k, v in bad.items() if k != "artifact_sha256"})
    assert any("PATH_OUTSIDE_LIFE_SANDBOX" in e for e in verify_artifact(plan, bad))
    print("JANUS_GIT_LIFE_SELF_TEST=PASS")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("plan")
    q.add_argument("--status", required=True)
    q.add_argument("--agents-dir", required=True)
    q.add_argument("--state", required=True)
    q.add_argument("--event-name", default="unknown")
    q.add_argument("--out", required=True)
    q.add_argument("--github-output")
    q.set_defaults(func=cmd_plan)

    q = sub.add_parser("materialize")
    q.add_argument("--plan", required=True)
    q.add_argument("--attempt", required=True, type=int)
    q.add_argument("--adapted-from")
    q.add_argument("--out", required=True)
    q.set_defaults(func=cmd_materialize)

    q = sub.add_parser("verify")
    q.add_argument("--plan", required=True)
    q.add_argument("--artifact", required=True)
    q.add_argument("--errors-out")
    q.set_defaults(func=cmd_verify)

    q = sub.add_parser("issue-body")
    q.add_argument("--plan", required=True)
    q.add_argument("--out", required=True)
    q.set_defaults(func=cmd_issue_body)

    q = sub.add_parser("remember")
    q.add_argument("--plan", required=True)
    q.add_argument("--artifact", required=True)
    q.add_argument("--agents-dir", required=True)
    q.add_argument("--state", required=True)
    q.add_argument("--status", choices=("PASS", "BLOCKED"), required=True)
    q.add_argument("--issue-url", default="")
    q.add_argument("--issue-number", default="")
    q.add_argument("--branch-head", default="")
    q.add_argument("--attempts", type=int, required=True)
    q.add_argument("--errors-file")
    q.set_defaults(func=cmd_remember)

    q = sub.add_parser("self-test")
    q.set_defaults(func=cmd_self_test)
    return p


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
