"""Bounded, read-only task-to-worker rotation preview for DADDY_KEYMASTER.

This module deliberately NEVER creates a runner, dispatches a workflow, grants
access, or publishes a candidate model. Queue/lease persistence and execution
are separate, security-reviewed production milestones.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from daddy_keymaster.broker import (
    ID, PROVIDERS, TYPES, build_registry, canonical, check_policy, clock,
    load, sha, utc_now,
)

SCHEMA = "janus.daddy_keymaster.dynamic_queue.v1"
RESULT_SCHEMA = "janus.daddy_keymaster.rotation_preview.v1"
PHASE = "R2_SEALED"
MAX_TASKS = 64
MAX_PARALLEL = 2  # Deliberately immutable in R0. Raise only after the R2 gates.


def _validate_queue(queue):
    if (queue.get("schema") != SCHEMA or
        not isinstance(queue.get("tasks"), list) or
        len(queue["tasks"]) > MAX_TASKS or
        not isinstance(queue.get("usage"), dict) or
        len(queue["usage"]) > 32):
        raise ValueError("DADDY_ROTATION_QUEUE_REFUSED")
    for name, count in queue["usage"].items():
        if (not isinstance(name, str) or not ID.fullmatch(name) or
            type(count) is not int or not 0 <= count <= 1000000):
            raise ValueError("DADDY_ROTATION_USAGE_INVALID")
    ids = set()
    for task in queue["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("DADDY_ROTATION_TASK_NOT_OBJECT")
        tid = task.get("id")
        if (not isinstance(tid, str) or not ID.fullmatch(tid) or tid in ids or
            task.get("kind") not in TYPES or
            type(task.get("cpu")) is not int or not 1 <= task["cpu"] <= 8 or
            type(task.get("max_seconds")) is not int or
            not 1 <= task["max_seconds"] <= 600 or
            type(task.get("priority")) is not int or
            task["priority"] not in (0, 1, 2) or
            task.get("access") != "PUBLIC_OR_SYNTHETIC_ONLY" or
            task.get("contains_secrets") is not False or
            task.get("exec") is not None or
            task.get("status") not in ("QUEUED", "LEASED", "COMPLETE", "HOLD")):
            raise ValueError("DADDY_ROTATION_TASK_ADMISSION_REFUSED")
        ids.add(tid)
        if task["status"] == "LEASED":
            wid = task.get("worker_id")
            if not isinstance(wid, str) or not ID.fullmatch(wid):
                raise ValueError("DADDY_ROTATION_LEASE_WORKER_INVALID")
            clock(task.get("lease_until"))
        elif "worker_id" in task or "lease_until" in task:
            raise ValueError("DADDY_ROTATION_STALE_LEASE_FIELDS")
    return queue


def preview(policy, registry, queue, now):
    """Plan one permitted task per presently available worker, without dispatch.

    Expired leases remain HOLD, never get silently replayed. Worker affinity
    rotates by previous usage; history is an input, not fabricated by the plan.
    """
    check_policy(policy)
    clock(now)
    _validate_queue(queue)
    if not isinstance(registry.get("active"), list):
        raise ValueError("DADDY_ROTATION_REGISTRY_INVALID")

    ready = {}
    for worker in registry["active"]:
        if not isinstance(worker, dict):
            raise ValueError("DADDY_ROTATION_WORKER_INVALID")
        wid, provider = worker.get("id"), worker.get("provider")
        if (not isinstance(wid, str) or not ID.fullmatch(wid) or
            wid in ready or provider not in PROVIDERS or
            not policy["providers"][provider]["enabled"] or
            type(worker.get("cpu")) is not int or not 1 <= worker["cpu"] <= 16 or
            not isinstance(worker.get("allowed_tasks"), list) or
            set(worker["allowed_tasks"]) - set(TYPES)):
            raise ValueError("DADDY_ROTATION_WORKER_NOT_ADMITTED")
        if provider == "github_actions":
            if (worker.get("state") != "CURRENT_JOB_ONLY" or
                worker.get("authorization") != "GITHUB_OWNED_RUNNER_CONTEXT" or
                worker.get("observed_at") != now or
                worker.get("expires_at") != now):
                raise ValueError("DADDY_ROTATION_GHA_NOT_CURRENT_JOB")
        elif worker.get("state") != "OWNER_REGISTERED_HEARTBEAT":
            raise ValueError("DADDY_ROTATION_EXTERNAL_NOT_REGISTERED")
        ready[wid] = worker

    reserved = set()
    hold = []
    completed = []
    for task in queue["tasks"]:
        if task["status"] == "LEASED":
            # Even an expired lease may have performed side effects.
            # Reconcile the exact execution receipt before any retry.
            reserved.add(task["worker_id"])
            hold.append({
                "task_id": task["id"],
                "reason": ("HOLD_EXPIRED_LEASE_RECONCILE" if
                           clock(task["lease_until"]) <= clock(now) else
                           "WAIT_ACTIVE_LEASE"),
            })
        elif task["status"] == "COMPLETE":
            completed.append(task["id"])

    provider_occupancy = {p: 0 for p in PROVIDERS}
    for wid in reserved:
        if wid in ready:
            provider_occupancy[ready[wid]["provider"]] += 1
    assignments = []
    used = set(reserved)
    available_tasks = sorted(
        (t for t in queue["tasks"] if t["status"] == "QUEUED"),
        key=lambda t: (-t["priority"], t["id"]),
    )
    for task in available_tasks:
        if len(assignments) + sum(wid in ready for wid in reserved) >= MAX_PARALLEL:
            hold.append({"task_id": task["id"], "reason": "WAIT_PARALLEL_CEILING"})
            continue
        candidates = [
            w for wid, w in ready.items()
            if wid not in used and task["kind"] in w["allowed_tasks"]
            and w["cpu"] >= task["cpu"]
            and provider_occupancy[w["provider"]] <
                policy["providers"][w["provider"]]["max_concurrent_tasks"]
        ]
        if not candidates:
            hold.append({"task_id": task["id"], "reason": "WAIT_AUTHORIZED_CAPACITY"})
            continue
        worker = min(candidates, key=lambda w: (
            queue["usage"].get(w["id"], 0), w["cpu"], w["id"]
        ))
        used.add(worker["id"])
        provider_occupancy[worker["provider"]] += 1
        assignments.append({
            "task_id": task["id"], "worker_id": worker["id"],
            "provider": worker["provider"], "max_seconds": task["max_seconds"],
            "status": "PREVIEW_ONLY_NO_LEASE_NO_DISPATCH",
        })

    result = {
        "schema": RESULT_SCHEMA,
        "phase": PHASE, "at": now,
        "source_policy_sha256": sha(policy),
        "source_registry_sha256": sha(registry),
        "source_queue_sha256": sha(queue),
        "max_parallel": MAX_PARALLEL,
        "assignments": assignments,
        "held": sorted(hold, key=lambda x: x["task_id"]),
        "completed_task_ids": sorted(completed),
        "runners_provisioned": 0, "actions_dispatched": 0,
        "lease_mutations": 0, "authority_delta": 0,
        "production_promotion": False,
        "status": "DRY_RUN_ROTATION_PREVIEW_ONLY",
    }
    result["receipt_sha256"] = sha(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path("daddy_keymaster/POLICY.json"))
    parser.add_argument("--registry", type=Path, default=Path("daddy_keymaster/OWNER_REGISTRY.json"))
    parser.add_argument("--queue", type=Path, default=Path("daddy_keymaster/DYNAMIC_POOL_QUEUE_EXAMPLE.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    policy = load(args.policy)
    now = utc_now()
    roster = build_registry(policy, load(args.registry), now)
    output = preview(policy, roster, load(args.queue), now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(output) + b"\n")
    print(json.dumps({"status": output["status"],
                      "planned": len(output["assignments"]),
                      "held": len(output["held"]),
                      "receipt_sha256": output["receipt_sha256"]}))


if __name__ == "__main__":
    main()
