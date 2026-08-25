import json
import tempfile
import unittest
from pathlib import Path

from restored.daemon_liveness_observer import snapshot
from restored.maxwell_compactor import compact_file, compact_records


class MaxwellTests(unittest.TestCase):
    def test_deterministic_semantics_except_generated_at(self):
        rows = [
            {"timestamp": "2026-01-01T00:00:00Z", "type": "INFO", "x": 1},
            {"timestamp": "2026-01-01T00:01:00Z", "type": "ERROR", "error": "boom"},
        ]
        a = compact_records(rows, source="test")
        b = compact_records(rows, source="test")
        a.pop("generated_at")
        b.pop("generated_at")
        self.assertEqual(a, b)
        self.assertTrue(a["originals_preserved"])
        self.assertFalse(a["destructive_actions"])
        self.assertEqual(a["error_like_count"], 1)

    def test_source_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "log.jsonl"
            out = Path(td) / "crystal.json"
            original = '{"type":"INFO","x":1}\n'
            src.write_text(original, encoding="utf-8")
            compact_file(src, out)
            self.assertEqual(src.read_text(encoding="utf-8"), original)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8"))["originals_preserved"])
            with self.assertRaises(ValueError):
                compact_file(src, src)


class DaemonObserverTests(unittest.TestCase):
    def test_fresh_and_missing_without_actuation(self):
        with tempfile.TemporaryDirectory() as td:
            hb = Path(td) / "heartbeat.json"
            hb.write_text('{"status":"ok"}', encoding="utf-8")
            result = snapshot([hb, Path(td) / "missing.json"], stale_after_sec=999999)
            self.assertTrue(result["no_actuation"])
            self.assertFalse(result["automatic_restart"])
            self.assertFalse(result["automatic_retry"])
            self.assertFalse(result["automatic_recovery"])
            statuses = {x["status"] for x in result["observations"]}
            self.assertEqual(statuses, {"FRESH", "MISSING"})


if __name__ == "__main__":
    unittest.main()
