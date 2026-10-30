"""Persist truthful post-run roster: ephemeral CI workers are not leased capacity."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from daddy_keymaster.broker import PROVIDERS, canonical, sha, clock


def finalize(observation):
    claimed = observation.get("receipt_sha256")
    body = {k: v for k, v in observation.items() if k != "receipt_sha256"}
    if (observation.get("schema") != "janus.daddy_keymaster.report.v1" or
        claimed != sha(body) or
        observation.get("status") != "DRY_RUN_NO_REMOTE_DISPATCH" or
        observation.get("authority_delta") != 0 or
        observation.get("automatic_remote_dispatch") is not False or
        observation.get("external_instances_created") != 0 or
        set(observation.get("providers", {})) != set(PROVIDERS) or
        not isinstance(observation.get("active"), list)):
        raise ValueError("DADDY_ROSTER_SOURCE_REJECTED")
    clock(observation.get("observed_at"))
    persistent = []
    retired = []
    for worker in observation["active"]:
        if not isinstance(worker, dict) or worker.get("authority_delta") != 0:
            raise ValueError("DADDY_ROSTER_WORKER_INVALID")
        if worker.get("provider") == "github_actions":
            if (worker.get("state") != "CURRENT_JOB_ONLY" or
                worker.get("authorization") != "GITHUB_OWNED_RUNNER_CONTEXT" or
                worker.get("expires_at") != observation["observed_at"]):
                raise ValueError("DADDY_ROSTER_EPHEMERAL_BINDING")
            retired.append({"id": worker["id"], "provider": "github_actions",
                            "reason": "CURRENT_JOB_ONLY_NEVER_PERSIST_AS_AVAILABLE"})
        else:
            # v0.1 cannot prove that remotely registered nodes remain live
            # once this check ends. Preserve their evidence, not execution rights.
            retired.append({"id": worker["id"], "provider": worker.get("provider"),
                            "reason": "REQUIRES_FRESH_AUTHENTICATED_HEARTBEAT"})
    result = {
        "schema": "janus.daddy_keymaster.persistent_roster.v1",
        "name": "JANUS DADDY_KEYMASTER",
        "source_receipt_sha256": claimed,
        "last_observation_at": observation["observed_at"],
        "available_outside_witness_job": persistent,
        "last_seen_now_unavailable": retired,
        "source_provider_status": observation["providers"],
        "persistent_provider_ready_counts": {p: 0 for p in PROVIDERS},
        "status": "NO_PERSISTENT_CAPACITY_ATTESTED",
        "remote_dispatch_authority": False,
        "authority_delta": 0,
        "law": "EPHEMERAL_ACTIONS_RUNNER_NE_PERSISTENT_WORKER",
    }
    result["roster_sha256"] = sha(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.receipt.read_bytes()
    if len(raw) > 100000:
        raise ValueError("DADDY_ROSTER_INPUT_TOO_LARGE")
    result = finalize(json.loads(raw))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"status": result["status"], "outside_run_capacity": 0,
                      "source_receipt_sha256": result["source_receipt_sha256"]}))


if __name__ == "__main__":
    main()
