#!/usr/bin/env python3
"""JANUS NIST-010H: inspect ORIGINAL NIST processed HDF5 metadata.

Source: NIST 2015 published HDF5, created by authors' pipeline.
This is not independent time calibration: author processing may have aligned
PPS epochs, applied timing adjustments, and used predeclared or observed
data. We identify the *metadata fields* and provenance; do not claim they
are externally calibrated or causally certified. Read-only, bandwidth-capped.
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
import h5py
import numpy as np

BASE="https://s3.amazonaws.com/nist-belltestdata/belldata/processed_compressed/hdf5/2015_09_18/"
DATASETS={
 "training": {
  "file":"03_31_CH_pockel_100kHz.run4.afterTimingfix2_training.dat.compressed.build.hdf5",
  "kind":"TRAINING_BAD_MODELOCK_NOT_VALID_FOR_BELL_OUTCOME",
  "download_cap_bytes":145_000_000
 },
 "corrected": {
  "file":"03_43_CH_pockel_100kHz.run4.afterTimingfix2_afterfixingModeLocking.dat.compressed.build.hdf5",
  "kind":"POST_TIMING_FIX_WITH_LATE_FRIDGE_WARMING",
  "download_cap_bytes":870_000_000
 }
}
MAX_NODES=800
MAX_DEPTH=5
MAX_ATTRS_PER_NODE=60
MAX_PREVIEW_ELEMENTS=32
KEYWORDS=re.compile(r"gps|sync|skip|offset|shift|align|delay|tim|clock|misalign|start|epoch|anom|window|radius|config|path",re.I)
DOCUMENTATION="https://s3.amazonaws.com/nist-belltestdata/belldata/File_Folder_Descriptions.pdf"
PROCESSING_DOC="https://s3.amazonaws.com/nist-belltestdata/belldata/code/analysis/DataProcessingDescription.pdf"


def safe_scalar(value):
    if isinstance(value,(np.integer,int)):return int(value)
    if isinstance(value,(np.floating,float)):
        val=float(value)
        if not np.isfinite(val):return repr(val)
        return val
    if isinstance(value,(np.bool_,bool)):return bool(value)
    if isinstance(value,(np.bytes_,bytes)):return bytes(value)[:1000].decode("utf-8","replace")
    if isinstance(value,str):return value[:1000]
    return repr(value)[:300]


def preview(obj):
    a=np.asarray(obj)
    if a.size>MAX_PREVIEW_ELEMENTS:
        return {"shape":list(a.shape),"dtype":str(a.dtype),"value_not_loaded":True}
    if a.ndim==0:return safe_scalar(a.item())
    return [safe_scalar(x) for x in a.flat]


def download(selected,path):
    spec=DATASETS[selected]
    uri=BASE+spec["file"]
    req=urllib.request.Request(uri,headers={"User-Agent":"JANUS-010H NIST public archival provenance"})
    h=hashlib.sha256();total=0
    with urllib.request.urlopen(req,timeout=180) as source,path.open("xb") as dest:
        ctype=source.headers.get("Content-Length")
        if ctype and int(ctype)>spec["download_cap_bytes"]:raise ValueError("DECLARED_HDF5_TOO_BIG")
        while True:
            buf=source.read(4*1024*1024)
            if not buf:break
            total+=len(buf)
            if total>spec["download_cap_bytes"]:raise ValueError("HDF5_EXCEEDS_DOWNLOAD_CAP")
            h.update(buf);dest.write(buf)
        dest.flush();os.fsync(dest.fileno())
    return uri,total,h.hexdigest()


def collect_metadata(filename):
    """Metadata, not outcomes: never read large datasets or select trials."""
    results=[]
    hits=[]
    total_objects=0
    truncated=False
    with h5py.File(filename,"r") as f:
        def walk(obj,path,depth):
            nonlocal total_objects,truncated
            if total_objects>=MAX_NODES or depth>MAX_DEPTH:
                truncated=True
                return
            total_objects+=1
            is_group=isinstance(obj,h5py.Group)
            item={"path":path,"kind":"group" if is_group else "dataset"}
            if is_group:
                item["children_count"]=len(obj)
            else:
                item["shape"]=list(obj.shape)
                item["dtype"]=str(obj.dtype)
                item["storage_bytes"]=obj.id.get_storage_size()
            attrs={}
            for i,name in enumerate(obj.attrs.keys()):
                if i>=MAX_ATTRS_PER_NODE:
                    item["attributes_truncated"]=True;break
                val=obj.attrs[name]
                attrs[name]=preview(val)
            if attrs:item["attributes"]=attrs
            if KEYWORDS.search(path):
                item["clock_field_candidate"]=True
                if not is_group and obj.size<=MAX_PREVIEW_ELEMENTS:
                    try:item["small_dataset_value"]=preview(obj[()])
                    except Exception as exc:item["small_dataset_read_error"]=type(exc).__name__
                hits.append(item)
            else:
                results.append(item)
            if is_group:
                for name in list(obj.keys()):
                    if total_objects>=MAX_NODES:
                        truncated=True;break
                    try:
                        child=obj.get(name)
                    except Exception:
                        truncated=True;continue
                    if child is None:continue
                    walk(child,path.rstrip("/")+"/"+name,depth+1)
        walk(f,"/",0)
    return {
      "total_objects_inspected":total_objects,
      "depth_limit":MAX_DEPTH,"object_limit":MAX_NODES,
      "metadata_truncated":truncated,
      "clock_or_sync_named_fields":hits,
      "other_metadata_fields":results[:150],
      "other_metadata_fields_truncated_to_first_150":len(results)>150,
      "candidate_fields_are_not_a_verified_clock_alignment":True,
      "values_stored_in_authors_HDF5_are_not_independent_measurements_by_JANUS":True
    }


def run(selected,output):
    spec=DATASETS[selected]
    with tempfile.TemporaryDirectory(prefix="janus-nist-010h-") as d:
        local=Path(d)/spec["file"]
        uri,nbytes,sha=download(selected,local)
        with local.open("rb") as f:magic=f.read(8)
        if magic!=b"\x89HDF\r\n\x1a\n":raise ValueError("NOT_HDF5_SIGNATURE")
        print("NIST_010H_DOWNLOAD "+json.dumps({"selection":selected,
                  "nbytes":nbytes,"source_sha256":sha},sort_keys=True),flush=True)
        meta=collect_metadata(local)
    rec={
      "schema":"janus.nist010h.processed_hdf5_clock_metadata.v1",
      "original_NIST_hdf5_url":uri,"source_nbytes":nbytes,
      "source_sha256":sha,"selection":selected,
      "selection_warning":spec["kind"],
      "original_NIST_source_documentation":DOCUMENTATION,
      "original_NIST_processing_description":PROCESSING_DOC,
      "kind":"RETROSPECTIVE_AUTHOR_PROCESSED_METADATA_INSPECTION_ONLY",
      "physical_new_measurements_performed":False,
      "raw_photon_pair_data_used_to_fit_clock":False,
      "clock_offset_independently_verified":False,
      "clock_UTC_second_index_certified":False,
      "retrocausality_proven":False,
      "metadata":meta
    }
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf8") as h:
        json.dump(rec,h,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
        h.write("\n");h.flush();os.fsync(h.fileno())
    print("NIST_010H_RESULT "+json.dumps({
      "selection":selected,"fields_total":meta["total_objects_inspected"],
      "candidate_clock_fields":len(meta["clock_or_sync_named_fields"]),
      "paths":[x["path"] for x in meta["clock_or_sync_named_fields"]][:90],
      "metadata_truncated":meta["metadata_truncated"],
      "original_source_sha256":sha,"absolute_alignment_verified":False
      },sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",choices=list(DATASETS),default="training")
    p.add_argument("--output",required=True)
    a=p.parse_args();run(a.source,a.output)
