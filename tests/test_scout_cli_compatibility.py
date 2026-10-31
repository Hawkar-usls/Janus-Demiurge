import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import demiurge_scout_swarm as swarm


class ScoutCliCompatibilityTests(unittest.TestCase):
    def test_actual_scout_call_preserves_restrictions_and_parses_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "mission.md").write_text("Observe only the supplied snapshot.")
            response = json.dumps({"type": "assistant.message", "data": {
                "content": json.dumps({"summary": "Checked the current snapshot", "lessons": ["Recheck next turn"]})}})
            with mock.patch.object(swarm, "ROOT", root), mock.patch.object(
                    swarm.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=response)) as run:
                result = swarm.call_copilot({"agent_file": "mission.md", "focus": "recovery"},
                                            {"target_commit": "a" * 40}, {"turn": 2})
                self.assertEqual(result["summary"], "Checked the current snapshot")
                args, kwargs = run.call_args
                command = args[0]
                self.assertIn("--sync-session=off", command)
                for removed in ("--no-remote", "--no-remote-export"):
                    self.assertNotIn(removed, command)
                for denied in ("read", "write", "shell", "url", "memory"):
                    self.assertIn("--deny-tool=" + denied, command)
                self.assertIn("--no-custom-instructions", command)
                self.assertIn("--disable-builtin-mcps", command)
                self.assertIn("--no-ask-user", command)
                self.assertNotEqual(Path(kwargs["cwd"]), ROOT)
                self.assertEqual(kwargs["timeout"], 180)
                self.assertEqual(kwargs["env"]["COPILOT_AUTO_UPDATE"], "false")
                self.assertEqual(kwargs["env"]["GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS"], "false")

    def test_preflight_uses_same_supported_options_and_pinned_cli(self):
        workflow = (ROOT / ".github/workflows/janus-demiurge-scout-swarm.yml").read_text()
        self.assertNotIn("--no-remote", workflow)
        self.assertIn("--sync-session=off", workflow)
        self.assertEqual(workflow.count("npm install -g @github/copilot@1.0.105"), 2)

    def test_cli_failure_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "mission.md").write_text("Observe only.")
            with mock.patch.object(swarm, "ROOT", root), mock.patch.object(
                    swarm.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="quota_exceeded")):
                with self.assertRaisesRegex(RuntimeError, "COPILOT_CLI_EXIT_1:quota_exceeded"):
                    swarm.call_copilot({"agent_file": "mission.md", "focus": "recovery"}, {}, {})


if __name__ == "__main__":
    unittest.main()
