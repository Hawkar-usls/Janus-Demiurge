"""Contract tests for ESSENCE v2.2 source watcher: no network or promotion."""
from __future__ import annotations

import copy
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import essence_v22_source_watch as watch


class SourceWatch(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for day in range(44):
            date = (datetime.date(2026, 7, 1) +
                    datetime.timedelta(days=day)).isoformat()
            for i, name in enumerate(("LINEAR", "TRUMP", "OSIRIS", "CONNECTION", "ECHO")):
                (self.root / f"JANUS-{name}-{date}-SOURCE-{i}.json").write_text(
                    json.dumps({"schema": "record", f"feature_{i}": day,
                                "date": date, "evidence": "historical"}))
        self.source = "c" * 40

    @unittest.skipUnless(os.environ.get('ESSENCE_VERIFY_TORCH_PARITY') == '1',
                         'Torch parity verified separately in v1.9 contract')
    def test_matches_the_actual_training_collector_byte_for_byte(self):
        from tools import janus_essence_real_json_train as reference
        rows, parts, _ = watch.collect(self.root)
        groups, description = reference.collect(self.root)
        self.assertEqual(watch.digest(rows), description["dataset_sha256"])
        self.assertEqual(parts["train"], groups["train"])
        self.assertEqual(parts["validation"], groups["validation"])
        self.assertEqual(parts["holdout"], groups["test"])

    def test_diverse_source_only_requests_a_research_trial(self):
        result = watch.audit(self.root, self.source)
        self.assertTrue(result["eligible_for_research_trial"])
        self.assertEqual(result["status"], "READY_FOR_RESEARCH_TRIAL")
        self.assertFalse(result["production_authority"])
        self.assertFalse(result["model_quality_improvement_proven"])
        self.assertNotIn("holdout_label_counts", result)
        self.assertEqual(watch.decision(result, []), "DISPATCH_RESEARCH_ONLY")

    def test_heldout_class_collapse_is_a_hold(self):
        for path in list(self.root.glob("*.json")):
            if "2026-08-" in path.name:
                path.rename(self.root / ("OTHER-" + path.name))
        result = watch.audit(self.root, self.source)
        self.assertFalse(result["eligible_for_research_trial"])
        self.assertIn("HOLD_HOLDOUT_LOW_INFORMATION", result["rejection_codes"])
        self.assertEqual(watch.decision(result, []), "HOLD_SOURCE_NOT_READY")

    def test_rejected_report_cannot_be_resealed_without_integrity_change(self):
        result = watch.audit(self.root, self.source)
        edited = copy.deepcopy(result)
        edited["production_authority"] = True
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_SOURCE_READINESS"):
            watch.decision(edited, [])
        edited = copy.deepcopy(result)
        edited["eligible_for_research_trial"] = False
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_SOURCE_READINESS"):
            watch.decision(edited, [])

    def test_prior_attempt_same_dataset_deduplicates(self):
        result = watch.audit(self.root, self.source)
        runs = [{"display_title": "ESSENCE dataset " + result["dataset_sha256"],
                 "head_branch": "main", "status": "completed",
                 "conclusion": "failure"}]
        self.assertEqual(watch.decision(result, runs),
                         "HOLD_DATASET_ALREADY_ATTEMPTED")
        self.assertEqual(watch.decision(result, runs, exhaustive=False),
                         "HOLD_DISPATCH_HISTORY_NOT_EXHAUSTIVE")

    def test_invalid_source_commit_denied(self):
        with self.assertRaisesRegex(ValueError, "UNPINNED_META_REGISTRY_COMMIT"):
            watch.audit(self.root, "main")

    def test_duplicate_versions_not_counted_as_new_data(self):
        before = watch.audit(self.root, self.source)["dataset_sha256"]
        original = next(self.root.glob("JANUS-LINEAR-2026-07-01*.json"))
        (self.root / original.name.replace(".json", "-v2.json")).write_bytes(
            original.read_bytes())
        self.assertEqual(watch.audit(self.root, self.source)["dataset_sha256"],
                         before)


if __name__ == "__main__":
    unittest.main()
