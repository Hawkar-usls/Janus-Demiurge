#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable

from tools.demiurge_full_launcher import (
    build_dispatch_command,
    discover_local,
    gh_workflow_inventory,
    normalize_active,
)

POLICY_SCHEMA = "janus.demiurge.conductor_policy.v1"
RECEIPT_SCHEMA = "janus.demiurge.conductor_receipt.v1"
STATE_SCHEMA = "janus.demiurge.conductor_state.v1"
TERMINAL = {"completed"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return obj


def canonical_sha(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA or policy.get("enabled") is not True:
        raise RuntimeError("CONDUCTOR_POLICY_DISABLED_OR_UNSUPPORTED")
    auth = policy.get("authority") or {}
    forbidden = (
        "conductor_is_admission",
        "conductor_grants_code_admission",
        "conductor_grants_lifecycle",
        "conductor_grants_evidence_status",
        "conductor_bypasses_nexus",
        "conductor_bypasses_auditor",
        "child_success_is_world_truth",
    )
    if any(auth.get(k) is not False for k in forbidden) or auth.get("authority_delta") != 0:
        raise RuntimeError("CONDUCTOR_AUTHORITY_FIREWALL_FAIL")
    graph = policy.get("phase_graph")
    if not isinstance(graph, dict) or "START" not in graph:
        raise RuntimeError("CONDUCTOR_PHASE_GRAPH_REQUIRED")
    if int(policy.get("max_steps_per_cycle", 0)) not in range(1, 17):
        raise RuntimeError("CONDUCTOR_STEP_BUDGET_REJECTED")


def classify_phase(filename: str, policy: dict[str, Any]) -> str:
    override = (policy.get("phase_overrides") or {}).get(filename)
    if override:
        return str(override)
    for row in policy.get("phase_rules") or []:
        if not isinstance(row, dict):
            continue
        pattern = str(row.get("pattern") or "")
        phase = str(row.get("phase") or "")
        if pattern and phase and re.search(pattern, filename, flags=re.I):
            return phase
    return "VERIFY"


def admitted_buttons(
    policy: dict[str, Any],
    launcher_policy: dict[str, Any],
    workflow_dir: pathlib.Path,
    active_rows: list[dict[str, Any]],
    current_phase: str,
    used: set[str],
    step_count: int,
) -> list[dict[str, Any]]:
    excluded = set(str(x) for x in policy.get("excluded_workflows") or [])
    allowed_phases = set(str(x) for x in (policy.get("phase_graph") or {}).get(current_phase, []))
    active = normalize_active(active_rows)
    rows: list[dict[str, Any]] = []
    repeat = policy.get("repeat_workflow_in_same_cycle") is True
    for row in discover_local(workflow_dir, str(policy.get("self_workflow") or "janus-demiurge-conductor.yml")):
        filename = row["file"]
        if filename in excluded or row.get("is_self"):
            continue
        if row.get("manual_dispatch") is not True:
            continue
        remote = active.get(filename)
        if not remote or remote.get("state") != "active":
            continue
        if not repeat and filename in used:
            continue
        phase = classify_phase(filename, policy)
        if phase not in allowed_phases:
            continue
        rows.append({
            "kind": "WORKFLOW",
            "workflow": filename,
            "name": row.get("name") or filename,
            "phase": phase,
            "score_text": f"{phase} {row.get('name') or filename}",
            "declares_target_sha": row.get("declares_target_sha") is True,
            "delegates": row.get("delegates") or [],
        })
    minimum = int(policy.get("min_steps_before_complete", 2))
    if "COMPLETE" in allowed_phases and step_count >= minimum:
        rows.append({
            "kind": "COMPLETE",
            "workflow": None,
            "name": "COMPLETE CYCLE",
            "phase": "COMPLETE",
            "score_text": str((policy.get("native_choice") or {}).get("complete_score_text") or "COMPLETE CYCLE"),
            "declares_target_sha": False,
            "delegates": [],
        })
    return rows


def bounded_signal(path: str) -> dict[str, Any]:
    raw: bytes | None = None
    p = subprocess.run(["git", "show", f"origin/main:{path}"], capture_output=True)
    if p.returncode == 0:
        raw = p.stdout
    else:
        local = pathlib.Path(path)
        if local.is_file():
            raw = local.read_bytes()
    if raw is None:
        return {"path": path, "state": "MISSING"}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"path": path, "state": "UNPARSEABLE", "sha256": hashlib.sha256(raw).hexdigest()}
    if not isinstance(obj, dict):
        return {"path": path, "state": "NON_OBJECT", "sha256": hashlib.sha256(raw).hexdigest()}
    keys = (
        "schema", "status", "state", "selected_candidate_id", "record_count",
        "training_eligible_count", "last_training_status", "source_attempt_count",
        "promotion_count", "rejection_count",
    )
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "summary": {k: obj[k] for k in keys if k in obj and isinstance(obj[k], (str, int, float, bool, type(None)))},
    }


def refresh_signals(policy: dict[str, Any]) -> list[dict[str, Any]]:
    subprocess.run(["git", "fetch", "origin", "main"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return [bounded_signal(str(path)) for path in policy.get("state_inputs") or []]


def decision_prompt(
    *, source_sha: str, current_phase: str, step_count: int,
    history: list[dict[str, Any]], signals: list[dict[str, Any]], candidates: list[dict[str, Any]],
) -> str:
    hist = [
        {
            "workflow": h.get("workflow"), "phase": h.get("phase"),
            "conclusion": h.get("conclusion"), "status": h.get("status"),
        }
        for h in history[-6:]
    ]
    payload = {
        "source": source_sha[:12],
        "phase": current_phase,
        "step": step_count,
        "history": hist,
        "signals": signals,
        "choices": [{"phase": c["phase"], "button": c["workflow"] or "COMPLETE"} for c in candidates],
    }
    return "JANUS CONDUCTOR STATE|" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "|NEXT="


def select_with_scorer(
    prompt: str,
    candidates: list[dict[str, Any]],
    score_fn: Callable[[str, str], float],
    *, current_phase: str, history: list[dict[str, Any]], policy: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not candidates:
        raise RuntimeError("CONDUCTOR_NO_ADMITTED_BUTTONS")
    cfg = policy.get("native_choice") or {}
    fail_penalty = float(cfg.get("failure_penalty_nll", 0.06))
    same_phase_penalty = float(cfg.get("repeat_phase_penalty_nll", 0.02))
    last_failures = {h.get("workflow") for h in history[-4:] if h.get("conclusion") not in (None, "success")}
    scored: list[dict[str, Any]] = []
    for row in candidates:
        raw = float(score_fn(prompt, row["score_text"]))
        penalty = 0.0
        if row.get("workflow") in last_failures:
            penalty += fail_penalty
        if row.get("phase") == current_phase and row.get("phase") != "COMPLETE":
            penalty += same_phase_penalty
        scored.append(dict(row, raw_nll=raw, policy_penalty_nll=penalty, adjusted_nll=raw + penalty))
    scored.sort(key=lambda x: (x["adjusted_nll"], x.get("workflow") or ""))
    return scored[0], scored


def native_select(
    checkpoint: pathlib.Path, prompt: str, candidates: list[dict[str, Any]],
    *, current_phase: str, history: list[dict[str, Any]], policy: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not checkpoint.is_file():
        raise RuntimeError("CONDUCTOR_PROMOTED_CHECKPOINT_REQUIRED")
    from janus_model.train_registry import load_checkpoint
    from janus_model.decision import continuation_avg_nll
    model, _ = load_checkpoint(checkpoint)
    return select_with_scorer(
        prompt, candidates, lambda p, c: continuation_avg_nll(model, p, c),
        current_phase=current_phase, history=history, policy=policy,
    )


def replace_input(cmd: list[str], key: str, value: str) -> list[str]:
    needle = key + "="
    out = list(cmd)
    for i, token in enumerate(out):
        if token == "-f" and i + 1 < len(out) and out[i + 1].startswith(needle):
            out[i + 1] = needle + value
            return out
    out.extend(["-f", needle + value])
    return out


def list_workflow_run_ids(repo: str, workflow: str) -> set[int]:
    p = subprocess.run(
        ["gh", "run", "list", "--repo", repo, "--workflow", workflow, "--event", "workflow_dispatch", "--limit", "30", "--json", "databaseId"],
        text=True, capture_output=True,
    )
    if p.returncode != 0:
        return set()
    try:
        rows = json.loads(p.stdout or "[]")
        return {int(r["databaseId"]) for r in rows if isinstance(r, dict) and r.get("databaseId")}
    except Exception:
        return set()


def observe_new_run(repo: str, workflow: str, before: set[int], timeout: int = 90) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = list_workflow_run_ids(repo, workflow)
        new = sorted(current - before, reverse=True)
        if new:
            return new[0]
        time.sleep(3)
    return None


def wait_run(repo: str, run_id: int, timeout: int, poll: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        p = subprocess.run(
            ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "status,conclusion,url,headSha,workflowName"],
            text=True, capture_output=True,
        )
        if p.returncode == 0:
            try:
                last = json.loads(p.stdout or "{}")
            except Exception:
                last = {}
            if last.get("status") in TERMINAL:
                return dict(last, terminal=True)
        time.sleep(poll)
    return dict(last, terminal=False, timeout=True)


def dispatch_and_wait(
    *, chosen: dict[str, Any], repo: str, source_sha: str,
    launcher_policy: dict[str, Any], policy: dict[str, Any], prompt: str,
) -> dict[str, Any]:
    workflow = str(chosen["workflow"])
    before = list_workflow_run_ids(repo, workflow)
    row = {
        "file": workflow,
        "declares_target_sha": chosen.get("declares_target_sha") is True,
    }
    cmd = build_dispatch_command(
        row, repo, str(policy.get("dispatch_ref") or "main"), source_sha, launcher_policy,
    )
    if workflow == "janus-native-model.yml":
        cmd = replace_input(cmd, "mode", "run")
        cmd = replace_input(cmd, "prompt", "JANUS Conductor: choose and execute the next bounded system action; cycle state digest=" + hashlib.sha256(prompt.encode()).hexdigest()[:16])
    started = datetime.now(timezone.utc).isoformat()
    p = subprocess.run(cmd, text=True, capture_output=True)
    base = {
        "workflow": workflow,
        "phase": chosen["phase"],
        "dispatch_started_at": started,
        "dispatch_command": cmd,
        "dispatch_returncode": p.returncode,
        "dispatch_stdout": p.stdout.strip()[-1000:],
        "dispatch_stderr": p.stderr.strip()[-1000:],
    }
    if p.returncode != 0:
        return dict(base, status="DISPATCH_FAILED", conclusion="dispatch_failed", terminal=True)
    run_id = observe_new_run(repo, workflow, before)
    if run_id is None:
        return dict(base, status="DISPATCHED_UNOBSERVED", conclusion="unknown", terminal=False)
    result = wait_run(
        repo, run_id,
        int(policy.get("wait_timeout_seconds", 900)),
        int(policy.get("poll_interval_seconds", 10)),
    )
    return dict(
        base,
        status="CHILD_TERMINAL" if result.get("terminal") else "CHILD_TIMEOUT",
        run_id=run_id,
        conclusion=result.get("conclusion") or ("timeout" if result.get("timeout") else "unknown"),
        child_status=result.get("status"),
        child_head_sha=result.get("headSha"),
        child_url=result.get("url"),
        terminal=result.get("terminal") is True,
    )


def run_cycle(
    *, policy: dict[str, Any], launcher_policy: dict[str, Any], repo: str,
    source_sha: str, workflow_dir: pathlib.Path, active_rows: list[dict[str, Any]],
    checkpoint: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    validate_policy(policy)
    cycle_id = f"demiurge-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{source_sha[:8]}"
    current_phase = "START"
    used: set[str] = set()
    history: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    max_steps = int(policy["max_steps_per_cycle"])
    terminal_reason = "STEP_BUDGET_EXHAUSTED"

    for step in range(max_steps):
        signals = refresh_signals(policy)
        candidates = admitted_buttons(
            policy, launcher_policy, workflow_dir, active_rows,
            current_phase, used, step,
        )
        if not candidates:
            terminal_reason = "NO_ADMITTED_BUTTONS"
            break
        prompt = decision_prompt(
            source_sha=source_sha, current_phase=current_phase,
            step_count=step, history=history, signals=signals, candidates=candidates,
        )
        chosen, scores = native_select(
            checkpoint, prompt, candidates,
            current_phase=current_phase, history=history, policy=policy,
        )
        decision = {
            "step": step + 1,
            "current_phase": current_phase,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "signals": signals,
            "candidate_count": len(candidates),
            "scores": [
                {
                    "workflow": x.get("workflow"), "phase": x["phase"],
                    "raw_nll": x["raw_nll"], "policy_penalty_nll": x["policy_penalty_nll"],
                    "adjusted_nll": x["adjusted_nll"],
                }
                for x in scores
            ],
            "chosen": {"kind": chosen["kind"], "workflow": chosen.get("workflow"), "phase": chosen["phase"]},
        }
        decisions.append(decision)
        if chosen["kind"] == "COMPLETE":
            terminal_reason = "JANUS_SELECTED_COMPLETE"
            current_phase = "COMPLETE"
            break
        result = dispatch_and_wait(
            chosen=chosen, repo=repo, source_sha=source_sha,
            launcher_policy=launcher_policy, policy=policy, prompt=prompt,
        )
        history.append(result)
        used.add(str(chosen["workflow"]))
        current_phase = chosen["phase"]
        if result.get("terminal") is not True:
            terminal_reason = "CHILD_RESULT_UNRESOLVED__STOP_FAIL_CLOSED"
            break
    else:
        terminal_reason = "STEP_BUDGET_EXHAUSTED"

    authority = policy["authority"]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "cycle_id": cycle_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "source_sha": source_sha,
        "native_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "policy_sha256": canonical_sha(policy),
        "launcher_policy_sha256": canonical_sha(launcher_policy),
        "decision_count": len(decisions),
        "dispatch_count": len(history),
        "final_phase": current_phase,
        "terminal_reason": terminal_reason,
        "decisions": decisions,
        "child_runs": history,
        "authority": authority,
        "authority_delta": 0,
        "claim_ceiling": {
            "native_choice_is_admission": False,
            "dispatch_is_success": False,
            "child_success_is_world_truth": False,
            "conductor_bypasses_child_gates": False,
        },
        "law": policy.get("law"),
    }
    state = {
        "schema": STATE_SCHEMA,
        "status": "CONDUCTOR_CYCLE_RECORDED",
        "last_cycle_id": cycle_id,
        "last_source_sha": source_sha,
        "last_receipt_sha256": canonical_sha(receipt),
        "last_final_phase": current_phase,
        "last_terminal_reason": terminal_reason,
        "last_dispatch_count": len(history),
        "last_child_conclusions": [
            {"workflow": h.get("workflow"), "phase": h.get("phase"), "conclusion": h.get("conclusion")}
            for h in history
        ],
        "authority_delta": 0,
    }
    rc = 0 if terminal_reason in {"JANUS_SELECTED_COMPLETE", "STEP_BUDGET_EXHAUSTED"} else 2
    return receipt, state, rc


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS native-model Demiurge Conductor")
    ap.add_argument("--policy", default="demiurge/JANUS_CONDUCTOR_POLICY.json")
    ap.add_argument("--launcher-policy", default="demiurge/DEMIURGE_LAUNCHER_POLICY.json")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--workflow-dir", default=".github/workflows")
    ap.add_argument("--checkpoint", default="janus_model/checkpoints/promoted.pt")
    ap.add_argument("--out-dir", default="demiurge/conductor/runs")
    ap.add_argument("--state-out", default="demiurge/conductor/state/JANUS_CONDUCTOR_STATE.json")
    a = ap.parse_args()

    if not a.repo or not re.fullmatch(r"[0-9a-f]{40}", a.source_sha or ""):
        raise SystemExit("CONDUCTOR_REPO_AND_EXACT_SOURCE_SHA_REQUIRED")
    policy = load_json(pathlib.Path(a.policy))
    launcher = load_json(pathlib.Path(a.launcher_policy))
    active = gh_workflow_inventory(a.repo)
    receipt, state, rc = run_cycle(
        policy=policy, launcher_policy=launcher, repo=a.repo, source_sha=a.source_sha,
        workflow_dir=pathlib.Path(a.workflow_dir), active_rows=active,
        checkpoint=pathlib.Path(a.checkpoint),
    )
    out_dir = pathlib.Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"{receipt['cycle_id']}.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_path = pathlib.Path(a.state_out)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS" if rc == 0 else "STOPPED_FAIL_CLOSED",
        "cycle_id": receipt["cycle_id"],
        "dispatch_count": receipt["dispatch_count"],
        "final_phase": receipt["final_phase"],
        "terminal_reason": receipt["terminal_reason"],
        "receipt": receipt_path.as_posix(),
        "authority_delta": 0,
    }, ensure_ascii=False, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
