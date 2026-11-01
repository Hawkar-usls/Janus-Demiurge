"""Bounded CI heartbeat: durable task lifecycle and fail-closed controls."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from daddy_keymaster.broker import sha
from daddy_keymaster.bounded_ci import (
    ARCH_TASK, audit, context, finish, prepare, run_contract, take,
)
from daddy_keymaster.git_cas_queue import Conflict, empty, verify

SOURCE = "e" * 40
NOW = "2026-10-31T12:00:00Z"
ENV = {
    "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "Hawkar-usls/Janus-Demiurge",
    "GITHUB_EVENT_NAME": "schedule", "GITHUB_REF": "refs/heads/main",
    "GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": "41299999999",
    "JANUS_DADDY_CI_RUNTIME": "TRUE",
    "JANUS_RELAY_CAS_WRITE_AUTHORIZED": "TRUE",
    "RUNNER_ARCH": "X64",
}
ROOT = Path(__file__).resolve().parents[1]

class Store:
    def __init__(self):
        self.state = empty()
        self.epoch = 0
        self.conflict_once = False
    def read(self):
        return f"{self.epoch:040x}", copy.deepcopy(self.state)
    def compare_and_swap(self, head, old, new):
        if self.conflict_once:
            self.conflict_once = False
            raise Conflict("test transient race")
        if head != f"{self.epoch:040x}" or old != self.state:
            raise Conflict("stale")
        verify(new)
        self.state = copy.deepcopy(new)
        self.epoch += 1

class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        # Unit-store tests isolate task policy; Git archive CAS is tested
        # separately against real competing bare Git clones.
        a = patch("daddy_keymaster.bounded_ci.rotate_if_ready",
                  return_value={"status": "EMPTY", "segment": 0})
        b = patch("daddy_keymaster.bounded_ci.archive_status",
                  side_effect=lambda store, source: {
                      "state": store.read()[1],
                      "current_already_archived": False,
                  })
        a.start()
        b.start()
        self.addCleanup(a.stop)
        self.addCleanup(b.stop)

    def test_cloud_stages_use_exact_same_event_source_not_mutable_main(self):
        workflow = (ROOT / ".github/workflows/janus-daddy-keymaster-bounded-heartbeat.yml").read_text()
        self.assertEqual(workflow.count("ref: ${{ github.sha }}"), 3)
        self.assertNotIn("          ref: main", workflow)
        self.assertIn("group: janus-daddy-keymaster-bounded-heartbeat", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("needs: prepare", workflow)
        self.assertIn("needs: [prepare, worker]", workflow)
        self.assertIn("git worktree add --detach", workflow)
        self.assertNotIn("git push --force", workflow)
        self.assertNotIn("repository_dispatch:", workflow)

    def test_context_does_not_accept_pr_or_untrusted_run(self):
        self.assertEqual(context(ENV)["GITHUB_RUN_ID"], ENV["GITHUB_RUN_ID"])
        for changes in ({"GITHUB_EVENT_NAME": "pull_request"},
                        {"GITHUB_REF": "refs/pull/390/merge"},
                        {"JANUS_DADDY_CI_RUNTIME": "FALSE"},
                        {"GITHUB_REPOSITORY": "stranger/project"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    context({**ENV, **changes})

    def test_preparation_idempotent_and_version_bound(self):
        store = Store()
        first = prepare(store, ENV, now=NOW)
        self.assertEqual(first["queued"], 2)
        self.assertEqual(store.state["epoch"], 2)
        second = prepare(store, ENV, now=NOW)
        self.assertEqual(second["queued"], 2)
        self.assertEqual(store.state["epoch"], 2)
        self.assertTrue(second["no_remote_dispatch"])

    def test_new_main_version_skips_only_unclaimed_old_tasks(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        newer = {**ENV, "GITHUB_SHA": "f" * 40}
        status = prepare(store, newer, now=NOW)
        self.assertEqual(status["queued"], 2)
        self.assertEqual(sum(v["state"] == "SKIPPED"
                             for v in store.state["tasks"].values()), 2)
        self.assertEqual(sum(v["state"] == "QUEUED"
                             for v in store.state["tasks"].values()), 2)
        self.assertEqual(take(store, newer, "X64", now=NOW)["task_id"],
                         "ci-contract-" + "f" * 40)

    def test_claimed_old_task_is_not_skipped(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        token = take(store, ENV, "X64", now=NOW)
        newer = {**ENV, "GITHUB_SHA": "f" * 40}
        prepare(store, newer, now=NOW)
        self.assertEqual(store.state["tasks"][token["task_id"]]["state"], "LEASED")

    def test_transient_cas_conflict_recalculated_not_replayed(self):
        store = Store()
        store.conflict_once = True
        prepare(store, ENV, now=NOW)
        self.assertEqual(store.state["epoch"], 2)
        self.assertEqual(len(store.state["tasks"]), 2)

    def test_independent_worker_claim_checkpoint_complete_and_witness(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        a = take(store, ENV, "X64", now=NOW)
        b = take(store, ENV, "ARM64", now=NOW)
        self.assertNotEqual(a["task_id"], b["task_id"])
        self.assertIsNone(take(store, ENV, "X64", now=NOW))
        receipts = []
        for token, arch in ((a, "X64"), (b, "ARM64")):
            record = {
                "schema": "janus.daddy_keymaster.bounded_ci_result.v1",
                "status": "ALLOWLISTED_TEST_SUITE_PASSED",
                "source_sha256": token["source_sha256"],
                "task_id": token["task_id"], "holder": token["holder"],
                "generation": token["generation"],
                "suite": ("test_daddy_keymaster_git_cas_state.py" if arch == "X64"
                          else "test_daddy_keymaster_dynamic_pool.py"),
                "worker_arch": arch, "run_id": ENV["GITHUB_RUN_ID"],
                "stdout_sha256": "0"*64, "stderr_sha256": "0"*64,
                "external_effects": 0, "model_promotions": 0,
            }
            record["receipt_sha256"] = sha(record)
            result = finish(store, ENV, token, record, now=NOW)
            self.assertEqual(result, "COMPLETE")
            receipts.append(record)
        result = audit(store.read()[1], receipts, SOURCE, ENV["GITHUB_RUN_ID"])
        self.assertEqual(result["verified_receipts"], 2)
        self.assertEqual(store.state["epoch"], 8)
        with self.assertRaises(ValueError):
            audit(store.read()[1], receipts[:1], SOURCE, ENV["GITHUB_RUN_ID"])

    def test_forged_digest_or_result_rejected_without_commit(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        token = take(store, ENV, "X64", now=NOW)
        fake = {
            "status": "ALLOWLISTED_TEST_SUITE_PASSED",
            "source_sha256": token["source_sha256"],
            "task_id": token["task_id"], "run_id": ENV["GITHUB_RUN_ID"],
            "external_effects": 0, "model_promotions": 0,
            "receipt_sha256": "a"*64,
        }
        old = store.read()[1]["epoch"]
        with self.assertRaises(ValueError):
            finish(store, ENV, token, fake, now=NOW)
        self.assertEqual(store.read()[1]["epoch"], old)

    def test_witness_reports_old_unresolved_hold_as_degraded(self):
        from daddy_keymaster.git_cas_queue import reconcile_expired
        store = Store()
        prepare(store, ENV, now=NOW)
        token = take(store, ENV, "X64", now=NOW)
        _, state = store.read()
        state, held = reconcile_expired(state, now="2026-10-31T12:10:00Z")
        self.assertEqual(held, [token["task_id"]])
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_HOLD"):
            audit(state, [], SOURCE, ENV["GITHUB_RUN_ID"])

    def test_invalid_arch_can_not_claim(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        with self.assertRaises(ValueError):
            take(store, ENV, "GPU", now=NOW)

    def test_real_allowlisted_ci_suites_complete_across_two_workers(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        receipts = []
        for arch in ("X64", "ARM64"):
            token = take(store, ENV, arch, now=NOW)
            record = run_contract(token, {**ENV, "RUNNER_ARCH": arch}, ROOT)
            self.assertEqual(record["status"], "ALLOWLISTED_TEST_SUITE_PASSED")
            self.assertEqual(record["external_effects"], 0)
            self.assertEqual(finish(store, ENV, token, record, now=NOW), "COMPLETE")
            receipts.append(record)
        receipt = audit(store.read()[1], receipts, SOURCE, ENV["GITHUB_RUN_ID"])
        self.assertEqual(receipt["verified_receipts"], 2)
        self.assertEqual(receipt["status"], "INDEPENDENT_BOUND_CI_WITNESS")

    def test_run_contract_rejects_arch_mismatch_without_subprocess(self):
        store = Store()
        prepare(store, ENV, now=NOW)
        token = take(store, ENV, "ARM64", now=NOW)
        with self.assertRaisesRegex(ValueError, "ARCH_MISMATCH"):
            run_contract(token, ENV, ROOT)

if __name__ == "__main__":
    unittest.main()
