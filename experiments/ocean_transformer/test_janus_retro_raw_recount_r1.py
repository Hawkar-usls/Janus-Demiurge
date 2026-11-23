#!/usr/bin/env python3
"""Tests for independent raw A/B ledger recount, including older records."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import janus_retro_raw_recount_r1 as a


def fixture(root: Path, tag="janus-retro-test1", late_bits=None, old=True):
    late_bits = late_bits if late_bits is not None else "0"*8+"1"*248
    early_bits = "0"*256
    b = int(late_bits,2).to_bytes(32,"big")
    location = root/tag
    location.mkdir(parents=True)
    early = {
        "trial_id": tag, "number_bits": 256, "predicted_bits": early_bits,
        "predicted_256_bits_sha256": hashlib.sha256(early_bits.encode()).hexdigest(),
        "issued_at_epoch_utc": 100., "p1_model_probs": [.25]*256,
        "model_sha256": "fake-fixed-model-digest"
    }
    late = {
        "trial_id": tag, "future_bits": late_bits,
        "receiver_commit_confirmed_epoch": 200.,
        "future_generated_epoch_utc": 320.125,
        "minimum_separation_seconds": 120,
        "target_payload_hex": b.hex(),
        "target_sha256": hashlib.sha256(b).hexdigest()
    }
    comp = {
        "trial_id": tag, "total_bits":256,
        "predicted_bits_sha256": early["predicted_256_bits_sha256"],
        "late_random_sha256": late["target_sha256"],
        "unconditional_matching_bits": sum(x==y for x,y in zip(early_bits,late_bits)),
        "physical_retrocausality_proven":False
    }
    if not old:
        comp["unconditional_full_byte_matches"] = {
            "count": sum(early_bits[i:i+8] == late_bits[i:i+8]
                         for i in range(0,256,8)),
            "indices_zero_based":[i//8 for i in range(0,256,8)
                         if early_bits[i:i+8]==late_bits[i:i+8]]
        }
    for name,obj in (("early.json",early),("future.json",late),("comparison.json",comp)):
        (location/name).write_text(json.dumps(obj),encoding="utf-8")
    return location


def change(path, field, value):
    obj=json.loads(path.read_text())
    obj[field]=value
    path.write_text(json.dumps(obj))


class RecountTests(unittest.TestCase):
    def test_exact_binary_tail(self):
        self.assertEqual(a.tail_fair_bits(8,0),1)
        self.assertAlmostEqual(a.tail_fair_bits(8,8),1/256)
        self.assertAlmostEqual(a.tail_byte_matches(1,1),1/256)
        self.assertEqual(a.tail_byte_matches(32,0),1)

    def test_read_old_schema_recovers_full_byte_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=fixture(Path(tmp))
            r=a.examine(folder)
            self.assertEqual(r["recomputed_bits_correct"],8)
            self.assertEqual(r["recomputed_full_byte_count"],1)
            self.assertEqual(r["recomputed_full_byte_indices"],[0])
            self.assertFalse(r["original_comparison_includes_byte_metric"])
            self.assertFalse(r["physically_attested_timestamps"])

    def test_read_new_schema_checks_full_byte_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=fixture(Path(tmp),old=False)
            r=a.examine(folder)
            self.assertTrue(r["original_comparison_includes_byte_metric"])
            self.assertEqual(r["recomputed_full_byte_count"],1)

    def test_all_trials_aggregated_unconditionally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fixture(root,tag="janus-retro-test1")
            fixture(root,tag="janus-retro-test2",late_bits="1"*256)
            r=a.audit(root)
            self.assertEqual(r["trial_count"],2)
            self.assertEqual(r["total_bits"],512)
            self.assertEqual(r["unconditionally_correct_bits"],8)
            self.assertEqual(r["matching_full_bytes"],1)
            self.assertEqual(r["old_schema_records_with_recovered_byte_counts"],2)
            self.assertFalse(r["physical_retrocausal_signal_demonstrated"])

    def test_early_prediction_sha_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            change(d/"early.json","predicted_bits","1"*256)
            with self.assertRaisesRegex(ValueError,"EARLY_PREDICTION_HASH"):
                a.examine(d)

    def test_future_payload_hash_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            change(d/"future.json","future_bits","1"*256)
            with self.assertRaisesRegex(ValueError,"FUTURE_TARGET_HASH"):
                a.examine(d)

    def test_late_timestamp_not_120_seconds_later_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            change(d/"future.json","future_generated_epoch_utc",319.)
            with self.assertRaisesRegex(ValueError,"INTERNAL_CHRONOLOGY"):
                a.examine(d)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            (d/"future.json").unlink()
            with self.assertRaisesRegex(ValueError,"TRIAL_MISSING"):
                a.examine(d)

    def test_retroactively_edited_comparison_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            change(d/"comparison.json","unconditional_matching_bits",255)
            with self.assertRaisesRegex(ValueError,"REPORTED_BIT_COUNT"):
                a.examine(d)

    def test_forged_byte_count_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp),old=False)
            change(d/"comparison.json","unconditional_full_byte_matches",
                   {"count":3,"indices_zero_based":[0,3,8]})
            with self.assertRaisesRegex(ValueError,"REPORTED_BYTE_COUNTS"):
                a.examine(d)

    def test_physical_claim_in_archived_comparison_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=fixture(Path(tmp))
            change(d/"comparison.json","physical_retrocausality_proven",True)
            with self.assertRaisesRegex(ValueError,"UNSUPPORTED_PHYSICAL_CLAIM"):
                a.examine(d)

    def test_empty_ledger_cannot_give_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"UNBOUNDED_OR_EMPTY"):
                a.audit(Path(tmp))


if __name__=="__main__":
    unittest.main(verbosity=2)
