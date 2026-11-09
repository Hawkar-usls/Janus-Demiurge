#!/usr/bin/env python3
"""No-network tests for V2 Wolfram MCP evidence imported through Meta Registry."""
import copy
import json
import unittest
import wolfram_v2_registry_gate as gate


def source():
    return {
        "schema":"janus.research.wolfram_mcp_numeric_outcome.v2",
        "record_id":"JANUS-WOLFRAM-MCP-FORMAT-V2-2026-11-09",
        "experiment_id":"JANUS-ZENO-TEMPORAL-001",
        "status":"LIVE_WOLFRAM_MCP_ARITHMETIC_MATCH_CONFIRMED",
        "source":{"live_run_url":gate.EXPECTED_RUN,
                  "server":"https://agenttools.wolfram.com/mcp",
                  "provider_content_sha256":"a"*64,
                  "provider_output_retained":False},
        "fixed_query":{
            "case_id":"zeno_format_probe_v2","public_expression":"cos(pi/4)^4",
            "independently_computed_expected":.25,"wolframalpha_tool_calls":1,
            "authentication_required":False,"bulk_requests_made":False},
        "verification":{
            "reported_parser_decision":"PROVIDER_MATH_MATCH_CONFIRMED",
            "arithmetic_match_verified":True,"parse_input_in_memory":True},
        "historical_result_preserved":{
            "previous_status":"PROVIDER_NUMERIC_RESULT_UNAVAILABLE",
            "previous_outcome_rewritten":False},
        "limits":{"retrosignal_proven":False,
                  "quantum_zeno_observed_in_hardware":False,
                  "electron_tachyon_identity_proven":False,
                  "production_model_modified":False},
    }


class FakeResponse:
    status=200
    def __init__(self,data):self.data=data
    def read(self,cap):return self.data[:cap]
    def geturl(self):return gate.RECORD_URL
    def __enter__(self):return self
    def __exit__(self,*args):return False


class FakeOpener:
    def open(self,request,timeout):
        assert request.full_url==gate.RECORD_URL
        return FakeResponse(json.dumps(source()).encode())


class Tests(unittest.TestCase):
    def test_good_source_is_arithmetic_only(self):
        result=gate.report(source())
        self.assertEqual(result["status"],"SOURCE_BOUND_WOLFRAM_ARITHMETIC_MATCH_RECORDED")
        self.assertTrue(result["external_arithmetic_reported_verified"])
        self.assertEqual(result["provider_direct_calls_by_ocean"],0)
        self.assertFalse(result["independent_physics_experiment_verified"])
        self.assertFalse(result["physical_retrocausal_signal_verified"])
        self.assertFalse(result["replaces_prior_failed_record"])

    def test_malicious_retroclaim_fails_closed(self):
        d=source()
        d["limits"]["retrosignal_proven"]=True
        self.assertEqual(gate.decision(d),"REJECTED_PHYSICAL_AUTHORITY")
        d=source()
        d["fixed_query"]["bulk_requests_made"]=True
        self.assertEqual(gate.decision(d),"REJECTED_QUERY_SCOPE")
        d=source()
        d["verification"]["arithmetic_match_verified"]=False
        self.assertEqual(gate.decision(d),"REJECTED_MATH_CLAIM")

    def test_cannot_rewrite_old_failure(self):
        d=source()
        d["historical_result_preserved"]["previous_outcome_rewritten"]=True
        self.assertEqual(gate.decision(d),"REJECTED_HISTORICAL_OVERWRITE_CLAIM")

    def test_missing_record_is_not_success(self):
        p=gate.pending("SOURCE_RECORD_NOT_PUBLISHED")
        self.assertFalse(p["external_arithmetic_reported_verified"])
        self.assertEqual(p["status"],"SOURCE_RECORD_NOT_PUBLISHED")

    def test_readonly_fixed_source(self):
        d=gate.retrieve(FakeOpener())
        self.assertTrue(d["external_arithmetic_reported_verified"])
        self.assertFalse(d["promotion_of_production_model"])


if __name__=="__main__":
    unittest.main(verbosity=2)
