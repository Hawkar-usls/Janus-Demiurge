#!/usr/bin/env python3
"""JANUS Ocean video-context research calibration regression (no external API)."""
import json
import math
import random
import tempfile
from pathlib import Path
import unittest

import ocean_video_calibration as m


class VideoCalibrationTests(unittest.TestCase):
    def test_classification_not_retrocausality_claim(self):
        c = m.video_card()
        self.assertEqual(c["source"]["video_id"], "KkKMZLvlmKA")
        self.assertEqual(len(c["extracted_topics"]), 6)
        self.assertFalse(c["physical_retrocausality_proven"])
        self.assertFalse(c["electron_tachyon_identity_proven"])
        self.assertFalse(c["trained_on_video_speech_as_measurement_outcomes"])
        kinds = {x["class"] for x in c["extracted_topics"]}
        self.assertIn("UNPROVEN_OPERATIONAL_CLAIM", kinds)
        self.assertIn("ESTABLISHED_MEASUREMENT_PHENOMENON", kinds)
        self.assertEqual(m.card_sha256(), m.card_sha256())

    def test_temperature_identity(self):
        for p in (0.01, 0.1, 0.5, 0.9, 0.99):
            self.assertAlmostEqual(m.temperature_probability(p, 1.0), p, places=7)
        self.assertAlmostEqual(m.temperature_probability(.5, .5), .5)
        self.assertGreater(m.temperature_probability(.9, .5), .9)
        self.assertLess(m.temperature_probability(.9, 2), .9)

    def test_metrics_brier_and_nll(self):
        p = [0, 1, .5, .5]
        y = [0, 1, 0, 1]
        scores = m.metrics(p,y)
        self.assertEqual(scores["n"], 4)
        self.assertAlmostEqual(scores["brier"], .125)
        self.assertAlmostEqual(scores["accuracy"], 1.0)
        self.assertTrue(0 <= scores["ece10"] <= 1)

    def test_calibration_never_peeks_at_test_labels(self):
        val_labels = [i % 2 for i in range(2048)]
        val_probs = [.98 if y else .02 for y in val_labels]
        test_probs = [.75 if i % 2 else .25 for i in range(2048)]
        test_labels = [i % 2 for i in range(2048)]
        a = m.calibrate(val_probs, val_labels, test_probs, test_labels, test_probs)
        b = m.calibrate(val_probs, val_labels, test_probs,
                        [1-y for y in test_labels], test_probs)
        self.assertEqual(a["chosen_temperature"], b["chosen_temperature"])
        self.assertEqual(a["validation_nll_calibrated"], b["validation_nll_calibrated"])
        self.assertLessEqual(a["validation_nll_calibrated"], a["validation_nll_raw"])
        self.assertNotEqual(a["test_calibrated"]["brier"], b["test_calibrated"]["brier"])
        self.assertFalse(a["calibration_selection_used_test_labels"])
        self.assertFalse(a["future_signal_or_quantum_collapse_proven"])
        self.assertEqual(a["video_card_sha256"], m.card_sha256())

    def test_random_future_bit_control_no_gain_from_test_peeking(self):
        rng = random.Random(4101)
        probs = [.2 if rng.random() < .5 else .8 for _ in range(2048)]
        val = [rng.randrange(2) for _ in range(2048)]
        test = [rng.randrange(2) for _ in range(2048)]
        result = m.calibrate(probs, val, probs, test, [.5]*2048)
        self.assertTrue(result["test_calibrated"]["nll"] >= 0.0)
        self.assertAlmostEqual(result["test_analytic_born"]["brier"], .25)

    def test_fail_closed_for_invalid_inputs(self):
        with self.assertRaises(ValueError):
            m.calibrate([.5], [0], [.5]*2048, [0]*2048, [.5]*2048)
        with self.assertRaises(ValueError):
            m.metrics([float("nan")], [1])
        with self.assertRaises(ValueError):
            m.metrics([.5], [2])
        with self.assertRaises(ValueError):
            m.temperature_probability(.5, 0)

    def test_non_overwriting_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "video-card.json"
            m.save_card(p)
            self.assertEqual(json.loads(p.read_text())["source"]["video_id"],
                             "KkKMZLvlmKA")
            with self.assertRaises(RuntimeError):
                m.save_card(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
