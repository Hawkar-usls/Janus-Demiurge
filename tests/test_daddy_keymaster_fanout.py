"""Adversarial 4/8-worker audit tests (synthetic receipts, no model/billing)."""
import copy
import json
from pathlib import Path
import unittest

from daddy_keymaster.broker import sha
from daddy_keymaster.fanout import (
    SCHEMA, WORKLOADS, plan, audit, check_env, source_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
ENV = {
    "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "Hawkar-usls/Janus-Demiurge",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "41250000001",
    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
    "GITHUB_JOB": "worker", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
}


def make(row):
    wid, arch, _, suite = row
    d = {
        "schema": SCHEMA, "status": "EXECUTED_ALLOWLISTED_TESTS",
        "worker_id": wid, "platform": arch, "suite": suite, "cases": 3,
        "repository": ENV["GITHUB_REPOSITORY"], "run_id": ENV["GITHUB_RUN_ID"],
        "attempt": ENV["GITHUB_RUN_ATTEMPT"], "commit": ENV["GITHUB_SHA"],
        "runner_os": "Linux", "source_manifest": source_manifest(ROOT),
        "external_model_used": False, "paid_resources_used": False,
        "persistent_worker": False, "authority_delta": 0,
    }
    d["receipt_sha256"] = sha(d)
    return d


def sealed(d):
    d["receipt_sha256"] = sha({k: v for k, v in d.items() if k != "receipt_sha256"})
    return d


class BoundedFanoutTests(unittest.TestCase):
    def test_schedule_is_four_and_manual_eight_is_explicit(self):
        self.assertEqual(len(plan(4)["include"]), 4)
        self.assertEqual(len(plan(8)["include"]), 8)
        for invalid in (0, 2, 3, 17, "8", True):
            with self.subTest(count=invalid), self.assertRaises(ValueError):
                plan(invalid)
        ids = [row["id"] for row in plan(8)["include"]]
        self.assertEqual(len(set(ids)), 8)

    def test_exact_four_and_eight_worker_witness(self):
        for count in (4, 8):
            with self.subTest(count=count):
                out = audit(ROOT, [make(row) for row in WORKLOADS[:count]], ENV, count)
                self.assertEqual(out["status"], f"{count}_EPHEMERAL_WORKERS_VERIFIED")
                self.assertEqual(len(out["workers"]), count)
                self.assertEqual(out["max_parallel"], 4)
                self.assertFalse(out["paid_resources_used"])
                self.assertFalse(out["persistent_capacity_claim"])
                self.assertEqual(out["authority_delta"], 0)
                self.assertEqual(out["receipt_sha256"], sha({
                    k: v for k, v in out.items() if k != "receipt_sha256"}))

    def test_missing_duplicate_or_extra_worker_refused(self):
        rows = [make(r) for r in WORKLOADS[:4]]
        for bad in (rows[:3], rows[:3] + [rows[0]],
                    rows + [make(WORKLOADS[4])]):
            with self.assertRaises(ValueError):
                audit(ROOT, bad, ENV, 4)

    def test_tampered_digest_and_resealed_bad_claims_refused(self):
        base = [make(r) for r in WORKLOADS[:4]]
        variants = [
            ("receipt_sha256", "f" * 64),
            ("run_id", "41250000002"), ("attempt", "2"),
            ("commit", "b" * 40), ("platform", "ARM64"),
            ("suite", "test_secret_injection.py"), ("cases", 0),
            ("source_manifest", {}), ("paid_resources_used", True),
            ("external_model_used", True), ("persistent_worker", True),
            ("authority_delta", 1),
        ]
        for name, value in variants:
            with self.subTest(field=name):
                rows = copy.deepcopy(base)
                rows[0][name] = value
                if name != "receipt_sha256":
                    sealed(rows[0])
                with self.assertRaises(ValueError):
                    audit(ROOT, rows, ENV, 4)

    def test_untrusted_or_unbounded_execution_context_refused(self):
        for name, value in (
            ("GITHUB_ACTIONS", "false"),
            ("GITHUB_REPOSITORY", "attacker/repo"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/other"),
            ("GITHUB_SHA", "bad"),
            ("RUNNER_ARCH", "GPU"),
            ("RUNNER_OS", "Windows"),
            ("GITHUB_JOB", "audit"),
        ):
            with self.subTest(field=name), self.assertRaises(ValueError):
                check_env({**ENV, name: value}, worker=True)

    def test_workflow_denies_pr_runtime_and_write_on_workers(self):
        text = (ROOT / ".github/workflows/janus-daddy-keymaster-fanout.yml").read_text()
        self.assertIn("max-parallel: 4", text)
        self.assertIn("worker_count:", text)
        self.assertIn("github.event_name != 'pull_request'", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("schedule:", text)
        self.assertIn("daddy-keymaster-state", text)
        self.assertNotIn("curl", text)
        self.assertNotIn("copilot", text.lower())


if __name__ == "__main__":
    unittest.main()
