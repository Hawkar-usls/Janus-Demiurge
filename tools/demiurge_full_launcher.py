#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

POLICY_SCHEMA = "janus.demiurge.full_launcher_policy.v1"
RECEIPT_SCHEMA = "janus.demiurge.full_launcher_receipt.v1"
WORKFLOW_DISPATCH_RE = re.compile(r"(?m)^\s{2,}workflow_dispatch\s*:")
NAME_RE = re.compile(r"(?m)^name\s*:\s*(.+?)\s*$")
TARGET_SHA_RE = re.compile(r"(?m)^\s{6,}target_sha\s*:")
DELEGATE_RE = re.compile(r"gh\s+workflow\s+run\s+([A-Za-z0-9_.\-/]+\.ya?ml)")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"JSON object required: {path}")
    return obj


def workflow_name(text: str, fallback: str) -> str:
    m = NAME_RE.search(text)
    return m.group(1).strip().strip("'\"") if m else fallback


def declares_manual_dispatch(text: str) -> bool:
    return bool(WORKFLOW_DISPATCH_RE.search(text))


def declares_target_sha(text: str) -> bool:
    return bool(TARGET_SHA_RE.search(text))


def delegated_workflows(text: str) -> list[str]:
    return sorted({pathlib.PurePosixPath(x).name for x in DELEGATE_RE.findall(text)})


def discover_local(workflow_dir: pathlib.Path, self_workflow: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        rows.append({
            "file": path.name,
            "path": path.as_posix(),
            "name": workflow_name(text, path.name),
            "manual_dispatch": declares_manual_dispatch(text),
            "declares_target_sha": declares_target_sha(text),
            "delegates": delegated_workflows(text),
            "is_self": path.name == self_workflow,
        })
    return rows


def gh_workflow_inventory(repo: str) -> list[dict[str, Any]]:
    cmd = [
        "gh", "workflow", "list", "--repo", repo, "--all", "--limit", "200",
        "--json", "name,path,state",
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        raise SystemExit(f"unable to list GitHub workflows: {p.stderr.strip()}")
    rows = json.loads(p.stdout or "[]")
    if not isinstance(rows, list):
        raise SystemExit("GitHub workflow inventory must be a list")
    return rows


def normalize_active(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = str(row.get("path") or "")
        if not path:
            continue
        out[pathlib.PurePosixPath(path).name] = {
            "path": path,
            "name": str(row.get("name") or pathlib.PurePosixPath(path).name),
            "state": str(row.get("state") or "unknown"),
        }
    return out


def ordered_launchables(
    local_rows: list[dict[str, Any]],
    active_by_file: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    priority = [str(x) for x in policy.get("priority") or []]
    rank = {name: idx for idx, name in enumerate(priority)}
    launchable: list[dict[str, Any]] = []
    passive: list[dict[str, Any]] = []
    for row in local_rows:
        remote = active_by_file.get(row["file"])
        state = (remote or {}).get("state", "not_registered")
        enriched = dict(row, workflow_state=state)
        if row["is_self"]:
            enriched["reason"] = "self_workflow_refused"
            passive.append(enriched)
            continue
        if not row["manual_dispatch"]:
            enriched["reason"] = "no_workflow_dispatch__passive_or_event_driven"
            passive.append(enriched)
            continue
        if state != "active":
            enriched["reason"] = f"workflow_state_{state}"
            passive.append(enriched)
            continue
        launchable.append(enriched)
    launchable.sort(key=lambda x: (rank.get(x["file"], 10_000), x["file"]))
    return launchable, passive


def build_dispatch_command(
    row: dict[str, Any],
    repo: str,
    ref: str,
    source_sha: str,
    policy: dict[str, Any],
) -> list[str]:
    cmd = ["gh", "workflow", "run", row["file"], "--repo", repo, "--ref", ref]
    overrides = (policy.get("workflow_inputs") or {}).get(row["file"], {})
    if not isinstance(overrides, dict):
        raise SystemExit(f"workflow_inputs for {row['file']} must be an object")
    inputs = {str(k): str(v).lower() if isinstance(v, bool) else str(v) for k, v in overrides.items()}
    if policy.get("inject_target_sha_when_declared") is True and row.get("declares_target_sha"):
        inputs.setdefault("target_sha", source_sha)
    for key in sorted(inputs):
        cmd.extend(["-f", f"{key}={inputs[key]}"])
    return cmd


def run_launcher(
    *,
    policy: dict[str, Any],
    repo: str,
    source_sha: str,
    workflow_dir: pathlib.Path,
    active_rows: list[dict[str, Any]],
    dry_run: bool,
) -> tuple[dict[str, Any], int]:
    if policy.get("schema") != POLICY_SCHEMA:
        raise SystemExit("unsupported launcher policy")
    authority = policy.get("authority") or {}
    forbidden_true = (
        "launcher_is_admission",
        "launcher_grants_code_admission",
        "launcher_grants_lifecycle",
        "launcher_grants_evidence_status",
        "launcher_bypasses_nexus",
        "launcher_bypasses_auditor",
    )
    if any(authority.get(k) is not False for k in forbidden_true) or authority.get("authority_delta") != 0:
        raise SystemExit("launcher authority firewall refused policy")

    self_workflow = str(policy.get("self_workflow") or "janus-demiurge-full-launcher.yml")
    ref = str(policy.get("dispatch_ref") or "main")
    max_dispatches = int(policy.get("max_dispatches", 96))
    delay = float(policy.get("dispatch_delay_seconds", 1.0))
    strict = policy.get("strict_dispatch") is True

    local_rows = discover_local(workflow_dir, self_workflow)
    active_by_file = normalize_active(active_rows)
    launchable, passive = ordered_launchables(local_rows, active_by_file, policy)
    if len(launchable) > max_dispatches:
        raise SystemExit(f"dispatch budget exceeded: {len(launchable)}>{max_dispatches}")

    results: list[dict[str, Any]] = []
    for row in launchable:
        cmd = build_dispatch_command(row, repo, ref, source_sha, policy)
        item = {
            "file": row["file"],
            "name": row["name"],
            "workflow_state": row["workflow_state"],
            "delegates": row["delegates"],
            "declares_target_sha": row["declares_target_sha"],
            "command": cmd,
            "status": "PLANNED" if dry_run else "PENDING",
        }
        if dry_run:
            results.append(item)
            continue
        p = subprocess.run(cmd, text=True, capture_output=True)
        item["returncode"] = p.returncode
        item["stdout"] = p.stdout.strip()[-2000:]
        item["stderr"] = p.stderr.strip()[-2000:]
        item["status"] = "DISPATCHED" if p.returncode == 0 else "DISPATCH_FAILED"
        results.append(item)
        if delay > 0:
            time.sleep(delay)

    failures = [x for x in results if x["status"] == "DISPATCH_FAILED"]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": policy.get("mode"),
        "repository": repo,
        "source_sha": source_sha,
        "dispatch_ref": ref,
        "dry_run": dry_run,
        "workflow_files_observed": len(local_rows),
        "manual_active_launchable": len(launchable),
        "passive_or_refused_count": len(passive),
        "dispatched_count": sum(x["status"] == "DISPATCHED" for x in results),
        "planned_count": sum(x["status"] == "PLANNED" for x in results),
        "dispatch_failure_count": len(failures),
        "dispatches": results,
        "passive_or_refused": passive,
        "authority": authority,
        "authority_delta": 0,
        "claim_ceiling": {
            "dispatch_is_execution_success": False,
            "dispatch_is_evidence": False,
            "launcher_grants_admission": False,
            "launcher_grants_lifecycle": False,
        },
        "law": "LAUNCHER_MAY_WAKE_NE_LAUNCHER_MAY_CROWN",
    }
    rc = 2 if failures and strict else 0
    return receipt, rc


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS Demiurge registry-driven full-system launcher")
    ap.add_argument("--policy", default="demiurge/DEMIURGE_LAUNCHER_POLICY.json")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--source-sha", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--workflow-dir", default=".github/workflows")
    ap.add_argument("--active-workflows-json", default="")
    ap.add_argument("--out", default="runtime/DEMIURGE_FULL_LAUNCH_RECEIPT.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.repo:
        raise SystemExit("repository is required")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha or ""):
        raise SystemExit("exact 40-hex source SHA is required")

    policy = load_json(pathlib.Path(args.policy))
    if args.active_workflows_json:
        active_rows = json.loads(pathlib.Path(args.active_workflows_json).read_text(encoding="utf-8"))
    else:
        active_rows = gh_workflow_inventory(args.repo)

    receipt, rc = run_launcher(
        policy=policy,
        repo=args.repo,
        source_sha=args.source_sha,
        workflow_dir=pathlib.Path(args.workflow_dir),
        active_rows=active_rows,
        dry_run=args.dry_run,
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS" if rc == 0 else "DISPATCH_FAILURE",
        "source_sha": receipt["source_sha"],
        "launchable": receipt["manual_active_launchable"],
        "dispatched": receipt["dispatched_count"],
        "planned": receipt["planned_count"],
        "failures": receipt["dispatch_failure_count"],
        "receipt": out.as_posix(),
        "authority_delta": 0,
    }, ensure_ascii=False, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
