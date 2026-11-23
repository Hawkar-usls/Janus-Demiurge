#!/usr/bin/env python3
"""Frozen pre-future early-only challenger suite regression tests."""
import copy
import json
from pathlib import Path
import unittest

import janus_retro_decoder_challengers_r1 as c

SPEC=Path(__file__).with_name("janus_retro_decoder_challengers_r1.json")


class FixedDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads(SPEC.read_text(encoding="utf-8"))

    def test_manifest_is_locked_at_four(self):
        self.assertTrue(c.validate_addendum(self.manifest))
        self.assertEqual(tuple(x["id"] for x in self.manifest["candidates"]), c.IDS)

    def test_four_early_decoders_need_no_future_bit(self):
        a=[0,1]*128
        conf=[0,0,1,1]*64
        predictions=c.precommitted_decoders(a,conf)
        self.assertEqual(set(predictions),set(c.IDS))
        self.assertEqual(predictions["RAW"],a)
        self.assertEqual(predictions["INVERTED"],[1-x for x in a])
        self.assertEqual(predictions["CONFIDENCE_HIGH_FLIP"],
                         [x^y for x,y in zip(a,conf)])
        self.assertEqual(predictions["CONFIDENCE_LOW_FLIP"],
                         [x^(1^y) for x,y in zip(a,conf)])

    def test_change_to_early_prediction_cannot_modify_inputs(self):
        a=[0,1]*128
        conf=[0,1]*128
        snapshot=(a[:],conf[:])
        c.precommitted_decoders(a,conf)
        self.assertEqual((a,conf),snapshot)

    def test_reject_mismatched_counts_or_future_in_early_register(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PRECOMMITTED_EARLY"):
            c.precommitted_decoders([0]*256,[1]*255)
        with self.assertRaisesRegex(ValueError,"INVALID_PRECOMMITTED_EARLY"):
            c.precommitted_decoders([0]*255+[2],[1]*256)

    def test_manifest_candidate_reordering_or_alpha_fails(self):
        x=copy.deepcopy(self.manifest)
        x["candidates"].reverse()
        with self.assertRaisesRegex(ValueError,"CANDIDATE_FAMILY_CHANGED"):
            c.validate_addendum(x)
        x=copy.deepcopy(self.manifest)
        x["alpha_familywise"]=0.05
        with self.assertRaisesRegex(ValueError,"INVALID_OR_UNFROZEN_ADDENDUM"):
            c.validate_addendum(x)

    def test_precommitted_synthetic_inverse_predictor_can_win_not_physical(self):
        a=[0,1]*128
        conf=[0]*256
        late=[1-x for x in a]  # Deliberately planted future leak fixture.
        groups=[(a,conf,late) for _ in range(24)]
        r=c.score_challengers(groups,self.manifest)
        self.assertEqual(r["all_precommitted_candidates"]["INVERTED"]["correct"],6144)
        self.assertEqual(r["all_precommitted_candidates"]["RAW"]["correct"],0)
        self.assertTrue(r["candidate_familywise_anomaly"])
        self.assertFalse(r["physical_retrocausality_proven"])
        self.assertFalse(r["promotion_allowed"])

    def test_cannot_select_only_good_trials(self):
        a=[0,1]*128
        conf=[0]*256
        with self.assertRaisesRegex(ValueError,"FROZEN_SAMPLE_SIZE_MISMATCH"):
            c.score_challengers([(a,conf,a) for _ in range(23)],self.manifest)


if __name__=="__main__":
    unittest.main(verbosity=2)
