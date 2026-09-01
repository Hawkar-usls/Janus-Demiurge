import sys
import unittest
from pathlib import Path

# JANUS_GIT_LIFE_CONTROLLED_TRIGGER_2026_09_01: non-functional marker used to initiate one push-born Scout -> Life Gate integration run.

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scout_observation_health import classify_reports


class ScoutObservationHealthTests(unittest.TestCase):
    def test_snapshot_success_survives_model_failure(self):
        expected = ["A", "B"]
        reports = {
            "A": {"status": "DEGRADED_MODEL_UNAVAILABLE", "repository_snapshot": {"target_commit": "a"}, "model_error": "x"},
            "B": {"status": "DEGRADED_MODEL_UNAVAILABLE", "repository_snapshot": {"target_commit": "b"}, "model_error": "x"},
        }
        h = classify_reports(reports, expected)
        self.assertEqual(h["agents_observed"], 2)
        self.assertEqual(h["agents_model_synthesis_ok"], 0)
        self.assertEqual(h["status"], "LIVE_17_OF_17_SNAPSHOTS__MODEL_SYNTHESIS_DEGRADED")

    def test_target_failure_remains_degraded(self):
        expected = ["A", "B"]
        reports = {
            "A": {"status": "OBSERVED_REPOSITORY_STATE", "repository_snapshot": {"target_commit": "a"}},
            "B": {"status": "DEGRADED_TARGET_UNAVAILABLE", "repository_snapshot": {"snapshot_error": "clone failed"}},
        }
        h = classify_reports(reports, expected)
        self.assertEqual(h["agents_observed"], 1)
        self.assertEqual(h["agents_target_unavailable"], ["B"])
        self.assertEqual(h["status"], "DEGRADED_PARTIAL")

    def test_full_model_success_remains_live(self):
        expected = ["A", "B"]
        reports = {
            "A": {"status": "OBSERVED_REPOSITORY_STATE", "repository_snapshot": {"target_commit": "a"}},
            "B": {"status": "OBSERVED_REPOSITORY_STATE", "repository_snapshot": {"target_commit": "b"}},
        }
        h = classify_reports(reports, expected)
        self.assertEqual(h["agents_observed"], 2)
        self.assertEqual(h["agents_model_synthesis_ok"], 2)
        self.assertEqual(h["status"], "LIVE_17_OF_17")


if __name__ == "__main__":
    unittest.main()
