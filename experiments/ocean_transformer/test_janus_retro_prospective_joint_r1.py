#!/usr/bin/env python3
"""JANUS prospective fixed-N anti-selection and leakage tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import janus_retro_prospective_joint_r1 as p

PROTOCOL=Path(__file__).with_name("janus_retro_prospective_joint_r1.json")


def write_json(path, obj):
    path.write_text(json.dumps(obj,sort_keys=True),encoding="utf-8")


def make_trial(root, name, stamp, complete=True, corrupted=False):
    d=root/name
    d.mkdir()
    bits=("01"*128) if not corrupted else ("10"*128)
    early={
        "trial_id": name,
        "number_bits": 256,
        "predicted_bits": "01"*128,
        "predicted_256_bits_sha256": hashlib.sha256(("01"*128).encode()).hexdigest(),
        "issued_at_epoch_utc": stamp,
        "p1_model_probs":[.6]*256,
        "model_sha256":p.EXPECTED_MODEL,
    }
    write_json(d/"early.json",early)
    if complete:
        payload = bytes(int(bits[i:i+8],2) for i in range(0,256,8))
        late={
            "trial_id": name,
            "future_bits": bits,
            "target_payload_hex":payload.hex(),
            "target_sha256": hashlib.sha256(payload).hexdigest(),
            "receiver_commit_confirmed_epoch":stamp+1,
            "future_generated_epoch_utc":stamp+121.25,
            "minimum_separation_seconds":120
        }
        comp={
            "trial_id": name,
            "total_bits":256,
            "predicted_bits_sha256":early["predicted_256_bits_sha256"],
            "late_random_sha256":late["target_sha256"],
            "unconditional_matching_bits":sum(x==y for x,y in
                                                zip(early["predicted_bits"],bits)),
            "physical_retrocausality_proven":False
        }
        write_json(d/"future.json",late)
        write_json(d/"comparison.json",comp)
    return d


class ProspectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads(PROTOCOL.read_text(encoding="utf-8"))
        cls.start,_=p.validate_protocol(cls.spec)

    def test_protocol_precommits_N_alpha_and_no_postselection(self):
        self.assertEqual(self.spec["trials_required"],24)
        self.assertEqual(self.spec["primary_alpha"],.0001)
        self.assertTrue(self.spec["no_postselection"])
        self.assertFalse(self.spec["independent_physical_resources_available"])

    def test_histories_before_cutoff_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            make_trial(root,"janus-retro-legacy",self.start-3600,True)
            x=p.audit(root,self.spec,permutations=99)
            self.assertEqual(x["status"],"PENDING_MORE_PRECOMMITTED_TRIALS")
            self.assertEqual(len(x["selected_trial_ids"]),0)
            self.assertIsNone(x["primary_exact_p"])

    def test_not_enough_future_trials_no_p(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(4):
                make_trial(root,f"janus-retro-{1000+i}",self.start+i*240,True)
            x=p.audit(root,self.spec,permutations=99)
            self.assertEqual(x["selected_so_far"],4)
            self.assertIsNone(x["primary_exact_p"])
            self.assertFalse(x["physical_retrocausality_proven"])

    def test_incomplete_selected_attempt_must_not_be_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(25):
                make_trial(root,f"janus-retro-{1000+i}",
                           self.start+i*240,i!=0)
            x=p.audit(root,self.spec,permutations=99)
            self.assertEqual(x["status"],"HOLD_INCOMPLETE_PRESELECTED_TRIALS")
            self.assertIn("janus-retro-1000",x["missing_or_incomplete_trial_ids"])
            self.assertEqual(len(x["selected_trial_ids"]),24)
            self.assertNotIn("janus-retro-1024",x["selected_trial_ids"])
            self.assertIsNone(x["primary_exact_p"])

    def test_complete_synthetic_fixture_remains_not_physical(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(24):
                make_trial(root,f"janus-retro-{1000+i}",
                           self.start+i*240,True)
            x=p.audit(root,self.spec,permutations=99)
            self.assertEqual(x["unconditionally_correct_bits"],24*256)
            self.assertEqual(x["unconditional_accuracy"],1)
            self.assertFalse(x["physical_retrocausality_proven"])
            self.assertFalse(x["production_promotion"])
            self.assertFalse(x["primary_statistical_anomaly"])
            self.assertFalse(x["external_physical_time_attestation"])
            self.assertEqual(x["status"],"REGRESSION_ONLY_REDUCED_PERMUTATION_BUDGET")

    def test_model_change_precommit_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(24):
                make_trial(root,f"janus-retro-{1000+i}",
                           self.start+i*240,True)
            entry=root/"janus-retro-1001"/"early.json"
            e=json.loads(entry.read_text())
            e["model_sha256"]="retrospectively-custom-model"
            write_json(entry,e)
            with self.assertRaisesRegex(ValueError,"MIXED_PRECOMMITTED_MODEL"):
                p.audit(root,self.spec,permutations=99)

    def test_cutoff_or_sample_size_tampering_refused(self):
        protocol=dict(self.spec)
        protocol["trials_required"]=7
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_SAMPLE_SIZE"):
            p.validate_protocol(protocol)
        protocol=dict(self.spec)
        protocol["primary_alpha"]=.05
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_TEST_ALPHA"):
            p.validate_protocol(protocol)

    def test_preselected_attempt_data_integrity_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(24):
                make_trial(root,f"janus-retro-{1000+i}",
                           self.start+i*240,True)
            path=root/"janus-retro-1000"/"comparison.json"
            comp=json.loads(path.read_text())
            comp["unconditional_matching_bits"]=0
            write_json(path,comp)
            with self.assertRaisesRegex(ValueError,"REPORTED_BIT_COUNT_CONTRADICTS_RAW_DATA"):
                p.audit(root,self.spec,permutations=99)


if __name__=="__main__":
    unittest.main(verbosity=2)
