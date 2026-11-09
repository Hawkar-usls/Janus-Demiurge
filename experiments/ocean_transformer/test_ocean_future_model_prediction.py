#!/usr/bin/env python3
"""No-network precommit integrity, real-model input boundary and late-blind scoring."""
import copy
import datetime as dt
import math
import tempfile
import unittest
from pathlib import Path

import ocean_future_model_prediction as m
import blind_drand_pilot as drand


def fixture():
    r=33810100
    now=(drand.QUICKNET_GENESIS_UNIX+(r-1)*drand.QUICKNET_PERIOD_SECONDS)*1000+1000
    target=r+m.FUTURE_OFFSET
    predicted_probs=[.51 if i%2==0 else .49 for i in range(256)]
    early={
        "schema":m.SCHEMA,
        "experiment_id":m.EXPERIMENT_ID,
        "phase":"EARLY_PRECOMMIT",
        "model_name":"JanusTinyTransformer",
        "model_training":"PREVIOUS_FROZEN_BORN_RULE_SYNTHETIC_ONLY",
        "trained_checkpoint_github_run":m.SOURCE_RUN,
        "trained_checkpoint_artifact_id":m.SOURCE_ARTIFACT_ID,
        "trained_checkpoint_artifact_sha256":m.SOURCE_ARTIFACT_SHA256,
        "trained_checkpoint_sha256":"a"*64,
        "trained_checkpoint_report_sha256":"b"*64,
        "public_feature_encoder":"V1_TARGET_ROUND_AND_POSITION_TO_BORN_3_TOKENS",
        "features_from_future_labels":False,
        "round_picked_before_future_release":True,
        "future_beacon_result_seen_during_prediction":False,
        "training_or_calibration_used_target_beacon":False,
        "training_after_prediction":False,
        "early_recorded_at_unix_ms":now,
        "latest_verified_round_at_prepare":r,
        "beacon_chain_hash":drand.CHAIN_HASH,
        "beacon_period_seconds":drand.QUICKNET_PERIOD_SECONDS,
        "beacon_genesis_unix":drand.QUICKNET_GENESIS_UNIX,
        "predeclared_future_round":target,
        "predeclared_future_round_publication_unix_ms":(
            drand.QUICKNET_GENESIS_UNIX+(target-1)*3)*1000,
        "n_bits":256,
        "predicted_one_probabilities":predicted_probs,
        "early_bits":"10"*128,
        "prediction_threshold":.5,
        "postselection_allowed":False,
        "model_weights_modified":False,
        "source_class":"CROSS_DOMAIN_REUSE_OF_BORN_MODEL_EXPECT_CHANCE_ON_INDEPENDENT_DRAND",
        "physical_retrocausality_proven":False,
    }
    early["early_receipt_sha256"]=m.digest(early)
    beacon={
        "round":target,
        "chain_hash":drand.CHAIN_HASH,
        "signature_verified_by_pinned_client":True,
        "randomness":"a5"*32,
    }
    timestamp=dt.datetime.fromtimestamp((now+5000)/1000,dt.timezone.utc).isoformat()
    after=early["predeclared_future_round_publication_unix_ms"]+1000
    return early,beacon,timestamp,after

class FrozenModelForecastTests(unittest.TestCase):
    def test_fixed_256_early_probs_are_valid_and_source_bound(self):
        e,b,ts,after=fixture()
        self.assertEqual(m.verify_early(e),e["early_receipt_sha256"])
        self.assertEqual(len(e["predicted_one_probabilities"]),256)
        self.assertEqual(e["trained_checkpoint_github_run"],42596763409)

    def test_real_model_public_feature_encoder_does_not_read_future_bits(self):
        for j in range(256):
            theta,basis,deph=m.tokens_for_public_round(33810180,j)
            self.assertTrue(0<=theta<5)
            self.assertIn(basis,("Z","X"))
            self.assertTrue(0<=deph<3)
        with self.assertRaises(ValueError):
            m.tokens_for_public_round(33810180,256)

    def test_assess_all_bits_with_brier_and_chance(self):
        early,beacon,ts,after=fixture()
        result=m.assess(early,beacon,ts,after)
        self.assertEqual(result["n_all_bits"],256)
        self.assertAlmostEqual(result["brier_score_uniform_half_baseline"],.25)
        self.assertAlmostEqual(result["binary_logloss_uniform_half_baseline"],math.log(2))
        self.assertTrue(result["all_256_bits_scored"])
        self.assertFalse(result["physical_retrocausal_signal_proven"])
        self.assertFalse(result["automatic_model_promotion"])
        self.assertEqual(result["early_model_prediction_receipt_sha256"],early["early_receipt_sha256"])

    def test_no_post_selection_or_future_feature_leakage(self):
        for key in ("future_beacon_result_seen_during_prediction","training_or_calibration_used_target_beacon",
                    "features_from_future_labels","postselection_allowed","training_after_prediction","model_weights_modified"):
            e,b,ts,after=fixture()
            e[key]=True
            e["early_receipt_sha256"]=m.digest({k:v for k,v in e.items() if k!="early_receipt_sha256"})
            with self.assertRaisesRegex(ValueError,"UNTRUSTED_MODEL_OR_TARGET_BOUNDARY"):
                m.assess(e,b,ts,after)

    def test_flip_bit_with_original_sha_rejected(self):
        e,b,ts,after=fixture()
        e["early_bits"]="0"+e["early_bits"][1:]
        with self.assertRaisesRegex(ValueError,"PRECOMMIT_SHA_MISMATCH"):
            m.assess(e,b,ts,after)

    def test_wrong_future_round_and_signature_rejected(self):
        e,b,ts,after=fixture()
        b["round"]+=1
        with self.assertRaisesRegex(ValueError,"WRONG_OR_UNSIGNED_FUTURE_ROUND"):
            m.assess(e,b,ts,after)
        b["round"]-=1
        b["signature_verified_by_pinned_client"]=False
        with self.assertRaisesRegex(ValueError,"WRONG_OR_UNSIGNED_FUTURE_ROUND"):
            m.assess(e,b,ts,after)

    def test_late_publication_never_counts_as_early(self):
        e,b,ts,after=fixture()
        late=(e["predeclared_future_round_publication_unix_ms"]-5000)/1000
        ts=dt.datetime.fromtimestamp(late,dt.timezone.utc).isoformat()
        with self.assertRaisesRegex(ValueError,"FORECAST_NOT_INDEPENDENTLY_PUBLISHED"):
            m.assess(e,b,ts,after)

    def test_cannot_assess_before_beacon(self):
        e,b,ts,after=fixture()
        with self.assertRaisesRegex(ValueError,"FUTURE_TARGET_NOT_RELEASED"):
            m.assess(e,b,ts,e["predeclared_future_round_publication_unix_ms"]-1000)

    def test_probabilities_and_binary_decisions_must_match(self):
        e,b,ts,after=fixture()
        e["predicted_one_probabilities"][0]=.1
        e["early_receipt_sha256"]=m.digest({k:v for k,v in e.items() if k!="early_receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"MODEL_PREDICTIONS_NOT_SELF_CONSISTENT"):
            m.assess(e,b,ts,after)

    def test_append_only_evidence(self):
        e,b,ts,after=fixture()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"prediction.json"
            m.write_once(path,e)
            with self.assertRaisesRegex(ValueError,"REFUSE_OVERWRITE"):
                m.write_once(path,e)

if __name__=="__main__":
    unittest.main(verbosity=2)
