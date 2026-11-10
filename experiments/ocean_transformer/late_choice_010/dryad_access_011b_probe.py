#!/usr/bin/env python3
"""011B pre-analysis source probe: public Dryad only, no model calculation.

This deliberately attempts authenticated Dryad public HTTPS API/file routes
with bounded sizes. It logs a deterministic availability report and redacts
the transfer payload: first two lines only for ONE original outcome CSV.
A blocked download is not a scientific negative result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

BASE="https://datadryad.org"
MAX=400000
URLS=[
 BASE+"/api/v2/datasets/doi%3A10.5061%2Fdryad.8kprr4z24",
 BASE+"/api/v2/datasets/doi%3A10.5061/dryad.8kprr4z24",
 BASE+"/downloads/file_stream/4817730",
 BASE+"/api/v2/files/4817730/download",
 BASE+"/downloads/doi:10.5061/dryad.8kprr4z24",
 BASE+"/api/v2/versions/448155",
 BASE+"/api/v2/versions/448155/files",
 BASE+"/api/v2/datasets/doi%3A10.5061%2Fdryad.8kprr4z24/download",
 BASE+"/api/v2/files/4817730",
 BASE+"/api/v2/versions/448155/download",
]
def probe(url):
    try:
        req=Request(url,headers={"User-Agent":"JANUS/011B (public-scientific-audit; email not required)","Accept":"application/json,text/csv,application/octet-stream;q=0.7"})
        with urlopen(req,timeout=25) as f:
            typ=f.headers.get("Content-Type","")
            raw=f.read(MAX+1)
            if len(raw)>MAX:
                return {"url":url,"status":"REFUSED_OVER_CAP"}
            if typ.startswith("text/html") and not raw.lstrip().startswith(b"{"):
                return {"url":url,"status":"HTML_INSTEAD_OF_PUBLIC_CSV_OR_JSON","sha256":hashlib.sha256(raw).hexdigest()}
            out={"url":url,"status":"RECEIVED","byte_count":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"content_type":typ}
            if "json" in typ or raw.lstrip().startswith(b"{"):
                try:
                    data=json.loads(raw)
                    out["top_keys"]=sorted(data.keys()) if isinstance(data,dict) else []
                    out["dataset_keys"]=data.get("_links") if isinstance(data,dict) else None
                    out["first_file_metadata"]=data.get("_embedded",{}) if isinstance(data,dict) else None
                except ValueError:out["parse_error"]="INVALID_JSON"
            elif "csv" in typ or b"," in raw[:400]:
                lines=raw.decode("utf-8-sig","replace").splitlines()
                out["first_two_lines"]=[x[:250] for x in lines[:2]]
            return out
    except (HTTPError,URLError,TimeoutError) as e:
        return {"url":url,"status":"HTTP_OR_NETWORK_ERROR","error_type":type(e).__name__,"code":getattr(e,"code",None)}

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);arg=p.parse_args()
    paths=[probe(url) for url in URLS]
    result={"schema":"janus.011b.dryad_access_probe.v1","dataset_doi":"10.5061/dryad.8kprr4z24","results":paths,
            "public_source_access_confirmed":any(x["status"]=="RECEIVED" for x in paths),
            "original_16_csv_results_analyzed":False,"retrocause_signal_observed":False}
    out=Path(arg.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x") as f:json.dump(result,f,indent=2)
    print("JANUS_011B_PROBE "+json.dumps(result,sort_keys=True),flush=True)
if __name__=="__main__":main()
