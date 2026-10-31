"""DADDY_KEYMASTER two-process Ray-local smoke on ONE ephemeral GitHub CPU VM.

This is NOT a private multi-node Ray cluster, an external provider activation,
persistent capacity, or authorization to dispatch code to non-owned machines.
Only two static synthetic SHA-256 tasks; dashboard disabled, jobs API unused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "janus.daddy_keymaster.ray_local_cpu_sandbox.v1"
SLOTS = ("RAY-LOCAL-1", "RAY-LOCAL-2")
SEEDS = (1408, 20261101)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def expected(slot: str, seed: int) -> str:
    if slot not in SLOTS or type(seed) is not int or seed != SEEDS[SLOTS.index(slot)]:
        raise ValueError("RAY_SANDBOX_TASK_NOT_ALLOWLISTED")
    return hashlib.sha256(f"JANUS|RAY_LOCAL|{slot}|{seed}".encode()).hexdigest()


def check_context(env: dict):
    if (env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge"
            or env.get("GITHUB_EVENT_NAME") not in ("pull_request", "push", "workflow_dispatch")
            or not re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", ""))
            or not re.fullmatch(r"[0-9]{5,}", env.get("GITHUB_RUN_ID", ""))):
        raise ValueError("RAY_SANDBOX_UNAUTHORIZED_CONTEXT")


def run_sandbox(env: dict):
    check_context(env)
    import ray

    @ray.remote(num_cpus=1, max_restarts=0)
    class FixedWorker:
        def __init__(self, slot):
            if slot not in SLOTS:
                raise ValueError("RAY_SANDBOX_UNKNOWN_ACTOR")
            self.slot = slot

        def verify(self, seed):
            if seed != SEEDS[SLOTS.index(self.slot)]:
                raise ValueError("RAY_SANDBOX_UNAPPROVED_WORK")
            return {
                "slot": self.slot,
                "pid": os.getpid(),
                "digest": expected(self.slot, seed),
            }

    try:
        ray.init(num_cpus=2, include_dashboard=False, log_to_driver=False,
                 logging_level="ERROR")
        nodes = [n for n in ray.nodes() if n.get("Alive")]
        if len(nodes) != 1:
            raise ValueError("RAY_SANDBOX_NOT_SINGLE_GITHUB_NODE")
        actors = [FixedWorker.remote(slot) for slot in SLOTS]
        got = ray.get([actor.verify.remote(seed)
                       for actor, seed in zip(actors, SEEDS)], timeout=75)
        if (len(got) != 2 or len({row["pid"] for row in got}) != 2
                or set(row["slot"] for row in got) != set(SLOTS)):
            raise ValueError("RAY_SANDBOX_MISSING_INDEPENDENT_PROCESSES")
        for row in got:
            if row["digest"] != expected(row["slot"], SEEDS[SLOTS.index(row["slot"])]):
                raise ValueError("RAY_SANDBOX_INDEPENDENT_DIGEST_MISMATCH")
        record = {
            "schema": SCHEMA,
            "status": "TWO_RAY_LOCAL_PROCESSES_VERIFIED_SINGLE_EPHEMERAL_VM",
            "repository": env["GITHUB_REPOSITORY"],
            "run_id": env["GITHUB_RUN_ID"],
            "control_sha": env["GITHUB_SHA"],
            "ray_version": ray.__version__,
            "local_nodes": len(nodes),
            "separate_processes": 2,
            "tasks": [{"slot": row["slot"], "digest": row["digest"]}
                      for row in sorted(got, key=lambda row: row["slot"])],
            "ray_dashboard_enabled": False,
            "external_provider_activated": False,
            "private_distributed_cluster_verified": False,
            "persistent_compute_capacity": False,
            "paid_provider_requested": False,
            "authority_delta": 0,
        }
        record["receipt_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
        return record
    finally:
        ray.shutdown()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = run_sandbox(os.environ)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("xb") as f:
        f.write(canonical(result) + b"\n")
    print(json.dumps({"status": result["status"],
                      "receipt_sha256": result["receipt_sha256"],
                      "private_distributed_cluster_verified": False}))


if __name__ == "__main__":
    main()
