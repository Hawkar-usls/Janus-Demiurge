"""Replay, lease and stale-token tests for staged Git CAS queue."""
import copy
import hashlib
import unittest
from daddy_keymaster.broker import sha
from daddy_keymaster.git_cas_queue import (
    empty, enqueue, claim, checkpoint, complete, verify, reconcile_expired,
)
SOURCE = hashlib.sha256(b"synthetic-pin").hexdigest()
NOW = "2026-10-31T12:00:00Z"
LATER = "2026-10-31T12:10:00Z"

class GitCASStateTests(unittest.TestCase):
    def seed(self):
        a = enqueue(empty(), "task-a", "contract_test", SOURCE, priority=2)
        return enqueue(a, "task-b", "pure_module_eval", SOURCE, priority=1)

    def test_projection_and_hash_chain(self):
        s = self.seed()
        self.assertEqual(s, verify(s))
        altered = copy.deepcopy(s)
        altered["tasks"]["task-a"]["source_sha256"] = "f"*64
        with self.assertRaises(ValueError):
            verify(altered)
        altered = copy.deepcopy(s)
        altered["events"][0]["detail"]["priority"] = 0
        with self.assertRaises(ValueError):
            verify(altered)

    def test_two_workers_then_limit(self):
        s, a = claim(self.seed(), "worker-a", ["contract_test"], 2, now=NOW)
        self.assertEqual(a["task_id"], "task-a")
        s, b = claim(s, "worker-b", ["pure_module_eval"], 2, now=NOW)
        self.assertEqual(b["task_id"], "task-b")
        _, no = claim(s, "worker-c", ["contract_test"], 2, now=NOW)
        self.assertIsNone(no)
        s = checkpoint(s, a, SOURCE, now=NOW)
        s = complete(s, a, sha({"pass": True}), now=NOW)
        self.assertEqual(s["tasks"]["task-a"]["state"], "COMPLETE")
        with self.assertRaises(ValueError):
            checkpoint(s, a, SOURCE, now=NOW)

    def test_expired_lease_goes_hold(self):
        s, tok = claim(self.seed(), "worker-a", ["contract_test"], 2, now=NOW)
        next_state, held = reconcile_expired(s, now=LATER)
        self.assertEqual(held, ["task-a"])
        self.assertEqual(next_state["tasks"]["task-a"]["state"], "HOLD")
        with self.assertRaises(ValueError):
            complete(next_state, tok, SOURCE, now=LATER)

    def test_token_mutations_rejected(self):
        s, tok = claim(self.seed(), "worker-a", ["contract_test"], 2, now=NOW)
        for changes in ({"holder":"worker-b"},{"generation":3},
                        {"source_sha256":"0"*64},{"lease_until":LATER}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    checkpoint(s, {**tok, **changes}, SOURCE, now=NOW)

    def test_reject_nonapproved_task_types(self):
        with self.assertRaises(ValueError):
            enqueue(empty(), "task-a", "unsupported_kind", SOURCE)
        with self.assertRaises(ValueError):
            enqueue(empty(), "task-a", "contract_test", SOURCE, max_seconds=9999)
        with self.assertRaises(ValueError):
            enqueue(empty(), "task-a", "contract_test", "invalid-sha")
if __name__ == "__main__":
    unittest.main()
