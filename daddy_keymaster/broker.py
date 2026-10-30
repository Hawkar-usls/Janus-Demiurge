"""JANUS DADDY_KEYMASTER: permission-first multi-provider compute broker.

Discovery means reading owner-approved registrations or observing this *current*
GitHub Actions job. It never scans hosts, creates cloud instances, submits BOINC
work, connects to Ray clusters or executes remote commands.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "janus.daddy_keymaster.report.v1"
PROVIDERS = ("github_actions", "oracle_always_free", "boinc_volunteer", "ray_cluster")
TYPES = ("contract_test", "readonly_index", "pure_module_eval")
ID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
RUN = re.compile(r"^[0-9]{5,}$")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def clock(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("DADDY_TIME_FORMAT")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("DADDY_TIME_FORMAT") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("DADDY_TIME_NOT_UTC")
    return parsed


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path, maximum=100000):
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError("DADDY_INPUT_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("DADDY_OBJECT_REQUIRED")
    return obj


def check_policy(policy):
    if (policy.get("schema") != "janus.daddy_keymaster.policy.v1" or
        policy.get("enabled") is not True or
        policy.get("automatic_remote_dispatch") is not False or
        policy.get("cloud_provisioning") is not False or
        policy.get("paid_resources") is not False or
        policy.get("host_scanning") is not False or
        policy.get("permission_escalation") is not False or
        policy.get("authority_delta") != 0 or
        set(policy.get("providers", {})) != set(PROVIDERS) or
        policy.get("allowed_task_kinds") != list(TYPES)):
        raise ValueError("DADDY_POLICY_REFUSED")
    for p in PROVIDERS:
        entry = policy["providers"][p]
        if (entry.get("source") != p or entry.get("owner_authorization_required") is not True or
            entry.get("max_concurrent_tasks") != 1 or
            entry.get("free_only") is not True or
            type(entry.get("enabled")) is not bool):
            raise ValueError("DADDY_PROVIDER_POLICY_REFUSED:" + p)
    if any(policy["providers"][p]["enabled"] for p in PROVIDERS if p != "github_actions"):
        raise ValueError("DADDY_REMOTE_PROVIDER_MUST_START_DISABLED")
    return policy


def validate_approved_registry(registry):
    """Only an owner-reviewed file is accepted; never public-host discovery."""
    if (registry.get("schema") != "janus.daddy_keymaster.owner_registry.v1" or
        registry.get("authority_delta") != 0 or
        not isinstance(registry.get("workers"), list) or len(registry["workers"]) > 32):
        raise ValueError("DADDY_REGISTRY_REFUSED")
    seen = set()
    for worker in registry["workers"]:
        if not isinstance(worker, dict):
            raise ValueError("DADDY_WORKER_NOT_OBJECT")
        name, provider = worker.get("id"), worker.get("provider")
        if (not isinstance(name, str) or not ID.fullmatch(name) or
            name in seen or provider not in PROVIDERS or provider == "github_actions"):
            raise ValueError("DADDY_WORKER_ID_OR_PROVIDER")
        seen.add(name)
        authority = worker.get("authorization", {})
        if (authority.get("kind") != "OWNER_REVIEWED_REGISTRATION" or
            authority.get("approved") is not True or
            authority.get("revoked") is not False or
            not isinstance(authority.get("approved_by"), str) or
            authority.get("approved_by") != "Hawkar-usls"):
            raise ValueError("DADDY_WORKER_NOT_AUTHORIZED")
        if (not isinstance(worker.get("heartbeat_at"), str) or
            not isinstance(authority.get("expires_at"), str) or
            not isinstance(worker.get("allowed_tasks"), list) or
            not worker["allowed_tasks"] or
            set(worker["allowed_tasks"]) - set(TYPES) or
            not isinstance(worker.get("cpu"), int) or type(worker["cpu"]) is bool or
            not 1 <= worker["cpu"] <= 16 or
            worker.get("gpu", 0) != 0 or
            worker.get("monthly_cost_usd") != 0):
            raise ValueError("DADDY_WORKER_CAPACITY_OR_COST")
        clock(worker["heartbeat_at"])
        clock(authority["expires_at"])
    return registry


def observe_github(env, policy, now):
    if not policy["providers"]["github_actions"]["enabled"]:
        return None
    if (env.get("GITHUB_ACTIONS") != "true" or
        env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge" or
        not RUN.fullmatch(env.get("GITHUB_RUN_ID", "")) or
        not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", "")) or
        not env.get("RUNNER_OS", "").startswith("Linux")):
        return None
    return {
        "id": "gha-" + env["GITHUB_RUN_ID"] + "-" + env["GITHUB_RUN_ATTEMPT"],
        "provider": "github_actions",
        "state": "CURRENT_JOB_ONLY",
        "observed_at": now,
        "expires_at": now,
        "cpu": min(os.cpu_count() or 1, 8),
        "gpu": 0,
        "allowed_tasks": list(TYPES),
        "authorization": "GITHUB_OWNED_RUNNER_CONTEXT",
        "authority_delta": 0,
    }


def build_registry(policy, approved_registry, now, env=None):
    check_policy(policy)
    validate_approved_registry(approved_registry)
    current = clock(now)
    active = []
    excluded = []
    gha = observe_github(env if env is not None else os.environ, policy, now)
    if gha is not None:
        active.append(gha)
    for worker in approved_registry["workers"]:
        # Owner permission is NEVER inferred from reachability or a published URL.
        when, until = clock(worker["heartbeat_at"]), clock(worker["authorization"]["expires_at"])
        provider = worker["provider"]
        if not policy["providers"][provider]["enabled"]:
            reason = "ADAPTER_NOT_ACTIVATED"
        elif until <= current:
            reason = "LEASE_EXPIRED"
        elif when > current:
            reason = "FUTURE_HEARTBEAT"
        elif current - when > timedelta(minutes=30):
            reason = "STALE_HEARTBEAT"
        else:
            reason = "READY"
        if reason != "READY":
            excluded.append({"id": worker["id"], "provider": provider, "reason": reason})
            continue
        active.append({
            "id": worker["id"], "provider": provider, "state": "OWNER_REGISTERED_HEARTBEAT",
            "observed_at": worker["heartbeat_at"], "expires_at": worker["authorization"]["expires_at"],
            "cpu": worker["cpu"], "gpu": 0, "allowed_tasks": worker["allowed_tasks"],
            "authorization": "OWNER_REVIEWED_REGISTRATION", "authority_delta": 0
        })
    configured = {p: {"configured": policy["providers"][p]["enabled"],
                       "ready_workers": sum(w["provider"] == p for w in active)}
                  for p in PROVIDERS}
    return {"active": sorted(active, key=lambda w: w["id"]),
            "excluded": sorted(excluded, key=lambda w: w["id"]),
            "provider_status": configured}


def plan(tasks, registry):
    if (tasks.get("schema") != "janus.daddy_keymaster.tasks.v1" or
        not isinstance(tasks.get("tasks"), list) or len(tasks["tasks"]) > 16):
        raise ValueError("DADDY_TASKS_REFUSED")
    ready = list(registry["active"])
    used = set()
    assigned, blocked = [], []
    seen = set()
    for task in tasks["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("DADDY_TASK_MALFORMED")
        name, kind, cpu, seconds = (task.get("id"), task.get("kind"),
                                     task.get("cpu"), task.get("max_seconds"))
        if (not isinstance(name, str) or not ID.fullmatch(name) or name in seen or
            kind not in TYPES or type(cpu) is not int or not 1 <= cpu <= 8 or
            type(seconds) is not int or not 1 <= seconds <= 600 or
            task.get("access") != "PUBLIC_OR_SYNTHETIC_ONLY" or
            task.get("contains_secrets") is not False or
            task.get("exec") is not None):
            raise ValueError("DADDY_TASK_ADMISSION_REFUSED")
        seen.add(name)
        # GHA worker is only usable inside its own currently running job.
        candidates = [w for w in ready if w["id"] not in used and
                      kind in w["allowed_tasks"] and w["cpu"] >= cpu]
        if not candidates:
            blocked.append({"task_id": name, "status": "WAIT_NO_AUTHORIZED_CAPACITY"})
        else:
            selected = sorted(candidates, key=lambda w: (w["cpu"], w["id"]))[0]
            used.add(selected["id"])
            assigned.append({"task_id": name, "worker_id": selected["id"],
                             "provider": selected["provider"],
                             "status": "DRY_RUN_NOT_DISPATCHED"})
    return {"assigned": assigned, "blocked": blocked}


def report(policy, owner_registry, tasks, now, env=None):
    registry = build_registry(policy, owner_registry, now, env)
    decision = plan(tasks, registry)
    result = {"schema": SCHEMA, "name": "JANUS DADDY_KEYMASTER",
              "observed_at": now, "providers": registry["provider_status"],
              "active": registry["active"], "excluded": registry["excluded"],
              "scheduler": decision, "source_registry_sha256": sha(owner_registry),
              "policy_sha256": sha(policy), "tasks_sha256": sha(tasks),
              "status": "DRY_RUN_NO_REMOTE_DISPATCH",
              "automatic_remote_dispatch": False, "authority_delta": 0,
              "paid_resources_used": False, "external_instances_created": 0}
    result["receipt_sha256"] = sha(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("daddy_keymaster/POLICY.json"))
    parser.add_argument("--registry", type=Path, default=Path("daddy_keymaster/OWNER_REGISTRY.json"))
    parser.add_argument("--tasks", type=Path, default=Path("daddy_keymaster/TASKS.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now", default=None)
    args = parser.parse_args()
    now = args.now or utc_now()
    clock(now)
    result = report(load(args.policy), load(args.registry), load(args.tasks), now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"status": result["status"],
                      "ready": len(result["active"]),
                      "waiting": len(result["scheduler"]["blocked"]),
                      "receipt_sha256": result["receipt_sha256"]}))


if __name__ == "__main__":
    main()
