#!/usr/bin/env python3
"""JANUS Ocean V3 reproducibility, no-signalling and non-claim controls."""
import json
import math
import tempfile
import unittest
from pathlib import Path

import zeno_science_council_v3 as s


class ScienceCouncilTests(unittest.TestCase):
    def test_three_cases_are_distinct_quantities_not_recycled_one_number(self):
        rows=s.reference_cases()
        self.assertEqual(len(rows),3)
        values=[r["analytical_reference"] for r in rows]
        self.assertAlmostEqual(values[0],.625)
        self.assertAlmostEqual(values[1],math.cos(math.pi/8)**8)
        self.assertAlmostEqual(values[2],.5)
        self.assertEqual(len(set(round(v,8) for v in values)),3)
        self.assertTrue(all(not r["remote_wolfram_checked_for_this_case"] for r in rows))

    def test_raw_early_marginal_does_not_depend_on_late_choice(self):
        for i in range(513):
            angle=math.pi*i/512
            row=s.bell_late_measurement(angle)
            self.assertAlmostEqual(row["early_p_a0_unconditioned_after_late_choice"],.5)
            self.assertAlmostEqual(sum(row["raw_four_joint_probabilities"]),1.0)
            self.assertAlmostEqual(row["late_p_b0"],.5)
            self.assertAlmostEqual(row["postselected_p_a0_given_b0"],
                                   math.cos(angle)**2)
            self.assertEqual(row["independent_early_marginal_check"],True)

    def test_heralded_subset_varies_but_cannot_be_signal(self):
        r=s.build_report()
        self.assertAlmostEqual(r["unconditional_max_min_difference"],0,places=11)
        self.assertGreaterEqual(r["postselection_conditional_range"],.999999)
        self.assertEqual(r["logic"]["no_signalling"],"PASS_UNCONDITIONAL_EQUAL_0_5")
        self.assertEqual(r["logic"]["postselection_trap"],"CONDITIONAL_VARIATION_NOT_SIGNAL")

    def test_no_new_wolfram_or_physical_claim(self):
        r=s.build_report()
        self.assertEqual(r["wolfram"]["new_cases_remote_checked"],0)
        self.assertEqual(r["wolfram"]["live_wolfram_queries_in_this_process"],0)
        self.assertFalse(r["wolfram"]["provider_key_or_login_used"])
        self.assertTrue(all(value is False for value in r["claims"].values()))
        self.assertFalse(r["logic"]["future_choice_bits_used_in_early_training"])
        self.assertFalse(r["logic"]["postselected_records_used_for_primary_test"])

    def test_disallow_invalid_late_basis(self):
        for bad in (-.1,math.nan,math.inf,math.pi+1,"pi",True):
            with self.assertRaises(ValueError):
                s.bell_late_measurement(bad)

    def test_immutable_json_source_hash(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"V3.json"
            digest=s.immutable_json(str(path),s.build_report())
            import hashlib
            self.assertEqual(digest,hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(json.loads(path.read_text())["schema"],s.SCHEMA)
            with self.assertRaisesRegex(RuntimeError,"REFUSE_OVERWRITE"):
                s.immutable_json(str(path),{"tampered":True})


if __name__=="__main__":
    unittest.main(verbosity=2)
