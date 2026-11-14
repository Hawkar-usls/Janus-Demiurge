"""Sentinel prevents useless gradient jobs on low-information dated cohorts."""
from __future__ import annotations
import copy
import datetime
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v19_gradirnya as e
from tools import essence_v21_curriculum_sentinel as sentinel

class CurriculumAuditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root=Path(cls.tmp.name)
        src=root/"src";src.mkdir()
        for day in range(44):
            date=(datetime.date(2026,7,1)+datetime.timedelta(days=day)).isoformat()
            for i,kind in enumerate(("LINEAR","TRUMP","OSIRIS","CONNECTION","ECHO")):
                (src/f"JANUS-{kind}-{date}-EVIDENCE{day}-{i}.json").write_text(
                    json.dumps({"schema":"trial","feature":i,
                                f"key_{i}":"observed", "recorded_date":date}))
        cls.manifest=e.prepare(src,"b"*40,root/"splits")
        cls.train=e.read_json(root/"splits"/"train.json")
        cls.validation=e.read_json(root/"splits"/"validation.json")
        cls.holdout=e.read_json(root/"splits"/"holdout.json")

    def assess(self,holdout=None,validation=None,manifest=None,train=None):
        return sentinel.assess(manifest or self.manifest,
                               train or self.train,
                               validation or self.validation,
                               holdout or self.holdout)

    def reseal(self,packet):
        packet["packet_sha256"]=e.seal({k:v for k,v in packet.items() if k!="packet_sha256"})
        return packet

    def with_manifest(self,**packets):
        m=copy.deepcopy(self.manifest)
        for k,p in packets.items():
            m["split_sha256"][k]=p["packet_sha256"]
        m["receipt_sha256"]=e.seal({k:v for k,v in m.items() if k!="receipt_sha256"})
        return m

    def test_diverse_date_cohort_can_enter_research_only(self):
        r=self.assess()
        self.assertEqual(r["status"],"RESEARCH_COHORT_SUITABLE_FOR_TRIAL")
        self.assertTrue(r["eligible_for_research_training"])
        self.assertFalse(r["production_authority"])
        self.assertFalse(r["scientific_model_improvement_proven"])
        self.assertNotIn("heldout_class_counts",r)
        self.assertNotIn("heldout_labels",r)

    def test_collapsed_holdout_blocks_before_training(self):
        bad=copy.deepcopy(self.holdout)
        for row in bad["rows"]:row["label"]=len(e.r.LABELS)-1
        self.reseal(bad)
        result=self.assess(holdout=bad,manifest=self.with_manifest(holdout=bad))
        self.assertEqual(result["status"],"HOLD_PRETRAIN_COHORT_INFORMATION_FAILURE")
        self.assertIn("HOLD_HOLDOUT_LOW_INFORMATION",result["rejection_codes"])
        self.assertFalse(result["eligible_for_research_training"])

    def test_collapsed_validation_blocks_before_training(self):
        bad=copy.deepcopy(self.validation)
        for row in bad["rows"]:row["label"]=0
        self.reseal(bad)
        result=self.assess(validation=bad,manifest=self.with_manifest(validation=bad))
        self.assertIn("HOLD_VALIDATION_LOW_INFORMATION",result["rejection_codes"])

    def test_unmodified_hash_cannot_hide_label_injection(self):
        bad=copy.deepcopy(self.holdout)
        bad["rows"][0]["label"]=0
        with self.assertRaisesRegex(ValueError,"SPLIT_DIGEST_OR_SOURCE_MISMATCH"):
            self.assess(holdout=bad)

    def test_resealed_wrong_manifest_packet_denied(self):
        bad=copy.deepcopy(self.holdout)
        bad["rows"][0]["label"]=(bad["rows"][0]["label"]+1)%len(e.r.LABELS)
        self.reseal(bad)
        with self.assertRaisesRegex(ValueError,"PROSPECTIVE_PACKET_NOT_MANIFEST_BOUND"):
            self.assess(holdout=bad)

    def test_duplicate_identity_rejected_even_if_resigned(self):
        bad=copy.deepcopy(self.holdout)
        bad["rows"][0]["identity"]=self.train["rows"][0]["identity"]
        self.reseal(bad)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_DOCUMENT_ACROSS_COHORTS"):
            self.assess(holdout=bad,manifest=self.with_manifest(holdout=bad))

    def test_nonchronological_holdout_rejected(self):
        bad=copy.deepcopy(self.holdout)
        for row in bad["rows"]:row["date"]=self.train["rows"][0]["date"]
        self.reseal(bad)
        m=self.with_manifest(holdout=bad)
        m["split_dates"]["holdout"]=[bad["rows"][0]["date"]]*2
        m["receipt_sha256"]=e.seal({k:v for k,v in m.items() if k!="receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"NON_CHRONOLOGICAL_SPLITS"):
            self.assess(holdout=bad,manifest=m)

    def test_tampered_trust_parent_denied(self):
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_RESEARCH_PARENT"):
            sentinel.assess(self.manifest,self.train,self.validation,self.holdout,
                            past_parent={"production_authority":True})

if __name__=="__main__":
    unittest.main()
