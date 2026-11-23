#!/usr/bin/env python3
"""ESSENCE G9: bounded Sentinel schedule-gap recovery planner.

GitHub Actions schedules are best effort. This planner reads *actual* GitHub
schedule, workflow_dispatch and push run metadata for Sentinel A/B/C and
proposes at most ONE recovery-only workflow_dispatch per invocation.
It does not claim to repair the missing 24h natural-cron evidence: the
separate sentinel_cadence_audit remains the authoritative FAIL/PASS gate.

The default CLI only produces a plan; the explicitly separate workflow
dispatch step can act on a plan while checking repository, branch, event,
workflow allowlist and recent-work ceiling. No model/production promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "Hawkar-usls/Janus-Demiurge"
WORKFLOWS = {
    "A": "sentinel-node-a.yml",
    "B": "sentinel-node-b.yml",
    "C": "sentinel-node-c.yml",
}
SCHEMA = "janus.essence.g9.sentinel_cadence_recovery_plan/1.0"
MAX_SCHEDULE_AGE_MIN = 90
RECOVERY_COOLDOWN_MIN = 120
MAX_RESPONSE_BYTES = 3_000_000
MAX_RUNS_PER_NODE = 100


def utc(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and len(value) < 55:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("G9_BAD_TIME")
    if dt.tzinfo is None:
        raise ValueError("G9_TIME_MUST_BE_ZONE_AWARE")
    return dt.astimezone(timezone.utc)


def sha(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def plan(histories, now, *, repo=REPO):
    now = utc(now)
    if repo != REPO or not isinstance(histories, dict) or set(histories) != set(WORKFLOWS):
        raise ValueError("G9_UNTRUSTED_REPOSITORY_OR_ROLES")
    details = {}
    candidates = []
    for role, filename in WORKFLOWS.items():
        rows = histories[role]
        if not isinstance(rows, list) or len(rows) > MAX_RUNS_PER_NODE:
            raise ValueError("G9_UNTRUSTED_GITHUB_RUNS")
        seen = set()
        schedule = []
        any_recent = []
        for item in rows:
            if not isinstance(item, dict) or item.get("head_branch") != "main":
                continue
            if item.get("event") not in ("schedule", "workflow_dispatch", "push"):
                continue
            rid = item.get("id")
            if type(rid) is not int or rid <= 0 or rid in seen:
                raise ValueError("G9_UNTRUSTED_RUN_ID")
            seen.add(rid)
            created = utc(item.get("created_at"))
            if created > now + timedelta(seconds=60):
                raise ValueError("G9_FUTURE_RUN_TIMESTAMP")
            if now - timedelta(minutes=RECOVERY_COOLDOWN_MIN) <= created <= now:
                any_recent.append(item)
            if item["event"] == "schedule" and item.get("conclusion") == "success" and item.get("status") == "completed":
                schedule.append(created)
        latest_schedule = max(schedule, default=None)
        age = ((now-latest_schedule).total_seconds()/60) if latest_schedule else None
        # When a recently launched run exists, do not spam recovery, even if
        # its result is a failure or still in progress. A separate audit handles it.
        cooldown = bool(any_recent)
        stalled = latest_schedule is None or age > MAX_SCHEDULE_AGE_MIN
        eligible = stalled and not cooldown
        details[role] = {
            "workflow": filename,
            "last_successful_schedule_utc": latest_schedule.isoformat() if latest_schedule else None,
            "minutes_since_successful_schedule": round(age, 2) if age is not None else None,
            "recent_any_event_cooldown": cooldown,
            "needs_recovery": eligible,
            "successful_schedule_count_in_inventory": len(schedule),
        }
        if eligible:
            candidates.append((age if age is not None else float("inf"), role))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    chosen = candidates[0][1] if candidates else None
    result = {
        "schema": SCHEMA,
        "mode": "GITHUB_ACTIONS_RECOVERY_ONLY_NOT_CRON_PROOF",
        "repository": REPO,
        "evaluated_at_utc": now.isoformat(),
        "action": "DISPATCH_ONE_BOUNDED_RECOVERY" if chosen else "HOLD_NO_RECOVERY_NEEDED",
        "role": chosen,
        "workflow": WORKFLOWS[chosen] if chosen else None,
        "workflow_input": {"recovery_only": "true"} if chosen else None,
        "nodes": details,
        "maximum_dispatches_from_this_plan": 1,
        "physical_24h_cron_delivery_proven": False,
        "natural_schedule_events_fabricated": False,
        "changes_model_weights": False,
        "production_promotion": False,
        "common_github_failure_domain": True,
        "audit_separate_and_authoritative": "sentinel_cadence_audit.py",
    }
    result["sha256"] = sha(result)
    return result


def fetch_runs(role, token):
    if role not in WORKFLOWS or not token or len(token) > 4096:
        raise ValueError("G9_INVALID_SOURCE_OR_TOKEN")
    url = (f"https://api.github.com/repos/{REPO}/actions/workflows/"
           f"{WORKFLOWS[role]}/runs?per_page={MAX_RUNS_PER_NODE}&page=1")
    req = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "JANUS-ESSENCE-G9-Sentinel-Gap-Planner",
    })
    with urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise ValueError("G9_GITHUB_RUNS_HTTP_FAILURE")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("G9_ACTIONS_RESPONSE_TOO_LARGE")
    obj = json.loads(data)
    if not isinstance(obj, dict) or not isinstance(obj.get("workflow_runs"), list):
        raise ValueError("G9_INVALID_GITHUB_ACTIONS_RESPONSE")
    return obj["workflow_runs"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    result = plan({role: fetch_runs(role, token) for role in WORKFLOWS},
                  datetime.now(timezone.utc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"action": result["action"], "role": result["role"],
                      "sha256": result["sha256"]}))


if __name__ == "__main__":
    main()
