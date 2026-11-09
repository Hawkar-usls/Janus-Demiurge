#!/usr/bin/env python3
"""Read-only, fail-closed JANUS Ocean import of Beetle Wolfram MCP *arithmetic* evidence.

Only the small source-bound Beetle attestation is fetched from the exact
public beetle-state branch. This module never calls the Wolfram provider, sends
a model prompt, reads secrets, or treats an external calculation as physical
proof. The fetched data may come from a user-controlled repository; therefore
this gate is a provenance indicator, NOT an independent lab witness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import zeno_temporal_001 as quantum

BEETLE_URL = ("https://raw.githubusercontent.com/Hawkar-usls/janus-lapis/"
              "beetle-state/data/beetle-state/wolfram_math/zeno_n2_verified_v1.json")
MAX_BYTES = 16_384
SCHEMA = "janus.ocean.beetle_wolfram_readonly_gate.v1"
SOURCE_SCHEMA = "janus.beetle.wolfram_ocean_math_attestation.v1"
EXPECTED_QUERY = "cos(pi/4)^4"
EXPECTED_CASE = "zeno_n2_verified_v1"
PROVIDER = "https://agenttools.wolfram.com/mcp"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def source_decision(source):
    if not isinstance(source, dict):
        return "REJECTED_MALFORMED_SOURCE"
    allowed_keys = {
        "schema", "experiment_id", "query_id", "research_query",
        "independent_reference", "verified_arithmetic_match",
        "verification_status", "mcp_provider_response_sha256",
        "beetle_receipt_sha256", "beetle_candidate_id", "created_utc",
        "provider_endpoint", "provider_raw_result_retained",
        "future_outcomes_transmitted", "live_external_arithmetic_only",
        "physical_retrocausality_proven", "production_model_promoted",
    }
    if set(source) != allowed_keys:
        return "REJECTED_UNEXPECTED_OR_MISSING_FIELDS"
    required = {
        "schema": SOURCE_SCHEMA,
        "experiment_id": quantum.EXPERIMENT_ID,
        "query_id": EXPECTED_CASE,
        "research_query": EXPECTED_QUERY,
        "provider_endpoint": PROVIDER,
        "provider_raw_result_retained": False,
        "future_outcomes_transmitted": False,
        "live_external_arithmetic_only": True,
        "physical_retrocausality_proven": False,
        "production_model_promoted": False,
    }
    if any(source.get(k) != v for k, v in required.items()):
        return "REJECTED_SOURCE_BOUNDARY"
    expected = quantum.probabilities(math.pi, 2)["all_zero_measurement_record_probability"]
    value = source.get("independent_reference")
    if type(value) not in (float, int) or not math.isfinite(value):
        return "REJECTED_REFERENCE_NONNUMERIC"
    if abs(value - expected) > 1e-12:
        return "REJECTED_REFERENCE_CHANGED"
    for key in ("mcp_provider_response_sha256","beetle_receipt_sha256"):
        sha=source.get(key)
        if not isinstance(sha, str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
            return "REJECTED_DIGEST_MALFORMED"
    if source.get("verification_status") != "PROVIDER_MATH_MATCH_CONFIRMED":
        return "REPORTED_BUT_NUMERIC_NOT_CONFIRMED"
    if source.get("verified_arithmetic_match") is not True:
        return "REJECTED_INCONSISTENT_MATH_STATUS"
    return "BEETLE_WOLFRAM_MATH_REPORTED_MATCH"


def validate_and_bind(source):
    status=source_decision(source)
    canon=json.dumps(source,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return {
        "schema": SCHEMA,
        "experiment_id": quantum.EXPERIMENT_ID,
        "beetle_public_source": BEETLE_URL,
        "source_sha256": hashlib.sha256(canon).hexdigest(),
        "status": status,
        "remote_mcp_math_verified_reported": status=="BEETLE_WOLFRAM_MATH_REPORTED_MATCH",
        "source_beetle_receipt_sha256": source.get("beetle_receipt_sha256") if status=="BEETLE_WOLFRAM_MATH_REPORTED_MATCH" else None,
        "standard_zeno_analytic_reference": quantum.probabilities(math.pi,2)["all_zero_measurement_record_probability"],
        "origin": "GITHUB_PUBLIC_BEETLE_BRANCH_NOT_INDEPENDENT_EXTERNAL_LAB",
        "wolfram_provider_called_by_this_job": False,
        "api_key_used": False,
        "provider_output_stored": False,
        "real_quantum_hardware_used": False,
        "physical_retrocausal_channel_proven": False,
        "production_checkpoint_changed": False,
    }


def pending(reason):
    if reason not in ("NO_RECEIPT_YET", "SOURCE_UNAVAILABLE"):
        raise ValueError("UNEXPECTED_SOURCE_REASON")
    return {
        "schema": SCHEMA, "experiment_id": quantum.EXPERIMENT_ID,
        "beetle_public_source": BEETLE_URL,
        "status": reason,
        "remote_mcp_math_verified_reported": False,
        "source_sha256": None,
        "origin": "GITHUB_PUBLIC_BEETLE_BRANCH_NOT_INDEPENDENT_EXTERNAL_LAB",
        "wolfram_provider_called_by_this_job": False,
        "api_key_used": False,
        "provider_output_stored": False,
        "physical_retrocausal_channel_proven": False,
        "production_checkpoint_changed": False,
    }


def retrieve(opener=None):
    # 404 is expected until the new bounded Beetle query actually succeeds.
    if opener is None:
        opener=build_opener(NoRedirect())
    try:
        req=Request(BEETLE_URL,headers={"User-Agent":"JANUS-OCEAN-READONLY/1",
                                       "Accept":"application/json"})
        with opener.open(req,timeout=12) as response:
            if response.geturl()!=BEETLE_URL:
                return pending("SOURCE_UNAVAILABLE")
            if response.status!=200:
                return pending("SOURCE_UNAVAILABLE")
            body=response.read(MAX_BYTES+1)
    except HTTPError as e:
        if e.code==404:
            return pending("NO_RECEIPT_YET")
        return pending("SOURCE_UNAVAILABLE")
    except (URLError,TimeoutError,OSError):
        return pending("SOURCE_UNAVAILABLE")
    if len(body)>MAX_BYTES:
        return pending("SOURCE_UNAVAILABLE")
    try:
        source=json.loads(body)
    except (ValueError,UnicodeError):
        return pending("SOURCE_UNAVAILABLE")
    return validate_and_bind(source)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    p=Path(args.output)
    if p.exists():
        raise RuntimeError("REFUSE_OVERWRITE_SOURCE_RECEIPT")
    data=retrieve()
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":data["status"],
                      "wolfram_provider_called":False,
                      "physical_retrocausal_channel_proven":False},sort_keys=True))


if __name__=="__main__":
    main()
