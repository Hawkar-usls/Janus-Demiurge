#!/usr/bin/env python3
"""JANUS-010N April CALIBRATION-ONLY original archive format discovery.

Never opens June validation outcomes. Source MD5 from Zenodo metadata
is pinned in the pre-data freeze 010N commit ee8ff5fd. No inference here.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.request
import zipfile

URL="https://zenodo.org/records/22936124/files/Bell_2016-04-15.zip?download=1"
MD5="53544819317d4dcfbe5c63e039a8aa38"
CAP=2_000_000
UNZIP_TOTAL=60_000_000
PER_FILE_CAP=15_000_000

def download():
    req=urllib.request.Request(URL,headers={"User-Agent":"JANUS physical-010N schema-only April calibration"})
    with urllib.request.urlopen(req,timeout=90) as resp:
        blob=resp.read(CAP+1)
    if len(blob)>CAP:raise ValueError("ORIGINAL_ARCHIVE_EXCEEDS_CAP")
    if hashlib.md5(blob).hexdigest()!=MD5:raise ValueError("APRIL_ZENODO_MD5_MISMATCH")
    return blob

def inventory(blob):
    result=[]
    total=0
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for m in z.infolist():
            if m.is_dir():continue
            total+=m.file_size
            if total>UNZIP_TOTAL or m.file_size>PER_FILE_CAP:
                raise ValueError("DECOMPRESSED_SOURCE_OVERCAP")
            if m.filename.startswith("/") or ".." in Path(m.filename).parts:
                raise ValueError("UNSAFE_ZIP_PATH")
            data=z.read(m)
            if len(data)!=m.file_size:raise ValueError("ZIP_UNCOMPRESSED_SIZE_MISMATCH")
            obj={"name":m.filename,"uncompressed_bytes":len(data),
                 "sha256":hashlib.sha256(data).hexdigest()}
            try:
                lines=data.decode("utf8-sig").splitlines()
                obj["utf8_text"]=True
                obj["line_count"]=len(lines)
                # Only calibration archive, plus at most four short lines for schema
                obj["first_four_original_text_lines"]=[s[:220] for s in lines[:4]]
                obj["last_line_char_length"]=len(lines[-1]) if lines else 0
            except (UnicodeDecodeError,ValueError):
                obj["utf8_text"]=False
                obj["first_bytes_hex"]=data[:40].hex()
            result.append(obj)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    a=p.parse_args()
    blob=download()
    report={"schema":"janus.physical010n.april_source_schema.v1",
       "source_archival_DOI":"10.5281/zenodo.22936124",
       "source_original_publication_DOI":"10.1103/PhysRevLett.119.010402",
       "read_only_source":URL,
       "source_role":"APRIL_2016_CALIBRATION_ONLY",
       "source_zip_md5":MD5,
       "source_zip_sha256":hashlib.sha256(blob).hexdigest(),
       "source_zip_bytes":len(blob),
       "entries":inventory(blob),
       "June_2016_validation_archive_inspected":False,
       "external_new_physical_measurements_produced":False,
       "retrocausality_proven":False}
    dst=Path(a.output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf8") as f:
        json.dump(report,f,sort_keys=True,indent=2,ensure_ascii=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("JANUS_010N_SCHEMA "+json.dumps({"zip_sha256":report["source_zip_sha256"],"n_entries":len(report["entries"]),
      "entries":[{"name":e["name"],"size":e["uncompressed_bytes"],
                  "utf8":e["utf8_text"],"first_lines":e.get("first_four_original_text_lines")} for e in report["entries"]][:18],
      "June_archive_untouched":True},sort_keys=True),flush=True)

if __name__=="__main__":main()
