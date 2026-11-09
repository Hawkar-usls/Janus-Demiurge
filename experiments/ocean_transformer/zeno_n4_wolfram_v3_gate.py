#!/usr/bin/env python3
"""JANUS Ocean read-only audit of a single keyless Wolfram MCP Zeno N4 receipt.

Source is immutable by value-binding: a public GitHub Beetle proof receipt,
not independent laboratory evidence. This process makes no Wolfram requests,
uses no credentials, and never upgrades math to physical retrocausality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import zeno_science_council_v3 as physics

SCHEMA = "janus.ocean.zeno_n4_beetle_mcp_math_gate.v3"
SOURCE_SCHEMA = "janus.beetle.wolfram_ocean_math_attestation.v3"
SOURCE_URL = ("https://raw.githubusercontent.com/Hawkar-usls/janus-lapis/"
              "beetle-state/data/beetle-state/wolfram_math/zeno_n4_unconditional_v3.json")
RESPONSE_SHA = "2b5410a0acd9b50d571e6553e4db63821ab3e9df5e817d3d991d5bb9a389c46e"
BEETLE_RECEIPT_SHA = "010a087fccf8e445bdb4d36690537a378544dc4a45a0dcc4a3b3a9a9ac2f1a2a"
CPU_REPORT_SHA = "fc93a5f12690cb969b68aea55fdf06dbe8c2e13a4b120add5c735890b5c8d8a2"
LIMIT = 8192


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decision(item):
    if not isinstance(item,dict):
        return "REJECTED_NONOBJECT"
    keys = {
        "schema","experiment_id","query_id","research_query",
        "independent_reference","verified_arithmetic_match",
        "verification_status","mcp_provider_response_sha256",
        "beetle_receipt_sha256","beetle_candidate_id","created_utc",
        "provider_endpoint","provider_raw_result_retained",
        "future_outcomes_transmitted","live_external_arithmetic_only",
        "physical_retrocausality_proven","production_model_promoted",
        "physical_observable","competing_observable_not_equal",
        "zeno_cpu_v3_report_sha256","older_v1_attestation_overwritten",
    }
    if set(item) != keys:
        return "REJECTED_SCHEMA_FIELDS"
    fixed = {
        "schema": SOURCE_SCHEMA,
        "experiment_id": physics.EXPERIMENT,
        "query_id":"zeno_n4_unconditional_v3",
        "research_query":"(1+cos(pi/4)^4)/2",
        "verification_status":"PROVIDER_MATH_MATCH_CONFIRMED",
        "verified_arithmetic_match":True,
        "provider_endpoint":"https://agenttools.wolfram.com/mcp",
        "provider_raw_result_retained":False,
        "future_outcomes_transmitted":False,
        "live_external_arithmetic_only":True,
        "physical_retrocausality_proven":False,
        "production_model_promoted":False,
        "physical_observable":"N4_FINAL_ZERO_WITH_EARLIER_RESULTS_UNREAD",
        "competing_observable_not_equal":"N4_ALL_FOUR_ZERO",
        "zeno_cpu_v3_report_sha256": CPU_REPORT_SHA,
        "older_v1_attestation_overwritten":False,
        "mcp_provider_response_sha256": RESPONSE_SHA,
        "beetle_receipt_sha256": BEETLE_RECEIPT_SHA,
    }
    if any(item.get(k) != v for k,v in fixed.items()):
        return "REJECTED_SOURCE_BOUNDARY"
    expected = physics.reference_cases()[0]
    value = item.get("independent_reference")
    if type(value) not in (int,float) or not math.isfinite(value):
        return "REJECTED_REFERENCE_TYPE"
    if abs(value-expected["analytical_reference"]) > 1e-12:
        return "REJECTED_REFERENCE_MISMATCH"
    if expected["case_id"] != "zeno_n4_unconditional":
        return "REJECTED_CPU_CASE_ORDER"
    return "EXTERNAL_MCP_N4_ARITHMETIC_MATCH_RECORDED"


def audit(source):
    status=decision(source)
    digest=hashlib.sha256(json.dumps(source,sort_keys=True,
                         ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    return {
        "schema":SCHEMA,"source_url":SOURCE_URL,"source_sha256":digest,
        "status":status,
        "external_math_reported_confirmed":status=="EXTERNAL_MCP_N4_ARITHMETIC_MATCH_RECORDED",
        "local_analytic_n4_unconditional":physics.reference_cases()[0]["analytical_reference"],
        "local_analytic_n4_all_zero":physics.reference_cases()[1]["analytical_reference"],
        "different_events_not_conflated":True,
        "provider_calls_by_ocean":0,
        "raw_provider_output_stored":False,
        "independent_physics_measurements_verified":False,
        "physical_retrocausal_channel_proven":False,
        "production_model_weights_modified":False,
    }


def pending(state):
    if state not in ("RECEIPT_NOT_PUBLISHED","SOURCE_UNAVAILABLE"):
        raise ValueError("INVALID_PENDING_REASON")
    return {"schema":SCHEMA,"source_url":SOURCE_URL,"status":state,
            "external_math_reported_confirmed":False,
            "provider_calls_by_ocean":0,"raw_provider_output_stored":False,
            "independent_physics_measurements_verified":False,
            "physical_retrocausal_channel_proven":False,
            "production_model_weights_modified":False}


def retrieve(opener=None):
    if opener is None:
        opener=build_opener(NoRedirect())
    request=Request(SOURCE_URL,headers={"User-Agent":"JANUS-OCEAN-N4-READONLY/1",
                                        "Accept":"application/json"})
    try:
        with opener.open(request,timeout=12) as response:
            if response.geturl()!=SOURCE_URL or response.status!=200:
                return pending("SOURCE_UNAVAILABLE")
            data=response.read(LIMIT+1)
    except HTTPError as e:
        return pending("RECEIPT_NOT_PUBLISHED" if e.code==404 else "SOURCE_UNAVAILABLE")
    except (URLError,TimeoutError,OSError):
        return pending("SOURCE_UNAVAILABLE")
    if len(data)>LIMIT:
        return pending("SOURCE_UNAVAILABLE")
    try:
        item=json.loads(data)
    except (ValueError,UnicodeError):
        return pending("SOURCE_UNAVAILABLE")
    return audit(item)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    path=Path(args.output)
    if path.exists():
        raise RuntimeError("REFUSE_OVERWRITE_RESEARCH_EVIDENCE")
    report=retrieve()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":report["status"],"provider_calls":0,
                      "physical_retrocausal_channel_proven":False},sort_keys=True))


if __name__=="__main__":
    main()
