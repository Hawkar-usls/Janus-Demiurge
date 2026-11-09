#!/usr/bin/env python3
"""Source-bound read-only JANUS Ocean import of Wolfram Cloud MCP V2 registry evidence.

This checks the user's append-only Meta Registry science record, not the
underlying Wolfram provider. A PASS means source-bound arithmetic evidence
was recorded; it cannot establish physical retrocausality, Zeno lab
measurement, or trusted independent timing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

RECORD_URL = ("https://raw.githubusercontent.com/Hawkar-usls/janus-meta-registry/"
              "main/data/experiments/JANUS-WOLFRAM-MCP-FORMAT-V2-LIVE-2026-11-09.json")
EXPECTED_RECORD_ID = "JANUS-WOLFRAM-MCP-FORMAT-V2-2026-11-09"
EXPECTED_RUN = "https://github.com/Hawkar-usls/janus-lapis/actions/runs/42621020575"
EXPECTED_EXPRESSION = "cos(pi/4)^4"
MAX_BYTES=16_384
SCHEMA="janus.ocean.wolfram_registry_v2_readonly_gate.v1"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def _sha(value):
    return (isinstance(value,str) and len(value)==64
            and all(x in "0123456789abcdef" for x in value))


def decision(obj):
    if not isinstance(obj,dict):
        return "REJECTED_NONOBJECT"
    if (obj.get("schema")!="janus.research.wolfram_mcp_numeric_outcome.v2" or
        obj.get("record_id")!=EXPECTED_RECORD_ID or
        obj.get("experiment_id")!="JANUS-ZENO-TEMPORAL-001" or
        obj.get("status")!="LIVE_WOLFRAM_MCP_ARITHMETIC_MATCH_CONFIRMED"):
        return "REJECTED_SOURCE_ID_OR_STATUS"
    source=obj.get("source",{})
    query=obj.get("fixed_query",{})
    ver=obj.get("verification",{})
    history=obj.get("historical_result_preserved",{})
    bounds=obj.get("limits",{})
    if not all(isinstance(x,dict) for x in (source,query,ver,history,bounds)):
        return "REJECTED_SOURCE_STRUCTURE"
    if (source.get("live_run_url")!=EXPECTED_RUN or
        source.get("server")!="https://agenttools.wolfram.com/mcp" or
        not _sha(source.get("provider_content_sha256")) or
        source.get("provider_output_retained") is not False):
        return "REJECTED_PROVIDER_PROVENANCE"
    if (query.get("case_id")!="zeno_format_probe_v2" or
        query.get("public_expression")!=EXPECTED_EXPRESSION or
        type(query.get("independently_computed_expected")) not in (int,float) or
        not math.isclose(query["independently_computed_expected"],.25,abs_tol=1e-12) or
        query.get("wolframalpha_tool_calls")!=1 or
        query.get("authentication_required") is not False or
        query.get("bulk_requests_made") is not False):
        return "REJECTED_QUERY_SCOPE"
    if (ver.get("reported_parser_decision")!="PROVIDER_MATH_MATCH_CONFIRMED" or
        ver.get("arithmetic_match_verified") is not True or
        ver.get("parse_input_in_memory") is not True):
        return "REJECTED_MATH_CLAIM"
    if (history.get("previous_status")!="PROVIDER_NUMERIC_RESULT_UNAVAILABLE" or
        history.get("previous_outcome_rewritten") is not False):
        return "REJECTED_HISTORICAL_OVERWRITE_CLAIM"
    if (bounds.get("retrosignal_proven") is not False or
        bounds.get("quantum_zeno_observed_in_hardware") is not False or
        bounds.get("electron_tachyon_identity_proven") is not False or
        bounds.get("production_model_modified") is not False):
        return "REJECTED_PHYSICAL_AUTHORITY"
    return "SOURCE_BOUND_WOLFRAM_ARITHMETIC_MATCH_RECORDED"


def report(obj):
    status=decision(obj)
    canon=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    return {
        "schema":SCHEMA,
        "source_url":RECORD_URL,
        "source_canonical_sha256":hashlib.sha256(canon).hexdigest(),
        "status":status,
        "external_arithmetic_reported_verified":status=="SOURCE_BOUND_WOLFRAM_ARITHMETIC_MATCH_RECORDED",
        "provider_direct_calls_by_ocean":0,
        "provider_raw_output_stored":False,
        "independent_physics_experiment_verified":False,
        "physical_retrocausal_signal_verified":False,
        "replaces_prior_failed_record":False,
        "promotion_of_production_model":False,
    }


def pending(state):
    if state not in ("SOURCE_RECORD_NOT_PUBLISHED","SOURCE_FETCH_UNAVAILABLE"):
        raise ValueError("INVALID_PENDING_STATE")
    return {
        "schema":SCHEMA,"source_url":RECORD_URL,"status":state,
        "external_arithmetic_reported_verified":False,
        "provider_direct_calls_by_ocean":0,
        "provider_raw_output_stored":False,
        "independent_physics_experiment_verified":False,
        "physical_retrocausal_signal_verified":False,
        "replaces_prior_failed_record":False,
        "promotion_of_production_model":False,
    }


def retrieve(opener=None):
    if opener is None:
        opener=build_opener(NoRedirect())
    request=Request(RECORD_URL,headers={"User-Agent":"JANUS-OCEAN-REGISTRY-READONLY/1",
                                       "Accept":"application/json"})
    try:
        with opener.open(request,timeout=12) as response:
            if response.status!=200 or response.geturl()!=RECORD_URL:
                return pending("SOURCE_FETCH_UNAVAILABLE")
            body=response.read(MAX_BYTES+1)
    except HTTPError as e:
        return pending("SOURCE_RECORD_NOT_PUBLISHED" if e.code==404 else "SOURCE_FETCH_UNAVAILABLE")
    except (URLError,TimeoutError,OSError):
        return pending("SOURCE_FETCH_UNAVAILABLE")
    if len(body)>MAX_BYTES:
        return pending("SOURCE_FETCH_UNAVAILABLE")
    try:
        obj=json.loads(body)
    except (ValueError,UnicodeError):
        return pending("SOURCE_FETCH_UNAVAILABLE")
    return report(obj)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    p=Path(args.output)
    if p.exists():
        raise RuntimeError("REFUSE_OVERWRITE_RESEARCH_RECEIPT")
    result=retrieve()
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "provider_calls":0,
                      "physical_retrocausality_proven":False},sort_keys=True))


if __name__=="__main__":
    main()
