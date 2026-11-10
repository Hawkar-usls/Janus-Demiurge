#!/usr/bin/env python3
"""JANUS NIST-010I: inspect original NIST analysis source WITHOUT executing it.

The official NIST archive may contain hundreds of MB of data alongside
analysis scripts. Only bounded source fragments may be inspected in memory.
This is provenance/semantics research, not confirmation of physical time
synchronization or of retrocausality.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
import zipfile

URL="https://s3.amazonaws.com/nist-belltestdata/belldata/code/analysis/bell_analysis_code.zip"
MAX_ZIP=875_000_000
MAX_FILES=30000
MAX_SCAN_BYTES=80_000_000
MAX_SINGLE_FILE=750_000
MAX_RESULT_FILES=125
MAX_MATCHES_PER_FILE=25
MAX_TOTAL_MATCHES=350
SOURCE_EXT={".py",".m",".txt",".yaml",".yml",".md",".r",".sh",".jl",".rst",".cfg",".ini"}
RE=re.compile(r"badSyncInfo|bitoffset|first.*GPS|common.*GPS|skip.*sync|clock.*misalign|time.?tag.*align|offset|align|sync",re.I)


def acquire(path):
    r=urllib.request.Request(URL,headers={"User-Agent":"JANUS-010I NIST public source provenance audit"})
    h=hashlib.sha256();size=0
    with urllib.request.urlopen(r,timeout=180) as src,path.open("xb") as dest:
        declared=src.headers.get("Content-Length")
        if declared and int(declared)>MAX_ZIP:raise ValueError("NIST_SOURCE_ZIP_EXCEEDS_CAP")
        while True:
            buf=src.read(4*1024*1024)
            if not buf:break
            size+=len(buf)
            if size>MAX_ZIP:raise ValueError("NIST_SOURCE_ZIP_STREAM_OVER_CAP")
            dest.write(buf);h.update(buf)
        dest.flush();os.fsync(dest.fileno())
    return size,h.hexdigest()


def analyze_archive(path):
    scanned_files=0;scanned_bytes=0;total_matches=0;matching=[]
    all_py=[]
    with zipfile.ZipFile(path) as z:
        members=z.infolist()
        if len(members)>MAX_FILES:raise ValueError("ZIP_HAS_TOO_MANY_ENTRIES")
        for info in members:
            if info.is_dir():continue
            ext=Path(info.filename).suffix.lower()
            if ext not in SOURCE_EXT:continue
            if ext==".py" and len(all_py)<300:
                all_py.append(info.filename)
            if info.file_size>MAX_SINGLE_FILE:continue
            if scanned_bytes+info.file_size>MAX_SCAN_BYTES:break
            scanned_bytes+=info.file_size;scanned_files+=1
            with z.open(info) as file:
                raw=file.read(MAX_SINGLE_FILE+1)
            if len(raw)>MAX_SINGLE_FILE:continue
            content=raw.decode("utf8","replace")
            found=[]
            for line_no,line in enumerate(content.splitlines(),1):
                if RE.search(line):
                    found.append({"line":line_no,"snippet":line.strip()[:220]})
                    total_matches+=1
                    if len(found)>=MAX_MATCHES_PER_FILE or total_matches>=MAX_TOTAL_MATCHES:break
            if found:
                matching.append({"path":info.filename,
                   "original_file_sha256":hashlib.sha256(raw).hexdigest(),
                   "file_size":info.file_size,"matching_lines":found})
                if len(matching)>=MAX_RESULT_FILES or total_matches>=MAX_TOTAL_MATCHES:break
    return {"archive_entries":len(members),"source_files_scanned":scanned_files,
            "source_bytes_scanned":scanned_bytes,
            "total_matching_lines_retained":total_matches,
            "matching_original_scripts":matching,
            "first_300_python_paths":all_py,
            "source_scan_may_be_incomplete":scanned_bytes>=MAX_SCAN_BYTES or total_matches>=MAX_TOTAL_MATCHES or len(matching)>=MAX_RESULT_FILES,
            "code_not_executed":True,
            "author_clock_calibration_still_requires_independent_validation":True}


def run(out):
    with tempfile.TemporaryDirectory(prefix="janus-nist-010i-") as d:
        path=Path(d)/"bell_analysis_code.zip"
        n,sha=acquire(path)
        print("NIST_010I_DOWNLOADED "+json.dumps({"original_source_zip_sha256":sha,"zip_bytes":n}),flush=True)
        audit=analyze_archive(path)
    rec={"schema":"janus.nist010i.original_analysis_source_audit.v1",
      "source_url":URL,"original_zip_sha256":sha,"original_zip_bytes":n,
      "audit":audit,
      "method":"Only bounded text-source matches and line references, no original raw data rehosted",
      "results_timing_metadata_verified_independently":False,
      "not_a_photon_analysis":True,
      "retrocausality_proven":False}
    dst=Path(out);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf8") as f:
        json.dump(rec,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010I_RESULT "+json.dumps({"scanned_files":audit["source_files_scanned"],
         "source_lines_matched":audit["total_matching_lines_retained"],
         "matching_paths":[x["path"] for x in audit["matching_original_scripts"]][:60],
         "scan_incomplete":audit["source_scan_may_be_incomplete"]},sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    run(p.parse_args().output)
