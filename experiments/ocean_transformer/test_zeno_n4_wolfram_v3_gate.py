#!/usr/bin/env python3
"""No-network tests for exact V3 Wolfram Cloud MCP Beetle receipt."""
import json
import unittest

import zeno_n4_wolfram_v3_gate as g


def fixture():
    return {
        "schema":"janus.beetle.wolfram_ocean_math_attestation.v3",
        "experiment_id":"JANUS-ZENO-TEMPORAL-002",
        "query_id":"zeno_n4_unconditional_v3",
        "research_query":"(1+cos(pi/4)^4)/2",
        "independent_reference":0.625,
        "verified_arithmetic_match":True,
        "verification_status":"PROVIDER_MATH_MATCH_CONFIRMED",
        "mcp_provider_response_sha256":g.RESPONSE_SHA,
        "beetle_receipt_sha256":g.BEETLE_RECEIPT_SHA,
        "beetle_candidate_id":"e7f8abac0ba6faef414ca51a",
        "created_utc":"2026-11-09T13:14:58.838691Z",
        "provider_endpoint":"https://agenttools.wolfram.com/mcp",
        "provider_raw_result_retained":False,
        "future_outcomes_transmitted":False,
        "live_external_arithmetic_only":True,
        "physical_retrocausality_proven":False,
        "production_model_promoted":False,
        "physical_observable":"N4_FINAL_ZERO_WITH_EARLIER_RESULTS_UNREAD",
        "competing_observable_not_equal":"N4_ALL_FOUR_ZERO",
        "zeno_cpu_v3_report_sha256":g.CPU_REPORT_SHA,
        "older_v1_attestation_overwritten":False,
    }


class Response:
    status=200
    def __init__(self, body): self.body=body
    def geturl(self): return g.SOURCE_URL
    def read(self, n): return self.body[:n]
    def __enter__(self): return self
    def __exit__(self, *args): return False


class Opener:
    def open(self, request, timeout):
        if request.full_url!=g.SOURCE_URL:
            raise AssertionError("UNAPPROVED_EXTERNAL_SOURCE")
        return Response(json.dumps(fixture()).encode())


class V3Tests(unittest.TestCase):
    def test_verified_math_is_not_physics(self):
        result=g.audit(fixture())
        self.assertEqual(result["status"],"EXTERNAL_MCP_N4_ARITHMETIC_MATCH_RECORDED")
        self.assertTrue(result["external_math_reported_confirmed"])
        self.assertEqual(result["provider_calls_by_ocean"],0)
        self.assertFalse(result["independent_physics_measurements_verified"])
        self.assertFalse(result["physical_retrocausal_channel_proven"])
        self.assertFalse(result["production_model_weights_modified"])

    def test_two_n4_observables_must_not_be_equal(self):
        result=g.audit(fixture())
        self.assertAlmostEqual(result["local_analytic_n4_unconditional"],.625)
        self.assertAlmostEqual(result["local_analytic_n4_all_zero"],.5307900429449552)
        self.assertTrue(result["different_events_not_conflated"])

    def test_any_scientific_claim_or_source_tampering_rejected(self):
        modifications={
            "mcp_provider_response_sha256":"0"*64,
            "zeno_cpu_v3_report_sha256":"0"*64,
            "physical_retrocausality_proven":True,
            "provider_raw_result_retained":True,
            "older_v1_attestation_overwritten":True,
            "verified_arithmetic_match":False,
            "independent_reference":.5307900429449552,
            "research_query":"1/2",
        }
        for key,value in modifications.items():
            item=fixture()
            item[key]=value
            self.assertFalse(g.audit(item)["external_math_reported_confirmed"],key)

    def test_extra_provider_content_rejected(self):
        item=fixture()
        item["provider_raw_content"]="secret provider output"
        self.assertEqual(g.decision(item),"REJECTED_SCHEMA_FIELDS")

    def test_pending_is_never_a_success(self):
        for code in ("RECEIPT_NOT_PUBLISHED","SOURCE_UNAVAILABLE"):
            value=g.pending(code)
            self.assertEqual(value["status"],code)
            self.assertFalse(value["external_math_reported_confirmed"])
        with self.assertRaises(ValueError):
            g.pending("PASS")

    def test_readonly_path_is_exact_source(self):
        report=g.retrieve(Opener())
        self.assertTrue(report["external_math_reported_confirmed"])
        self.assertEqual(report["provider_calls_by_ocean"],0)


if __name__=="__main__":
    unittest.main(verbosity=2)
