"""JANUS DADDY_KEYMASTER Git-CAS durable queue (R2 staging).

Git fast-forward-only updates provide cross-process compare-and-swap when
each proposed commit has the *observed* head as its single parent. This is a
bounded synthetic control-plane proof, NOT a production dispatcher or GitHub
Actions compute-service loop. No arbitrary shell task execution or secrets.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import re
import subprocess

from daddy_keymaster.broker import ID, TYPES, canonical, clock, sha

SCHEMA = "janus.daddy_keymaster.git_cas_queue.v1"
ZERO = "0" * 64
STATE_PATH = "state/relay_queue.json"
BRANCH = "janus/daddy-keymaster-cas-lab-20261031"
HEX = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
MAX_TASKS = 32
MAX_ACTIVE = 2
MAX_EVENTS = 256


class Conflict(RuntimeError):
    """Current state moved; caller MUST re-fetch and re-evaluate authorization."""


def _exact(obj, fields):
    if not isinstance(obj, dict) or set(obj) != set(fields):
        raise ValueError("CAS_UNEXPECTED_FIELDS")


def _id(s):
    if not isinstance(s, str) or not ID.fullmatch(s):
        raise ValueError("CAS_INVALID_ID")
    return s


def _sha(s):
    if not isinstance(s, str) or not HEX.fullmatch(s):
        raise ValueError("CAS_INVALID_SHA256")
    return s


def empty():
    return {"schema": SCHEMA, "epoch": 0, "tip_sha256": ZERO,
            "tasks": {}, "events": []}


def _transition(tasks, kind, tid, detail):
    """Replay an allowlisted event; return only verified state fields."""
    if kind == "ENQUEUE":
        _exact(detail, ("kind", "source_sha256", "priority", "cpu", "max_seconds"))
        if tid in tasks or len(tasks) >= MAX_TASKS:
            raise ValueError("CAS_DUPLICATE_OR_LIMIT")
        if (detail["kind"] not in TYPES or
            type(detail["cpu"]) is not int or not 1 <= detail["cpu"] <= 8 or
            type(detail["max_seconds"]) is not int or not 1 <= detail["max_seconds"] <= 600 or
            type(detail["priority"]) is not int or detail["priority"] not in (0, 1, 2)):
            raise ValueError("CAS_TASK_NOT_ADMITTED")
        _sha(detail["source_sha256"])
        tasks[tid] = {
            "kind": detail["kind"], "source_sha256": detail["source_sha256"],
            "priority": detail["priority"], "cpu": detail["cpu"],
            "max_seconds": detail["max_seconds"], "state": "QUEUED",
            "generation": 0, "holder": None, "lease_until": None,
            "checkpoint_sha256": None, "result_sha256": None,
        }
        return
    row = tasks.get(tid)
    if row is None:
        raise ValueError("CAS_TASK_NOT_FOUND")
    if kind == "CLAIM":
        _exact(detail, ("holder", "generation", "lease_until"))
        _id(detail["holder"])
        clock(detail["lease_until"])
        if (row["state"] != "QUEUED" or
            type(detail["generation"]) is not int or
            detail["generation"] != row["generation"] + 1):
            raise ValueError("CAS_INVALID_CLAIM")
        if sum(v["state"] == "LEASED" for v in tasks.values()) >= MAX_ACTIVE:
            raise ValueError("CAS_PARALLEL_LIMIT")
        if any(v["state"] == "LEASED" and v["holder"] == detail["holder"]
               for v in tasks.values()):
            raise ValueError("CAS_ONE_TASK_PER_WORKER")
        row.update(state="LEASED", generation=detail["generation"],
                   holder=detail["holder"], lease_until=detail["lease_until"])
    elif kind == "CHECKPOINT":
        _exact(detail, ("holder", "generation", "content_sha256"))
        _token_matches(row, detail)
        row["checkpoint_sha256"] = _sha(detail["content_sha256"])
    elif kind == "COMPLETE":
        _exact(detail, ("holder", "generation", "result_sha256",
                        "checkpoint_sha256"))
        _token_matches(row, detail)
        if (row["checkpoint_sha256"] is None or
            row["checkpoint_sha256"] != detail["checkpoint_sha256"]):
            raise ValueError("CAS_MISSING_CHECKPOINT")
        row.update(state="COMPLETE", result_sha256=_sha(detail["result_sha256"]))
    elif kind == "HOLD":
        _exact(detail, ("generation", "reason"))
        if (row["state"] != "LEASED" or
            type(detail["generation"]) is not int or
            row["generation"] != detail["generation"] or
            detail["reason"] != "EXPIRED_OUTCOME_UNCERTAIN"):
            raise ValueError("CAS_HOLD_ONLY_AFTER_UNCERTAIN_LEASE")
        row["state"] = "HOLD"
    else:
        raise ValueError("CAS_UNKNOWN_EVENT")


def _token_matches(row, d):
    if (row["state"] != "LEASED" or d["holder"] != row["holder"] or
        type(d["generation"]) is not int or
        d["generation"] != row["generation"]):
        raise ValueError("CAS_STALE_FENCE")


def verify(state):
    _exact(state, ("schema", "epoch", "tip_sha256", "tasks", "events"))
    if (state["schema"] != SCHEMA or
        not isinstance(state["events"], list) or len(state["events"]) > MAX_EVENTS or
        type(state["epoch"]) is not int or
        state["epoch"] != len(state["events"]) or
        not isinstance(state["tasks"], dict)):
        raise ValueError("CAS_BAD_STATE")
    tasks, tip = {}, ZERO
    for i, event in enumerate(state["events"], 1):
        _exact(event, ("seq", "kind", "task_id", "detail",
                       "previous_sha256", "event_sha256"))
        _id(event["task_id"])
        body = {k: event[k] for k in ("seq", "kind", "task_id",
                                     "detail", "previous_sha256")}
        if (type(event["seq"]) is not int or event["seq"] != i or
            event["previous_sha256"] != tip or
            event["event_sha256"] != sha(body)):
            raise ValueError("CAS_EVENT_CHAIN_INVALID")
        _transition(tasks, event["kind"], event["task_id"], event["detail"])
        tip = event["event_sha256"]
    if state["tip_sha256"] != tip or state["tasks"] != tasks:
        raise ValueError("CAS_STATE_PROJECTION_INVALID")
    return state


def _append(state, kind, tid, detail):
    state = json.loads(canonical(verify(state)))
    if len(state["events"]) >= MAX_EVENTS:
        raise ValueError("CAS_HISTORY_FULL")
    _id(tid)
    _transition(state["tasks"], kind, tid, detail)
    body = {"seq": state["epoch"] + 1, "kind": kind, "task_id": tid,
            "detail": detail, "previous_sha256": state["tip_sha256"]}
    digest = sha(body)
    state["events"].append({**body, "event_sha256": digest})
    state["epoch"] += 1
    state["tip_sha256"] = digest
    return verify(state)


def enqueue(state, task_id, kind, source_sha256, *, priority=1, cpu=1,
            max_seconds=120):
    return _append(state, "ENQUEUE", task_id, {
        "kind": kind, "source_sha256": source_sha256, "priority": priority,
        "cpu": cpu, "max_seconds": max_seconds,
    })


def claim(state, holder, allowed_kinds, cpu, *, now):
    """Pure choice; only subsequent successful CAS establishes ownership."""
    verify(state)
    _id(holder)
    clock(now)
    if (not isinstance(allowed_kinds, (tuple, list)) or
        not allowed_kinds or set(allowed_kinds) - set(TYPES) or
        type(cpu) is not int or not 1 <= cpu <= 16):
        raise ValueError("CAS_WORKER_NOT_ADMITTED")
    if sum(v["state"] == "LEASED" for v in state["tasks"].values()) >= MAX_ACTIVE:
        return state, None
    if any(v["state"] == "LEASED" and v["holder"] == holder
           for v in state["tasks"].values()):
        return state, None
    options = sorted(
        ((tid, task) for tid, task in state["tasks"].items()
         if task["state"] == "QUEUED" and task["kind"] in allowed_kinds
         and task["cpu"] <= cpu),
        key=lambda x: (-x[1]["priority"], x[0]))
    if not options:
        return state, None
    tid, task = options[0]
    until = (clock(now) + timedelta(seconds=task["max_seconds"])
             ).isoformat().replace("+00:00", "Z")
    gen = task["generation"] + 1
    new = _append(state, "CLAIM", tid,
                  {"holder": holder, "generation": gen, "lease_until": until})
    return new, {"task_id": tid, "holder": holder, "generation": gen,
                 "source_sha256": task["source_sha256"], "lease_until": until}


def _verify_token(state, token, now):
    clock(now)
    _exact(token, ("task_id", "holder", "generation", "source_sha256", "lease_until"))
    row = state["tasks"].get(_id(token["task_id"]))
    if row is None:
        raise ValueError("CAS_TASK_NOT_FOUND")
    _token_matches(row, token)
    if (row["source_sha256"] != token["source_sha256"] or
        row["lease_until"] != token["lease_until"] or
        clock(now) >= clock(row["lease_until"])):
        raise ValueError("CAS_STALE_OR_EXPIRED_TOKEN")
    return row


def checkpoint(state, token, checksum, *, now):
    verify(state)
    _sha(checksum)
    _verify_token(state, token, now)
    return _append(state, "CHECKPOINT", token["task_id"], {
        "holder": token["holder"], "generation": token["generation"],
        "content_sha256": checksum,
    })


def complete(state, token, checksum, *, now):
    verify(state)
    _sha(checksum)
    row = _verify_token(state, token, now)
    if row["checkpoint_sha256"] is None:
        raise ValueError("CAS_NO_CHECKPOINT")
    return _append(state, "COMPLETE", token["task_id"], {
        "holder": token["holder"], "generation": token["generation"],
        "checkpoint_sha256": row["checkpoint_sha256"],
        "result_sha256": checksum,
    })


def reconcile_expired(state, *, now):
    verify(state)
    clock(now)
    held = []
    for tid, row in sorted(state["tasks"].items()):
        if row["state"] == "LEASED" and clock(now) >= clock(row["lease_until"]):
            state = _append(state, "HOLD", tid,
                            {"generation": row["generation"],
                             "reason": "EXPIRED_OUTCOME_UNCERTAIN"})
            held.append(tid)
    return state, held


def _git(repo, *args, input_bytes=None, check=True):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes, capture_output=True, check=False, timeout=30,
    )
    if check and result.returncode:
        raise RuntimeError("CAS_GIT_IO_FAILED: " + result.stderr.decode(errors="replace")[-500:])
    return result


class GitCAS:
    """Fast-forward Git ref store for a *dedicated lab branch* and clean clone.

    A GitHub-hosted PR runner MUST NOT call write: pull requests are read-only.
    A production adapter needs scoped credentials, durable witness and quotas.
    """

    def __init__(self, repo, branch=BRANCH):
        if branch != BRANCH:
            raise ValueError("CAS_BRANCH_SCOPE_REFUSED")
        self.repo = Path(repo)
        self.branch = branch
        remote = _git(repo, "remote", "get-url", "origin").stdout.decode().strip()
        self.remote = remote
        if re.search(r"github\.com[:/]", remote, re.I):
            if not (os.getenv("JANUS_RELAY_CAS_WRITE_AUTHORIZED") == "TRUE"
                    and os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
                    and os.getenv("GITHUB_REF") == "refs/heads/main"
                    and os.getenv("GITHUB_REPOSITORY") == "Hawkar-usls/Janus-Demiurge"):
                raise ValueError("CAS_REMOTE_GITHUB_WRITE_NOT_AUTHORIZED")

    def read(self):
        _git(self.repo, "fetch", "--no-tags", "origin",
             "refs/heads/" + self.branch)
        head = _git(self.repo, "rev-parse", "FETCH_HEAD").stdout.decode().strip()
        if not COMMIT.fullmatch(head):
            raise ValueError("CAS_INVALID_HEAD")
        raw = _git(self.repo, "show", "FETCH_HEAD:" + STATE_PATH).stdout
        if len(raw) > 131072:
            raise ValueError("CAS_STATE_TOO_LARGE")
        return head, verify(json.loads(raw))

    def compare_and_swap(self, expected_head, old_state, new_state):
        if not isinstance(expected_head, str) or not COMMIT.fullmatch(expected_head):
            raise ValueError("CAS_EXPECTED_HEAD_REQUIRED")
        verify(old_state)
        verify(new_state)
        if (new_state["epoch"] != old_state["epoch"] + 1 or
            new_state["events"][:-1] != old_state["events"] or
            new_state["events"][-1]["previous_sha256"] != old_state["tip_sha256"]):
            raise ValueError("CAS_MUTATION_NOT_SINGLE_APPEND")
        # Do not allow a caller to write over an unknown local checkout.
        if _git(self.repo, "status", "--porcelain").stdout.strip():
            raise ValueError("CAS_CLONE_NOT_CLEAN")
        observed_head, observed = self.read()
        if observed_head != expected_head or observed != old_state:
            raise Conflict("CAS_EXPECTED_STATE_MOVED")
        _git(self.repo, "checkout", "--detach", expected_head)
        p = self.repo / STATE_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(canonical(new_state) + b"\n")
        _git(self.repo, "add", "--", STATE_PATH)
        _git(self.repo, "-c", "user.name=janus-cas-lab",
             "-c", "user.email=janus-cas-lab@users.noreply.github.com",
             "commit", "-m", f"daddy-cas: epoch {new_state['epoch']}")
        candidate_head = _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip()
        # A non-forced fast-forward-only push is atomic across independent
        # Git clients: competing siblings of the same base cannot both win.
        attempt = _git(self.repo, "push", "--porcelain", "origin",
                       "HEAD:refs/heads/" + self.branch, check=False)
        if attempt.returncode:
            raise Conflict("CAS_REMOTE_REF_MOVED_OR_PUSH_REFUSED")
        return candidate_head
