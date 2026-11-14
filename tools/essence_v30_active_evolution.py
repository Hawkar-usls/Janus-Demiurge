#!/usr/bin/env python3
"""JANUS ESSENCE v3.0: real bounded GitHub Actions evolutionary ignition.

This starts only existing source-reviewed workflows. Durable model weights
and Rex module lifecycle live in their native repository/state branches.
No fabricated scores, no direct arbitrary source execution, no external
compute, no production model promotion or trust-gate bypass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

REPOSITORY = "Hawkar-usls/Janus-Demiurge"
BASE = "https://api.github.com/repos/" + REPOSITORY + "/actions/workflows/"
SCHEMA = "janus.essence.active_evolution_cycle/3.0"
MAX_BOOTSTRAP = 7
MAX_CYCLE = 3
CYCLE_COOLDOWN = timedelta(hours=2)
FAILED_RETRY_BACKOFF = timedelta(hours=2)
MAX_FUTURE_SKEW = timedelta(minutes=5)

# Fixed allowlist of source-bound, already reviewed workflows. Their
# own cryptographic contracts / isolated admissions remain in force.
LANES = (
    ("module_need_discovery", "janus-rex-need-discovery.yml", {}),
    ("module_lifecycle", "janus-rex-lifecycle.yml", {"trigger_mode": "schedule"}),
    ("neural_prospective_exam", "essence-v26-prospective-neural.yml", {}),
    ("multi_core_beetle_bridge", "essence-v29-beetle-core-bridge.yml", {}),
    ("peer_ancestry", "essence-peer-inbox-v13.yml", {}),
    ("cooling_tower", "janus-cooling-tower-async.yml", {}),
    ("bounded_autonomy_pulse", "essence-v23-continuous-pulse.yml", {}),
)
TERMINAL_CONCLUSIONS = frozenset({
    "success", "failure", "cancelled", "timed_out", "skipped",
    "neutral", "action_required", "startup_failure", "stale"
})
ACTIVE_STATUSES = frozenset({
    "queued", "requested", "waiting", "pending", "in_progress"
})


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def when(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_ACTIONS_TIMESTAMP")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_ACTIONS_TIMESTAMP") from exc
    if result.tzinfo is None:
        raise ValueError("UNZONED_ACTIONS_TIMESTAMP")
    return result.astimezone(timezone.utc)


def latest_decision(runs, *, now, bootstrap=False):
    """Read last workflow run; no overlapping jobs, no rapid failed retries."""
    if not isinstance(runs, list) or len(runs) > 8:
        raise ValueError("UNTRUSTED_RUN_HISTORY")
    observed = []
    for item in runs:
        if not isinstance(item, dict) or item.get("head_branch") != "main":
            raise ValueError("UNTRUSTED_RUN_HISTORY")
        if type(item.get("id")) is not int or item["id"] <= 0:
            raise ValueError("INVALID_RUN_ID")
        created = when(item.get("created_at"))
        if created > now + MAX_FUTURE_SKEW:
            raise ValueError("RUN_CLOCK_IN_FUTURE")
        status = item.get("status")
        if status not in ACTIVE_STATUSES and status != "completed":
            raise ValueError("INVALID_RUN_STATUS")
        if status == "completed" and item.get("conclusion") not in TERMINAL_CONCLUSIONS:
            raise ValueError("INVALID_COMPLETED_CONCLUSION")
        observed.append((created, item))
    if not observed:
        return {"status": "READY_NO_PREVIOUS_RUN"}
    created, recent = max(observed, key=lambda pair: pair[0])
    out = {"last_run_id": recent["id"],
           "last_conclusion": recent.get("conclusion"),
           "last_created_utc": created.isoformat()}
    if recent["status"] != "completed":
        return dict(out, status="HOLD_EXISTING_WORKFLOW_ACTIVE")
    if (recent.get("conclusion") != "success"
        and now - created < FAILED_RETRY_BACKOFF):
        return dict(out, status="HOLD_FAILED_JOB_BACKOFF")
    if not bootstrap and now - created < CYCLE_COOLDOWN:
        return dict(out, status="HOLD_COOLDOWN")
    return dict(out, status="READY_TO_WAKE_EXISTING_CORE")


def candidate_order(now, *, bootstrap):
    if bootstrap:
        return list(LANES)
    # Rotate fairness so no organ can permanently starve under the 3-worker cap.
    offset = (int(now.timestamp()) // 10_800) % len(LANES)
    return list(LANES[offset:] + LANES[:offset])


def decide(histories, *, now, bootstrap=False):
    count = MAX_BOOTSTRAP if bootstrap else MAX_CYCLE
    out = []
    for name, workflow, inputs in candidate_order(now, bootstrap=bootstrap):
        data = histories.get(name, [])
        try:
            status = latest_decision(data, now=now, bootstrap=bootstrap)
        except (TypeError, ValueError, KeyError) as exc:
            status = {"status": "HOLD_UNTRUSTED_RUN_HISTORY",
                      "reason": type(exc).__name__}
        row = {"lane": name, "workflow": workflow, "inputs": inputs, **status}
        if row["status"].startswith("READY"):
            if count:
                row["status"] = "DISPATCH_PLANNED"
                count -= 1
            else:
                row["status"] = "HOLD_MAX_CYCLE_DISPATCHES"
        out.append(row)
    return out


def github(endpoint, token, payload=None):
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ValueError("MISSING_GITHUB_ACTIONS_TOKEN")
    url = BASE + endpoint
    req = Request(
        url, method="POST" if payload is not None else "GET",
        data=canonical(payload) if payload is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer " + token,
            "User-Agent": "JANUS-ESSENCE-ActiveEvolution/3.0",
        },
    )
    with urlopen(req, timeout=25) as response:
        if payload is not None:
            if response.status != 204:
                raise ValueError("WORKFLOW_DISPATCH_HTTP_NOT_204")
            return {}
        if response.status != 200:
            raise ValueError("WORKFLOW_HISTORY_HTTP_NOT_200")
        value = json.load(response)
        if not isinstance(value, dict):
            raise ValueError("WORKFLOW_HISTORY_INVALID_RESPONSE")
        return value


def execute(*, token, bootstrap, commit_sha):
    now = datetime.now(timezone.utc)
    if (os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_EVENT_NAME") not in
          ("push", "schedule", "workflow_dispatch")):
        raise ValueError("ACTIVE_EVOLUTION_REQUIRES_TRUSTED_MAIN")
    histories = {}
    unavailable = {}
    for name, filename, _ in LANES:
        try:
            response = github(quote(filename, safe="") + "/runs?branch=main&per_page=5", token)
            rows = response.get("workflow_runs")
            if not isinstance(rows, list) or len(rows) > 5:
                raise ValueError("INVALID_WORKFLOW_HISTORY")
            histories[name] = rows
        except Exception as exc:
            unavailable[name] = type(exc).__name__
            histories[name] = []
    rows = decide(histories, now=now, bootstrap=bootstrap)
    dispatched = 0
    for row in rows:
        if row["lane"] in unavailable:
            row["status"] = "HOLD_HISTORY_FETCH_FAILED"
            row["reason"] = unavailable[row["lane"]]
            continue
        if row["status"] != "DISPATCH_PLANNED":
            continue
        # A workflow_dispatch creates a real GitHub job, not evidence of
        # improvement; downstream fitness and blind tests decide independently.
        try:
            endpoint = quote(row["workflow"], safe="") + "/dispatches"
            github(endpoint, token, {"ref": "main", "inputs": row["inputs"]})
            row["status"] = "DISPATCH_ACCEPTED_BY_GITHUB_NOT_IMPROVEMENT"
            dispatched += 1
        except Exception as exc:
            row["status"] = "HOLD_DISPATCH_FAILED"
            row["reason"] = type(exc).__name__
    report = {
        "schema": SCHEMA,
        "timestamp_utc": now.isoformat(),
        "source_commit_sha": commit_sha,
        "mode": "ONE_SHOT_BOOTSTRAP" if bootstrap else "PERIODIC_RECONCILIATION",
        "repository": REPOSITORY,
        "lanes": rows,
        "dispatches_accepted": dispatched,
        "max_dispatched": MAX_BOOTSTRAP if bootstrap else MAX_CYCLE,
        "automatic_production_model_promotion": False,
        "automatic_main_code_changes_by_conductor": False,
        "no_external_workers": True,
        "scientific_improvement_proven_by_dispatch": False,
        "next_run_guaranteed": False,
        "proof_source": "Downstream workflows and SHA-pinned research checkpoint only"
    }
    report["receipt_sha256"] = sha(report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("bootstrap", "cycle"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    path = Path(args.out)
    if path.exists():
        raise ValueError("EVOLUTION_RECEIPT_MUST_BE_UNIQUE")
    report = execute(token=os.environ.get("GH_TOKEN", ""),
                     bootstrap=args.mode == "bootstrap",
                     commit_sha=os.environ.get("GITHUB_SHA", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "mode": report["mode"],
        "dispatches_accepted": report["dispatches_accepted"],
        "lanes": {x["lane"]: x["status"] for x in report["lanes"]},
        "production_authority": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
