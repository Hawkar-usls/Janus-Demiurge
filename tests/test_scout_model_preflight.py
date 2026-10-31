"""Fail-closed Scout Copilot preflight and 1-agent daily canary tests."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scout_model_preflight import classify
from demiurge_scout_snapshot_only import build_report


def event(kind, content):
    return json.dumps({"type": kind, "data": {"content": content}})


class ScoutModelPreflightTests(unittest.TestCase):
    def test_real_assistant_json_can_unlock_one_model(self):
        output = event("assistant.message", '{"preflight":"PASS"}')
        self.assertEqual(classify(output, 0),
                         {"model_status": "AVAILABLE", "failure_reason": "none"})

    def test_prompt_echo_and_model_nonanswer_cannot_unlock(self):
        echoed = event("user.message", 'Return only {"preflight":"PASS"}')
        self.assertEqual(classify(echoed, 0)["model_status"], "UNAVAILABLE")
        self.assertEqual(classify('{"preflight":"PASS"}', 0)["model_status"], "UNAVAILABLE")
        self.assertEqual(classify("PASS", 0)["model_status"], "UNAVAILABLE")
        self.assertEqual(classify(event("assistant.message", '{"preflight":"WRONG"}'), 0)["model_status"],
                         "UNAVAILABLE")
        self.assertEqual(classify(event("assistant.message", '{"preflight":"PASS","extra":1}'), 0)["model_status"],
                         "UNAVAILABLE")

    def test_shared_quota_error_triggers_fail_closed_without_spending_seventeen_calls(self):
        output = event("model.call_failure", '{"errorCode":"quota_exceeded"}')
        self.assertEqual(classify(output, 1),
                         {"model_status": "QUOTA_EXHAUSTED", "failure_reason": "rate_limit"})

    def test_cli_error_nonzero_and_invalid_flags_refused(self):
        self.assertEqual(classify(event("assistant.message", '{"preflight":"PASS"}'), 1)["model_status"],
                         "UNAVAILABLE")
        self.assertEqual(classify("error: --no-remote was removed", 2)["failure_reason"],
                         "invalid_cli_argument")

    def test_policy_hold_is_never_model_evidence(self):
        agent = {"id": "TEST", "role": "TEST", "target_repo": "owner/repo",
                 "target_ref": "main", "focus": "read-only"}
        report = build_report(agent, None, {"target_commit": "a" * 40},
                              model_status="SKIPPED_POLICY", token_fp="deadbeef",
                              failure_reason="policy_hold")
        self.assertEqual(report["status"], "DEGRADED_MODEL_POLICY_HOLD")
        self.assertFalse(report["model_preflight"]["model_call_attempted_by_this_scout"])
        self.assertFalse(report["evidence_gate"]["model_output_is_independent_confirmation"])
        self.assertEqual(report["synthesis_failure_reason"], "policy_hold")

    def test_canary_and_least_privilege_contract(self):
        workflow = (ROOT / ".github/workflows/janus-demiurge-scout-swarm.yml").read_text()
        self.assertIn("max-parallel: 4", workflow)
        self.assertIn("default: snapshot_only", workflow)
        self.assertIn("matrix.id == 'SCOUT_TERMINAL_07'", workflow)
        self.assertIn("github.event.schedule == '41 0 * * *'", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("permissions:\n      contents: read\n      copilot-requests: write", workflow)
        self.assertIn("tools/scout_model_preflight.py", workflow)
        self.assertIn("failure_reason", workflow)
        self.assertNotIn("grep -q 'PASS'", workflow)
        self.assertNotIn("--no-remote", workflow)


if __name__ == "__main__":
    unittest.main()
