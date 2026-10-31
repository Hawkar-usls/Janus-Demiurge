"""JANUS Async Compute Relay: crash-durable *local* SQLite handoff laboratory.

Only bounded, public/synthetic, allowlisted project work is recorded.
No remote dispatch, generic command execution, model promotion, or cloud provisioning.
A copied SQLite file is not a distributed transaction or an always-on coordinator.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from daddy_keymaster.broker import ID, TYPES, canonical, clock, sha, utc_now

SCHEMA = "janus.daddy_keymaster.async_relay.v1"
HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_ACTIVE = 2
MAX_TASKS = 64
ZERO = "0" * 64


def _digest(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("RELAY_SHA256_REQUIRED")
    return value


def _id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("RELAY_ID_INVALID")
    return value


class Relay:
    """Single-durable-host queue with fencing generations and atomic claims.

    Multi-host leasing requires a trusted shared transactional store. GitHub
    artifacts can *transport snapshots sequentially*, not arbitrate writers.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    cpu INTEGER NOT NULL CHECK (cpu BETWEEN 1 AND 8),
                    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 600),
                    priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 2),
                    state TEXT NOT NULL CHECK (state IN ('QUEUED','LEASED','HOLD','COMPLETE')),
                    generation INTEGER NOT NULL DEFAULT 0,
                    holder TEXT,
                    lease_until TEXT,
                    checkpoint_sha256 TEXT,
                    result_sha256 TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    prev_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL
                );
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    @staticmethod
    def _event(db, kind, task_id, detail):
        last = db.execute(
            "SELECT seq,event_sha256 FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        seq = (last["seq"] + 1) if last else 1
        prev = last["event_sha256"] if last else ZERO
        body = {"seq": seq, "kind": kind, "task_id": task_id,
                "detail": detail, "prev_sha256": prev}
        digest = sha(body)
        db.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?)",
            (seq, kind, task_id, canonical(detail).decode(), prev, digest),
        )
        return digest

    def enqueue(self, task_id, kind, source_sha256, *, cpu=1,
                max_seconds=120, priority=1):
        _id(task_id)
        _digest(source_sha256)
        if (kind not in TYPES or type(cpu) is not int or not 1 <= cpu <= 8 or
            type(max_seconds) is not int or not 1 <= max_seconds <= 600 or
            type(priority) is not int or priority not in (0, 1, 2)):
            raise ValueError("RELAY_TASK_NOT_ALLOWLISTED")
        with self._write() as db:
            if db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] >= MAX_TASKS:
                raise ValueError("RELAY_QUEUE_LIMIT")
            if db.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
                raise ValueError("RELAY_DUPLICATE_TASK")
            db.execute(
                """INSERT INTO tasks
                (id,kind,source_sha256,cpu,max_seconds,priority,state)
                VALUES (?,?,?,?,?,?,'QUEUED')""",
                (task_id, kind, source_sha256, cpu, max_seconds, priority),
            )
            self._event(db, "ENQUEUE", task_id,
                        {"source_sha256": source_sha256, "kind": kind,
                         "cpu": cpu, "max_seconds": max_seconds,
                         "priority": priority})

    def claim(self, holder, kinds, cpu, *, now):
        _id(holder)
        clock(now)
        if (not isinstance(kinds, (list, tuple)) or not kinds or
            set(kinds) - set(TYPES) or type(cpu) is not int or
            not 1 <= cpu <= 16):
            raise ValueError("RELAY_WORKER_NOT_ADMITTED")
        with self._write() as db:
            active = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE state='LEASED'"
            ).fetchone()[0]
            if active >= MAX_ACTIVE or db.execute(
                "SELECT 1 FROM tasks WHERE state='LEASED' AND holder=?",
                (holder,),
            ).fetchone():
                return None
            rows = db.execute(
                "SELECT * FROM tasks WHERE state='QUEUED' AND cpu<=? "
                "ORDER BY priority DESC, id ASC", (cpu,)
            ).fetchall()
            row = next((r for r in rows if r["kind"] in kinds), None)
            if row is None:
                return None
            generation = row["generation"] + 1
            deadline = (clock(now) + timedelta(
                seconds=row["max_seconds"]
            )).isoformat().replace("+00:00", "Z")
            db.execute(
                """UPDATE tasks SET state='LEASED', holder=?, generation=?,
                   lease_until=? WHERE id=? AND state='QUEUED'""",
                (holder, generation, deadline, row["id"]),
            )
            self._event(db, "LEASE", row["id"],
                        {"holder": holder, "generation": generation,
                         "lease_until": deadline})
            return {"task_id": row["id"], "holder": holder,
                    "generation": generation, "lease_until": deadline,
                    "source_sha256": row["source_sha256"],
                    "kind": row["kind"]}

    @staticmethod
    def _live(db, token, now):
        if not isinstance(token, dict):
            raise ValueError("RELAY_TOKEN_REQUIRED")
        task_id = _id(token.get("task_id"))
        holder = _id(token.get("holder"))
        gen = token.get("generation")
        if type(gen) is not int or gen < 1:
            raise ValueError("RELAY_FENCE_INVALID")
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if (row is None or row["state"] != "LEASED" or
            row["holder"] != holder or row["generation"] != gen or
            row["source_sha256"] != token.get("source_sha256") or
            row["lease_until"] != token.get("lease_until")):
            raise ValueError("RELAY_STALE_FENCE")
        if clock(now) >= clock(row["lease_until"]):
            raise ValueError("RELAY_LEASE_EXPIRED_RECONCILE")
        return row

    def checkpoint(self, token, content_sha256, *, now):
        _digest(content_sha256)
        clock(now)
        with self._write() as db:
            row = self._live(db, token, now)
            db.execute("UPDATE tasks SET checkpoint_sha256=? WHERE id=?",
                       (content_sha256, row["id"]))
            self._event(db, "CHECKPOINT", row["id"],
                        {"generation": row["generation"],
                         "content_sha256": content_sha256})

    def complete(self, token, result_sha256, *, now):
        _digest(result_sha256)
        clock(now)
        with self._write() as db:
            row = self._live(db, token, now)
            if row["checkpoint_sha256"] is None:
                raise ValueError("RELAY_NO_DURABLE_CHECKPOINT")
            db.execute(
                "UPDATE tasks SET state='COMPLETE', result_sha256=? WHERE id=?",
                (result_sha256, row["id"]),
            )
            self._event(db, "COMPLETE", row["id"],
                        {"generation": row["generation"],
                         "result_sha256": result_sha256,
                         "checkpoint_sha256": row["checkpoint_sha256"]})

    def reconcile_expired(self, *, now):
        """Expired, possibly executed leases become HOLD, NEVER queued."""
        clock(now)
        with self._write() as db:
            rows = db.execute(
                "SELECT id,generation,lease_until FROM tasks "
                "WHERE state='LEASED' ORDER BY id"
            ).fetchall()
            held = []
            for row in rows:
                if clock(row["lease_until"]) <= clock(now):
                    db.execute("UPDATE tasks SET state='HOLD' WHERE id=?",
                               (row["id"],))
                    self._event(db, "HOLD_UNCERTAIN", row["id"],
                                {"generation": row["generation"],
                                 "reason": "EXPIRED_MAY_HAVE_EXECUTED"})
                    held.append(row["id"])
            return held

    def witness(self):
        with self._connect() as db:
            db.execute("BEGIN")
            try:
                all_events = db.execute("SELECT * FROM events ORDER BY seq").fetchall()
                previous = ZERO
                for idx, event in enumerate(all_events, 1):
                    detail = json.loads(event["detail"])
                    body = {"seq": event["seq"], "kind": event["kind"],
                            "task_id": event["task_id"], "detail": detail,
                            "prev_sha256": event["prev_sha256"]}
                    if (event["seq"] != idx or
                        event["prev_sha256"] != previous or
                        event["event_sha256"] != sha(body)):
                        raise ValueError("RELAY_EVENT_CHAIN_INVALID")
                    previous = event["event_sha256"]
                rows = [dict(r) for r in db.execute(
                    "SELECT * FROM tasks ORDER BY id"
                ).fetchall()]
                # Every committed task state must have a corresponding terminal
                # journal event, not just an arbitrary row mutation.
                final = {}
                for event in all_events:
                    final[event["task_id"]] = event["kind"]
                for row in rows:
                    expected = {"QUEUED": "ENQUEUE", "LEASED": ("LEASE", "CHECKPOINT"),
                                "COMPLETE": "COMPLETE", "HOLD": "HOLD_UNCERTAIN"}
                    kinds = expected[row["state"]]
                    if final.get(row["id"]) not in (
                        kinds if isinstance(kinds, tuple) else (kinds,)
                    ):
                        raise ValueError("RELAY_ROW_JOURNAL_DIVERGED")
                return {
                    "schema": SCHEMA, "status": "LOCAL_JOURNAL_VERIFIED",
                    "tasks": rows, "events": len(all_events),
                    "tip_sha256": previous,
                    "max_active": MAX_ACTIVE,
                    "external_dispatches": 0, "authority_delta": 0,
                    "production_promotion": False,
                }
            finally:
                db.execute("ROLLBACK")

    def pack(self):
        """Checkpoint WAL into a self-contained SQLite file for sequential transfer."""
        self.witness()
        with self._connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def _at():
    return utc_now()


def _write_json(path, result):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(canonical(result) + b"\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("origin", "resume", "witness"))
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--parent", type=Path)
    args = p.parse_args()
    source = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    arch = os.environ.get("RUNNER_ARCH", "")
    if args.stage in ("origin", "resume"):
        if not re.fullmatch(r"[a-f0-9]{40}", source) or not run_id.isdigit():
            raise ValueError("RELAY_GITHUB_EXACT_SOURCE_REQUIRED")
        if (args.stage == "origin" and arch != "X64" or
            args.stage == "resume" and arch != "ARM64"):
            raise ValueError("RELAY_DIFFERENT_ARCH_REQUIRED")
    store = Relay(args.db)
    if args.stage == "origin":
        source_digest = hashlib.sha256(source.encode()).hexdigest()
        store.enqueue("test-contract-a", "contract_test", source_digest, priority=2)
        store.enqueue("test-contract-b", "pure_module_eval", source_digest, priority=1)
        token = store.claim("origin-worker", ["contract_test", "pure_module_eval"],
                            2, now=_at())
        assert token and token["task_id"] == "test-contract-a"
        store.checkpoint(token, sha({"step": 1, "task_id": token["task_id"]}), now=_at())
        store.complete(token, sha({"result": "PASS", "source": source}), now=_at())
        snap = store.witness()
        assert [t["state"] for t in snap["tasks"]] == ["COMPLETE", "QUEUED"]
        receipt = {"stage": "origin", "source_sha": source, "run_id": run_id,
                   "arch": arch, "tip_sha256": snap["tip_sha256"],
                   "events": snap["events"], "db_sha256": store.pack()}
    elif args.stage == "resume":
        if args.parent is None:
            raise ValueError("RELAY_PARENT_REQUIRED")
        parent = json.loads(args.parent.read_text())
        if (parent.get("stage") != "origin" or parent.get("source_sha") != source or
            parent.get("run_id") != run_id or parent.get("arch") != "X64" or
            parent.get("db_sha256") != hashlib.sha256(args.db.read_bytes()).hexdigest()):
            raise ValueError("RELAY_PARENT_SNAPSHOT_MISMATCH")
        snap = store.witness()
        if (snap["tip_sha256"] != parent["tip_sha256"] or
            snap["events"] != parent["events"] or
            [t["state"] for t in snap["tasks"]] != ["COMPLETE", "QUEUED"]):
            raise ValueError("RELAY_UNEXPECTED_RESUME_STATE")
        token = store.claim("resume-worker", ["pure_module_eval"], 2, now=_at())
        assert token and token["task_id"] == "test-contract-b"
        store.checkpoint(token, sha({"step": 2, "task_id": token["task_id"]}), now=_at())
        store.complete(token, sha({"result": "PASS", "source": source}), now=_at())
        after = store.witness()
        assert [t["state"] for t in after["tasks"]] == ["COMPLETE", "COMPLETE"]
        receipt = {"stage": "resume", "source_sha": source, "run_id": run_id,
                   "arch": arch, "parent_receipt_sha256": sha(parent),
                   "origin_tip_sha256": parent["tip_sha256"],
                   "tip_sha256": after["tip_sha256"],
                   "events": after["events"], "db_sha256": store.pack()}
    else:
        if args.parent is None:
            raise ValueError("RELAY_PARENT_REQUIRED")
        parent = json.loads(args.parent.read_text())
        state = store.witness()
        if (parent.get("stage") != "resume" or
            parent.get("db_sha256") != hashlib.sha256(args.db.read_bytes()).hexdigest() or
            parent.get("tip_sha256") != state["tip_sha256"] or
            any(x["state"] != "COMPLETE" for x in state["tasks"]) or
            state["events"] != 8):
            raise ValueError("RELAY_WITNESS_REJECTED")
        receipt = {"stage": "witness", "status": "TWO_EPHEMERAL_GITHUB_WORKERS_RELAYED",
                   "parent_receipt_sha256": sha(parent),
                   "tip_sha256": state["tip_sha256"], "events": state["events"],
                   "tasks_complete": len(state["tasks"]),
                   "external_dispatches": 0, "production_promotion": False}
    _write_json(args.out, receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
