"""Portable unit tests: trusted modern organ in a separate, SHA-pinned process.

No NAS/E: access, no external providers, no new agents, and no legacy code runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch

from restored.legacy_process_probation import (
    POLICY_PATH, ProcessProbationHold, _check_policy, _run_with_policy,
    canonical_bytes, run_approved_process_probation
)


def archived_graph():
    return {
        "schema": "janus.legacy_core.module_relationships_non_authoritative.v1",
        "status": "ARCHIVAL_RELATIONSHIP_PROJECTION_ONLY",
        "projection": {
            "node_count": 3, "relation_count": 3,
            "relations_with_both_endpoints_declared": 2,
            "relations_with_unresolved_endpoint": 1,
            "nodes": [
                {"id": "cortex", "kind": "cognition"},
                {"id": "memory", "kind": "memory"},
                {"id": "hero", "kind": "system"},
            ],
            "historical_relations": [
                {"from": "cortex", "to": "memory", "historical_relation": "reads",
                 "endpoints_declared_in_legacy_nodes": True},
                {"from": "memory", "to": "hero", "historical_relation": "context",
                 "endpoints_declared_in_legacy_nodes": True},
                {"from": "hero", "to": "external_service",
                 "historical_relation": "calls",
                 "endpoints_declared_in_legacy_nodes": False},
            ]
        }
    }


def synthetic_policy(graph=None):
    graph = archived_graph() if graph is None else graph
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy["archive_artifact_sha256"] = hashlib.sha256(canonical_bytes(graph)).hexdigest()
    return policy


class ProcessProbationTests(unittest.TestCase):
    def test_real_pinned_code_manifest_is_self_consistent(self):
        # Verifies the checked-in source bytes match all explicit pins.
        _check_policy(json.loads(POLICY_PATH.read_text(encoding="utf-8")))

    def test_operator_approval_precedes_any_child_process(self):
        graph = archived_graph()
        with patch("restored.legacy_process_probation.subprocess.run") as runner:
            with self.assertRaisesRegex(PermissionError, "APPROVAL"):
                _run_with_policy(graph, "cortex", "hero", operator_approved=False,
                                 timeout_seconds=4, policy=synthetic_policy(graph))
            runner.assert_not_called()

    def test_clean_subprocess_actual_known_organ_pass(self):
        graph = archived_graph()
        original = copy.deepcopy(graph)
        result = _run_with_policy(graph, "cortex", "hero", operator_approved=True,
                                  timeout_seconds=4, policy=synthetic_policy(graph))
        self.assertEqual(result["status"], "PASS_PROCESS_SEPARATED_SYNTHETIC_PROBATION")
        self.assertEqual(result["organ_receipt"]["path"], ["cortex", "memory", "hero"])
        self.assertEqual(result["organ_receipt"]["excluded_unresolved_relations"], 1)
        self.assertFalse(result["authority"]["os_security_sandbox_proven"])
        self.assertFalse(result["authority"]["production_activation"])
        self.assertEqual(graph, original)

    def test_artifact_tamper_blocks_before_subprocess(self):
        graph = archived_graph()
        policy = synthetic_policy(graph)
        graph["projection"]["nodes"][0]["id"] = "changed"
        with patch("restored.legacy_process_probation.subprocess.run") as runner:
            with self.assertRaisesRegex(ProcessProbationHold, "ARCHIVE_SOURCE_SHA_MISMATCH"):
                _run_with_policy(graph, "cortex", "hero", operator_approved=True,
                                 timeout_seconds=4, policy=policy)
            runner.assert_not_called()

    def test_code_pin_tamper_blocks(self):
        p = synthetic_policy()
        p["file_sha256"]["graph_port"] = "0" * 64
        with self.assertRaisesRegex(ProcessProbationHold, "CODE_IDENTITY_MISMATCH"):
            _check_policy(p)

    def test_unreviewed_authority_change_blocks(self):
        p = synthetic_policy()
        p["authority"]["production_activation"] = True
        with self.assertRaisesRegex(ProcessProbationHold, "AUTHORITY_FIREWALL_HOLD"):
            _check_policy(p)

    def test_absent_organ_refuses_in_child_without_traceback(self):
        graph = archived_graph()
        with self.assertRaisesRegex(ProcessProbationHold, "CHILD_PROBATION_HOLD"):
            _run_with_policy(graph, "cortex", "external_service", operator_approved=True,
                             timeout_seconds=4, policy=synthetic_policy(graph))

    def test_child_timeout_fails_closed(self):
        graph = archived_graph()
        with patch("restored.legacy_process_probation.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=1)):
            with self.assertRaisesRegex(ProcessProbationHold, "SUBPROCESS_TIMEOUT_KILLED"):
                _run_with_policy(graph, "cortex", "hero", operator_approved=True,
                                 timeout_seconds=1, policy=synthetic_policy(graph))

    def test_unknown_code_target_forbidden(self):
        p = synthetic_policy()
        p["target"] = "gen_untrusted_plugin"
        with self.assertRaisesRegex(ProcessProbationHold, "POLICY_DISABLED_OR_TARGET_HOLD"):
            _check_policy(p)

    def test_public_api_rejects_synthetic_fixture_not_pinned_to_archive(self):
        graph = archived_graph()
        with self.assertRaisesRegex(ProcessProbationHold, "ARCHIVE_SOURCE_SHA_MISMATCH"):
            run_approved_process_probation(graph, "cortex", "hero", operator_approved=True)

    def test_only_python_isolation_flags_and_clean_environment_passed(self):
        graph = archived_graph()
        real_subprocess_run = subprocess.run
        captured = []
        def spy(cmd, **kwargs):
            captured.append((cmd, kwargs))
            return real_subprocess_run(cmd, **kwargs)
        with patch("restored.legacy_process_probation.subprocess.run", side_effect=spy):
            _run_with_policy(graph, "cortex", "hero", operator_approved=True,
                             timeout_seconds=4, policy=synthetic_policy(graph))
        self.assertEqual(len(captured), 1)
        cmd, kwargs = captured[0]
        self.assertEqual(cmd[1:4], ["-I", "-S", "-B"])
        self.assertEqual(kwargs["env"], {})
        self.assertGreater(kwargs["timeout"], 0)
        self.assertNotIn("shell", kwargs)

    def test_worker_only_fixed_json_abi_not_source_code(self):
        graph = archived_graph()
        graph["source_code"] = "print('NOT_ALLOWED')"
        p = synthetic_policy(graph)
        # Even a syntactically valid extra JSON field is rejected by child
        # after all policy/code pins are checked.
        with self.assertRaisesRegex(ProcessProbationHold, "CHILD_PROBATION_HOLD"):
            _run_with_policy(graph, "cortex", "hero", operator_approved=True,
                             timeout_seconds=4, policy=p)


if __name__ == "__main__":
    unittest.main()
