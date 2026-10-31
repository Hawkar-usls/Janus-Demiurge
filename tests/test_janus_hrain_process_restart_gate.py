"""Disposable HRAiN real subprocess crash/restart; never owner-private memory."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.janus_hrain_process_restart_gate import (
    SCHEMA, run_gate, validate_graph,
)


class HrainHardRestartGateTests(unittest.TestCase):
    def test_real_child_sigkill_and_fresh_python_restore(self):
        result = run_gate()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"], "PASS_SYNTHETIC_HARD_CRASH_RESTART")
        self.assertTrue(result["hard_kill_observed"])
        self.assertTrue(result["torn_pending_file_isolated"])
        self.assertTrue(result["authoritative_state_unchanged_after_crash"])
        self.assertTrue(result["separate_process_restore_verified"])
        self.assertTrue(result["corrupt_authoritative_file_rejected"])
        self.assertFalse(result["private_graph_used"])
        self.assertFalse(result["production_autonomy_authorized"])
        self.assertFalse(result["real_owner_process_restart_tested"])

    def test_dangling_edge_and_malformed_graph_hold(self):
        good={"nodes":{"core":{"id":"core"},"shrine":{"id":"shrine"},
                       "daemon":{"id":"daemon"},"observer":{"id":"observer"}},
              "edges":{},"tick":0,"node_counter":4}
        validate_graph(good)
        for bad in ({**good,"nodes":{}},
                    {**good,"edges":{"core->unknown":{"direction":"bidir"}}},
                    {**good,"node_counter":"invalid"}):
            with self.assertRaises(ValueError):
                validate_graph(bad)

    def test_ledger_and_private_paths_not_in_report_contract(self):
        result = run_gate()
        self.assertNotIn("root_path", result)
        self.assertNotIn("private_owner_source", result)
        self.assertNotIn("auth_token", result)


if __name__ == "__main__":
    unittest.main()
