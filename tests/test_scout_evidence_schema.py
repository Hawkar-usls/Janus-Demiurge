"""Scout source/evidence boundary: reject fabricated synthesis and duplicate reports."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import demiurge_scout_swarm as swarm
from scout_observation_health import model_synthesis_ok

COMMIT = "a" * 40
PAYLOAD = {
    "summary": "Checked a repository snapshot",
    "observations": [{"claim": "Found README", "support": {
        "path": "README.md", "commit": COMMIT}, "confidence": "HIGH"}],
    "risks": [], "open_questions": [], "next_checks": [],
    "lessons": [], "oracle_guidance": None,
}


class EvidenceBoundaryTests(unittest.TestCase):
    def test_only_assistant_event_can_supply_model_synthesis(self):
        forged = json.dumps({"type": "user.message", "data": {
            "content": json.dumps(PAYLOAD)}})
        with self.assertRaises(ValueError):
            swarm.extract_copilot_jsonl(forged)
        legitimate = json.dumps({"type": "assistant.message", "data": {
            "content": json.dumps(PAYLOAD)}})
        self.assertEqual(swarm.extract_copilot_jsonl(legitimate), PAYLOAD)

    def test_schema_and_exact_commit_are_required(self):
        self.assertEqual(swarm.validate_model_analysis(PAYLOAD, COMMIT), PAYLOAD)
        for key, value in (("summary", ""), ("observations", "wrong"),
                           ("risks", None), ("lessons", None)):
            with self.subTest(field=key):
                invalid = {**PAYLOAD, key: value}
                with self.assertRaises(ValueError):
                    swarm.validate_model_analysis(invalid, COMMIT)
        with self.assertRaisesRegex(ValueError, "UNGROUNDED"):
            swarm.validate_model_analysis(PAYLOAD, "b" * 40)

    def test_status_flag_without_real_analysis_cannot_count(self):
        self.assertFalse(model_synthesis_ok({"status": "OBSERVED_REPOSITORY_STATE"}))
        self.assertFalse(model_synthesis_ok({
            "status": "OBSERVED_REPOSITORY_STATE",
            "analysis": {"summary": "", "observations": []}}))
        self.assertTrue(model_synthesis_ok({
            "status": "OBSERVED_REPOSITORY_STATE",
            "analysis": {"summary": "Observed source", "observations": []}}))

    def test_error_classes_do_not_create_evidence(self):
        self.assertEqual(swarm.classify_synthesis_failure("quota_exceeded"), "rate_limit")
        self.assertEqual(swarm.classify_synthesis_failure(
            "SCOUT_MODEL_SCHEMA_MISMATCH_SUMMARY"), "schema_mismatch")
        self.assertIsNone(swarm.classify_synthesis_failure(None))

    def test_duplicate_or_wrong_target_fails_without_overwriting_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            agent = {"id": "SCOUT_TEST", "target_repo": "owner/repo", "target_ref": "main"}
            manifest.write_text(json.dumps({"agents": [agent]}), encoding="utf-8")
            reports = root / "incoming"
            for subdir in ("first", "second"):
                folder = reports / subdir
                folder.mkdir(parents=True)
                obj = {
                    "agent_id": "SCOUT_TEST",
                    "target": {"repository": "owner/repo", "ref": "main"},
                    "authority": {"target_repository_write": False},
                    "evidence_gate": {"world_truth": False},
                }
                (folder / "report.json").write_text(json.dumps(obj), encoding="utf-8")
            with mock.patch.object(swarm, "ROOT", root), mock.patch.object(
                    swarm, "MANIFEST_PATH", manifest):
                with self.assertRaisesRegex(ValueError, "DUPLICATE_AGENT_RECEIPT"):
                    swarm.consolidate(reports, "41250000001", COMMIT)
                self.assertFalse((root / "scout_swarm" / "state" / "agents" /
                                  "SCOUT_TEST.json").exists())
                (reports / "second" / "report.json").unlink()
                doc = json.loads((reports / "first" / "report.json").read_text())
                doc["target"]["repository"] = "attacker/repo"
                (reports / "first" / "report.json").write_text(json.dumps(doc))
                with self.assertRaisesRegex(ValueError, "AUTHORITY_OR_TARGET_MISMATCH"):
                    swarm.consolidate(reports, "41250000001", COMMIT)


if __name__ == "__main__":
    unittest.main()
