#!/usr/bin/env python3
"""Synthetic regression only: does NOT demonstrate backwards communication."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import retro_channel_trial as retro


class ExactByteAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def compare_synthetic(self, match_indices):
        later_bytes=bytes(range(32))
        future=retro.bits_of(later_bytes)
        earlier_chunks=[]
        for i in range(32):
            target=future[i*8:(i+1)*8]
            earlier_chunks.append(target if i in match_indices
                                  else ("1" if target[0]=="0" else "0")+target[1:])
        predicted="".join(earlier_chunks)
        early={
          "schema":"janus.retro.lab.model_precommit.v1",
          "trial_id":"synthetic-001",
          "issued_at_epoch_utc":1000.0,
          "predicted_bits":predicted,
          "predicted_256_bits_sha256":hashlib.sha256(predicted.encode()).hexdigest(),
          "p1_model_probs":[.5]*256
        }
        later={
          "schema":"janus.retro.lab.independent_future_rng.v1",
          "trial_id":"synthetic-001",
          "receiver_commit_confirmed_epoch":1010.0,
          "future_generated_epoch_utc":1130.0,
          "future_bits":future,
          "target_payload_hex":later_bytes.hex(),
          "target_sha256":hashlib.sha256(later_bytes).hexdigest()
        }
        for name,item in (("early",early),("later",later)):
            (self.root/(name+".json")).write_text(json.dumps(item))
        retro.compare(SimpleNamespace(
            early=str(self.root/"early.json"),
            later=str(self.root/"later.json"),
            output=str(self.root/"result.json")))
        return json.loads((self.root/"result.json").read_text())

    def test_one_complete_byte_requires_all_eight_correct(self):
        result=self.compare_synthetic({25})
        bytes_=result["unconditional_full_byte_matches"]
        self.assertEqual(bytes_["count"],1)
        self.assertEqual(bytes_["indices_zero_based"],[25])
        self.assertEqual(bytes_["matched_byte_hex"],["19"])
        self.assertEqual(bytes_["total_bytes"],32)
        self.assertEqual(bytes_["expected_random_matches"],.125)
        self.assertFalse(bytes_["operational_retrocausal_byte_message_proven"])
        self.assertTrue(bytes_["full_population_included"])

    def test_no_complete_byte_keeps_nonmatches(self):
        result=self.compare_synthetic(set())
        summary=result["unconditional_full_byte_matches"]
        self.assertEqual(summary["count"],0)
        self.assertEqual(summary["exact_binomial_one_sided_pvalue"],1.)
        self.assertEqual(summary["indices_zero_based"],[])

    def test_all_complete_bytes_is_synthetic_not_evidence(self):
        result=self.compare_synthetic(set(range(32)))
        summary=result["unconditional_full_byte_matches"]
        self.assertEqual(summary["count"],32)
        self.assertLess(summary["exact_binomial_one_sided_pvalue"],1e-70)
        self.assertFalse(summary["operational_retrocausal_byte_message_proven"])
        self.assertFalse(result["physical_retrocausality_proven"])


if __name__=="__main__":
    unittest.main(verbosity=2)
