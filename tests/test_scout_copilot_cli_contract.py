"""Offline regression guards for Copilot CLI option compatibility and Scout isolation."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScoutCopilotCliContractTests(unittest.TestCase):
    def test_both_model_commands_use_supported_session_sync_opt_out(self):
        workflow = (ROOT / ".github/workflows/janus-demiurge-scout-swarm.yml").read_text(encoding="utf-8")
        engine = (ROOT / "tools/demiurge_scout_swarm.py").read_text(encoding="utf-8")
        for body in (workflow, engine):
            self.assertNotIn("--no-remote", body)
            self.assertNotIn("--no-remote-export", body)
            self.assertIn("--sync-session=off", body)
            self.assertIn("--no-custom-instructions", body)
            self.assertIn("--disable-builtin-mcps", body)
            self.assertIn("--deny-tool=write", body)
            self.assertIn("--deny-tool=shell", body)

    def test_preflight_failure_reason_is_passed_to_snapshot_only_reports(self):
        workflow = (ROOT / ".github/workflows/janus-demiurge-scout-swarm.yml").read_text(encoding="utf-8")
        fallback = (ROOT / "tools/demiurge_scout_snapshot_only.py").read_text(encoding="utf-8")
        self.assertIn("FAILURE_REASON='invalid_cli_argument'", workflow)
        self.assertIn("default: snapshot_only", workflow)
        self.assertIn("inputs.synthesis_rollout == 'canary'", workflow)
        self.assertIn("matrix.id == 'SCOUT_TERMINAL_07'", workflow)
        self.assertIn("SKIPPED_POLICY", workflow)
        self.assertIn('failure_reason=$FAILURE_REASON', workflow)
        self.assertIn('--failure-reason', workflow)
        self.assertIn("synthesis_failure_reason", fallback)
        self.assertIn("model_call_attempted_by_this_scout", fallback)
        self.assertIn('"target_repository_write": False', fallback)
        self.assertIn('"world_truth": False', fallback)


if __name__ == "__main__":
    unittest.main()
