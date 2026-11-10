#!/usr/bin/env python3
"""JANUS-010J: extract four ORIGINAL NIST author scripts for provenance audit.

Read-only; checks original official code ZIP SHA256 obtained in 010I.
Source is public NIST US-government software, not executable in this job.
No quantum outcomes, no data-dependent fitting and no retrocausal claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile

URL="https://s3.amazonaws.com/nist-belltestdata/belldata/code/analysis/bell_analysis_code.zip"
EXPECTED_SHA="80b452b55ce44bb46e37ffbcd1f1684ba3293aaf0b6445c36743da4a5d37c52d"
MAX_DOWNLOAD=850_000_000
PATHS=(
 "bell_analysis_code/build_file_txt.py",
 "bell_analysis_code/sync_hdf5.py",
 "bell_analysis_code/check_syncs.py",
 "bell_analysis_code/build_file_hdf5.py",
 "bell_analysis_code/build_file.yaml",
 "bell_analysis_code/settings_hdf5.py"
)
MAX_TEXT_BYTES=160000

def download(dest):
    req=urllib.request.Request(URL,headers={"User-Agent":"JANUS NIST 010J public code audit"})
    h=hashlib.sha256();bytes_seen=0
    with urllib.request.urlopen(req,timeout=150) as src,dest.open("xb") as out:
        reported=src.headers.get("Content-Length")
        if reported and int(reported)>MAX_DOWNLOAD:raise ValueError("TOO_LARGE_ORIGINAL_ZIP")
        while True:
            buf=src.read(4*1024*1024)
            if not buf:break
            bytes_seen+=len(buf)
            if bytes_seen>MAX_DOWNLOAD:raise ValueError("ZIP_EXCEEDS_CAP")
            h.update(buf);out.write(buf)
        out.flush();os.fsync(out.fileno())
    if h.hexdigest()!=EXPECTED_SHA:raise ValueError("ORIGINAL_NIST_CODE_SHA_CHANGED")
    return bytes_seen

def source_extract(zip_path):
    obj={}
    with zipfile.ZipFile(zip_path) as z:
        for name in PATHS:
            if name not in z.namelist():raise ValueError("MISSING_NIST_ORIGINAL_SCRIPT_"+name)
            info=z.getinfo(name)
            if info.file_size>MAX_TEXT_BYTES:raise ValueError("NIST_ORIGINAL_SCRIPT_OVER_CAP")
            txt=z.read(name).decode("utf8","replace")
            obj[name]={
                "sha256":hashlib.sha256(txt.encode("utf8")).hexdigest(),
                "original_source_lines":txt.splitlines(),
                "read_only_not_executed":True
            }
    return obj

def run(output):
    with tempfile.TemporaryDirectory(prefix="janus-nist-code-010j-") as d:
        path=Path(d)/"source.zip"
        n=download(path)
        contents=source_extract(path)
    rec={"schema":"janus.nist010j.original_sync_algorithm_source.v1",
         "source_uri":URL,"source_zip_sha256":EXPECTED_SHA,"archive_bytes":n,
         "original_nist_analysis_programs":contents,
         "author_hdf5_metadata_is_not_independent_clock_certification":True,
         "physics_experiment_performed":False,
         "retrocausality_proven":False}
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf8") as f:
        json.dump(rec,f,ensure_ascii=False,indent=2,sort_keys=True)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010J_RESULT "+json.dumps({
        "archive_bytes":n,"programs":[{"path":k,"lines":len(v["original_source_lines"])}
             for k,v in contents.items()],
        "source_sha256":EXPECTED_SHA,"clock_certified":False},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)
