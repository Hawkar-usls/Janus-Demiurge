"""ESSENCE v1.9: real gradient lineage and fail-closed separated evaluation."""
from __future__ import annotations
import copy
import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v19_gradirnya as e

class GradirnyaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source="a"*40

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        data=self.path/"source"
        data.mkdir()
        for day in range(44):
            dt=(datetime.date(2026,7,1)+datetime.timedelta(days=day)).isoformat()
            for j,name in enumerate(["LINEAR","TRUMP","OSIRIS","CONNECTION","ECHO"]):
                (data/f"JANUS-{name}-{dt}-CASE{day}-{j}.json").write_text(
                    json.dumps({"schema":"test", "sample":j, f"key_{j}":True,
                                "recorded":dt, "summary":{"a":j}}))
        self.manifest=e.prepare(data,self.source,self.path/"input")
        self.train=e.read_json(self.path/"input"/"train.json")
        self.val=e.read_json(self.path/"input"/"validation.json")
        self.hold=e.read_json(self.path/"input"/"holdout.json")

    def test_true_gradient_two_generations_and_receipt(self):
        result=e.train(0,self.train,self.val,self.manifest,self.path/"child",steps=20)
        self.assertEqual(len(result["generations"]),2)
        self.assertTrue(result["true_gradient_training"])
        self.assertFalse(result["training_saw_holdout"])
        self.assertEqual(result["holdout_sha256"],self.hold["packet_sha256"])
        self.assertFalse(result["production_authority"])
        self.assertTrue(any(x["proposed_weights_sha256"]!=x["parent_weights_sha256"]
                            for x in result["generations"]))
        self.assertEqual(result["generations"][1]["parent_weights_sha256"],
                         result["generations"][0]["retained_weights_sha256"])
        verified=e.verify(0,self.hold,self.manifest,result,self.path/"child"/"offspring.pt")
        self.assertEqual(verified["heldout_rows"],len(self.hold["rows"]))
        self.assertIn(verified["gate"],("RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN",
                                       "HOLD_NOT_BETTER_THAN_FROZEN_PRIOR_AND_PARENT"))
        self.assertFalse(verified["externally_custodied_test"])

    def test_replay_cannot_use_holdout_as_train(self):
        with self.assertRaisesRegex(ValueError,"SPLIT_DIGEST_OR_SOURCE_MISMATCH"):
            e.train(0,self.hold,self.val,self.manifest,self.path/"bad",steps=20)

    def test_chronology_and_disjointness(self):
        self.assertLess(self.manifest["split_dates"]["train"][1],
                        self.manifest["split_dates"]["validation"][0])
        self.assertLess(self.manifest["split_dates"]["validation"][1],
                        self.manifest["split_dates"]["holdout"][0])
        self.assertFalse({x["identity"] for x in self.train["rows"]}&
                         {x["identity"] for x in self.hold["rows"]})

    def test_tampered_split_fails_even_resealed_wrong_hash(self):
        forged=copy.deepcopy(self.train)
        forged["rows"][0]["label"]=(forged["rows"][0]["label"]+1)%len(e.r.LABELS)
        with self.assertRaisesRegex(ValueError,"SPLIT_DIGEST_OR_SOURCE_MISMATCH"):
            e.train(0,forged,self.val,self.manifest,self.path/"bad",steps=20)
        forged["packet_sha256"]=e.seal({k:v for k,v in forged.items() if k!="packet_sha256"})
        with self.assertRaisesRegex(ValueError,"TRAIN_PRIOR_COUNT_MISMATCH"):
            e.train(0,forged,self.val,self.manifest,self.path/"bad",steps=20)

    def test_tampered_lineage_fails_in_verifier(self):
        result=e.train(0,self.train,self.val,self.manifest,self.path/"child",steps=20)
        forgery=copy.deepcopy(result)
        forgery["production_authority"]=True
        with self.assertRaisesRegex(ValueError,"LINEAGE_OR_HOLDOUT_RECEIPT_TAMPERED"):
            e.verify(0,self.hold,self.manifest,forgery,self.path/"child"/"offspring.pt")

    def test_missing_or_corrupt_weight_file_denied(self):
        result=e.train(0,self.train,self.val,self.manifest,self.path/"child",steps=20)
        weights=self.path/"child"/"offspring.pt"
        weights.write_bytes(weights.read_bytes()+b"forged")
        with self.assertRaisesRegex(ValueError,"OFFSPRING_SHA_MISMATCH"):
            e.verify(0,self.hold,self.manifest,result,weights)

    def test_holdout_requires_strong_frozen_train_prior(self):
        result=e.train(0,self.train,self.val,self.manifest,self.path/"child",steps=20)
        v=e.verify(0,self.hold,self.manifest,result,self.path/"child"/"offspring.pt")
        self.assertIn("frozen_train_prior",v)
        if v["gate"]=="RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN":
            self.assertGreaterEqual(v["nll_gain_vs_prior"],0.02)
            self.assertGreater(v["accuracy_gain_vs_prior"],0)
        self.assertFalse(v["automatic_production_promotion"])

    def test_fake_train_prior_rejected_even_if_receipt_resigned(self):
        altered=copy.deepcopy(self.manifest)
        altered["train_label_counts"][0]+=1
        altered["train_label_counts"][1]-=1
        altered["receipt_sha256"]=e.seal({k:v for k,v in altered.items() if k!="receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"TRAIN_PRIOR_COUNT_MISMATCH"):
            e.train(0,self.train,self.val,altered,self.path/"fake",steps=20)

    def test_collapsed_temporal_holdout_must_be_hold(self):
        parent=e.train(0,self.train,self.val,self.manifest,self.path/"child",steps=20)
        altered_hold=copy.deepcopy(self.hold)
        for row in altered_hold["rows"]:
            row["label"]=len(e.r.LABELS)-1
        altered_hold["packet_sha256"]=e.seal({k:v for k,v in altered_hold.items() if k!="packet_sha256"})
        altered_manifest=copy.deepcopy(self.manifest)
        altered_manifest["split_sha256"]["holdout"]=altered_hold["packet_sha256"]
        altered_manifest["receipt_sha256"]=e.seal({k:v for k,v in altered_manifest.items() if k!="receipt_sha256"})
        altered_parent=copy.deepcopy(parent)
        altered_parent["manifest_sha256"]=altered_manifest["receipt_sha256"]
        altered_parent["holdout_sha256"]=altered_hold["packet_sha256"]
        altered_parent["receipt_sha256"]=e.seal({k:v for k,v in altered_parent.items() if k!="receipt_sha256"})
        result=e.verify(0,altered_hold,altered_manifest,altered_parent,self.path/"child"/"offspring.pt")
        self.assertEqual(result["gate"],"HOLD_DEGENERATE_TEMPORAL_COHORT")
        self.assertEqual(result["heldout_represented_classes"],1)
        self.assertFalse(result["diversity_gate"])
        self.assertFalse(result["automatic_production_promotion"])

    def test_no_automatic_research_overwrite(self):
        with self.assertRaises(FileExistsError):
            e.prepare(self.path/"source",self.source,self.path/"input")
        with self.assertRaises(FileExistsError):
            e.atomic_json(self.path/"input"/"manifest.json",{})

    def test_unbounded_generations_and_invalid_cell_denied(self):
        with self.assertRaisesRegex(ValueError,"BOUNDED_MICROCORE_TRAINING_ONLY"):
            e.train(6,self.train,self.val,self.manifest,self.path/"bad",steps=20)
        with self.assertRaisesRegex(ValueError,"BOUNDED_MICROCORE_TRAINING_ONLY"):
            e.train(0,self.train,self.val,self.manifest,self.path/"bad",steps=8000)

if __name__=="__main__":
    unittest.main()
