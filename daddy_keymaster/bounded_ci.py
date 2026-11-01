"""Bounded project-CI heartbeat on an authorized Git CAS queue.

Not an AI inference service, general-purpose cloud dispatcher, or self-requeue.
Use only GitHub Actions repo-related tests on schedule/manual main, with an
isolated state worktree and SHA-bound receipts.
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

from daddy_keymaster.broker import canonical, check_policy, load, sha, utc_now
from daddy_keymaster.queue_rotation import rotate_if_ready, status as archive_status
from daddy_keymaster.git_cas_queue import (
    Conflict, GitCAS, RUNTIME_BRANCH, claim, checkpoint, complete,
    enqueue, reconcile_expired, skip_unclaimed_obsolete, verify,
)

KINDS = ("contract_test", "pure_module_eval")
SUITES = {
    "contract_test": "test_daddy_keymaster_git_cas_state.py",
    "pure_module_eval": "test_daddy_keymaster_dynamic_pool.py",
}
ARCH_TASK = {"X64": "contract_test", "ARM64": "pure_module_eval"}
MAX_ATTEMPTS = 3


def context(env=None):
    env = dict(os.environ if env is None else env)
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge"
        or env.get("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch", "push")
        or env.get("GITHUB_REF") != "refs/heads/main"
        or not re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", ""))
        or not re.fullmatch(r"[0-9]{5,}", env.get("GITHUB_RUN_ID", ""))
        or env.get("JANUS_DADDY_CI_RUNTIME") != "TRUE"
        or env.get("JANUS_RELAY_CAS_WRITE_AUTHORIZED") != "TRUE"):
        raise ValueError("DADDY_HEARTBEAT_UNAUTHORIZED_CONTEXT")
    return env


def _source(env):
    return hashlib.sha256(env["GITHUB_SHA"].encode()).hexdigest()


def _task_id(kind, env):
    return ("ci-contract-" if kind == "contract_test" else "ci-eval-") + env["GITHUB_SHA"]


def _check_source(env, source_root):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   cwd=source_root, text=True).strip()
    if head != env["GITHUB_SHA"]:
        raise ValueError("DADDY_SOURCE_HEAD_MISMATCH")
    policy = load(Path(source_root) / "daddy_keymaster/POLICY.json")
    check_policy(policy)
    if policy["automatic_remote_dispatch"] is not False:
        raise ValueError("DADDY_UNAPPROVED_REMOTE_DISPATCH")
    return head


def _advance(store, operation, *, max_attempts=MAX_ATTEMPTS):
    """Re-read and recompute one safe event on conflict, with a hard ceiling."""
    for attempt in range(max_attempts):
        head, state = store.read()
        next_state, result = operation(state)
        if next_state is state or next_state == state:
            return result
        if next_state["epoch"] != state["epoch"] + 1:
            raise ValueError("DADDY_MULTI_EVENT_MUTATION_REFUSED")
        try:
            store.compare_and_swap(head, state, next_state)
            return result
        except Conflict:
            if attempt + 1 == max_attempts:
                raise
    raise Conflict("DADDY_RETRY_BUDGET_EXHAUSTED")


def prepare(store, env, *, now):
    """Idempotent per-source task pair, with a verified terminal-only rollover."""
    source = _source(env)
    # Fail closed before ANY obsolete-task drain. A delayed retry of a
    # previously archived main SHA must be read-only: it has no right to
    # supersede a newer queued generation, even if its own tasks are terminal.
    already = archive_status(store, source)
    if already["current_already_archived"]:
        if any(row["source_sha256"] == source for row in already["state"]["tasks"].values()):
            raise ValueError("DADDY_ARCHIVE_DUPLICATE_SOURCE_IN_ACTIVE")
        return {"status": "VERSION_ALREADY_ARCHIVED",
                "source_sha256": source, "epoch": already["state"]["epoch"],
                "queued": 0, "held": 0, "no_remote_dispatch": True}
    # Archive fully completed prior sources in one atomic Git ref update.
    first = rotate_if_ready(store, source)
    if first["status"] == "UNRESOLVED_LEASE":
        raise ValueError("DADDY_ARCHIVE_UNCERTAIN_LEASE_HOLD")
    # Old QUEUED work is explicitly superseded, never silently dropped.
    for _ in range(32):
        skipped = _advance(store, lambda state: skip_unclaimed_obsolete(state, source))
        if skipped is None:
            break
    else:
        raise ValueError("DADDY_SUPERSEDED_DRAIN_LIMIT")
    second = rotate_if_ready(store, source)
    if second["status"] == "UNRESOLVED_LEASE":
        raise ValueError("DADDY_ARCHIVE_UNCERTAIN_LEASE_HOLD")
    archive = archive_status(store, source)
    if archive["current_already_archived"]:
        if any(r["source_sha256"] == source for r in archive["state"]["tasks"].values()):
            raise ValueError("DADDY_ARCHIVE_DUPLICATE_SOURCE_IN_ACTIVE")
        return {"status": "VERSION_ALREADY_ARCHIVED",
                "source_sha256": source, "epoch": archive["state"]["epoch"],
                "queued": 0, "held": 0, "no_remote_dispatch": True}
    for kind in KINDS:
        tid = _task_id(kind, env)
        def add(state):
            if tid in state["tasks"]:
                if (state["tasks"][tid]["source_sha256"] != source or
                    state["tasks"][tid]["kind"] != kind):
                    raise ValueError("DADDY_TASK_ID_REBOUND")
                return state, "EXISTS"
            return enqueue(state, tid, kind, source,
                           priority=(2 if kind == "contract_test" else 1),
                           max_seconds=300), "QUEUED"
        _advance(store, add)
    for _ in range(2):
        def recover(state):
            nxt, held = reconcile_expired(state, now=now)
            if not held:
                return state, []
            if len(held) > 1:
                from daddy_keymaster.git_cas_queue import _append
                row = state["tasks"][held[0]]
                nxt = _append(state, "HOLD", held[0], {
                    "generation": row["generation"],
                    "reason": "EXPIRED_OUTCOME_UNCERTAIN",
                })
            return nxt, [held[0]]
        held = _advance(store, recover)
        if not held:
            break
    state = store.read()[1]
    return {"status": "BOUNDED_VERSION_QUEUE_READY",
            "source_sha256": source, "epoch": state["epoch"],
            "queued": sum(v["state"] == "QUEUED" for v in state["tasks"].values()),
            "held": sum(v["state"] == "HOLD" for v in state["tasks"].values()),
            "no_remote_dispatch": True}


def take(store, env, arch, *, now):
    if arch not in ARCH_TASK:
        raise ValueError("DADDY_UNKNOWN_ARCH")
    kind = ARCH_TASK[arch]
    holder = "gha-" + env["GITHUB_RUN_ID"] + "-" + arch.lower()
    tid = _task_id(kind, env)
    def select(state):
        row = state["tasks"].get(tid)
        if row is None:
            # Archived exact source identities remain terminal. A future
            # source revert must not silently rerun a historical test.
            archived = archive_status(store, _source(env))
            if archived["current_already_archived"]:
                return state, None
            raise ValueError("DADDY_TASK_NOT_QUEUED")
        if row["state"] == "COMPLETE":
            return state, None
        if row["state"] != "QUEUED":
            return state, None
        next_state, token = claim(state, holder, [kind], 2, now=now)
        if token and token["task_id"] != tid:
            raise ValueError("DADDY_UNEXPECTED_TASK_CLAIMED")
        return next_state, token
    return _advance(store, select)


def run_contract(token, env, source_root, *, timeout=240):
    """Run only hard-coded unit test selections from the checked-out project."""
    if token is None:
        return {"status": "NO_NEW_CI_TASK", "source_sha256": _source(env)}
    kind = "contract_test" if token["task_id"].startswith("ci-contract-") else "pure_module_eval"
    if (token["source_sha256"] != _source(env) or
        token["task_id"] != _task_id(kind, env)):
        raise ValueError("DADDY_RECEIPT_TASK_MISMATCH")
    if env.get("RUNNER_ARCH") not in ARCH_TASK or ARCH_TASK[env["RUNNER_ARCH"]] != kind:
        raise ValueError("DADDY_WORKER_KIND_ARCH_MISMATCH")
    suite = SUITES[kind]
    cmd = [sys.executable, "-m", "unittest", "discover",
           "-s", "tests", "-p", suite, "-v"]
    try:
        p = subprocess.run(cmd, cwd=source_root, capture_output=True,
                           text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError("DADDY_CI_TEST_TIMEOUT_HOLD")
    if p.returncode:
        raise RuntimeError("DADDY_CI_TEST_FAILED_HOLD:" + p.stderr[-500:])
    receipt = {
        "schema": "janus.daddy_keymaster.bounded_ci_result.v1",
        "status": "ALLOWLISTED_TEST_SUITE_PASSED",
        "source_sha256": _source(env),
        "task_id": token["task_id"], "holder": token["holder"],
        "generation": token["generation"],
        "suite": suite, "worker_arch": env.get("RUNNER_ARCH"),
        "run_id": env["GITHUB_RUN_ID"],
        "stdout_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(p.stderr.encode()).hexdigest(),
        "external_effects": 0, "model_promotions": 0,
    }
    receipt["receipt_sha256"] = sha(receipt)
    return receipt


def finish(store, env, token, receipt, *, now):
    if token is None:
        if receipt.get("status") != "NO_NEW_CI_TASK":
            raise ValueError("DADDY_EMPTY_TASK_RECEIPT_MISMATCH")
        return "IDLE"
    body = dict(receipt)
    observed = body.pop("receipt_sha256", None)
    if observed != sha(body) or body.get("status") != "ALLOWLISTED_TEST_SUITE_PASSED":
        raise ValueError("DADDY_INVALID_RESULT_RECEIPT")
    if (body["task_id"] != token["task_id"] or
        body["source_sha256"] != _source(env) or
        body["run_id"] != env["GITHUB_RUN_ID"] or
        body.get("external_effects") != 0 or
        body.get("model_promotions") != 0):
        raise ValueError("DADDY_RECEIPT_NOT_SOURCE_BOUND")
    # Result artifact must be uploaded BEFORE checkpoint/complete. Workflow
    # transports it for independent Witness; this function cannot attest upload.
    def next_event(state, function):
        row = state["tasks"].get(token["task_id"])
        if row is None or row["state"] != "LEASED":
            raise ValueError("DADDY_LEASE_NOT_LIVE")
        return function(state), "COMMITTED"
    _advance(store, lambda state: next_event(
        state, lambda s: checkpoint(s, token, observed, now=now)))
    _advance(store, lambda state: next_event(
        state, lambda s: complete(s, token, observed, now=now)))
    return "COMPLETE"


def audit(state, receipts, source_sha, run_id):
    verify(state)
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not run_id.isdigit():
        raise ValueError("DADDY_AUDIT_CONTEXT")
    source = hashlib.sha256(source_sha.encode()).hexdigest()
    seen = set()
    for receipt in receipts:
        if receipt.get("status") == "NO_NEW_CI_TASK":
            continue
        body = {k:v for k,v in receipt.items() if k != "receipt_sha256"}
        if sha(body) != receipt.get("receipt_sha256"):
            raise ValueError("DADDY_AUDIT_HASH_MISMATCH")
        tid = receipt.get("task_id")
        row = state["tasks"].get(tid, {})
        if (tid in seen or receipt.get("run_id") != run_id or
            receipt.get("source_sha256") != source or
            receipt.get("worker_arch") not in ARCH_TASK or
            ARCH_TASK[receipt["worker_arch"]] != row.get("kind") or
            receipt.get("suite") != SUITES.get(row.get("kind")) or
            row.get("holder") != receipt.get("holder") or
            row.get("generation") != receipt.get("generation") or
            row.get("state") != "COMPLETE" or
            row.get("result_sha256") != receipt["receipt_sha256"] or
            row.get("checkpoint_sha256") != receipt["receipt_sha256"] or
            receipt.get("external_effects") != 0):
            raise ValueError("DADDY_AUDIT_RECEIPT_NOT_COMMITTED")
        seen.add(tid)
    for tid, row in state["tasks"].items():
        if (row["state"] == "COMPLETE" and
            isinstance(row["holder"], str) and
            row["holder"].startswith("gha-" + run_id + "-") and
            tid not in seen):
            raise ValueError("DADDY_AUDIT_MISSING_COMMITTED_RECEIPT")
    if any(row["state"] == "HOLD" for row in state["tasks"].values()):
        raise ValueError("DADDY_WITNESS_UNRESOLVED_HOLD")
    return {"status": "INDEPENDENT_BOUND_CI_WITNESS",
            "verified_receipts": len(seen), "queue_epoch": state["epoch"],
            "tip_sha256": state["tip_sha256"], "production_promotion": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("prepare", "claim", "execute", "finish", "audit"))
    p.add_argument("--state-repo", type=Path)
    p.add_argument("--source-root", type=Path, default=Path("."))
    p.add_argument("--arch", choices=("X64", "ARM64"))
    p.add_argument("--token-file", type=Path)
    p.add_argument("--receipt-file", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    env = context()
    _check_source(env, args.source_root)
    store = GitCAS(args.state_repo, branch=RUNTIME_BRANCH) if args.state_repo else None
    if args.stage != "execute" and store is None:
        raise ValueError("DADDY_STATE_REPO_REQUIRED")
    if args.stage == "prepare":
        result = prepare(store, env, now=utc_now())
    elif args.stage == "claim":
        if args.arch is None:
            raise ValueError("DADDY_ARCH_REQUIRED")
        result = take(store, env, args.arch, now=utc_now())
    elif args.stage == "execute":
        if args.token_file is None:
            raise ValueError("DADDY_TOKEN_FILE_REQUIRED")
        result = run_contract(json.loads(args.token_file.read_text()),
                              env, args.source_root)
    elif args.stage == "finish":
        if args.token_file is None or args.receipt_file is None:
            raise ValueError("DADDY_RECEIPT_REQUIRED")
        result = finish(store, env,
                        json.loads(args.token_file.read_text()),
                        json.loads(args.receipt_file.read_text()), now=utc_now())
    else:
        # Witness can evaluate two artifacts produced by separate workers.
        if args.receipt_file is None:
            raise ValueError("DADDY_WITNESS_RECEIPTS_REQUIRED")
        receipts = json.loads(args.receipt_file.read_text())
        result = audit(store.read()[1], receipts,
                       env["GITHUB_SHA"], env["GITHUB_RUN_ID"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"stage": args.stage, "status": result.get("status") if isinstance(result,dict) else result,
                      "no_remote_dispatch": True}, sort_keys=True))


if __name__ == "__main__":
    main()
