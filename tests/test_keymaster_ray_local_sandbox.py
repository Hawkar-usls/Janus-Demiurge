"""Ray local sandbox admission, no real cloud provider or owner machine."""
import os
from pathlib import Path
import unittest

from daddy_keymaster.ray_local_sandbox import (
    SLOTS, SEEDS, check_context, expected,
)

ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "Hawkar-usls/Janus-Demiurge",
    "GITHUB_EVENT_NAME": "pull_request",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_RUN_ID": "41250000005",
}


class RayLocalSandboxTests(unittest.TestCase):
    def test_static_only_fixed_workloads(self):
        hashes = [expected(slot, seed) for slot, seed in zip(SLOTS, SEEDS)]
        self.assertEqual(len(set(hashes)), 2)
        for task in (("RAY-LOCAL-3", 3), ("RAY-LOCAL-1", 20261101),
                     ("RAY-LOCAL-2", 1408), ("RAY-LOCAL-1", True)):
            with self.subTest(task=task), self.assertRaises(ValueError):
                expected(*task)

    def test_refuses_non_owner_and_unapproved_context(self):
        check_context(ENV)
        for key, value in (("GITHUB_ACTIONS", "false"),
                           ("GITHUB_REPOSITORY", "somebody/else"),
                           ("GITHUB_EVENT_NAME", "schedule"),
                           ("GITHUB_SHA", "bad"), ("GITHUB_RUN_ID", "x")):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "UNAUTHORIZED"):
                check_context({**ENV, key: value})

    def test_ray_is_single_node_read_only_training_free(self):
        path = Path("daddy_keymaster/ray_local_sandbox.py")
        code = path.read_text()
        workflow = Path(".github/workflows/janus-keymaster-ray-local-sandbox.yml").read_text()
        self.assertIn("include_dashboard=False", code)
        self.assertIn("num_cpus=2", code)
        self.assertIn("private_distributed_cluster_verified", code)
        self.assertIn("external_provider_activated", code)
        self.assertNotIn("ray://", code)
        self.assertNotIn("ray start --head", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("ray==2.59.0", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn("ray stop --force", workflow)


if __name__ == "__main__":
    unittest.main()
