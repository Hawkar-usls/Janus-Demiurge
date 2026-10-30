"""JANUS DADDY_KEYMASTER: authorized ephemeral GitHub Actions workers.

Execute an exact, human-reviewed allowlist of existing JANUS test workloads
inside separate owned public-repo runners. No API for remote dispatch, no
provider secrets, network probes, untrusted task commands, arbitrary scripts,
long-running rented workers or shell commands.
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

SCHEMA = "janus.daddy_keymaster.github_compute_receipt.v1"
AUDIT_SCHEMA = "janus.daddy_keymaster.github_compute_audit.v1"
SUITES = ("test_daddy_keymaster.py", "test_daddy_keymaster_providers.py",
          "test_rex_code_need_bridge.py")
SOURCES = ("daddy_keymaster/compute.py", "daddy_keymaster/broker.py",
           "daddy_keymaster/providers.py", "daddy_keymaster/POLICY.json",
           "tests/test_daddy_keymaster.py", "tests/test_daddy_keymaster_providers.py",
           "tests/test_rex_code_need_bridge.py")
ARCH = ("X64", "ARM64")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
RUN = re.compile(r"^[0-9]{5,}$")
ATTEMPT = re.compile(r"^[1-9][0-9]*$")


def manifest(root):
    root = Path(root)
    return {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in SOURCES}


def check_env(env, *, allow_arch=True):
    if (env.get("GITHUB_ACTIONS") != "true" or
        env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge" or
        env.get("GITHUB_EVENT_NAME") not in ("push", "pull_request", "workflow_dispatch") or
        not COMMIT.fullmatch(env.get("GITHUB_SHA", "")) or
        not RUN.fullmatch(env.get("GITHUB_RUN_ID", "")) or
        not ATTEMPT.fullmatch(env.get("GITHUB_RUN_ATTEMPT", "")) or
        env.get("RUNNER_OS") != "Linux" or
        (allow_arch and env.get("RUNNER_ARCH") not in ARCH)):
        raise ValueError("DADDY_COMPUTE_UNAUTHORIZED_RUN_CONTEXT")
    return env


def execute(root, env):
    check_env(env)
    root = Path(root)
    if env.get("GITHUB_JOB") != "worker":
        raise ValueError("DADDY_COMPUTE_NOT_IN_WORKER_JOB")
    if (subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                       capture_output=True, text=True, check=True).stdout.strip()
            != env["GITHUB_SHA"]):
        raise ValueError("DADDY_COMPUTE_SOURCE_SHA_MISMATCH")
    file_hashes = manifest(root)
    executed = []
    for suite in SUITES:
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s",
                            "tests", "-p", suite, "-v"], cwd=root, text=True,
                           capture_output=True, timeout=120, check=False,
                           env={k:v for k,v in os.environ.items()
                                if not any(x in k.upper() for x in
                                           ("TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY"))})
        log = p.stdout + "\n" + p.stderr
        matches = re.findall(r"Ran (\d+) tests? in ", log)
        if p.returncode != 0 or len(matches) != 1 or "OK" not in log or int(matches[0]) < 1:
            raise ValueError("DADDY_COMPUTE_TEST_FAILURE:" + suite)
        executed.append({"suite": suite, "cases": int(matches[0]), "status": "PASS"})
    result = {
        "schema": SCHEMA, "run_id": env["GITHUB_RUN_ID"],
        "attempt": env["GITHUB_RUN_ATTEMPT"], "commit": env["GITHUB_SHA"],
        "repository": env["GITHUB_REPOSITORY"],
        "platform": env["RUNNER_ARCH"], "runner_os": env["RUNNER_OS"],
        "source_manifest": file_hashes, "suites": executed,
        "status": "EXECUTED_ALLOWLISTED_TESTS", "auth": "PUBLIC_REPO_GITHUB_RUNNER",
        "external_provider_activation": False, "paid_work": False,
        "arbitrary_code_from_research": False, "authority_delta": 0,
    }
    result["receipt_sha256"] = sha(result)
    return result


def audit(root, receipts, env):
    check_env(env, allow_arch=False)
    if len(receipts) != 2:
        raise ValueError("DADDY_COMPUTE_TWO_RECEIPTS_REQUIRED")
    local = manifest(root)
    seen = set()
    verified = []
    common = None
    for r in receipts:
        if not isinstance(r, dict):
            raise ValueError("DADDY_COMPUTE_RECEIPT_MALFORMED")
        body = {k:v for k,v in r.items() if k != "receipt_sha256"}
        if (r.get("schema") != SCHEMA or r.get("receipt_sha256") != sha(body) or
            r.get("run_id") != env["GITHUB_RUN_ID"] or
            r.get("attempt") != env["GITHUB_RUN_ATTEMPT"] or
            r.get("repository") != env["GITHUB_REPOSITORY"] or
            r.get("commit") != env["GITHUB_SHA"] or
            r.get("runner_os") != "Linux" or
            r.get("platform") not in ARCH or
            r.get("source_manifest") != local or
            r.get("status") != "EXECUTED_ALLOWLISTED_TESTS" or
            r.get("auth") != "PUBLIC_REPO_GITHUB_RUNNER" or
            r.get("external_provider_activation") is not False or
            r.get("paid_work") is not False or
            r.get("arbitrary_code_from_research") is not False or
            r.get("authority_delta") != 0):
            raise ValueError("DADDY_COMPUTE_UNVERIFIED_RECEIPT")
        platform = r["platform"]
        if platform in seen:
            raise ValueError("DADDY_COMPUTE_DUPLICATE_PLATFORM")
        seen.add(platform)
        suites = r.get("suites")
        if (not isinstance(suites, list) or len(suites) != len(SUITES) or
            [s.get("suite") for s in suites if isinstance(s, dict)] != list(SUITES) or
            any(not isinstance(s, dict) or s.get("status") != "PASS" or
                type(s.get("cases")) is not int or not 1 <= s["cases"] <= 10000
                for s in suites)):
            raise ValueError("DADDY_COMPUTE_UNVERIFIED_SUITES")
        counts = {s["suite"]: s["cases"] for s in suites}
        if common is not None and common != counts:
            raise ValueError("DADDY_COMPUTE_ARCH_TEST_DISAGREEMENT")
        common = counts
        verified.append({"platform": platform, "receipt_sha256": r["receipt_sha256"],
                         "cases": counts})
    if seen != set(ARCH):
        raise ValueError("DADDY_COMPUTE_ARCH_PAIR_INCOMPLETE")
    result = {
        "schema": AUDIT_SCHEMA, "status": "TWO_EPHEMERAL_WORKERS_VERIFIED",
        "run_id": env["GITHUB_RUN_ID"], "attempt": env["GITHUB_RUN_ATTEMPT"],
        "commit": env["GITHUB_SHA"], "repository": env["GITHUB_REPOSITORY"],
        "workers": sorted(verified, key=lambda row: row["platform"]),
        "total_test_cases_per_worker": sum(common.values()),
        "cross_architecture_agreement": True, "source_manifest": local,
        "worker_lease_after_job": False, "persistent_capacity_claim": False,
        "actual_remote_oracle_boinc_ray_used": False,
        "claims_full_distributed_recovery": False, "paid_resources_used": False,
        "authority_delta": 0,
    }
    result["receipt_sha256"] = sha(result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("operation", choices=("execute", "audit"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--inputs", type=Path)
    args = ap.parse_args()
    if args.operation == "execute":
        result = execute(args.root, os.environ)
    else:
        if args.inputs is None:
            ap.error("audit requires --inputs")
        rows = []
        for arch in ("x64", "arm64"):
            file = args.inputs / ("daddy-compute-" + arch) / "EXECUTION.json"
            if file.stat().st_size > 30000:
                raise ValueError("DADDY_COMPUTE_OVERSIZE_RECEIPT")
            rows.append(json.loads(file.read_text()))
        result = audit(args.root, rows, os.environ)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"status": result["status"],
                      "receipt_sha256": result["receipt_sha256"],
                      "authority_delta": 0}))


if __name__ == "__main__":
    main()
