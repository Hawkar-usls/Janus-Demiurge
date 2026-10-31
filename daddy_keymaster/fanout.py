"""Bounded 4/8-way JANUS GitHub Actions CPU fanout with independent receipts.

Not a general cloud provisioning API. GitHub creates only ordinary short-lived
workers owned by this public repository. No arbitrary task, paid model call,
external provider enrollment, or promotion authority can be supplied at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from daddy_keymaster.broker import canonical, sha

SCHEMA = "janus.daddy_keymaster.fanout_worker.v1"
AUDIT_SCHEMA = "janus.daddy_keymaster.fanout_audit.v1"
WORKLOADS = (
    ("X64-01", "X64", "ubuntu-24.04", "test_daddy_keymaster.py"),
    ("ARM64-01", "ARM64", "ubuntu-24.04-arm", "test_daddy_keymaster_providers.py"),
    ("X64-02", "X64", "ubuntu-24.04", "test_daddy_keymaster_dynamic_pool.py"),
    ("ARM64-02", "ARM64", "ubuntu-24.04-arm", "test_daddy_keymaster_queue_rotation.py"),
    ("X64-03", "X64", "ubuntu-24.04", "test_daddy_keymaster_git_cas_state.py"),
    ("ARM64-03", "ARM64", "ubuntu-24.04-arm", "test_daddy_keymaster_compute.py"),
    ("X64-04", "X64", "ubuntu-24.04", "test_daddy_keymaster_bounded_ci.py"),
    ("ARM64-04", "ARM64", "ubuntu-24.04-arm", "test_rex_code_need_bridge.py"),
)
SOURCE_FILES = (
    "daddy_keymaster/fanout.py",
    "daddy_keymaster/POLICY.json",
    ".github/workflows/janus-daddy-keymaster-fanout.yml",
    "tests/test_daddy_keymaster_fanout.py",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID = re.compile(r"[0-9]{5,}\Z")
ATTEMPT = re.compile(r"[1-9][0-9]*\Z")


def plan(count: int) -> dict:
    if type(count) is not int or count not in (4, 8):
        raise ValueError("FANOUT_COUNT_MUST_BE_4_OR_8")
    return {"include": [
        {"id": wid, "arch": arch, "platform": label, "suite": suite}
        for wid, arch, label, suite in WORKLOADS[:count]
    ]}


def source_manifest(root: Path) -> dict:
    files = SOURCE_FILES + tuple(f"tests/{row[3]}" for row in WORKLOADS)
    return {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in files}


def check_env(env: dict, *, worker: bool = False) -> None:
    if (env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge"
            or env.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch", "push")
            or env.get("GITHUB_REF") != "refs/heads/main"
            or not SHA.fullmatch(env.get("GITHUB_SHA", ""))
            or not RUN_ID.fullmatch(env.get("GITHUB_RUN_ID", ""))
            or not ATTEMPT.fullmatch(env.get("GITHUB_RUN_ATTEMPT", ""))):
        raise ValueError("FANOUT_UNAUTHORIZED_CONTEXT")
    if worker and (env.get("GITHUB_JOB") != "worker"
                   or env.get("RUNNER_OS") != "Linux"
                   or env.get("RUNNER_ARCH") not in ("X64", "ARM64")):
        raise ValueError("FANOUT_UNAUTHORIZED_WORKER")


def execute(root: Path, env: dict, worker_id: str) -> dict:
    check_env(env, worker=True)
    match = next((x for x in WORKLOADS if x[0] == worker_id), None)
    if match is None or match[1] != env["RUNNER_ARCH"]:
        raise ValueError("FANOUT_SHARD_MISMATCH")
    repo_head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                        cwd=root, text=True).strip()
    if repo_head != env["GITHUB_SHA"]:
        raise ValueError("FANOUT_SOURCE_SHA_MISMATCH")
    suite = match[3]
    clean_env = {k: v for k, v in os.environ.items()
                 if not any(s in k.upper() for s in
                            ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY"))}
    p = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", suite, "-v"],
        cwd=root, env=clean_env, capture_output=True, text=True,
        timeout=150, check=False,
    )
    log = (p.stdout or "") + "\n" + (p.stderr or "")
    numbers = re.findall(r"Ran (\d+) tests? in ", log)
    if p.returncode != 0 or len(numbers) != 1 or "OK" not in log or int(numbers[0]) < 1:
        raise ValueError("FANOUT_SUITE_FAILED:" + suite)
    receipt = {
        "schema": SCHEMA, "status": "EXECUTED_ALLOWLISTED_TESTS",
        "worker_id": worker_id, "platform": match[1],
        "suite": suite, "cases": int(numbers[0]),
        "repository": env["GITHUB_REPOSITORY"], "run_id": env["GITHUB_RUN_ID"],
        "attempt": env["GITHUB_RUN_ATTEMPT"], "commit": env["GITHUB_SHA"],
        "runner_os": env["RUNNER_OS"], "source_manifest": source_manifest(root),
        "external_model_used": False, "paid_resources_used": False,
        "persistent_worker": False, "authority_delta": 0,
    }
    receipt["receipt_sha256"] = sha(receipt)
    return receipt


def audit(root: Path, receipts: list, env: dict, count: int) -> dict:
    check_env(env)
    expected = {row[0]: row for row in WORKLOADS[:count]} if count in (4, 8) else {}
    if len(expected) != count or len(receipts) != count:
        raise ValueError("FANOUT_MISSING_OR_EXTRA_RECEIPTS")
    source = source_manifest(root)
    seen = set()
    verified = []
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("FANOUT_RECEIPT_NOT_OBJECT")
        wid = receipt.get("worker_id")
        row = expected.get(wid)
        body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        if (row is None or wid in seen or receipt.get("schema") != SCHEMA
                or receipt.get("receipt_sha256") != sha(body)
                or receipt.get("status") != "EXECUTED_ALLOWLISTED_TESTS"
                or receipt.get("platform") != row[1]
                or receipt.get("suite") != row[3]
                or type(receipt.get("cases")) is not int
                or not 1 <= receipt["cases"] <= 10000
                or receipt.get("repository") != env["GITHUB_REPOSITORY"]
                or receipt.get("run_id") != env["GITHUB_RUN_ID"]
                or receipt.get("attempt") != env["GITHUB_RUN_ATTEMPT"]
                or receipt.get("commit") != env["GITHUB_SHA"]
                or receipt.get("runner_os") != "Linux"
                or receipt.get("source_manifest") != source
                or receipt.get("external_model_used") is not False
                or receipt.get("paid_resources_used") is not False
                or receipt.get("persistent_worker") is not False
                or receipt.get("authority_delta") != 0):
            raise ValueError("FANOUT_INVALID_OR_DUPLICATE_RECEIPT")
        seen.add(wid)
        verified.append({
            "worker_id": wid, "platform": row[1], "suite": row[3],
            "cases": receipt["cases"], "receipt_sha256": receipt["receipt_sha256"],
        })
    if seen != set(expected):
        raise ValueError("FANOUT_MISSING_WORKER")
    result = {
        "schema": AUDIT_SCHEMA,
        "status": f"{count}_EPHEMERAL_WORKERS_VERIFIED",
        "run_id": env["GITHUB_RUN_ID"], "attempt": env["GITHUB_RUN_ATTEMPT"],
        "commit": env["GITHUB_SHA"], "repository": env["GITHUB_REPOSITORY"],
        "workers": sorted(verified, key=lambda x: x["worker_id"]),
        "source_manifest": source,
        "max_parallel": 4, "scheduled_worker_count": 4,
        "manual_worker_count": 8, "worker_job_timeout_minutes": 6,
        "no_arbitrary_dispatch": True, "paid_resources_used": False,
        "persistent_capacity_claim": False, "authority_delta": 0,
    }
    result["receipt_sha256"] = sha(result)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=("plan", "execute", "audit"))
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--worker-id")
    p.add_argument("--inputs", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.operation == "plan":
        print(json.dumps(plan(a.count), separators=(",", ":")))
        return
    if a.output is None:
        p.error("--output required")
    if a.operation == "execute":
        if a.worker_id is None:
            p.error("--worker-id required")
        record = execute(a.root, os.environ, a.worker_id)
    else:
        if a.inputs is None:
            p.error("--inputs required")
        files = sorted(a.inputs.glob("fanout-*/EXECUTION.json"))
        if len(files) != a.count:
            raise ValueError("FANOUT_INPUT_COUNT_MISMATCH")
        receipts = []
        for file in files:
            if file.stat().st_size > 25000:
                raise ValueError("FANOUT_RECEIPT_TOO_LARGE")
            receipts.append(json.loads(file.read_text(encoding="utf-8")))
        record = audit(a.root, receipts, os.environ, a.count)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(canonical(record) + b"\n")
    print(json.dumps({"status": record["status"],
                      "receipt_sha256": record["receipt_sha256"]}))


if __name__ == "__main__":
    main()
