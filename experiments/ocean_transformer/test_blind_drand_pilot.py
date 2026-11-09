#!/usr/bin/env python3
"""Pre-registered independent-future-beacon pilot, no-network tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import blind_drand_pilot as p


def latest(round_no=99999999):
    return {"chain_hash":p.CHAIN_HASH,"genesis_time":p.QUICKNET_GENESIS_UNIX,
            "period":p.QUICKNET_PERIOD_SECONDS,"round":round_no,
            "signature_verified_by_pinned_client":True}

def setup():
    b=latest()
    issued_at=(p.QUICKNET_GENESIS_UNIX+(b["round"]-1)*p.QUICKNET_PERIOD_SECONDS)*1000+1000
    early=p.prepare(b,issued_at,early_bits="01"*128)
    beacon={"chain_hash":p.CHAIN_HASH,
            "round":early["predeclared_future_round"],
            "signature_verified_by_pinned_client":True,
            "randomness":"a5"*32}
    artifact_at=__import__("datetime").datetime.fromtimestamp(
        (issued_at+5000)/1000,__import__("datetime").timezone.utc).isoformat()
    after=early["predeclared_future_round_publication_unix_ms"]+1000
    return early,beacon,artifact_at,after


class BlindDrandTests(unittest.TestCase):
    def test_early_committed_before_independent_future_round(self):
        early,beacon,artifact,after=setup()
        self.assertGreater(early["predeclared_future_round_publication_unix_ms"]
                           -early["early_recorded_at_unix_ms"],90000)
        self.assertEqual(p.check_early(early),early["early_receipt_sha256"])
        result=p.assess(early,beacon,artifact,after)
        self.assertEqual(result["status"],"BLIND_PUBLIC_BEACON_NEGATIVE_CONTROL_COMPLETE")
        self.assertEqual(result["n_all_raw_bits"],256)
        # Synthetic fixture is strictly 128/256, not a fabricated perfect hit.
        self.assertEqual(result["matches"],128)
        self.assertEqual(result["raw_accuracy"],.5)
        self.assertEqual(result["exact_two_sided_binomial_p_under_independent_fair_bit_null"],1.0)
        self.assertFalse(result["physical_retrocausal_signal_proven"])
        self.assertTrue(result["outlier_is_not_physical_retrocausality"])
        self.assertFalse(result["independent_physical_early_receiver"])
        self.assertTrue(result["no_postselection_or_early_retraining"])

    def test_witness_time_later_than_future_publication_is_refused(self):
        early,beacon,artifact,after=setup()
        late_artifact=__import__("datetime").datetime.fromtimestamp(
            (after+5000)/1000,__import__("datetime").timezone.utc).isoformat()
        with self.assertRaisesRegex(ValueError,"NO_INDEPENDENT_EARLY_ARTIFACT_TIMING_MARGIN"):
            p.assess(early,beacon,late_artifact,after)

    def test_modified_early_random_bits_after_commit_rejected(self):
        early,beacon,artifact,after=setup()
        early["early_bits"]="00"*128
        with self.assertRaisesRegex(ValueError,"EARLY_SHA256_MISMATCH"):
            p.assess(early,beacon,artifact,after)

    def test_wrong_future_round_or_unsigned_data_rejected(self):
        early,beacon,artifact,after=setup()
        beacon["round"]+=1
        with self.assertRaisesRegex(ValueError,"FUTURE_ROUND_OR_SIGNATURE_UNVERIFIED"):
            p.assess(early,beacon,artifact,after)
        beacon["round"]-=1
        beacon["signature_verified_by_pinned_client"]=False
        with self.assertRaisesRegex(ValueError,"FUTURE_ROUND_OR_SIGNATURE_UNVERIFIED"):
            p.assess(early,beacon,artifact,after)

    def test_future_beacon_cannot_be_fetched_before_release(self):
        early,beacon,artifact,after=setup()
        with self.assertRaisesRegex(ValueError,"BEACON_PRE_PUBLICATION_LOOKUP_REFUSED"):
            p.assess(early,beacon,artifact,after-5000)

    def test_untrusted_latest_without_signature_cannot_prep(self):
        record=latest()
        record["signature_verified_by_pinned_client"]=False
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_DRAND_CHAIN_INFO"):
            p.prepare(record,1000,early_bits="0"*256)

    def test_only_whole_fixed_256_bits_accepted(self):
        info=latest()
        ts=(p.QUICKNET_GENESIS_UNIX+(info["round"]-1)*3)*1000+1000
        for invalid in ("0"*128,"0"*255+"X","2"*256):
            with self.assertRaisesRegex(ValueError,"INVALID_EARLY_BITS"):
                p.prepare(info,ts,early_bits=invalid)

    def test_immutable_source_receipt_written_once(self):
        early,*_=setup()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"early.json"
            p.write_once(str(path),early)
            self.assertEqual(json.loads(path.read_text()),early)
            with self.assertRaisesRegex(ValueError,"REFUSE_OVERWRITE"):
                p.write_once(str(path),early)

    def test_drand_source_has_fixed_chain_hash_and_round_offset(self):
        early,beacon,artifact,after=setup()
        self.assertEqual(early["predeclared_future_round"]-early["latest_verified_round_at_prepare"],45)
        self.assertEqual(early["beacon_chain_hash"],"52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971")


if __name__=="__main__":
    unittest.main(verbosity=2)
