#!/usr/bin/env python3
"""ESSENCE v2.3: bounded GitHub-native continuous research coordination.

One short pulse can wake existing verified research / organogenesis workflows.
No permanent runner, no arbitrary code execution, no model or main mutation,
no cross-repository writes, no automatic scientific/production promotion.

The orchestration signal is source change + workflow history, not an assertion
that a new model or module has improved. The existing downstream gates retain
all authority. GitHub cron is best-effort, not a real-time guarantee.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SCHEMA = "janus.essence.continuous_pulse/2.3"
BASE = "https://api.github.com/repos/"
TARGET = "Hawkar-usls/Janus-Demiurge"
MAX_DISPATCHES_PER_PULSE = 2
RETRY_BACKOFF = timedelta(hours=2)
DISPATCH_COOLDOWN = timedelta(minutes=35)
CLOCK_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class Lane:
    name: str
    workflow: str
    source_repo: str
    source_ref: str
    source_paths: tuple[str, ...]
    max_idle: timedelta

LANES = (
    Lane("missing_module_discovery", "janus-rex-need-discovery.yml",
         TARGET, "main", ("rex/lifecycle_runs", "rex/runs",
                          "rex/need_discovery_policy.json"),
         timedelta(hours=3)),
    Lane("self_module_proposals", "janus-self-module-actuator.yml",
         "Hawkar-usls/janus-meta-registry",
         "janus/native-self-memory-modular-organism-v1",
         ("JANUS/PATCHES/PROPOSALS",), timedelta(hours=6)),
    Lane("fresh_dated_training_source", "essence-v22-source-watch.yml",
         "Hawkar-usls/janus-meta-registry", "main", ("data",),
         timedelta(hours=6)),
    Lane("peer_lessons", "essence-peer-inbox-v13.yml",
         TARGET, "main", ("research/essence/peer_v13/inbox.json",),
         timedelta(hours=6)),
)

def iso(value):
    if not isinstance(value, str):
        raise ValueError("UNTRUSTED_TIMESTAMP")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("UNTRUSTED_TIMESTAMP") from exc
    if t.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return t.astimezone(timezone.utc)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def source_decision(lane, latest_changes, runs, *, now):
    """Pure, fail-closed orchestration; never uses untrusted workflow names."""
    if now.tzinfo is None:
        raise ValueError("NAIVE_CURRENT_TIME")
    for name, record in (("changes", latest_changes), ("runs", runs)):
        if type(record) is not list or len(record) > 8:
            raise ValueError("UNTRUSTED_" + name.upper())
    changes = []
    for c in latest_changes:
        if not isinstance(c, dict):
            raise ValueError("UNTRUSTED_SOURCE_COMMIT")
        source_sha = c.get("sha")
        date = c.get("commit", {}).get("committer", {}).get("date")
        if (not isinstance(source_sha, str) or len(source_sha) != 40
            or any(x not in "0123456789abcdef" for x in source_sha)):
            raise ValueError("UNPINNED_SOURCE_COMMIT")
        changes.append((iso(date), source_sha))
    if not changes:
        return {"lane": lane.name, "status": "HOLD_NO_SOURCE_COMMITS"}
    newest, source_sha = max(changes)
    if newest > now + CLOCK_TOLERANCE:
        return {"lane": lane.name, "status": "HOLD_FUTURE_SOURCE_TIME"}

    examined = []
    for run in runs:
        if not isinstance(run, dict) or run.get("head_branch") != "main":
            raise ValueError("UNTRUSTED_WORKFLOW_HISTORY")
        rid = run.get("id")
        status = run.get("status")
        conclusion = run.get("conclusion")
        if (type(rid) is not int or rid <= 0 or
            status not in ("queued", "requested", "waiting", "pending",
                           "in_progress", "completed") or
            (status == "completed" and conclusion not in
             ("success", "failure", "cancelled", "timed_out", "skipped",
              "action_required", "startup_failure", "neutral", "stale"))):
            raise ValueError("UNTRUSTED_WORKFLOW_HISTORY")
        created = iso(run.get("created_at"))
        if created > now + CLOCK_TOLERANCE:
            raise ValueError("FUTURE_RUN_CLOCK")
        examined.append((created, run))
    newest_run = max(examined, key=lambda x: x[0]) if examined else None
    evidence = {"lane": lane.name, "source_sha": source_sha,
                "latest_source_time": newest.isoformat(),
                "workflow": lane.workflow,
                "last_workflow_run": newest_run[1]["id"] if newest_run else None}
    if newest_run is not None:
        created, run = newest_run
        if run["status"] != "completed":
            return {**evidence, "status": "HOLD_WORKER_ALREADY_RUNNING"}
        if now - created < DISPATCH_COOLDOWN:
            return {**evidence, "status": "HOLD_DISPATCH_COOLDOWN"}
        if run["conclusion"] != "success" and now - created < RETRY_BACKOFF:
            return {**evidence, "status": "HOLD_WORKER_RETRY_BACKOFF"}
        if (newest <= created and now - created < lane.max_idle
            and run["conclusion"] == "success"):
            return {**evidence, "status": "HOLD_NO_NEW_INPUT"}
    # The maximum idle check is a periodic fallback for backdated Git commits,
    # not proof of data novelty. Downstream actions must deduplicate again.
    return {**evidence, "status": "READY_EXISTING_GATED_WORKFLOW"}


def api_json(url, token, *, payload=None):
    if not token or len(token) > 4096:
        raise ValueError("MISSING_GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "Bearer " + token,
        "User-Agent": "JANUS-ESSENCE-Pulse/2.3"
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, headers=headers,
                      data=canonical(payload) if payload is not None else None,
                      method="POST" if payload is not None else "GET")
    with urlopen(request, timeout=25) as response:
        if payload is not None:
            if response.status != 204:
                raise ValueError("DISPATCH_NOT_CONFIRMED_BY_API")
            return {}
        obj = json.load(response)
        if not isinstance(obj, (dict, list)):
            raise ValueError("UNTRUSTED_GITHUB_RESPONSE")
        return obj


def fetch_inputs(lane, token):
    changes = []
    for path in lane.source_paths:
        params = urlencode({"sha": lane.source_ref, "path": path, "per_page": 1})
        url = BASE + lane.source_repo + "/commits?" + params
        data = api_json(url, token)
        if not isinstance(data, list) or len(data) > 1:
            raise ValueError("UNTRUSTED_SOURCE_HISTORY")
        changes.extend(data)
    workflow = quote(lane.workflow, safe="")
    url = (BASE + TARGET + "/actions/workflows/" + workflow
           + "/runs?branch=main&per_page=5")
    data = api_json(url, token)
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise ValueError("UNTRUSTED_ACTION_HISTORY")
    return changes, data["workflow_runs"]


def plan(lane_inputs, *, now):
    """One pulse cannot spin up unbounded descendants."""
    decisions = []
    budget = MAX_DISPATCHES_PER_PULSE
    for lane in LANES:
        try:
            changes, runs = lane_inputs[lane.name]
            item = source_decision(lane, changes, runs, now=now)
        except (ValueError, KeyError, TypeError) as error:
            item = {"lane": lane.name, "status": "HOLD_UNTRUSTED_EVIDENCE",
                    "reason": type(error).__name__ + ": " + str(error)[:80]}
        if item["status"] == "READY_EXISTING_GATED_WORKFLOW":
            if budget:
                item["status"] = "DISPATCH_PLANNED"
                budget -= 1
            else:
                item["status"] = "HOLD_PULSE_CAPACITY"
        decisions.append(item)
    return decisions


def run(*, token, do_dispatch):
    if do_dispatch and (
        os.environ.get("GITHUB_REF") != "refs/heads/main" or
        os.environ.get("GITHUB_EVENT_NAME") not in
        ("push", "schedule", "workflow_dispatch")):
        raise ValueError("WRITE_DISPATCH_REQUIRES_MAIN_TRUSTED_EVENT")
    now = datetime.now(timezone.utc)
    inputs = {}
    source_failures = {}
    for lane in LANES:
        try:
            inputs[lane.name] = fetch_inputs(lane, token)
        except Exception as error:
            # Fail closed per lane: outage in one evidence source must not
            # become a fabricated successful lesson or unbounded retry storm.
            inputs[lane.name] = ([], [])
            source_failures[lane.name] = type(error).__name__
    decisions = plan(inputs, now=now)
    dispatched = 0
    for item in decisions:
        if item["lane"] in source_failures:
            item["status"] = "HOLD_SOURCE_FETCH_FAILED"
            item["reason"] = source_failures[item["lane"]]
        if item["status"] != "DISPATCH_PLANNED":
            continue
        if not do_dispatch:
            item["status"] = "DRY_RUN_ONLY"
            continue
        lane = next(x for x in LANES if x.name == item["lane"])
        try:
            url = BASE + TARGET + "/actions/workflows/" + quote(lane.workflow, safe="") + "/dispatches"
            api_json(url, token, payload={"ref": "main"})
            item["status"] = "DISPATCH_REQUESTED_NOT_WORKER_PASS"
            dispatched += 1
        except Exception as error:
            item["status"] = "HOLD_DISPATCH_FAILED"
            item["reason"] = type(error).__name__
    receipt = {
        "schema": SCHEMA,
        "checked_at_utc": now.isoformat(),
        "target": TARGET,
        "pulse_interval_expected_minutes": 15,
        "interval_guaranteed": False,
        "max_dispatched_workflows": MAX_DISPATCHES_PER_PULSE,
        "requested_dispatches": dispatched,
        "lanes": decisions,
        "external_blind_improvement_proven": False,
        "module_candidate_is_trusted_code": False,
        "arbitrary_workflow_dispatch": False,
        "self_governance_override": False,
        "automatic_production_model_promotion": False,
        "automatic_merge": False,
        "main_code_changed_by_pulse": False
    }
    receipt["receipt_sha256"] = sha256(receipt)
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    destination = Path(args.out)
    if destination.exists():
        raise FileExistsError("IMMUTABLE_PULSE_RECEIPT")
    result = run(token=os.environ.get("GH_TOKEN", ""), do_dispatch=args.execute)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False,
                                      sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"schema": SCHEMA,
                      "requested_dispatches": result["requested_dispatches"],
                      "statuses": {x["lane"]: x["status"] for x in result["lanes"]},
                      "production_authority": False}))


if __name__ == "__main__":
    main()
