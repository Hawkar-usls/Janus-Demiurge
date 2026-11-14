#!/usr/bin/env python3
"""R5 trained JANUS -> externally signed future drand, adversarial regression.

Synthetic future signatures in this test are INVALID BLS; real workflow
independently checks actual signatures in drand-client before invoking scorer.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import janus_retro_trained_drand_r5 as q


def fixture(tmp, tid="700007", issued=1692803367+50000):
    bits="01"*128
    model={
      "schema":"janus.retro.lab.model_precommit.v1",
      "trial_id":f"janus-retro-{tid}",
      "number_bits":256,
      "predicted_bits":bits,
      "predicted_256_bits_sha256":hashlib.sha256(bits.encode()).hexdigest(),
      "p1_model_probs":[.4,.6]*128,
      "model_sha256":q.MODEL_SHA,
      "source_snapshot_sha256":q.SNAPSHOT_SHA,
      "source_trained_JANUS_run":q.TRAINED_RUN,
      "issued_at_epoch_utc":issued,
      "future_target_not_generated_yet":True,
      "real_physical_retrocausal_interface":False
    }
    file=Path(tmp)/"model-prediction.json"
    file.write_text(json.dumps(model,sort_keys=True)+"\n")
    early,plan=q.freeze(file,tid,now=issued+2)
    sig=bytes(range(48)).hex()
    future={
      "schema":"janus.external_beacon.future.r4",
      "trial_id":tid,
      "beacon_chain_id":q.CHAIN_ID,
      "beacon_chain_hash":q.CHAIN_HASH,
      "target_round":plan["target_round"],
      "signature":sig,
      "randomness":hashlib.sha256(bytes.fromhex(sig)).hexdigest(),
      "cryptographic_bls_verification":True,
      "verified_by":"drand-client@1.4.2",
      "read_early_forecast_bits":False,
      "retrieved_epoch":plan["target_release_epoch"]+1.
    }
    return model,file,early,plan,future


class FrozenModelFutureBeaconTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.model,self.path,self.early,self.plan,self.future=fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def score(self,early=None,plan=None,future=None):
        raw=self.path.read_bytes()
        return q.score(early or self.early,plan or self.plan,
                       future or self.future,(json.loads(raw),raw))

    def test_frozen_prediction_is_actual_model_not_hash_control(self):
        self.assertEqual(self.early["source"],"ACTUAL_TRAINED_JANUS_40_RIVER_V3")
        self.assertTrue(self.plan["actual_model_is_trained_janus"])
        self.assertNotIn("forecast_bits",self.plan)
        self.assertEqual(self.early["frozen_predictors"]["RAW"],"01"*128)
        self.assertGreaterEqual(self.plan["target_release_epoch"]-
                                self.early["frozen_epoch"],180)

    def test_four_early_only_decoders_are_predeclared(self):
        x=self.early["frozen_predictors"]
        self.assertEqual(tuple(x),q.IDS)
        self.assertEqual(x["INVERTED"],"10"*128)
        self.assertEqual(x["CONFIDENCE_HIGH_FLIP"],"01"*128)
        self.assertEqual(x["CONFIDENCE_LOW_FLIP"],"10"*128)

    def test_complete_synthetic_score_is_not_physical_proof(self):
        x=self.score()
        self.assertEqual(x["source"],"ACTUAL_TRAINED_JANUS_40_RIVER_V3")
        self.assertEqual(len(x["all_precommitted_candidates"]),4)
        self.assertTrue(x["all_256_bits_and_all_4_decoders_scored"])
        self.assertFalse(x["physical_retrocausality_proven"])
        self.assertFalse(x["physical_early_clock_attested_externally"])
        self.assertFalse(x["production_promotion"])

    def test_modified_prediction_rejected(self):
        e=copy.deepcopy(self.early)
        e["frozen_predictors"]["RAW"]="0"*256
        with self.assertRaisesRegex(ValueError,"EARLY_DECODERS_MODIFIED"):
            self.score(early=e)

    def test_modified_model_checkpoint_rejected(self):
        e=dict(self.model)
        e["model_sha256"]="wrong"
        self.path.write_text(json.dumps(e))
        with self.assertRaisesRegex(ValueError,"MODEL_FILE_DIGEST_CHANGED"):
            self.score()

    def test_wrong_round_rejected(self):
        p=copy.deepcopy(self.plan)
        p["target_round"]+=1
        with self.assertRaisesRegex(ValueError,"FUTURE_BEACON_OR_TIME_NOT_FROZEN"):
            self.score(plan=p)

    def test_future_signature_modified_rejected(self):
        f=copy.deepcopy(self.future)
        f["signature"]="00"*48
        with self.assertRaisesRegex(ValueError,"INVALID_SIGNED_FUTURE_PAYLOAD"):
            self.score(future=f)

    def test_disabled_bls_verification_rejected(self):
        f=copy.deepcopy(self.future)
        f["cryptographic_bls_verification"]=False
        with self.assertRaisesRegex(ValueError,"MISSING_VERIFIED_FUTURE_PROVENANCE"):
            self.score(future=f)

    def test_future_job_must_not_claim_read_early_bits(self):
        f=copy.deepcopy(self.future)
        f["read_early_forecast_bits"]=True
        with self.assertRaisesRegex(ValueError,"MISSING_VERIFIED_FUTURE_PROVENANCE"):
            self.score(future=f)

    def test_manifest_must_not_contain_forecast(self):
        p=copy.deepcopy(self.plan)
        p["forecast_bits"]="01"*128
        with self.assertRaisesRegex(ValueError,"PLAN_LEAK_OR_HASH_CHANGED"):
            self.score(plan=p)

    def test_bonferroni_guard_and_all_guesses_precommitted(self):
        x=self.score()
        ps=[v["nominal_upper_tail"] for v in x["all_precommitted_candidates"].values()]
        self.assertAlmostEqual(x["familywise_bonferroni_upper_tail_p"],
                               min(1.,4*min(ps)))
        self.assertEqual(set(v["total"] for v in x["all_precommitted_candidates"].values()),{256})

    def test_early_prediction_after_freeze_must_abort(self):
        with self.assertRaisesRegex(ValueError,"EARLY_MODEL_AFTER_PLAN_TIME"):
            q.freeze(self.path,"700007",now=self.model["issued_at_epoch_utc"]-1)


if __name__=="__main__":
    unittest.main(verbosity=2)
