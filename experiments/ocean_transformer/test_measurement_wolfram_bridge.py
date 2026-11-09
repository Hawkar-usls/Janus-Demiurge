#!/usr/bin/env python3
"""Offline regressions for bounded JANUS Ocean/Wolfram quantum research lane."""
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import measurement_priors as p
import wolfram_alpha_bridge as w


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, amount):
        return self.body[:amount]


class Tests(unittest.TestCase):
    def test_measurement_probabilities_and_coherence(self):
        self.assertAlmostEqual(p.born_probability(0, "Z", 2), 0.0)
        self.assertAlmostEqual(p.born_probability(4, "Z", 2), 1.0)
        self.assertAlmostEqual(p.born_probability(2, "X", 0), 0.0)
        self.assertAlmostEqual(p.born_probability(2, "X", 1), 0.25)
        self.assertAlmostEqual(p.born_probability(2, "X", 2), 0.5)
        self.assertAlmostEqual(p.born_probability(2, "Z", 0),
                               p.born_probability(2, "Z", 2))
        self.assertAlmostEqual(p.density_matrix(2, 0)[0][1], .5)
        self.assertAlmostEqual(p.density_matrix(2, 2)[0][1], 0.)

    def test_no_late_choice_signal_in_early_record(self):
        r = p.report()
        self.assertEqual(len(r["grid"]), 30)
        self.assertFalse(r["physical_retrocausality_proven"])
        self.assertFalse(r["electron_is_tachyon_proven"])
        for row in r["late_choice_no_signalling"]:
            self.assertAlmostEqual(row["early_marginal_after_late_choice"][1], .5)
            self.assertFalse(row["unconditioned_early_readout_contains_future_bit"])

    def test_invalid_parameters_fail_closed(self):
        for args in [(999, "Z", 0), (0, "OTHER", 0), (0, "X", -1)]:
            with self.assertRaises(ValueError):
                p.born_probability(*args)

    def test_numbers_are_not_executable_code(self):
        self.assertAlmostEqual(w.numerical_result("1/256 = 0.00390625"), 1/256)
        self.assertAlmostEqual(w.numerical_result("0.5"), .5)
        with self.assertRaises(w.WolframHold):
            w.numerical_result("__import__('os').system('echo BAD')")

    def test_offline_is_explicitly_not_external_verification(self):
        data = w.check(live=False)
        self.assertEqual(data["status"], "NO_EXTERNAL_QUERY_PERFORMED")
        self.assertFalse(data["upstream"]["authenticated"])
        self.assertFalse(data["evidence_of_retrocausality"])
        self.assertFalse(data["model_weights_updated"])
        self.assertTrue(all(not q["external_checked"] for q in data["queries"]))

    def test_mocked_wolfram_api_has_only_public_bounded_queries(self):
        observed = []
        expected = {query: val for _, query, val in w.CASES}
        def fake(request, timeout):
            parsed = urlsplit(request.full_url)
            params = parse_qs(parsed.query)
            self.assertEqual(parsed.hostname, "api.wolframalpha.com")
            self.assertEqual(params["appid"], ["SYNTHETIC_FAKE_SECRET"])
            expression = params["input"][0]
            observed.append(expression)
            val = expected[expression]
            reply = {"queryresult": {"success": True, "error": False, "pods": [
                {"id": "Result", "primary": True,
                 "subpods": [{"plaintext": str(val)}]}
            ]}}
            return FakeResponse(json.dumps(reply).encode())
        result = w.check(live=True, appid="SYNTHETIC_FAKE_SECRET", opener=fake)
        self.assertEqual(result["status"], "EXTERNAL_ARITHMETIC_CHECK_PASS")
        self.assertEqual(len(observed), len(w.CASES))
        self.assertNotIn("SYNTHETIC_FAKE_SECRET", json.dumps(result))
        self.assertTrue(all(q["agrees_with_standard_arithmetic"] for q in result["queries"]))

    def test_live_receipt_can_be_bound_but_not_offline_or_forged(self):
        expected = {expression: value for _, expression, value in w.CASES}

        def fake(request, timeout):
            expression = parse_qs(urlsplit(request.full_url).query)["input"][0]
            body = {"queryresult": {"success": True, "error": False, "pods": [
                {"id": "Result", "subpods": [{"plaintext": str(expected[expression])}]}
            ]}}
            return FakeResponse(json.dumps(body).encode("utf-8"))

        good = w.check(live=True, appid="MOCK_KEY_NOT_LIVE_PROVIDER", opener=fake)
        self.assertTrue(all("wolfram_numeric_result" not in row for row in good["queries"]))
        w.verify_live_math_receipt(good)

        for bad in [
            w.check(live=False),
            {**good, "status": "NO_EXTERNAL_QUERY_PERFORMED"},
            {**good, "source_binding": {"canonical_dataset_sha256": "wrong"}},
            {**good, "queries": list(good["queries"])[:-1]},
            {**good, "evidence_of_retrocausality": True},
        ]:
            with self.assertRaises(w.WolframHold):
                w.verify_live_math_receipt(bad)

        changed = json.loads(json.dumps(good))
        changed["queries"][0]["agrees_with_standard_arithmetic"] = False
        with self.assertRaises(w.WolframHold):
            w.verify_live_math_receipt(changed)

        changed = json.loads(json.dumps(good))
        changed["queries"][0]["public_expression"] = "future-target-payload"
        with self.assertRaises(w.WolframHold):
            w.verify_live_math_receipt(changed)

    def test_reject_free_text_query_and_bad_response(self):
        with self.assertRaisesRegex(w.WolframHold, "UNAPPROVED_QUERY"):
            w.remote_number("FAKE", "predict the future")
        with self.assertRaisesRegex(w.WolframHold, "WOLFRAM_UNSUCCESSFUL"):
            w.decode_result({"queryresult": {"success": False}})
        with self.assertRaisesRegex(w.WolframHold, "WOLFRAM_RESULT_POD_MISSING"):
            w.decode_result({"queryresult": {"success": True, "pods": []}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
