#!/usr/bin/env python3
"""ESSENCE v2.0 — immutable, cross-run research weight ancestry with anti-replay.

Pack ONLY historically independently CI-evaluated, class-diverse research
descendants. Download a matching archive from an older successful MAIN run
through read-only GitHub Actions API. Inheritance needs new dated observations
after the prior holdout; no CI test means external independent certification.
Never writes model service, production weights or repositories.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request
import zipfile

import torch
from tools import essence_v19_gradirnya as e

SCHEMA="janus.essence.cross_run_research_ancestry/2.0"
PARENT_SCHEMA="janus.essence.research_parent/2.0"
OWNER_REPO="Hawkar-usls/Janus-Demiurge"
WORKFLOW=".github/workflows/essence-v19-gradirnya.yml"
ARCHIVE_RE=re.compile(r"^essence-v20-reviewed-archive-([1-9][0-9]{0,12})$")
MAX_ANCESTOR_DEPTH=12
MAX_ZIP_BYTES=25_000_000
MAX_WEIGHT_BYTES=12_000_000

def load(p):
    return e.read_json(p)

def digest(data): return hashlib.sha256(data).hexdigest()

def write(path,data):
    path=Path(path)
    if path.exists():raise FileExistsError("IMMUTABLE_ANCESTRY_ARTIFACT")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)

def validate_verified_parent(manifest,lineage,verdict,weights,cell,*,depth=0):
    """One file and one independent CI verdict. Reject every synthetic PASS."""
    if type(cell) is not int or not 0<=cell<6:
        raise ValueError("UNTRUSTED_PARENT_CELL")
    if type(depth) is not int or not 0<=depth<MAX_ANCESTOR_DEPTH:
        raise ValueError("ANCESTRY_DEPTH_EXHAUSTED")
    src=manifest.get("source_commit") if isinstance(manifest,dict) else None
    e.validate_manifest(manifest,src)
    if (not isinstance(lineage,dict) or not isinstance(verdict,dict)
        or lineage.get("schema")!=e.LINEAGE
        or lineage.get("cell")!=cell
        or lineage.get("role")!=e.r.CELL_ROLES[cell]
        or lineage.get("source_commit")!=src
        or lineage.get("manifest_sha256")!=manifest["receipt_sha256"]
        or lineage.get("holdout_sha256")!=manifest["split_sha256"]["holdout"]
        or lineage.get("receipt_sha256")!=e.seal({k:v for k,v in lineage.items()
                                                  if k!="receipt_sha256"})
        or lineage.get("production_authority") is not False
        or lineage.get("training_saw_holdout") is not False
        or lineage.get("release_permission") is not False
        or type(lineage.get("accepted_generations")) is not int
        or not 1<=lineage["accepted_generations"]<=2):
        raise ValueError("UNTRUSTED_PARENT_LINEAGE")
    if (verdict.get("schema")!="janus.essence.gradirnya_verifier/1.9"
        or verdict.get("cell")!=cell
        or verdict.get("source_commit")!=src
        or verdict.get("lineage_sha256")!=lineage["receipt_sha256"]
        or verdict.get("holdout_sha256")!=lineage["holdout_sha256"]
        or verdict.get("receipt_sha256")!=e.seal({k:v for k,v in verdict.items()
                                                  if k!="receipt_sha256"})
        or verdict.get("gate")!="RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN"
        or verdict.get("diversity_gate") is not True
        or verdict.get("heldout_represented_classes",0)<3
        or not 0<=verdict.get("heldout_majority_fraction",2)<=0.85
        or verdict.get("nll_gain_vs_prior",-1)<0.02
        or verdict.get("accuracy_gain_vs_prior",0)<=0
        or verdict.get("research_artifact_only") is not True
        or verdict.get("externally_custodied_test") is not False
        or verdict.get("automatic_production_promotion") is not False
        or verdict.get("heldout_rows",0)<12):
        raise ValueError("NO_INDEPENDENT_RESEARCH_HOLDOUT_GAIN")
    if (not isinstance(weights,(bytes,bytearray))
        or not 0<len(weights)<=MAX_WEIGHT_BYTES
        or digest(weights)!=lineage.get("offspring_file_sha256")):
        raise ValueError("PARENT_WEIGHTS_SHA_MISMATCH")
    # Data-only loading with bounded allocation (weights_only=True) and strict
    # model-key/shape constraints. No foreign executable code is imported.
    pack=torch.load(io.BytesIO(weights),map_location="cpu",weights_only=True)
    if (not isinstance(pack,dict) or pack.get("schema")!=e.LINEAGE
        or pack.get("production_authority") is not False
        or pack.get("cell")!=cell or pack.get("source_commit")!=src):
        raise ValueError("PARENT_WEIGHT_HEADER_MISMATCH")
    initial,final=pack.get("initial_state"),pack.get("final_state")
    model=e.r.model_for(cell)
    ref=model.state_dict()
    if (not isinstance(initial,dict) or not isinstance(final,dict)
        or set(initial)!=set(ref) or set(final)!=set(ref)
        or sum(x.numel() for x in final.values())>1_000_000
        or any(not isinstance(initial[k],torch.Tensor)
               or not isinstance(final[k],torch.Tensor)
               or initial[k].shape!=ref[k].shape or final[k].shape!=ref[k].shape
               or not bool(torch.isfinite(initial[k]).all())
               or not bool(torch.isfinite(final[k]).all()) for k in ref)
        or e.stable_state(initial)!=lineage["initial_weights_sha256"]
        or e.stable_state(final)!=lineage["final_weights_sha256"]):
        raise ValueError("PARENT_TENSOR_LINEAGE_MISMATCH")
    meta={
        "schema":PARENT_SCHEMA,"repository":OWNER_REPO,
        "cell":cell,"role":e.r.CELL_ROLES[cell],"ancestry_depth":depth,
        "source_commit":src,
        "source_dataset_sha256":manifest["dataset_sha256"],
        "last_holdout_date":manifest["split_dates"]["holdout"][1],
        "last_holdout_sha256":lineage["holdout_sha256"],
        "last_verifier_sha256":verdict["receipt_sha256"],
        "last_lineage_sha256":lineage["receipt_sha256"],
        "parent_weight_sha256":lineage["final_weights_sha256"],
        "offspring_checkpoint_sha256":digest(weights),
        "research_only":True,"production_authority":False
    }
    meta["receipt_sha256"]=e.seal(meta)
    return meta

def pack_run(manifest_path,child_dir,verdict_dir,out,*,run_id,run_sha,depths=None):
    """One immutable archive per real run; HOLD also preserved as evidence."""
    if type(run_id) is not int or run_id<=0 or not e.SHA.fullmatch(run_sha):
        raise ValueError("INVALID_PARENT_SOURCE_RUN")
    manifest=load(manifest_path)
    e.validate_manifest(manifest,manifest.get("source_commit"))
    root=Path(out)
    if root.exists():raise FileExistsError("RESEARCH_ARCHIVE_ALREADY_EXISTS")
    accepted=[];rejected=[]
    records=[]
    for cell in range(6):
        lineage_path=Path(child_dir)/f"cell-{cell}"/"lineage.json"
        offspring_path=Path(child_dir)/f"cell-{cell}"/"offspring.pt"
        verdict_path=Path(verdict_dir)/f"cell-{cell}.json"
        if not lineage_path.is_file() or not offspring_path.is_file() or not verdict_path.is_file():
            rejected.append({"cell":cell,"reason":"MISSING_CELL_EVIDENCE"})
            continue
        try:
            depth=(depths or {}).get(cell,0)
            lineage,verdict=load(lineage_path),load(verdict_path)
            weights=offspring_path.read_bytes()
            meta=validate_verified_parent(manifest,lineage,verdict,weights,cell,depth=depth)
        except (OSError,RuntimeError,ValueError,KeyError,TypeError) as error:
            rejected.append({"cell":cell,"reason":str(error)[:100]})
            continue
        write(root/f"cell-{cell}"/"parent.pt",weights)
        e.atomic_json(root/f"cell-{cell}"/"parent.json",meta)
        accepted.append(cell);records.append(meta)
    status="RESEARCH_PARENTS_STAGED" if accepted else "HOLD_NO_ADMISSIBLE_PARENT"
    index={
        "schema":SCHEMA,"source_repository":OWNER_REPO,
        "origin_run_id":run_id,"origin_main_sha":run_sha,
        "origin_workflow":WORKFLOW,"source_commit":manifest["source_commit"],
        "source_dataset_sha256":manifest["dataset_sha256"],
        "accepted_cells":accepted,"rejected_cells":rejected,
        "parent_meta_sha256":{str(m["cell"]):m["receipt_sha256"] for m in records},
        "status":status,"external_blind_quality_proven":False,
        "target_device_proven":False,"real_service_rollback_proven":False,
        "production_authority":False,"automatic_promotion":False
    }
    index["receipt_sha256"]=e.seal(index)
    e.atomic_json(root/"index.json",index)
    return index

def _fetch_json(url,token,opener):
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JANUS-ESSENCE-v20"})
    with opener(req,timeout=20) as r:
        raw=r.read(MAX_ZIP_BYTES+1)
    if len(raw)>MAX_ZIP_BYTES:raise ValueError("PARENT_API_TOO_LARGE")
    return json.loads(raw)

def select_archive(api_artifacts,run_details,current_run,*,repository=OWNER_REPO):
    """Only immutable artifacts of completed successful MAIN self-workflow."""
    if repository!=OWNER_REPO:raise ValueError("FOREIGN_PARENT_REPOSITORY_DENIED")
    filtered=[]
    for art in api_artifacts:
        match=ARCHIVE_RE.fullmatch(art.get("name",""))
        if not match or art.get("expired") is not False:continue
        rid=int(match.group(1))
        ref=art.get("workflow_run")
        if (rid>=current_run or type(art.get("id")) is not int
            or not isinstance(ref,dict) or ref.get("id")!=rid):continue
        run=run_details.get(rid)
        if (not isinstance(run,dict) or run.get("status")!="completed"
            or run.get("conclusion")!="success"
            or run.get("head_branch")!="main"
            or run.get("event") not in ("push","schedule","workflow_dispatch")
            or not str(run.get("path","")).endswith(WORKFLOW)
            or not e.SHA.fullmatch(str(run.get("head_sha","")))):
            continue
        filtered.append((rid,art["id"],run["head_sha"]))
    return sorted(filtered,reverse=True)

def decode_archive(raw,expected_run,expected_sha):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_ZIP_BYTES:
        raise ValueError("UNTRUSTED_PARENT_ZIP")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries={}
        for member in z.infolist():
            if (member.is_dir() or member.file_size>MAX_WEIGHT_BYTES
                or member.compress_size>MAX_WEIGHT_BYTES
                or member.filename in entries
                or not re.fullmatch(r"index\.json|cell-[0-5]/parent\.(json|pt)",member.filename)
                or (member.external_attr>>16)&0o170000 == 0o120000):
                raise ValueError("UNSAFE_PARENT_ARCHIVE_STRUCTURE")
            entries[member.filename]=z.read(member)
        if "index.json" not in entries or len(entries)>13:
            raise ValueError("PARENT_INDEX_MISSING")
        index=json.loads(entries["index.json"])
    if (index.get("schema")!=SCHEMA or index.get("source_repository")!=OWNER_REPO
        or index.get("origin_run_id")!=expected_run
        or index.get("origin_main_sha")!=expected_sha
        or index.get("origin_workflow")!=WORKFLOW
        or index.get("receipt_sha256")!=e.seal({k:v for k,v in index.items() if k!="receipt_sha256"})
        or index.get("production_authority") is not False
        or index.get("automatic_promotion") is not False
        or index.get("external_blind_quality_proven") is not False):
        raise ValueError("UNTRUSTED_PARENT_INDEX")
    allowed=index.get("accepted_cells",[])
    if (not isinstance(allowed,list) or len(allowed)!=len(set(allowed))
        or any(type(k) is not int or not 0<=k<6 for k in allowed)):
        raise ValueError("UNTRUSTED_PARENT_CELL_LIST")
    expected={"index.json"}|{f"cell-{k}/parent.{ext}" for k in allowed for ext in ("json","pt")}
    if set(entries)!=expected:
        raise ValueError("INCOMPLETE_OR_EXTRA_ARCHIVE_FILES")
    for k in allowed:
        metadata=json.loads(entries[f"cell-{k}/parent.json"])
        if (metadata.get("schema")!=PARENT_SCHEMA
            or metadata.get("cell")!=k
            or metadata.get("research_only") is not True
            or metadata.get("production_authority") is not False
            or metadata.get("receipt_sha256")!=index.get("parent_meta_sha256",{}).get(str(k))
            or metadata.get("receipt_sha256")!=e.seal({a:b for a,b in metadata.items() if a!="receipt_sha256"})
            or digest(entries[f"cell-{k}/parent.pt"])!=metadata.get("offspring_checkpoint_sha256")):
            raise ValueError("PARENT_CHECKPOINT_ATTESTATION_MISMATCH")
    return index,entries

def valid_for_new_history(metadata,current_manifest):
    """Hard temporal anti-replay gate before any descendant is trained."""
    e.validate_manifest(current_manifest,current_manifest.get("source_commit"))
    if (not isinstance(metadata,dict)
        or metadata.get("schema")!=PARENT_SCHEMA
        or metadata.get("repository")!=OWNER_REPO
        or metadata.get("research_only") is not True
        or metadata.get("production_authority") is not False
        or metadata.get("receipt_sha256")!=e.seal({k:v for k,v in metadata.items() if k!="receipt_sha256"})):
        raise ValueError("UNTRUSTED_RESEARCH_PARENT")
    if (metadata.get("source_commit")==current_manifest["source_commit"]
        or metadata.get("source_dataset_sha256")==current_manifest["dataset_sha256"]):
        raise ValueError("NO_NEW_INDEPENDENT_SOURCE_SNAPSHOT")
    if not current_manifest["split_dates"]["holdout"][0]>metadata.get("last_holdout_date","9999-99-99"):
        raise ValueError("FUTURE_ONLY_EVALUATION_REQUIRED")
    if (type(metadata.get("ancestry_depth")) is not int
        or not 0<=metadata["ancestry_depth"]<MAX_ANCESTOR_DEPTH):
        raise ValueError("MAX_ANCESTRY_DEPTH_REACHED")
    return True

def cli():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("pack")
    for key in ("manifest","children","verdicts","out","run-sha"):a.add_argument("--"+key,required=True)
    a.add_argument("--run-id",type=int,required=True)
    b=sub.add_parser("check")
    b.add_argument("--parent",required=True);b.add_argument("--current-manifest",required=True)
    opts=p.parse_args()
    if opts.mode=="pack":
        obj=pack_run(opts.manifest,opts.children,opts.verdicts,opts.out,
                     run_id=opts.run_id,run_sha=opts.run_sha)
        print(json.dumps({"status":obj["status"],"accepted":obj["accepted_cells"],
                          "rejected":len(obj["rejected_cells"]),"production_authority":False}))
    else:
        valid_for_new_history(load(opts.parent),load(opts.current_manifest))
        print(json.dumps({"status":"RESEARCH_PARENT_NEW_SOURCE_ELIGIBLE",
                          "production_authority":False}))

if __name__=="__main__":cli()
