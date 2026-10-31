"""Offline adversarial tests for sealed DADDY_KEYMASTER dynamic pool planning."""
import copy
import json
from pathlib import Path
import unittest

from daddy_keymaster.broker import build_registry, sha
from daddy_keymaster.dynamic_pool import MAX_PARALLEL, preview

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "daddy_keymaster/POLICY.json").read_text())
OWNER = json.loads((ROOT / "daddy_keymaster/OWNER_REGISTRY.json").read_text())
QUEUE = json.loads((ROOT / "daddy_keymaster/DYNAMIC_POOL_QUEUE_EXAMPLE.json").read_text())
NOW = "2026-10-31T09:00:00Z"
ENV = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "Hawkar-usls/Janus-Demiurge",
       "GITHUB_RUN_ID": "41199991234", "GITHUB_RUN_ATTEMPT": "1", "RUNNER_OS": "Linux"}


def roster():
    return build_registry(POLICY, OWNER, NOW, ENV)


class DynamicPoolTests(unittest.TestCase):
    def test_current_github_job_plans_at_most_one_task_no_dispatch(self):
        result = preview(POLICY, roster(), QUEUE, NOW)
        self.assertEqual(result["status"], "DRY_RUN_ROTATION_PREVIEW_ONLY")
        self.assertEqual(len(result["assignments"]), 1)
        self.assertEqual(result["assignments"][0]["task_id"], "contract-gate-demo")
        self.assertEqual(result["assignments"][0]["status"], "PREVIEW_ONLY_NO_LEASE_NO_DISPATCH")
        self.assertEqual(result["actions_dispatched"], 0)
        self.assertEqual(result["runners_provisioned"], 0)
        self.assertEqual(result["lease_mutations"], 0)
        self.assertFalse(result["production_promotion"])
        self.assertEqual(result["max_parallel"], MAX_PARALLEL)

    def test_no_runner_means_zero_assignments(self):
        empty = build_registry(POLICY, OWNER, NOW, {})
        result = preview(POLICY, empty, QUEUE, NOW)
        self.assertEqual(result["assignments"], [])
        self.assertEqual(len(result["held"]), 2)

    def test_deterministic_with_sha_bound_receipt(self):
        a = preview(POLICY, roster(), QUEUE, NOW)
        self.assertEqual(a, preview(POLICY, roster(), QUEUE, NOW))
        body = {k: v for k, v in a.items() if k != "receipt_sha256"}
        self.assertEqual(a["receipt_sha256"], sha(body))

    def test_fair_selection_uses_explicit_usage_not_random_host_hunting(self):
        r = roster()
        worker = copy.deepcopy(r["active"][0])
        worker["id"] = "gha-41199991235-1"
        r["active"].append(worker)
        q = copy.deepcopy(QUEUE)
        q["usage"] = {r["active"][0]["id"]: 8, worker["id"]: 0}
        result = preview(POLICY, r, q, NOW)
        self.assertEqual(len(result["assignments"]), 1)  # per-provider cap
        self.assertEqual(result["assignments"][0]["worker_id"], worker["id"])

    def test_one_worker_never_receives_two_tasks(self):
        result = preview(POLICY, roster(), QUEUE, NOW)
        workers = [r["worker_id"] for r in result["assignments"]]
        self.assertEqual(len(workers), len(set(workers)))

    def test_unfinished_lease_blocks_runner(self):
        r = roster()
        q = copy.deepcopy(QUEUE)
        q["tasks"][0].update(
            status="LEASED", worker_id=r["active"][0]["id"],
            lease_until="2026-10-31T09:04:00Z")
        result = preview(POLICY, r, q, NOW)
        self.assertEqual(result["assignments"], [])
        self.assertIn(
            {"task_id": "contract-gate-demo", "reason": "WAIT_ACTIVE_LEASE"},
            result["held"])

    def test_expired_lease_stays_hold_never_requeues(self):
        r = roster()
        q = copy.deepcopy(QUEUE)
        q["tasks"][0].update(
            status="LEASED", worker_id=r["active"][0]["id"],
            lease_until="2026-10-31T08:59:00Z")
        result = preview(POLICY, r, q, NOW)
        self.assertEqual(result["assignments"], [])
        self.assertIn(
            {"task_id": "contract-gate-demo", "reason": "HOLD_EXPIRED_LEASE_RECONCILE"},
            result["held"])

    def test_completed_job_releases_capacity_for_next(self):
        q = copy.deepcopy(QUEUE)
        q["tasks"][0]["status"] = "COMPLETE"
        result = preview(POLICY, roster(), q, NOW)
        self.assertEqual(result["completed_task_ids"], ["contract-gate-demo"])
        self.assertEqual(result["assignments"][0]["task_id"], "module-eval-demo")

    def test_reject_secret_or_code_execution(self):
        for key, value in [
            ("contains_secrets", True),
            ("access", "PRIVATE_DATA"),
            ("exec", "python arbitrary_script.py"),
            ("max_seconds", 86400),
            ("cpu", 999),
            ("priority", 10),
        ]:
            with self.subTest(key=key):
                q = copy.deepcopy(QUEUE)
                q["tasks"][0][key] = value
                with self.assertRaises(ValueError):
                    preview(POLICY, roster(), q, NOW)

    def test_reject_duplicate_and_missing_lease_binding(self):
        q = copy.deepcopy(QUEUE)
        q["tasks"].append(copy.deepcopy(q["tasks"][0]))
        with self.assertRaises(ValueError):
            preview(POLICY, roster(), q, NOW)
        q = copy.deepcopy(QUEUE)
        q["tasks"][0]["status"] = "LEASED"
        with self.assertRaises(ValueError):
            preview(POLICY, roster(), q, NOW)

    def test_reject_spoofed_github_runner(self):
        r = roster()
        r["active"][0]["observed_at"] = "2026-10-30T09:00:00Z"
        with self.assertRaises(ValueError):
            preview(POLICY, r, QUEUE, NOW)

    def test_policy_cannot_enable_unregistered_external_provider(self):
        policy = copy.deepcopy(POLICY)
        policy["providers"]["ray_cluster"]["enabled"] = True
        with self.assertRaises(ValueError):
            preview(policy, roster(), QUEUE, NOW)

    def test_no_unsupported_automatic_fanout(self):
        q = copy.deepcopy(QUEUE)
        q["tasks"] = q["tasks"] * 40
        with self.assertRaises(ValueError):
            preview(POLICY, roster(), q, NOW)


if __name__ == "__main__":
    unittest.main()
