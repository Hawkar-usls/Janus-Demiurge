#!/usr/bin/env python3
"""JANUS Gull R12 real-data acquisition and lossless schema/provenance audit.

On GitHub Actions only, fetch original official sources. The output does NOT
conflate 2024 gull eyes, 2019/2020 human-gaze tasks, and 2013-22 Texel
tracks: these are DIFFERENT individuals and experimental settings.

Verify Zenodo publisher MD5 checksums and retain source SHA-256, parse
original per-bird DOCX table cells without guessing missing NR or bird IDs,
audit Dryad anonymous public dataset/files access, and stream gzip schema.
Never execute code from source data; never upload raw GPS coordinates, and
never invent unavailable source files.

Dependencies: Python 3 stdlib. No browser automation or API credential.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

DOI_GULL="10.1111/ibi.13360"
ZENODO="https://zenodo.org/records/23923176/files/"
DRYAD_API="https://datadryad.org/api/v2/"
DOCX_CANDIDATES=[
 "https://onlinelibrary.wiley.com/doi/suppl/10.1111/ibi.13360/supinfo/ibi13360-sup-0001-Tables.docx",
 "https://onlinelibrary.wiley.com/doi/supinfo/10.1111/ibi.13360/ibi13360-sup-0001-Tables.docx",
]
MAX_BYTES=12_000_000
XML_NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def assert_source(ok,reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def download(url,max_bytes=MAX_BYTES):
    if not url.startswith("https://"):
        raise ValueError("NONHTTPS_SOURCE")
    req=urllib.request.Request(
        url,headers={"User-Agent":"JANUS-gull-science-provenance/1.0 "
                                      "(read-only public data audit)",
                     "Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=18) as response:
        if response.status != 200:
            raise RuntimeError("NON_200_SOURCE")
        content=response.read(max_bytes+1)
        assert_source(len(content)<=max_bytes,"SOURCE_FILE_TOO_LARGE")
        return content


def status_reason(exc):
    if isinstance(exc,urllib.error.HTTPError):
        return "HTTP_"+str(exc.code)
    if isinstance(exc,urllib.error.URLError):
        return "UNAVAILABLE_NETWORK"
    if isinstance(exc,TimeoutError):
        return "NETWORK_TIMEOUT"
    return "INVALID_SOURCE_OR_FORMAT_"+type(exc).__name__


def wtext(node):
    return "".join(t.text or "" for t in node.findall(".//w:t",XML_NS)).strip()


def extract_docx_tables(payload):
    assert_source(len(payload)<500_000 and
                  zipfile.is_zipfile(io.BytesIO(payload)),
                  "NOT_ORIGINAL_SMALL_DOCX")
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert_source("word/document.xml" in z.namelist(),
                      "DOCX_HAS_NO_WORD_DOCUMENT")
        raw=z.read("word/document.xml")
        assert_source(len(raw)<3_000_000,"DOCX_XML_RESOURCE_CAP")
    root=ET.fromstring(raw)
    ns=XML_NS["w"]
    tables=[]
    for tbl in root.findall(".//w:tbl",XML_NS):
        rows=[]
        for tr in tbl.findall("w:tr",XML_NS):
            row=[wtext(tc) for tc in tr.findall("w:tc",XML_NS)]
            if row and any(x for x in row):
                rows.append(row)
        if rows:
            tables.append(rows)
    paragraphs=[wtext(p) for p in root.findall(".//w:body/w:p",XML_NS)]
    assert_source(0<len(tables)<=32,"DOCX_TABLE_COUNT_NOT_SUPPORTED")
    report={
      "source_format":"docx",
      "data_sha256":sha(payload),
      "table_count":len(tables),
      "table_dimensions":[{"rows":len(t),"max_columns":max(map(len,t))}
                          for t in tables],
      "headings_first_20":[p[:120] for p in paragraphs if p][:20],
      "NR_cells":sum(str(cell).strip().upper()=="NR"
                      for t in tables for row in t for cell in row),
      "preserved_all_original_cells":True,
      "individual_table_mapping_confirmed":False,
      "source_bird_identifiers_are_unverified":True,
    }
    return report,{"source_doi":DOI_GULL,
                   "license":"CC BY as published by Wiley",
                   "source_bytes_sha256":sha(payload),
                   "tables":tables,
                   "warnings":["Raw table cells only; bird header/column identity "
                               "not normalized without verified mapping",
                               "NR never interpreted as numeric zero"]}


def inspect_csv_bytes(content,max_rows=4000000):
    rows=0; names=set(); labels=Counter()
    # Strict utf8/UTF8-BOM fallback; CSV quote parsing. Source header only
    text=io.TextIOWrapper(
        gzip.GzipFile(fileobj=io.BytesIO(content)) if
        content[:2]==b"\x1f\x8b" else io.BytesIO(content),
        encoding="utf-8-sig",errors="replace",newline="")
    first=text.readline()
    delimiter="\t" if first.count("\t")>first.count(",") else ","
    rd=csv.DictReader(__import__("itertools").chain([first],text),delimiter=delimiter)
    header=rd.fieldnames or []
    assert_source(1<=len(header)<=200,"CSV_EMPTY_OR_TOO_MANY_FIELDS")
    identity_fields=[name for name in header if name.lower().strip() in
                     ("individual-local-identifier","individual-local-identifier-raw",
                      "individual-id","animal-id")]
    behavior_fields=[name for name in header
                     if re.search(r"behav|label|study-specific-measurement|annotation",name,re.I)]
    nonzero=0
    for row in rd:
        rows+=1
        if rows>max_rows:
            break
        for key in identity_fields:
            if row.get(key):
                names.add(row[key])
        for key in behavior_fields:
            value=(row.get(key) or "").strip()
            if value:
                labels[(key,value)]+=1
        if any(v not in (None,"") for v in row.values()):
            nonzero+=1
    return {
        "columns":header,
        "rows_scanned":min(rows,max_rows),
        "truncated_at_row_limit":rows>max_rows,
        "nonempty_rows_scanned":nonzero,
        "identity_column_names":identity_fields,
        "distinct_individuals_in_scanned_rows":len(names),
        "behavior_column_names":behavior_fields,
        "top_behavior_values_in_scanned_rows":[
            {"column":k,"value":v,"n":n}
            for (k,v),n in labels.most_common(25)],
        "individual_identifiers_or_coordinates_exported":False,
        "data_kind":"REAL_TRACKING_OR_ANNOTATION_ROWS_NOT_PAIRWISE_VISION"
    }


def zenodo_probe(manifest,output):
    source=next(s for s in manifest["sources"]
                if s["id"]=="hg_texel2026_individual_tracks")
    results=[]
    for file in source["files"]:
        fname=file["name"]
        row={"name":fname,"expected_md5":file["md5"],
             "published_url":ZENODO+fname+"?download=1"}
        try:
            content=download(row["published_url"],file["max_bytes"])
            md5=hashlib.md5(content).hexdigest()
            assert_source(md5==file["md5"],
                          "OFFICIAL_ZENODO_MD5_MISMATCH")
            row.update({"status":"VERIFIED_ORIGINAL_BYTES",
                        "sha256":sha(content),"actual_bytes":len(content),
                        "md5_check_pass":True})
            if fname.endswith((".csv",".csv.gz")):
                row["schema_audit"]=inspect_csv_bytes(content)
            elif fname.endswith(".json"):
                parsed=json.loads(content)
                row["data_package_type"]=type(parsed).__name__
                row["data_package_resource_count"]=len(parsed.get("resources",[]))
        except Exception as exc:
            row.update({"status":"NOT_INGESTED_"+status_reason(exc),
                        "error_class":type(exc).__name__})
        results.append(row)
    return results


def wiley_probe(output):
    attempts=[]; extracted=None
    for url in DOCX_CANDIDATES:
        row={"attempted_url":url,"url_path_is_inferred_not_publisher_confirmed":True}
        try:
            content=download(url,500000)
            info,extracted=extract_docx_tables(content)
            row.update({"status":"DOCX_TABLES_EXTRACTED",
                        "evidence":info})
            # Extracted full cells may be CC-BY but never upload the
            # original DOCX or claim bird-level mapping yet.
            output.joinpath("wiley-raw-tables.json").write_text(
                json.dumps(extracted,indent=2,ensure_ascii=False)+"\n")
            attempts.append(row)
            break
        except Exception as exc:
            row.update({"status":"NOT_INGESTED_"+status_reason(exc),
                        "error_class":type(exc).__name__})
            attempts.append(row)
    return attempts


def dryad_probe(doi):
    """Only published anonymous Dryad API paths; do not infer raw results.

    Dryad's /datasets/{doi} returns an id that may be a version id.
    Also look up /versions and nested links. Each candidate must resolve
    through an actual file catalog before attempting public file streams.
    """
    encoded="doi%3A"+doi.replace("/","%2F")
    report={"doi":doi,"files_checked":[]}
    try:
        raw=download(DRYAD_API+"datasets/"+encoded,500_000)
        metadata=json.loads(raw)
        report["metadata_status"]="FETCHED"
        report["metadata_sha256"]=sha(raw)
        report["metadata_top_level_keys"]=sorted(metadata.keys())
        report["metadata_id_type"]=type(metadata.get("id")).__name__
        links=metadata.get("_links") or {}
        report["metadata_link_types"]=sorted(links)
        ids=[]
        for key in ("id","versionID","versionId"):
            v=metadata.get(key)
            if type(v) in (str,int) and str(v).isdigit():
                ids.append(int(v))
        try:
            vraw=download(DRYAD_API+"datasets/"+encoded+"/versions",500_000)
            versions=json.loads(vraw)
            report["versions_type"]=type(versions).__name__
            if isinstance(versions,dict):
                report["versions_keys"]=sorted(versions)
                val=versions.get("_embedded") or {}
                list_candidate=(val.get("stash:versions") or
                                versions.get("versions") or
                                versions.get("items") or [])
            else:
                list_candidate=versions
            if isinstance(list_candidate,list):
                ids.extend(int(x.get("id") or x.get("versionID") or x.get("versionId"))
                           for x in list_candidate if isinstance(x,dict)
                           and str(x.get("id") or x.get("versionID") or
                                   x.get("versionId") or "").isdigit())
        except Exception as e:
            report["version_list_status"]="NOT_INGESTED_"+status_reason(e)
        ids=sorted(set(ids),reverse=True)
        report["version_candidates_count"]=len(ids)
        catalog=[]
        for vid in ids[:4]:
            try:
                catalog_raw=download(DRYAD_API+"versions/"+str(vid)+"/files",500_000)
                listing=json.loads(catalog_raw)
                if isinstance(listing,list):
                    files=listing
                elif isinstance(listing,dict):
                    nested=listing.get("_embedded") or {}
                    files=(nested.get("stash:files") or listing.get("files") or
                           listing.get("items") or [])
                    if isinstance(files,dict):
                        files=list(files.values())
                else:
                    files=[]
                if isinstance(files,list) and files:
                    catalog=files
                    report["source_version_id"]=vid
                    break
            except Exception as e:
                report.setdefault("catalog_failures",[]).append({
                    "version_candidate_index":ids.index(vid),
                    "status":"NOT_INGESTED_"+status_reason(e)})
        if not catalog:
            report["file_status"]="NO_PUBLIC_FILE_CATALOG"
            return report
        report["file_catalog_count"]=len(catalog)
        for f in catalog:
            if not isinstance(f,dict):
                continue
            fname=f.get("path") or f.get("name") or f.get("fileName") or ""
            if not str(fname).lower().endswith((".txt",".csv")):
                continue
            file_id=f.get("id") or f.get("fileId")
            if not file_id:
                continue
            entry={"filename":fname,"file_id":file_id}
            try:
                content=download(
                    "https://datadryad.org/downloads/file_stream/"+str(file_id),
                    max_bytes=100_000)
                entry["raw_status"]="FETCHED_PUBLIC_FILE"
                entry["sha256"]=sha(content)
                entry["schema_audit"]=inspect_csv_bytes(content,5000)
            except Exception as e:
                entry["raw_status"]="NOT_INGESTED_"+status_reason(e)
            report["files_checked"].append(entry)
        report["file_status"]="PUBLIC_FILE_CATALOG_READ"
    except Exception as e:
        report["metadata_status"]="NOT_INGESTED_"+status_reason(e)
        report["error_class"]=type(e).__name__
    return report


def analyze_manifest(manifest):
    assert_source(manifest.get("schema")==
                  "janus.gull.real_individual_sources.v2",
                  "SOURCE_MANIFEST_SCHEMA_CHANGED")
    source_ids={s.get("id") for s in manifest.get("sources",[])}
    assert_source(source_ids=={
        "cantlay2024_individual_visual_fields",
        "goumas2019_individual_behavior_gaze",
        "goumas2020_cue_foraging_behavior",
        "hg_texel2026_individual_tracks"},"SOURCE_SET_CHANGED")
    assert_source(manifest["hypothesis_test"][
        "actual_same_individual_vision_plus_behavior_dataset_available"] is False,
        "FORBID_JOINING_UNRELATED_GULL_SAMPLES")
    return True


def run(source,output):
    manifest=json.loads(source.read_text(encoding="utf8"))
    analyze_manifest(manifest)
    output.mkdir(parents=True,exist_ok=True)
    report={
      "schema":"janus.gull.real_sources.audit.v2",
      "manifest_sha256":sha(source.read_bytes()),
      "source_set":["10.1111/ibi.13360",
                    "10.5061/dryad.3jf80g4",
                    "10.5061/dryad.bnzs7h469",
                    "10.5281/zenodo.23923176"],
      "wiley_individual_visual_fields":wiley_probe(output),
      "dryad_gaze_2019":dryad_probe("10.5061/dryad.3jf80g4"),
      "dryad_cue_2020":dryad_probe("10.5061/dryad.bnzs7h469"),
      "zenodo_texel":zenodo_probe(manifest,output),
      "real_same_birds_have_both_eye_fields_and_behavior":False,
      "actual_cross_bird_geometry_vs_utility_theory_test_valid":False,
      "full_public_gps_or_sensitive_nesting_coordinates_exported":False,
      "source_failure_is_not_negative_hypothesis_test":True,
      "production_models_modified":False,
      "interpretation":"Data provenance and schema audit only; downstream behavioral predictive model requires actual individually matched predictors, outcomes and held-out bird IDs."
    }
    out=output/"source-audit.json"
    assert_source(not out.exists(),"REFUSE_SOURCE_AUDIT_OVERWRITE")
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False,
                              sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
       "stage":"PUBLIC_REAL_GULL_SOURCE_AUDIT_COMPLETED",
       "wiley_status":[r["status"] for r in report["wiley_individual_visual_fields"]],
       "dryad_2019":report["dryad_gaze_2019"],
       "dryad_2020":report["dryad_cue_2020"],
       "zenodo":[{"name":r["name"],"status":r["status"],
                  "columns":r.get("schema_audit",{}).get("columns",[])[:14],
                  "rows":r.get("schema_audit",{}).get("rows_scanned"),
                  "human_annotation_candidates":r.get("schema_audit",{}).get(
                      "top_behavior_values_in_scanned_rows",[])[:14],
                  "unique_individuals":r.get("schema_audit",{}).get(
                      "distinct_individuals_in_scanned_rows")}
                 for r in report["zenodo_texel"]],
       "real_joint_theory_test_possible":False
    },ensure_ascii=False,sort_keys=True))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    run(args.manifest,args.output)


if __name__=="__main__":
    main()
