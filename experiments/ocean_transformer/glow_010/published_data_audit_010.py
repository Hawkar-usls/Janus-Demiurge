#!/usr/bin/env python3
"""GLOW-010: audit CC-BY public SrAl2O4:Eu,Dy published raw decay data.

This is a read-only retrospective source inventory. No SUNLU filament tested.
Do NOT claim OPJ/raw numerical time-series successfully extracted until
explicit data parsing, units, and provenance checks are completed.
"""
import hashlib
import io
import json
from pathlib import PurePosixPath,Path
import urllib.request
import zipfile
from collections import Counter

SOURCE="https://zenodo.org/records/18862107/files/metadata.zip?download=1"
MD5="3a11f363c6ce6cb3d465611682577662"
DOI="10.5281/zenodo.18862107"
LICENSE="CC-BY-4.0"
MAX_BYTES=20_000_000

def fetch():
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"JANUS-GLOW-010/1.0 (scientific public dataset audit)"})
    with urllib.request.urlopen(req,timeout=55) as f:
        data=f.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("SOURCE_SIZE_TOO_LARGE")
    if hashlib.md5(data).hexdigest()!=MD5:
        raise ValueError("PUBLISHED_ZENODO_MD5_MISMATCH")
    return data

def inspect_archive(blob):
    if hashlib.md5(blob).hexdigest()!=MD5:
        raise ValueError("PUBLISHED_ZENODO_MD5_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members=[]
        nested=[]
        for i in z.infolist():
            if i.is_dir():
                continue
            name=PurePosixPath(i.filename)
            if (".." in name.parts or name.is_absolute() or i.file_size>200_000_000):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            members.append({"name":i.filename,"uncompressed_bytes":i.file_size,
                            "crc32":f"{i.CRC:08x}",
                            "suffix":name.suffix.lower()})
            if name.suffix.lower()==".opju":
                inner=z.read(i.filename)
                sample={"name":i.filename,"is_zip_based":zipfile.is_zipfile(io.BytesIO(inner)),
                        "header_magic_hex":inner[:16].hex()}
                if sample["is_zip_based"]:
                    with zipfile.ZipFile(io.BytesIO(inner)) as child:
                        sample["inner_count"]=len(child.namelist())
                        sample["inner_paths"]=child.namelist()[:25]
                nested.append(sample)
    extensions=dict(sorted(Counter(x["suffix"] for x in members).items()))
    return {
      "schema":"janus.ocean.glow010.published_dataset_inventory.v1",
      "status":"SOURCE_ARCHIVE_HASH_VERIFIED_FORMAT_INVENTORIED",
      "experiment":"GLOW-010",
      "source_doi":DOI,"source_archive_url":SOURCE,
      "reported_license":LICENSE,
      "zip_md5":MD5,"zip_sha256":hashlib.sha256(blob).hexdigest(),
      "n_entries":len(members),"extension_counts":extensions,
      "members":members[:300],
      "opju_nested_metadata":nested,
      "members_truncated":len(members)>300,
      "physical_raw_decay_curve_parsed":False,
      "phosphor_lifetimes_reestimated":False,
      "SUNLU_sample_measured":False,
      "retrocausality_proven":False,
      "next_gate":"Identify original SrAl2O4:Eu,Dy afterglow worksheets and extract verified intensity/time rows with units before fitting."
    }

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    result=inspect_archive(fetch())
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x") as f:
        f.write(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:result[k] for k in ("status","n_entries","extension_counts","zip_sha256")},sort_keys=True))

if __name__=="__main__":
    main()
