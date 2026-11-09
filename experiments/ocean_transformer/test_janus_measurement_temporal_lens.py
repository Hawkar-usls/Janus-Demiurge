#!/usr/bin/env python3
"""Fail-closed physics and data-leakage regression tests for JANUS lens."""
import math
import random
import unittest

import janus_measurement_temporal_lens as lens


class MeasurementTemporalLensTests(unittest.TestCase):
    def test_born_probability_limits_and_rejected_inputs(self):
        self.assertAlmostEqual(lens.born_p1(.5, 0, 0, "X"), 0.)
        self.assertAlmostEqual(lens.born_p1(.5, math.pi, 0, "X"), 1.)
        self.assertAlmostEqual(lens.born_p1(.5, math.pi / 2, 0, "Y"), 0.)
        self.assertAlmostEqual(lens.born_p1(.5, 0, 0, "Z"), .5)
        self.assertAlmostEqual(lens.born_p1(1., 0, 0, "Z"), 0.)
        for args in [(-.01, 0, 0, "Z"), (.5, 0, 1.01, "Z"),
                     (.5, float("nan"), 0, "X"), (.5, 0, 0, "W")]:
            with self.assertRaises(ValueError):
                lens.born_p1(*args)

    def test_which_path_distinguishability_removes_interference(self):
        for p0 in (.15, .5, .85):
            for phase in lens.PHASES:
                self.assertAlmostEqual(lens.born_p1(p0, phase, 1, "X"), .5)
                self.assertAlmostEqual(lens.born_p1(p0, phase, 1, "Y"), .5)
                for dephase in lens.DEPHASING:
                    self.assertAlmostEqual(
                        lens.born_p1(p0, phase, dephase, "Z"), 1 - p0
                    )
        self.assertAlmostEqual(lens.born_p1(.5, 0, .5, "X"), .25)

    def test_detector_sampling_matches_born_rule_not_a_magic_trigger(self):
        rng = random.Random(407)
        n = 20000
        sample = sum(lens.detect(.5, 0, .5, "X", rng) for _ in range(n)) / n
        self.assertAlmostEqual(sample, .25, delta=.015)

    def test_late_local_gate_cannot_change_earlier_marginal(self):
        controls = lens.no_signalling_control()
        self.assertEqual(set(controls), {"I", "X", "Z", "H"})
        for gate in controls:
            for basis in ("Z", "X"):
                self.assertEqual(len(controls[gate][basis]), 2)
                for p in controls[gate][basis]:
                    self.assertAlmostEqual(p, 0.5, places=12)
        report = lens.physics_report()
        self.assertFalse(report["physical_retrocausality_demonstrated"])
        self.assertFalse(report["early_operational_bit_from_late_free_choice"])
        self.assertFalse(report["objective_dynamical_collapse_implemented"])

    def test_holdout_settings_disjoint_and_deterministic(self):
        splits = lens.partitions()
        sets = [set(v) for v in splits.values()]
        self.assertEqual(sum(map(len, sets)), len(lens.settings()))
        self.assertEqual(len(set.union(*sets)), len(lens.settings()))
        self.assertTrue(sets[0].isdisjoint(sets[1]))
        self.assertTrue(sets[0].isdisjoint(sets[2]))
        self.assertTrue(sets[1].isdisjoint(sets[2]))
        self.assertEqual(splits, lens.partitions())
        for setting in lens.settings():
            seq = lens.tokens(setting)
            self.assertEqual(len(seq), 4)
            self.assertTrue(all(0 <= t <= 14 for t in seq))
            self.assertTrue(0 <= lens.target(setting) <= 1)

    def test_research_veto_is_permanent(self):
        self.assertIn("NO_EARLY_MESSAGE", lens.VETO)
        self.assertIn("NO_PRODUCTION_PROMOTION", lens.VETO)
        self.assertEqual(lens.MODEL_CONFIG["vocab_size"], 17)


if __name__ == "__main__":
    unittest.main(verbosity=2)
