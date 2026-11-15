"""Prospective neural weights: synthetic negative gates, not real GH proof."""
from datetime import datetime,timezone,timedelta
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import sentinel_weight_gate as g
from tools import sentinel_transformer as m

NOW=datetime(2026,11,15,12,0,tzinfo=timezone.utc)


def model(weights):
    meta={"schema":m.SCHEMA,"model_type":"CAUSAL_ATTENTION_SHARED_A_B",
          "model_width":m.WIDTH,"sequence_len":m.SEQ,
          "temperature":0.5,"weights":{"toy":weights},
          "production_authority":False,"dispatch_authority":False,
          "last_test_utc":NOW.isoformat(),"status":"RESEARCH_ONLY"}
    meta["checkpoint_sha256"]=m.digest(meta)
    return meta


def cohort():
    return [([1]*8+[64+(i%16)],1 if i%8==0 else 0,10000+i,
             (NOW+timedelta(minutes=i+1)).isoformat())
            for i in range(128)]


class ProspectiveWeightGate(unittest.TestCase):
    def setUp(self):
        self.parent=model([1.])
        self.child=model([2.])
        self.child["parent_checkpoint_sha256"]=self.parent["checkpoint_sha256"]
        self.child["replaces_previous"]=False
        self.child["checkpoint_sha256"]=m.digest({
            k:v for k,v in self.child.items() if k!="checkpoint_sha256"})

    def test_two_unseen_64_cohorts_must_both_win(self):
        x=cohort()
        parent_scores=[.5]*128
        candidate=[.9 if y[1] else .1 for y in x]
        r=g.paired_gate(self.parent,self.child,x,
                        parent_prob=parent_scores,child_prob=candidate)
        self.assertTrue(r["accepted"])
        self.assertEqual(r["status"],"PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN")
        self.assertEqual([p["n"] for p in r["split_evidence"]],[64,64])
        self.assertFalse(r["production_authority"])
        self.assertEqual(len(set(r["source_run_ids"])),128)

    def test_a_win_b_loss_must_not_be_promoted(self):
        x=cohort()
        candidate=[(.9 if y[1] else .1) if i<64 else .5
                   for i,y in enumerate(x)]
        r=g.paired_gate(self.parent,self.child,x,
                        parent_prob=[.5]*128,child_prob=candidate)
        self.assertFalse(r["accepted"])
        self.assertEqual(r["status"],"HOLD_NO_PAIRED_NEURAL_GAIN")

    def test_no_real_changed_weights_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"NO_GENUINE_NEURAL_WEIGHT_CHANGE"):
            g.paired_gate(self.parent,self.parent,cohort(),
                          parent_prob=[.5]*128,child_prob=[.2]*128)

    def test_no_failure_signal_or_low_diversity_refused(self):
        x=cohort()
        x=[(p,0,r,t) for p,_,r,t in x]
        with self.assertRaisesRegex(ValueError,"FORWARD_COHORT_LACKS_FAIL"):
            g.paired_gate(self.parent,self.child,x,
                          parent_prob=[.5]*128,child_prob=[.1]*128)

    def test_manifest_requires_precommitted_parent_and_sha(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"sentinel/model"
            (root/"candidates").mkdir(parents=True)
            (root/"checkpoint.json").write_text(json.dumps(self.parent))
            (root/"candidates/123456.json").write_text(json.dumps(self.child))
            v={"schema":g.MANIFEST,"source_run_id":"123456",
               "candidate_file":"sentinel/model/candidates/123456.json",
               "candidate_checkpoint_sha256":self.child["checkpoint_sha256"],
               "parent_checkpoint_sha256":self.parent["checkpoint_sha256"],
               "production_authority":False,"research_only":True}
            v["receipt_sha256"]=m.digest(v)
            (root/"pending-challenge.json").write_text(json.dumps(v))
            frozen=g.frozen_models(d)
            self.assertEqual(frozen[2]["checkpoint_sha256"],self.child["checkpoint_sha256"])
            v["parent_checkpoint_sha256"]="tampered"
            (root/"pending-challenge.json").write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,"UNTRUSTED_NEURAL_CHALLENGE_MANIFEST"):
                g.frozen_models(d)


if __name__=="__main__":
    unittest.main()
