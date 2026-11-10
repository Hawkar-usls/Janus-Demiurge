#!/usr/bin/env python3
"""JANUS-010K: provenance-only, pinned source-code audit of later author code.

A similar function name is not evidence of the missing 2015 NIST
build_file_txt.py. Critically these *later* implementations explicitly
optimize photon/detector coincidences when estimating offsets, so the
estimated offset is NOT an independent physical clock reference.
Only code is fetched, no original data, no source executed.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import urllib.request

REPOS={
    "kshalm/bellhelpers":{
        "commit":"c84205362e1ab8620cfb03d321f2c15834e9c684",
        "repo_created_utc":"2022-09-16T20:44:33Z",
        "commit_utc":"2023-07-24T20:01:48Z",
        "paths":{
            "process":"bellhelper/data/processBellData.py",
            "tt":"bellhelper/data/timetaggers.py",
            "coinc":"bellhelper/data/coinclib.py"
        }
    },
    "kshalm/bellanalysishelper":{
        "commit":"a7827601816b1d3f0403935b86069568f99b8df1",
        "repo_created_utc":"2023-02-10T22:28:00Z",
        "commit_utc":"2023-10-24T02:03:15Z",
        "paths":{
            "process":"analysishelper/processBellData.py",
            "tt":"analysishelper/timetaggers.py",
            "coinc":"analysishelper/coinclib.py"
        }
    }
}
MAX_SINGLE_SOURCE=125_000

def calls_of_function(code,name):
    """Use Python AST; never import or execute downloaded code."""
    tree=ast.parse(code)
    candidates=[v for v in ast.walk(tree) if isinstance(v,(ast.FunctionDef,ast.AsyncFunctionDef)) and v.name==name]
    if len(candidates)!=1:
        raise ValueError(f"AUTHOR_FUNCTION_{name}_MISSING_OR_DUPLICATE")
    body=candidates[0]
    calls=[]
    for n in ast.walk(body):
        if not isinstance(n,ast.Call): continue
        fn=n.func
        if isinstance(fn,ast.Name): calls.append(fn.id)
        elif isinstance(fn,ast.Attribute):
            try: calls.append(ast.unparse(fn))
            except Exception: calls.append(fn.attr)
    return sorted(set(calls))

def audit_source_triplet(sources):
    p=calls_of_function(sources["process"],"find_ttag_offset")
    t=calls_of_function(sources["tt"],"find_sync_offset2")
    c=calls_of_function(sources["coinc"],"calc_offset")
    gates={
        "find_ttag_offset_calls_find_sync_offset2":"timeTaggers.find_sync_offset2" in p,
        "find_sync_offset2_calls_calc_offset":"cl.calc_offset" in t,
        "calc_offset_calls_coincidence_matching":"find_offset_coinc" in c,
        "calc_offset_optimizes_matching_count":"np.argmax" in c,
        "calc_offset_averages_matched_photon_timetags":"np.mean" in c
    }
    if not all(gates.values()):
        raise ValueError("AUTHOR_SOURCE_PROVENANCE_CHAIN_INCOMPLETE")
    return {"gates":gates,"function_call_graph":{
        "find_ttag_offset":p,
        "find_sync_offset2":t,
        "calc_offset":c
    },
    "independent_UTC_clock_anchor_from_this_algorithm":False,
    "methodological_caveat":"Post-hoc maximization of detected coincidences is not an independent time anchor for a hypothetical reversed-time signalling analysis"}

def obtain(repo,commit,path):
    url=f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    req=urllib.request.Request(url,headers={"User-Agent":"JANUS 010K public source provenance only"})
    with urllib.request.urlopen(req,timeout=40) as f:
        raw=f.read(MAX_SINGLE_SOURCE+1)
    if len(raw)>MAX_SINGLE_SOURCE:
        raise ValueError("SOURCE_EXCEEDS_FETCH_CAP")
    return url,raw.decode("utf8-sig"),hashlib.sha256(raw).hexdigest()

def run(destination):
    examined=[]
    for repo,spec in REPOS.items():
        src={}
        hashes={}
        for part,path in spec["paths"].items():
            url,code,digest=obtain(repo,spec["commit"],path)
            src[part]=code
            hashes[part]={"source_url":url,"source_sha256":digest,"bytes":len(code.encode("utf8"))}
        analysis=audit_source_triplet(src)
        examined.append({"repository":repo,"pin":spec["commit"],
                        "repository_created_utc":spec["repo_created_utc"],
                        "commit_utc":spec["commit_utc"],
                        "files":hashes,
                        "analysis":analysis,
                        "this_source_is_original_2015_build_file_txt_py":False})
    record={
        "schema":"janus.nist010k.later_author_code_provenance.v1",
        "kind":"LATER_AUTHOR_CODE_METHODOLOGY_REVIEW_NOT_2015_NIST_REPRODUCTION",
        "sources":examined,
        "original_2015_build_file_txt_py_found":False,
        "independent_2015_A_B_clock_offset_obtained":False,
        "2015_clock_provenance_gap_remains":True,
        "physical_retrocausality_measurement_performed":False,
        "retrocausality_proven":False,
        "admission":"REFUSE_AUTHOR_LATER_COINCIDENCE_TUNED_OFFSETS_AS_INDEPENDENT_CLOCK_REFERENCE",
        "next_gate":"Obtain exact 2015 build_file_txt.py or independently certified UTC-aligned sync reference; validate corrected-run time windows prospectively before using photon data"
    }
    dst=Path(destination);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf8") as f:
        json.dump(record,f,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010K_AUDIT "+json.dumps({
        "repos":len(examined),
        "code_provenance_gates_all_pass":all(all(z["analysis"]["gates"].values()) for z in examined),
        "eligible_independent_clock":False,
        "original_2015_dependency_found":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    run(ap.parse_args().output)
