#!/usr/bin/env python3
"""No-network tests for JANUS Ocean's untrusted public Beetle Wolfram receipt."""
import copy
import hashlib
import json
import unittest

import beetle_wolfram_readonly_gate as gate


def fixture(verified=True):
    return {
        "schema":"janus.beetle.wolfram_ocean_math_attestation.v1",
        "experiment_id":"JANUS-ZENO-TEMPORAL-001",
        "query_id":"zeno_n2_verified_v1",
        "research_query":"cos(pi/4)^4",
        "independent_reference":0.25,
        "verified_arithmetic_match":verified,
        "verification_status":"PROVIDER_MATH_MATCH_CONFIRMED"
            if verified else "PROVIDER_NUMERIC_RESULT_UNAVAILABLE",
        "mcp_provider_response_sha256":"a"*64,
        "beetle_receipt_sha256":"b"*64,
        "beetle_candidate_id":"c"*24,
        "created_utc":"2026-11-09T12:00:00Z",
        "provider_endpoint":"https://agenttools.wolfram.com/mcp",
        "provider_raw_result_retained":False,
        "future_outcomes_transmitted":False,
        "live_external_arithmetic_only":True,
        "physical_retrocausality_proven":False,
        "production_model_promoted":False,
    }


class HttpResponse:
    status=200
    def __init__(self, text): self.text=text.encode()
    def geturl(self): return gate.BEETLE_URL
    def read(self, cap): return self.text[:cap]
    def __enter__(self): return self
    def __exit__(self, *_): return False


class TestOceanBeetleWolfram(unittest.TestCase):
    def test_verified_beetle_math_yields_arithmetic_only(self):
        obj=gate.validate_and_bind(fixture())
        self.assertEqual(obj["status"],"BEETLE_WOLFRAM_MATH_REPORTED_MATCH")
        self.assertTrue(obj["remote_mcp_math_verified_reported"])
        self.assertFalse(obj["physical_retrocausal_channel_proven"])
        self.assertFalse(obj["wolfram_provider_called_by_this_job"])
        self.assertAlmostEqual(obj["standard_zeno_analytic_reference"],.25,places=12)
        self.assertNotIn("provider_raw_output",json.dumps(obj))

    def test_unparseable_provider_is_not_math_proof(self):
        obj=gate.validate_and_bind(fixture(False))
        self.assertEqual(obj["status"],"REPORTED_BUT_NUMERIC_NOT_CONFIRMED")
        self.assertFalse(obj["remote_mcp_math_verified_reported"])

    def test_forged_telemetry_not_allowed(self):
        for key,val in (
            ("research_query","predict future now"),
            ("independent_reference",0.26),
            ("provider_raw_result_retained",True),
            ("physical_retrocausality_proven",True),
            ("mcp_provider_response_sha256","1234"),
        ):
            src=fixture()
            src[key]=val
            self.assertFalse(gate.validate_and_bind(src)["remote_mcp_math_verified_reported"], key)
        obj=fixture()
        obj["raw_provider_output"]="PROVIDER_TEXT_NOT_TO_CACHE"
        self.assertEqual(gate.source_decision(obj),"REJECTED_UNEXPECTED_OR_MISSING_FIELDS")

    def test_uncertain_source_is_not_claimed_as_a_pass(self):
        for status in ("NO_RECEIPT_YET","SOURCE_UNAVAILABLE"):
            report=gate.pending(status)
            self.assertFalse(report["remote_mcp_math_verified_reported"])
            self.assertEqual(report["status"],status)
        with self.assertRaises(ValueError):
            gate.pending("LIVE_MCP_MATH_VERIFIED")

    def test_readonly_input_uses_only_hardcoded_source(self):
        class FakeOpener:
            called=False
            def open(self, req, timeout):
                self.called=True
                self_url=req.full_url
                self.expected=gate.BEETLE_URL
                if self_url!=self.expected:
                    raise AssertionError("WRONG_SOURCE_URL")
                return HttpResponse(json.dumps(fixture()))
        f=FakeOpener()
        output=gate.retrieve(opener=f)
        self.assertTrue(f.called)
        self.assertEqual(output["status"],"BEETLE_WOLFRAM_MATH_REPORTED_MATCH")
        self.assertFalse(output["physical_retrocausal_channel_proven"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
