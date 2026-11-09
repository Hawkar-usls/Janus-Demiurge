#!/usr/bin/env python3
"""Wolfram mathematics bridge: fixed budget, credentials, provenance, no promotion."""
import copy
import json
import unittest
from unittest.mock import patch

import wolfram_ocean_bridge as bridge


class WolframOceanBridgeTests(unittest.TestCase):
    def test_offline_does_not_make_any_requests(self):
        with patch.object(bridge.urllib.request, "urlopen", side_effect=AssertionError("network!")):
            result = bridge.create_report()
        self.assertEqual(result["mode"], "OFFLINE_TEST_ONLY")
        self.assertEqual(result["request_count"], 0)
        self.assertEqual(result["status"], bridge.STATUS_FIXTURE)
        self.assertEqual(len(result["cases"]), 6)
        self.assertFalse(result["model_promotion_allowed"])
        self.assertFalse(result["physical_retrocausality"])
        with self.assertRaisesRegex(ValueError, "NOT_A_VALID_LIVE"):
            bridge.validate_certificate(result)

    def test_expected_values_parsed_strictly(self):
        for s, expected in (("1/4", .25), ("0.00390625", 1/256),
                            ("1e-3", .001), ("\u22121/2", -.5)):
            self.assertAlmostEqual(bridge.as_number(s), expected)
        for s in ("0.25 or 0.5", "nan", "inf", "1+1", "__import__('os')", "1/0"):
            with self.assertRaises((ValueError, ZeroDivisionError)):
                bridge.as_number(s)

    def test_provider_validates_results_and_rejects_wrong_math(self):
        case = bridge.EXPECTED[0]
        row = bridge.validate_case(case, bridge.fixture_response(case[2]))
        self.assertTrue(row["validated"])
        self.assertNotIn("appid", json.dumps(row).lower())
        incorrect = bridge.fixture_response(bridge.Fraction(1, 3))
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_MATH_DISAGREEMENT"):
            bridge.validate_case(case, incorrect)
        bad = bridge.fixture_response(case[2])
        bad["queryresult"]["success"] = False
        with self.assertRaisesRegex(ValueError, "PROVIDER_REJECTED_QUERY"):
            bridge.extract_result(bad)

    def test_live_credentials_are_required_and_not_in_reports(self):
        with self.assertRaisesRegex(RuntimeError, "LIVE_PROVIDER_APPID_REQUIRED"):
            bridge.create_report(live=True)
        credentials = "secret-test-appid-do-not-disclose"
        with patch.object(bridge, "query_provider", side_effect=lambda q, appid:
                bridge.fixture_response(next(c[2] for c in bridge.EXPECTED if c[1] == q))) as mock:
            report = bridge.create_report(live=True, appid=credentials)
        self.assertEqual(mock.call_count, 6)
        self.assertNotIn(credentials, json.dumps(report))
        self.assertEqual(report["request_count"], 6)
        self.assertFalse(report["source_authenticated"])
        bridge.validate_certificate(report)

    def test_certificate_rejects_mismatch_or_fake(self):
        with patch.object(bridge, "query_provider", side_effect=lambda q, appid:
                bridge.fixture_response(next(c[2] for c in bridge.EXPECTED if c[1] == q))):
            good = bridge.create_report(live=True, appid="mock-not-real")
        bridge.validate_certificate(good)
        for key, value in (("mode", "OFFLINE_TEST_ONLY"),
                           ("model_promotion_allowed", True),
                           ("queried_future_data", True)):
            altered = copy.deepcopy(good)
            altered[key] = value
            with self.assertRaises(ValueError):
                bridge.validate_certificate(altered)
        altered = copy.deepcopy(good)
        altered["cases"][0]["computed"] = "1"
        with self.assertRaises(ValueError):
            bridge.validate_certificate(altered)
        altered = copy.deepcopy(good)
        altered["cases"][0]["input_sha256"] = "deadbeef"
        with self.assertRaises(ValueError):
            bridge.validate_certificate(altered)

    def test_no_unapproved_external_queries(self):
        with self.assertRaisesRegex(ValueError, "UNAPPROVED_QUERY"):
            bridge.query_provider("next future RNG bytes", "fake")
        self.assertEqual(bridge.MAX_QUERIES, len(bridge.EXPECTED))
        self.assertEqual(bridge.BASE, "https://api.wolframalpha.com/v2/query")


if __name__ == "__main__":
    unittest.main(verbosity=2)
