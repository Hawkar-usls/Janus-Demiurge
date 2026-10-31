"""Adversarial tests for local durable JANUS async compute relay."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor

from daddy_keymaster.async_relay import Relay, MAX_ACTIVE
from daddy_keymaster.broker import sha

SRC = hashlib.sha256(b"source-commit").hexdigest()
NOW = "2026-10-31T11:00:00Z"
LATER = "2026-10-31T11:04:00Z"
ROOT = Path(__file__).resolve().parents[1]


def rival_claim(filename, worker):
    store = Relay(filename)
    return store.claim(worker, ["contract_test"], 2, now=NOW)


class AsyncRelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "state.sqlite")
        self.store = Relay(self.db)

    def add(self, name="task-one", **kwargs):
        self.store.enqueue(name, "contract_test", SRC, **kwargs)

    def test_enqueue_claim_checkpoint_complete_next_worker(self):
        self.add("task-one")
        self.add("task-two", priority=0)
        token = self.store.claim("worker-first", ["contract_test"], 2, now=NOW)
        self.assertEqual(token["task_id"], "task-one")
        self.assertIsNone(self.store.claim("worker-first", ["contract_test"], 2, now=NOW))
        self.store.checkpoint(token, sha({"step": 1}), now=NOW)
        self.store.complete(token, sha({"ok": True}), now=NOW)
        self.assertEqual(self.store.witness()["tasks"][0]["state"], "COMPLETE")
        with self.assertRaises(ValueError):
            self.store.complete(token, sha({"ok": True}), now=NOW)
        nxt = self.store.claim("worker-second", ["contract_test"], 2, now=NOW)
        self.assertEqual(nxt["task_id"], "task-two")
        self.assertNotEqual(nxt["holder"], token["holder"])

    def test_reject_secret_like_arbitrary_work_and_duplicate_id(self):
        for item in [
            ("kind", "run_shell"), ("cpu", 99), ("priority", 20),
            ("max_seconds", 500000), ("source_sha256", "bad"),
        ]:
            name, value = item
            params = {"task_id": "task-one", "kind": "contract_test",
                      "source_sha256": SRC}
            params[name] = value
            with self.assertRaises(ValueError):
                self.store.enqueue(**params)
        self.add()
        with self.assertRaises(ValueError):
            self.add()
        with self.assertRaises(ValueError):
            self.store.claim("worker-first", ["run_shell"], 4, now=NOW)

    def test_no_receipt_without_durable_checkpoint(self):
        self.add()
        token = self.store.claim("worker-first", ["contract_test"], 2, now=NOW)
        with self.assertRaisesRegex(ValueError, "RELAY_NO_DURABLE_CHECKPOINT"):
            self.store.complete(token, sha({"ok": True}), now=NOW)
        self.assertEqual(self.store.witness()["tasks"][0]["state"], "LEASED")

    def test_stale_lease_goes_hold_not_silent_retry(self):
        self.add()
        token = self.store.claim("worker-first", ["contract_test"], 2, now=NOW)
        self.assertEqual(self.store.reconcile_expired(now=LATER), ["task-one"])
        self.assertIsNone(self.store.claim("worker-second", ["contract_test"], 2, now=LATER))
        self.assertEqual(self.store.witness()["tasks"][0]["state"], "HOLD")
        with self.assertRaises(ValueError):
            self.store.checkpoint(token, SRC, now=LATER)
        self.assertEqual(self.store.reconcile_expired(now=LATER), [])

    def test_expired_claim_not_accepted_even_without_reconciler(self):
        self.add(max_seconds=1)
        token = self.store.claim("worker-first", ["contract_test"], 1, now=NOW)
        with self.assertRaisesRegex(ValueError, "RELAY_LEASE_EXPIRED"):
            self.store.checkpoint(token, SRC, now=LATER)
        with self.assertRaisesRegex(ValueError, "RELAY_LEASE_EXPIRED"):
            self.store.complete(token, SRC, now=LATER)

    def test_token_source_binding_cannot_be_forged(self):
        self.add()
        token = self.store.claim("worker-first", ["contract_test"], 2, now=NOW)
        for mutation in ({"holder": "worker-second"}, {"generation": 2},
                         {"source_sha256": "f" * 64},
                         {"lease_until": "2026-10-31T12:00:00Z"}):
            forged = {**token, **mutation}
            with self.assertRaises(ValueError):
                self.store.checkpoint(forged, SRC, now=NOW)
        self.store.checkpoint(token, SRC, now=NOW)

    def test_max_two_claims_across_workers(self):
        for i in range(5):
            self.add(f"task-{i}")
        tokens = [
            self.store.claim(f"worker-{i}", ["contract_test"], 2, now=NOW)
            for i in range(5)
        ]
        self.assertEqual(sum(v is not None for v in tokens), MAX_ACTIVE)
        self.assertEqual(sum(r["state"] == "LEASED"
                             for r in self.store.witness()["tasks"]), MAX_ACTIVE)

    def test_independent_processes_compete_for_atomic_claim(self):
        self.add()
        with ProcessPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(rival_claim, self.db, f"worker-{n}")
                       for n in (1, 2)]
            actual = [f.result(timeout=20) for f in futures]
        self.assertEqual(sum(x is not None for x in actual), 1)
        self.assertEqual(self.store.witness()["tasks"][0]["state"], "LEASED")

    def test_process_death_after_committed_lease_survives_restart(self):
        self.add()
        code = (
            "import os; from daddy_keymaster.async_relay import Relay;"
            f"r=Relay({self.db!r}); "
            f"t=r.claim('worker-crash',['contract_test'],1,now={NOW!r});"
            "assert t; os._exit(17)"
        )
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 17, p.stderr)
        reopened = Relay(self.db)
        self.assertEqual(reopened.witness()["tasks"][0]["state"], "LEASED")
        self.assertIsNone(reopened.claim("worker-new", ["contract_test"], 1, now=NOW))
        self.assertEqual(reopened.reconcile_expired(now=LATER), ["task-one"])
        self.assertEqual(reopened.witness()["tasks"][0]["state"], "HOLD")

    def test_checkpoint_can_be_replayed_by_new_process(self):
        self.add()
        token = self.store.claim("worker-first", ["contract_test"], 2, now=NOW)
        self.store.checkpoint(token, SRC, now=NOW)
        other = Relay(self.db)
        self.assertEqual(other.witness()["tasks"][0]["checkpoint_sha256"], SRC)
        other.complete(token, SRC, now=NOW)
        self.assertEqual(Relay(self.db).witness()["tasks"][0]["state"], "COMPLETE")

    def test_db_file_backup_roundtrip_for_sequential_handoff(self):
        self.add()
        first = self.store.claim("worker-first", ["contract_test"], 1, now=NOW)
        self.store.checkpoint(first, SRC, now=NOW)
        self.store.complete(first, SRC, now=NOW)
        before = self.store.witness()
        digest = self.store.pack()
        self.assertEqual(hashlib.sha256(Path(self.db).read_bytes()).hexdigest(), digest)
        copied = str(Path(self.tmp.name) / "restored.sqlite")
        Path(copied).write_bytes(Path(self.db).read_bytes())
        reopened = Relay(copied)
        after = reopened.witness()
        self.assertEqual(before["tip_sha256"], after["tip_sha256"])
        self.assertEqual(before["tasks"], after["tasks"])

    def test_tampered_event_fails_closed(self):
        self.add()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE events SET detail='{}' WHERE seq=1")
        with self.assertRaisesRegex(ValueError, "RELAY_EVENT_CHAIN_INVALID"):
            self.store.witness()

    def test_arbitrary_db_state_mutation_detected(self):
        self.add()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET state='COMPLETE' WHERE id='task-one'")
        with self.assertRaisesRegex(ValueError, "RELAY_ROW_JOURNAL_DIVERGED"):
            self.store.witness()


if __name__ == "__main__":
    unittest.main()
