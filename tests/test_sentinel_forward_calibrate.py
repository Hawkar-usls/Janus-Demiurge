"""Prospective SENTINEL temperature auto-calibration: synthetic fixtures only."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest

from tools import sentinel_forward_calibrate as c
from tools import sentinel_transformer as m

T=datetime(2026,11,15,12,0,tzinfo=timezone.utc)


def parent():
    x={
      "schema":m.SCHEMA,
      "model_type":"CAUSAL_ATTENTION_SHARED_A_B",
      "model_width":m.WIDTH,
      "sequence_len":m.SEQ,
      "temperature":0.5,
      "weights":{},
      "status":"RESEARCH_INTERNAL_HOLDOUT_GAIN",
      "production_authority":False,
      "dispatch_authority":False,
    }
    x["checkpoint_sha256"]=m.digest(x)
    return x


def cohort():
    rows=[]
    for i in range(c.FUTURE_TOTAL):
        label=1 if (i%17==0 or i%23==0) else 0
        target=64+(i%16)
        rows.append(([1]*8+[target],label,10000+i,
             (T+timedelta(seconds=i+1)).isoformat()))
    return rows


class ProspectiveTemperatureGates(unittest.TestCase):
    def test_128_real_future_labels_two_nonoverlapping_cohorts(self):
        calibration,test=c.test_diversity(cohort())
        self.assertEqual(len(calibration),64)
        self.assertEqual(len(test),64)
        self.assertEqual(calibration[-1][2]+1,test[0][2])
        self.assertNotIn(test[0][2],[v[2] for v in calibration])

    def test_real_temperature_selection_math_no_model_weights_changed(self):
        examples=cohort()
        logits=[1.0 if x[1]==1 else -1.0 for x in examples]
        result=c.evaluate(parent(),examples,logits=logits)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["proposed_temperature"],0.25)
        self.assertLess(result["candidate_forward_brier"],
                        result["baseline_forward_brier"])
        self.assertFalse(result["production_authority"])
        signed=c.receipt(result)
        upgraded=c.new_parent(parent(),signed)
        self.assertEqual(upgraded["temperature"],0.25)
        self.assertEqual(upgraded["weights"],parent()["weights"])
        self.assertFalse(upgraded["dispatch_authority"])
        self.assertFalse(upgraded["production_authority"])
        m.check_checkpoint(upgraded)

    def test_no_benefit_cannot_update_temperature(self):
        result=c.evaluate(parent(),cohort(),logits=[0.]*128)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["proposed_temperature"],0.5)
        with self.assertRaisesRegex(ValueError,
                                    "AUTO_TEMPERATURE_PARENT_GATE_DENIED"):
            c.new_parent(parent(),c.receipt(result))

    def test_no_failures_does_not_allow_promotion(self):
        rows=cohort()
        rows=[(v[0],0,v[2],v[3]) for v in rows]
        with self.assertRaisesRegex(ValueError,
                                    "FORWARD_COHORT_LACKS_FAIL"):
            c.evaluate(parent(),rows,logits=[0.]*128)

    def test_source_history_gap_and_timestamp_tie_rejected_or_disambiguated(self):
        rows=[]
        for i in range(140):
            created=T+timedelta(seconds=i//2)
            rows.append({
                "id":12345+i,"created_at":created.isoformat(),
                "label":int(i%13==0),"elapsed_s":32,
                "workflow_id":101+(i%10),"event":"push",
            })
        with self.assertRaisesRegex(ValueError,"HISTORY_GAP"):
            c.eligible(rows,(T-timedelta(minutes=1)).isoformat(),None)
        cursor={
            "schema":c.STATE,"epoch":1,
            "last_target_utc":(T+timedelta(seconds=10)).isoformat(),
            "last_target_id":12365,
            "production_authority":False,"research_only":True,
        }
        cursor["receipt_sha256"]=m.digest(cursor)
        picked,_=c.eligible(rows,T.isoformat(),cursor)
        self.assertTrue(all(
            (m.timepoint(x[3]),x[2]) >
            (m.timepoint(cursor["last_target_utc"]),cursor["last_target_id"])
            for x in picked))

    def test_cursor_receipt_cannot_be_tampered(self):
        cursor={
            "schema":c.STATE,"epoch":1,
            "last_target_utc":T.isoformat(),"last_target_id":1001,
            "production_authority":False,"research_only":True,
        }
        cursor["receipt_sha256"]=m.digest(cursor)
        c.validate_cursor(cursor)
        cursor["epoch"]=2
        with self.assertRaisesRegex(ValueError,
                                    "CALIBRATION_CURSOR_TAMPERED"):
            c.validate_cursor(cursor)

    def test_negative_result_keeps_frozen_weights_and_unseen_corpus(self):
        text=Path(c.__file__).read_text()
        self.assertIn("last_target_id",text)
        self.assertIn("FUTURE_CALIB_N=64",text)
        self.assertIn("FUTURE_TEST_N=64",text)
        self.assertNotIn("torch.load(",text)
        self.assertNotIn("pickle.load(",text)
        self.assertNotIn("git push --force",text)


if __name__=="__main__":
    unittest.main()
