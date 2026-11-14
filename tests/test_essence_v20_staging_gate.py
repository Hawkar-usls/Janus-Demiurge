"""Cross-run research canary policy: only independently evaluated descendants."""
from __future__ import annotations
import copy
import datetime
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v19_gradirnya as e
from tools import essence_v20_staging_gate as gate

class StagingEligibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root=Path(cls.tmp.name)
        src=root/"data";src.mkdir()
        for day in range(44):
            date=(datetime.date(2026,7,1)+datetime.timedelta(days=day)).isoformat()
            for i,name in enumerate(("LINEAR","TRUMP","OSIRIS","CONNECTION","ECHO")):
                (src/f"JANUS-{name}-{date}-CASE{day}-{i}.json").write_text(
                    json.dumps({"schema":"test","key":i,f"feature_{i}":True}))
        e.prepare(src,"b"*40,root/"splits")
        cls.validation=e.read_json(root/"splits"/"validation.json")
        cls.holdout=e.read_json(root/"splits"/"holdout.json")
        cls.root=root

    def signed(self,obj):
        obj["receipt_sha256"]=e.seal({k:v for k,v in obj.items() if k!="receipt_sha256"})
        return obj

    def receipts(self):
        v=self.validation
        lineage={
            "schema":e.LINEAGE,"cell":0,"source_commit":v["source_commit"],
            "dataset_sha256":v["dataset_sha256"],
            "validation_sha256":v["packet_sha256"],
            "holdout_sha256":self.holdout["packet_sha256"],
            "initial_weights_sha256":"a"*64,
            "final_weights_sha256":"b"*64,
            "cross_run_inheritance":{"parent_weights_sha256":"a"*64,
                                      "ancestry_depth":1},
            "accepted_generations":1,"production_authority":False
        }
        self.signed(lineage)
        verdict={
            "schema":"janus.essence.gradirnya_verifier/1.9",
            "cell":0,"source_commit":v["source_commit"],
            "lineage_sha256":lineage["receipt_sha256"],
            "holdout_sha256":self.holdout["packet_sha256"],
            "gate":"RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN",
            "diversity_gate":True,"heldout_represented_classes":4,
            "heldout_majority_fraction":0.4,
            "nll_gain_vs_prior":0.15,"accuracy_gain_vs_prior":0.1,
            "research_artifact_only":True,
            "externally_custodied_test":False,
            "automatic_production_promotion":False
        }
        self.signed(verdict)
        return verdict,lineage

    def test_positive_policy_still_has_no_production_authority(self):
        verdict,lineage=self.receipts()
        self.assertTrue(gate.eligible(verdict,lineage,self.validation))
        self.assertFalse(verdict["automatic_production_promotion"])
        self.assertFalse(lineage["production_authority"])

    def test_low_information_holdout_never_starts_canary(self):
        verdict,lineage=self.receipts()
        verdict["gate"]="HOLD_DEGENERATE_TEMPORAL_COHORT"
        self.signed(verdict)
        self.assertFalse(gate.eligible(verdict,lineage,self.validation))

    def test_future_only_lineage_required(self):
        verdict,lineage=self.receipts()
        lineage["cross_run_inheritance"]=None
        self.signed(lineage)
        verdict["lineage_sha256"]=lineage["receipt_sha256"]
        self.signed(verdict)
        self.assertFalse(gate.eligible(verdict,lineage,self.validation))

    def test_forged_source_or_receipt_rejected(self):
        verdict,lineage=self.receipts()
        forged=copy.deepcopy(verdict)
        forged["cell"]=1
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_NEW_SUCCESSOR_RESEARCH_RECEIPTS"):
            gate.eligible(forged,lineage,self.validation)

    def test_reject_staged_checkpoint_not_bound_to_parent(self):
        verdict,lineage=self.receipts()
        lineage["cross_run_inheritance"]["parent_weights_sha256"]="c"*64
        self.signed(lineage)
        verdict["lineage_sha256"]=lineage["receipt_sha256"]
        self.signed(verdict)
        with self.assertRaisesRegex(ValueError,"CROSS_RUN_STARTING_WEIGHTS_NOT_PINNED"):
            gate.eligible(verdict,lineage,self.validation)

    def test_sealed_test_packet_cannot_be_used_to_canary_tune(self):
        verdict,lineage=self.receipts()
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_CANARY_VALIDATION_PACKET"):
            gate.eligible(verdict,lineage,self.holdout)

    def test_zero_qualified_children_produce_immutable_hold_not_fake_pass(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            child=root/"children"/"essence-v20-offspring-0-123"
            child.mkdir(parents=True)
            (root/"verdicts").mkdir()
            verdict,lineage=self.receipts()
            verdict["gate"]="HOLD_NOT_BETTER_THAN_FROZEN_PRIOR_AND_PARENT"
            self.signed(verdict)
            (root/"verdicts"/"cell-0.json").write_text(json.dumps(verdict))
            (child/"lineage.json").write_text(json.dumps(lineage))
            (child/"offspring.pt").write_bytes(b"not a model, must never execute")
            val=root/"validation.json";val.write_text(json.dumps(self.validation))
            report=gate.stage(root/"children",root/"verdicts",val,root/"stage")
            self.assertEqual(report["status"],"HOLD_NO_ELIGIBLE_CROSS_RUN_SUCCESSOR")
            self.assertFalse(report["automatic_service_promotion"])
            self.assertFalse(report["real_deployed_service_rollback"])
            self.assertEqual(list((root/"stage").glob("cell-*")),[])

if __name__=="__main__":
    unittest.main()
