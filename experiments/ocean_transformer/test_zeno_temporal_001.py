#!/usr/bin/env python3
"""Scientific and security regressions: JANUS-ZENO-TEMPORAL-001 (CPU only)."""
from __future__ import annotations

import json
import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import zeno_temporal_001 as z
import zeno_retro_control as retro
import zeno_wolfram_bridge as wolfram
from wolfram_alpha_bridge import WolframHold


class FakeResponse:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.data[:limit]


class ZenoTest(unittest.TestCase):
    def test_unobserved_and_repeated_unread_measurement(self):
        baseline = z.probabilities(math.pi, 0)
        self.assertAlmostEqual(baseline["unconditional_final_p0"], 0.0, delta=1e-12)
        n1 = z.probabilities(math.pi, 1)
        self.assertAlmostEqual(n1["unconditional_final_p0"], 0.0, delta=1e-12)
        n2 = z.probabilities(math.pi, 2)
        self.assertAlmostEqual(n2["all_zero_measurement_record_probability"], 0.25)
        self.assertAlmostEqual(n2["unconditional_final_p0"], 0.5)
        n4 = z.probabilities(math.pi, 4)
        self.assertAlmostEqual(n4["unconditional_final_p0"], .625)
        self.assertNotAlmostEqual(n4["unconditional_final_p0"],
                                  n4["all_zero_measurement_record_probability"])
        self.assertGreater(z.probabilities(math.pi, 256)["unconditional_final_p0"], .99)

    def test_computational_recurrence_matches_closed_forms(self):
        for rotation in z.ROTATIONS:
            for n in z.MEASUREMENT_COUNTS:
                r = z.probabilities(rotation, n)
                self.assertAlmostEqual(r["unconditional_final_p0"],
                                       r["analytic_unconditional_final_p0"], delta=1e-11)
                self.assertTrue(0 <= r["unconditional_final_p0"] <= 1)

    def test_fixed_standard_qm_not_retro_claim(self):
        r = z.build_report()
        self.assertEqual(r["experiment_id"], z.EXPERIMENT_ID)
        self.assertFalse(r["scope"]["real_physical_measurement_performed"])
        self.assertFalse(r["scope"]["physical_retrocausality_proven"])
        self.assertFalse(r["scope"]["forced_collapse_outcome"])
        svg = z.chart_svg(r)
        ET.fromstring(svg)
        self.assertIn("All measurement results", svg)

    def test_reject_invalid_grid(self):
        for n in (-1, 4097, 1.2):
            with self.assertRaises(ValueError): z.probabilities(math.pi, n)
        with self.assertRaises(ValueError): z.probabilities(float("nan"), 2)

    def test_precommit_then_late_choice_receipts(self):
        a = retro.receiver(512)
        b = retro.sender(a)
        r = retro.assess(a, b)
        self.assertLess(a["clock_wall_time_ns"], b["clock_wall_time_ns"])
        self.assertEqual(r["n"], 512)
        self.assertTrue(0 <= r["raw_two_sided_p"] <= 1)
        self.assertFalse(r["findings"]["independent_physical_retrocausal_signal_established"])
        self.assertFalse(r["sampling"]["external_temporal_witness"])
        self.assertFalse(r["negative_control"]["postselection_allowed_for_primary_test"])
        self.assertEqual(r["negative_control"]["selected_cases"], r["raw_matches"])

    def test_tampering_is_rejected(self):
        a = retro.receiver(512)
        b = retro.sender(a)
        a["early_bits"] = ("1" if a["early_bits"][0] == "0" else "0") + a["early_bits"][1:]
        with self.assertRaisesRegex(ValueError, "EARLY_SHA256_PRECOMMIT_MISMATCH"):
            retro.assess(a, b)

    def test_exact_binomial_symmetry(self):
        self.assertEqual(retro.exact_two_sided_binomial_p(2, 4), 1.0)
        self.assertAlmostEqual(retro.exact_two_sided_binomial_p(4, 4), .125)
        self.assertAlmostEqual(retro.exact_two_sided_binomial_p(0, 4), .125)

    def test_zenu_wolfram_offline_no_external_or_proof(self):
        result = wolfram.verify(live=False)
        self.assertEqual(result["status"], "NO_LIVE_API_CALL")
        self.assertEqual(len(result["queries"]), 4)
        self.assertFalse(result["proof_of_retrocausality"])
        self.assertFalse(result["provider_result_text_or_values_cached"])
        self.assertTrue(all(not q["external_checked"] for q in result["queries"]))

    def test_wolfram_mock_live_is_read_only_bounded(self):
        answers = {q: number for _, q, number in wolfram.CASES}
        received = []
        def fake_opener(request, timeout):
            p = parse_qs(urlparse(request.full_url).query)
            self.assertEqual(p["appid"], ["DUMMY_TEST_ONLY"])
            expression = p["input"][0]
            received.append(expression)
            body = {"queryresult": {"success": True, "error": False, "pods": [
                {"id": "Result", "primary": True, "subpods": [
                    {"plaintext": str(answers[expression])}
                ]}
            ]}}
            return FakeResponse(json.dumps(body).encode())
        result = wolfram.verify(live=True, appid="DUMMY_TEST_ONLY", opener=fake_opener)
        self.assertEqual(result["status"], "WOLFRAM_LIVE_MATH_CHECKED")
        self.assertEqual(len(received), 4)
        self.assertTrue(all(q["math_agrees"] for q in result["queries"]))
        self.assertNotIn("DUMMY_TEST_ONLY", json.dumps(result))
        self.assertFalse(result["proof_of_retrocausality"])

    def test_wolfram_reject_arbitrary_query(self):
        with self.assertRaises(WolframHold):
            wolfram.remote_value("DUMMY", "predict tomorrow")
        with self.assertRaises(WolframHold):
            wolfram.remote_value("", wolfram.CASES[0][1])

    def test_refuse_overwrite_immutable_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "test.json"
            retro.write_once(p, {"test": 1})
            with self.assertRaises(ValueError):
                retro.write_once(p, {"test": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
