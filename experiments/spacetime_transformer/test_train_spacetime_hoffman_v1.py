#!/usr/bin/env python3
"""JANUS science corpus: fail-closed provenance and held-out Hoffman checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import train_spacetime_hoffman_v1 as s


SOURCE=Path(__file__).with_name("spacetime_sources_v1.json")


class CorpusTests(unittest.TestCase):
    def test_38_sources_and_sealed_hoffman_counterevidence(self):
        obj,groups,digest=s.corpus(SOURCE)
        self.assertEqual(sum(map(len,groups.values())),38)
        self.assertEqual(len(s.HOFFMAN_REQUIRED),11)
        self.assertEqual(len(groups["train"]),24)
        self.assertEqual(len(groups["validation"]),6)
        self.assertEqual(len(groups["test"]),8)
        self.assertEqual(len(digest),64)

    def test_all_held_out_ids_disjoint(self):
        _,groups,_=s.corpus(SOURCE)
        ids=[{x["id"] for x in groups[k]} for k in s.SPLITS]
        self.assertFalse(ids[0]&ids[1])
        self.assertFalse(ids[0]&ids[2])
        self.assertFalse(ids[1]&ids[2])

    def test_train_falsehood_not_marked_as_established(self):
        _,groups,_=s.corpus(SOURCE)
        for part in groups.values():
            for item in part:
                if item["id"].startswith("hoffman_") and item["id"]!="hoffman_2000_shape_illusion":
                    self.assertNotIn(item["status"],
                        {"ESTABLISHED","ESTABLISHED_THEORY","OBSERVATION"})

    def test_untranscribed_video_not_training_input(self):
        obj,_,_=s.corpus(SOURCE)
        x=obj["excluded_user_reference"]
        self.assertEqual(x["video_id"],"wPRyiDMJ0ro")
        self.assertFalse(x["training_included"])
        self.assertFalse(x["transcript_obtained"])

    def test_prepare_texts_and_manifest_sealed(self):
        with tempfile.TemporaryDirectory() as d:
            manifest=s.prepare(SOURCE,d)
            self.assertEqual(manifest["source_record_count"],38)
            self.assertEqual(manifest["hoffman_research_cards"],11)
            self.assertTrue(manifest["train_isolated_from_validation_and_test"])
            for part in s.SPLITS:
                text=(Path(d)/(part+".txt")).read_text(encoding="utf8")
                self.assertGreater(len(text),1000)
                self.assertIn("Evidence:",text)
                self.assertIn("Source:",text)
            with self.assertRaisesRegex(ValueError,"REFUSE_TO_OVERWRITE"):
                s.prepare(SOURCE,d)

    def test_missing_2026_critical_peer_review_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data=json.loads(SOURCE.read_text(encoding="utf8"))
            data["records"]=[r for r in data["records"]
                             if r["id"]!="hoffman_2026_mattes_critique"]
            path=Path(d)/"corrupt.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"HOFFMAN_OR_COUNTEREVIDENCE_MISSING"):
                s.corpus(path)

    def test_misclassified_theory_as_observation_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data=json.loads(SOURCE.read_text(encoding="utf8"))
            next(r for r in data["records"] if r["id"]=="hoffman_2023_fusions")[
                "status"]="OBSERVATION"
            path=Path(d)/"wrong_status.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"HOFFMAN_SPECULATION_LAUNDERED_AS_FACT"):
                s.corpus(path)

    def test_source_without_credible_url_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data=json.loads(SOURCE.read_text(encoding="utf8"))
            data["records"][0]["source_url"]="not-a-source"
            path=Path(d)/"bad_source.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"MISSING_PRIMARY_SOURCE"):
                s.corpus(path)


if __name__=="__main__":
    unittest.main(verbosity=2)
