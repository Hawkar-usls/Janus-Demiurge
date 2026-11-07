#!/usr/bin/env python3
"""JANUS R4 external drand precommit and witness *format* regression tests."""
import copy
import hashlib
import unittest
import janus_retro_drand_external_r4 as q


class ExternalBeaconTests(unittest.TestCase):
    def setUp(self):
        self.e,self.p=q.early("52000001",now=1692803367+3*100000,
                              nonce="0"*64)
        sig=hashlib.sha256(b"synthetic-sig").digest()+hashlib.sha256(b"extra").digest()[:16]
        self.f={
            "schema":"janus.external_beacon.future.r4",
            "trial_id":self.e["trial_id"],
            "beacon_chain_id":"quicknet",
            "beacon_chain_hash":q.CHAIN_HASH,
            "target_round":self.p["target_round"],
            "signature":sig.hex(),
            "randomness":hashlib.sha256(sig).hexdigest(),
            "cryptographic_bls_verification":True,
            "verified_by":"drand-client@1.4.2",
            "retrieved_epoch":self.p["target_release_epoch"]+1,
            "read_early_forecast_bits":False,
        }
        # This synthetic fixture is NOT a real valid BLS signature. The live
        # future/score jobs use drand-client for real BLS verification.

    def test_future_round_is_at_least_180s_after_early(self):
        self.assertGreaterEqual(self.p["target_release_epoch"]-
                                self.e["created_epoch"],180)
        self.assertEqual(q.round_release_epoch(self.p["target_round"]),
                         self.p["target_release_epoch"])

    def test_early_plan_does_not_contain_prediction(self):
        self.assertIn("forecast_bits",self.e)
        self.assertNotIn("forecast_bits",self.p)
        self.assertEqual(self.p["forecast_sha256"],
                         hashlib.sha256(self.e["forecast_bits"].encode()).hexdigest())

    def test_synthetic_metadata_score_does_not_claim_physical_signal(self):
        z=q.score(self.e,self.p,self.f)
        self.assertEqual(z["total_bits"],256)
        self.assertEqual(len(z["future_beacon_randomness"]),64)
        self.assertTrue(z["all_256_bits_scored"])
        self.assertFalse(z["physical_retrocausality_proven"])
        self.assertFalse(z["independent_physical_clock_and_outcome_attested"])
        self.assertEqual(z["source"],"SHA256_CONTROL_NOT_TRAINED_JANUS")

    def test_score_consistent_under_repeated_read(self):
        self.assertEqual(q.score(self.e,self.p,self.f),q.score(self.e,self.p,self.f))

    def test_corrupted_early_commit_denied(self):
        e=copy.deepcopy(self.e)
        e["forecast_bits"]="1"*256
        with self.assertRaisesRegex(ValueError,"EARLY_COMMITMENT_MISMATCH"):
            q.score(e,self.p,self.f)

    def test_changed_round_or_beacon_chain_denied(self):
        f=copy.deepcopy(self.f)
        f["target_round"]+=1
        with self.assertRaisesRegex(ValueError,"ROUND_OR_CHAIN_CHANGED"):
            q.score(self.e,self.p,f)
        f=copy.deepcopy(self.f)
        f["beacon_chain_hash"]="bad"
        with self.assertRaisesRegex(ValueError,"ROUND_OR_CHAIN_CHANGED"):
            q.score(self.e,self.p,f)

    def test_mismatched_signature_sha_denied(self):
        f=copy.deepcopy(self.f)
        f["randomness"]="0"*64
        with self.assertRaisesRegex(ValueError,"SIGNATURE_TO_RANDOMNESS_SHA256_MISMATCH"):
            q.score(self.e,self.p,f)

    def test_future_randomness_without_bls_assertion_denied(self):
        f=copy.deepcopy(self.f)
        f["cryptographic_bls_verification"]=False
        with self.assertRaisesRegex(ValueError,"MISSING_BLS_VERIFICATION_EVIDENCE"):
            q.score(self.e,self.p,f)

    def test_external_time_window_cannot_be_changed(self):
        p=copy.deepcopy(self.p)
        p["target_release_epoch"]=self.e["created_epoch"]+10
        with self.assertRaisesRegex(ValueError,"TIME_GATE_FAILED"):
            q.score(self.e,p,self.f)

    def test_false_publication_time_denied(self):
        f=copy.deepcopy(self.f)
        f["retrieved_epoch"]=self.p["target_release_epoch"]-10
        with self.assertRaisesRegex(ValueError,"BEACON_RETRIEVED_BEFORE_PUBLIC_RELEASE"):
            q.score(self.e,self.p,f)

    def test_exact_binomial_boundaries(self):
        self.assertEqual(q.binomial_p(256,0),1.)
        self.assertAlmostEqual(q.binomial_p(8,8),1/256)
        self.assertAlmostEqual(q.binomial_p(8,4),163/256)


if __name__=="__main__":
    unittest.main(verbosity=2)
