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
CONTINUITY_WORKFLOW=".github/workflows/essence-v20-ancestry.yml"
ALLOWED_WORKFLOWS=(WORKFLOW,CONTINUITY_WORKFLOW)
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

def pack_run(manifest_path,child_dir,verdict_dir,out,*,run_id,run_sha,depths=None,origin_workflow=WORKFLOW):
    """One immutable archive per real run; HOLD also preserved as evidence."""
    if (type(run_id) is not int or run_id<=0 or not e.SHA.fullmatch(run_sha)
        or origin_workflow not in ALLOWED_WORKFLOWS):
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
            lineage,verdict=load(lineage_path),load(verdict_path)
            depth=(depths or {}).get(cell,0)
            history=lineage.get("cross_run_inheritance")
            if history is not None:
                if (not isinstance(history,dict) or type(history.get("ancestry_depth")) is not int
                    or history["ancestry_depth"]!=depth):
                    raise ValueError("CROSS_RUN_ANCESTRY_DEPTH_MISMATCH")
            elif depth!=0:
                raise ValueError("UNPROVEN_ANCESTRY_DEPTH")
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
        "origin_workflow":origin_workflow,"source_commit":manifest["source_commit"],
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
            or run.get("event") not in ("push","schedule","workflow_dispatch","workflow_run")
            or not any(str(run.get("path","")).endswith(p) for p in ALLOWED_WORKFLOWS)
            or not e.SHA.fullmatch(str(run.get("head_sha","")))):
            continue
        wf=next(p for p in ALLOWED_WORKFLOWS if str(run["path"]).endswith(p))
        filtered.append((rid,art["id"],run["head_sha"],wf))
    return sorted(filtered,reverse=True)

def decode_archive(raw,expected_run,expected_sha,expected_workflow=WORKFLOW):
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
        if (sum(v.file_size for v in z.infolist())>MAX_ZIP_BYTES
            or "index.json" not in entries or len(entries)>13):
            raise ValueError("PARENT_INDEX_MISSING_OR_OVERSIZED")
        index=json.loads(entries["index.json"])
    if (index.get("schema")!=SCHEMA or index.get("source_repository")!=OWNER_REPO
        or index.get("origin_run_id")!=expected_run
        or index.get("origin_main_sha")!=expected_sha
        or expected_workflow not in ALLOWED_WORKFLOWS
        or index.get("origin_workflow")!=expected_workflow
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

def prepare_successor(data_root,source_sha,out,previous_archive=None):
    """Reserve validation/test exclusively after the previous holdout cutoff.

    Previously evaluated public documents may be added to subsequent training,
    but later verification must use newly dated distinct documents. When there
    is no sufficient new cohort, the caller's inherited-parent gate still
    blocks any reuse of the old holdout.
    """
    root=Path(previous_archive) if previous_archive else None
    idx=root/"index.json" if root else None
    if idx is None or not idx.is_file():return e.prepare(data_root,source_sha,out)
    index=load(idx)
    if (index.get("schema")!=SCHEMA or index.get("source_repository")!=OWNER_REPO
        or index.get("receipt_sha256")!=e.seal({k:v for k,v in index.items() if k!="receipt_sha256"})
        or index.get("production_authority") is not False):
        raise ValueError("UNTRUSTED_PREVIOUS_COHORT_ARCHIVE")
    cells=index.get("accepted_cells")
    if not isinstance(cells,list) or not cells:
        return e.prepare(data_root,source_sha,out)
    parents=[load(root/f"cell-{cell}"/"parent.json") for cell in cells]
    if any(m.get("receipt_sha256")!=index.get("parent_meta_sha256",{}).get(str(m.get("cell")))
           or m.get("receipt_sha256")!=e.seal({k:v for k,v in m.items() if k!="receipt_sha256"})
           or m.get("production_authority") is not False for m in parents):
        raise ValueError("PREDECESSOR_METADATA_UNTRUSTED")
    cutoffs={m["last_holdout_date"] for m in parents}
    if len(cutoffs)!=1:raise ValueError("MIXED_PARENT_DATE_CUTOFF")
    cutoff=next(iter(cutoffs))
    if not e.SHA.fullmatch(source_sha):raise ValueError("UNPINNED_NEXT_SOURCE_COMMIT")
    if any(m["source_commit"]==source_sha for m in parents):
        return e.prepare(data_root,source_sha,out)
    groups,desc=e.r.collect(data_root)
    all_rows=sorted((row for group in groups.values() for row in group),
                    key=lambda x:(x["date"],x["identity"]))
    fresh=sorted({row["date"] for row in all_rows if row["date"]>cutoff})
    if len(fresh)<8:return e.prepare(data_root,source_sha,out)
    first=fresh[len(fresh)//2]
    second=fresh[max(len(fresh)//2+1,3*len(fresh)//4)]
    rows={
      "train":[x for x in all_rows if x["date"]<first],
      "validation":[x for x in all_rows if first<=x["date"]<second],
      "holdout":[x for x in all_rows if x["date"]>=second]
    }
    if min(map(len,rows.values()))<12 or max(map(len,rows.values()))>4200:
        return e.prepare(data_root,source_sha,out)
    if (max(x["date"] for x in rows["train"])>=min(x["date"] for x in rows["validation"])
        or max(x["date"] for x in rows["validation"])>=min(x["date"] for x in rows["holdout"])
        or min(x["date"] for x in rows["validation"])<=cutoff
        or min(x["date"] for x in rows["holdout"])<=cutoff):
        raise ValueError("FUTURE_ONLY_COHORT_LEAKAGE")
    sets=[{x["identity"] for x in group} for group in rows.values()]
    if len(set.union(*sets))!=sum(map(len,sets)):
        raise ValueError("FUTURE_COHORT_IDENTITY_DUPLICATE")
    packets={k:e.split_packet(k,v,source_sha,desc["dataset_sha256"]) for k,v in rows.items()}
    result={
      "schema":e.SCHEMA,"source_commit":source_sha,
      "dataset_sha256":desc["dataset_sha256"],
      "split_sha256":{k:p["packet_sha256"] for k,p in packets.items()},
      "split_sizes":{k:len(p["rows"]) for k,p in packets.items()},
      "train_label_counts":[sum(x["label"]==i for x in rows["train"]) for i in range(len(e.r.LABELS))],
      "split_dates":{k:[min(x["date"] for x in v),max(x["date"] for x in v)] for k,v in rows.items()},
      "cohort_protocol":"FUTURE_ONLY_AFTER_PREVIOUS_HOLDOUT",
      "previous_last_holdout_date":cutoff,"new_distinct_dates":len(fresh),
      "test_data_in_training_artifact":False,"external_custodian":False,
      "training_task":"PUBLIC_META_REGISTRY_KEY_CLASSIFICATION","production_authority":False
    }
    result["receipt_sha256"]=e.seal(result)
    for k,p in packets.items():
        e.check_packet(p,k,source_sha,desc["dataset_sha256"])
        e.atomic_json(Path(out)/f"{k}.json",p)
    e.atomic_json(Path(out)/"manifest.json",result)
    return result

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

def fetch_trusted_research_ancestors(out,*,token,current_run,opener=urllib.request.urlopen):
    """Read-only, bounded latest eligible artifact. Never use a PR or fork run."""
    if not token or type(current_run) is not int or current_run<=0:
        raise ValueError("GITHUB_READ_ONLY_CREDENTIALS_REQUIRED")
    root=Path(out)
    if root.exists():raise FileExistsError("ANCESTOR_ARCHIVE_ALREADY_EXISTS")
    api="https://api.github.com/repos/"+OWNER_REPO
    arts=[]
    for page in (1,2,3):
        obj=_fetch_json(api+f"/actions/artifacts?per_page=100&page={page}",token,opener)
        batch=obj.get("artifacts") if isinstance(obj,dict) else None
        if not isinstance(batch,list):raise ValueError("GITHUB_ARTIFACT_DISCOVERY_FAILED")
        arts.extend(batch)
        if len(batch)<100:break
    candidates=[]
    for art in arts:
        match=ARCHIVE_RE.fullmatch(art.get("name",""))
        if match and int(match.group(1))<current_run and art.get("expired") is False:
            candidates.append(art)
    candidates.sort(key=lambda art:int(ARCHIVE_RE.fullmatch(art["name"]).group(1)),reverse=True)
    if len(candidates)>25:
        candidates=candidates[:25]
    runs={}
    for art in candidates:
        rid=int(ARCHIVE_RE.fullmatch(art["name"]).group(1))
        if rid not in runs:
            runs[rid]=_fetch_json(api+f"/actions/runs/{rid}",token,opener)
    possible=select_archive(candidates,runs,current_run)
    outcomes=[]
    for rid,artifact_id,head_sha,expected_workflow in possible:
        url=api+f"/actions/artifacts/{artifact_id}/zip"
        req=urllib.request.Request(url,headers={
            "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JANUS-ESSENCE-v20"})
        try:
            with opener(req,timeout=25) as response:
                raw=response.read(MAX_ZIP_BYTES+1)
            idx,files=decode_archive(raw,rid,head_sha,expected_workflow)
            if not idx["accepted_cells"]:
                outcomes.append({"run":rid,"reason":"NO_ELIGIBLE_RESEARCH_PARENT"})
                continue
        except (OSError,RuntimeError,ValueError,zipfile.BadZipFile) as ex:
            outcomes.append({"run":rid,"reason":type(ex).__name__})
            continue
        for name,data in files.items():
            write(root/name,data)
        status={"schema":SCHEMA,"status":"VERIFIED_PAST_MAIN_RESEARCH_PARENTS",
                "source_artifact_id":artifact_id,"source_run_id":rid,
                "parent_cells":idx["accepted_cells"],"production_authority":False,
                "candidates_not_yet_prospectively_revalidated":True}
        e.atomic_json(root/"fetch_receipt.json",status)
        return status
    status={"schema":SCHEMA,"status":"HOLD_NO_QUALIFIED_CROSS_RUN_PARENT",
            "checked_archives":len(candidates),
            "trusted_run_candidates":len(possible),
            "reasons":outcomes[:25],
            "parent_cells":[],"production_authority":False}
    e.atomic_json(root/"fetch_receipt.json",status)
    return status

def verified_parent_for_cell(folder,cell,current_manifest):
    """Load one exact SHA-bound parent for continuing genuine gradients."""
    root=Path(folder)
    idx=load(root/"index.json")
    if (idx.get("schema")!=SCHEMA or idx.get("source_repository")!=OWNER_REPO
        or idx.get("production_authority") is not False
        or idx.get("receipt_sha256")!=e.seal({k:v for k,v in idx.items() if k!="receipt_sha256"})
        or type(cell) is not int or cell not in idx.get("accepted_cells",[])):
        raise ValueError("PARENT_NOT_SELECTED_FROM_TRUSTED_RUN")
    meta=load(root/f"cell-{cell}"/"parent.json")
    valid_for_new_history(meta,current_manifest)
    if meta["receipt_sha256"]!=idx.get("parent_meta_sha256",{}).get(str(cell)):
        raise ValueError("PARENT_INDEX_IDENTITY_BROKEN")
    p=root/f"cell-{cell}"/"parent.pt"
    if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_WEIGHT_BYTES:
        raise ValueError("PARENT_FILE_PRECHECK_FAILED")
    raw=p.read_bytes()
    if digest(raw)!=meta.get("offspring_checkpoint_sha256"):
        raise ValueError("PARENT_FILE_HASH_MISMATCH")
    bundle=torch.load(io.BytesIO(raw),map_location="cpu",weights_only=True)
    if (not isinstance(bundle,dict) or bundle.get("schema")!=e.LINEAGE
        or bundle.get("cell")!=cell or bundle.get("source_commit")!=meta["source_commit"]
        or bundle.get("production_authority") is not False):
        raise ValueError("PARENT_PRETRAINED_MODEL_UNTRUSTED")
    model=e.r.model_for(cell)
    ref=model.state_dict()
    state=bundle.get("final_state")
    if (not isinstance(state,dict) or set(state)!=set(ref)
        or any(not isinstance(state[k],torch.Tensor) or state[k].shape!=ref[k].shape
               or not bool(torch.isfinite(state[k]).all()) for k in ref)
        or e.stable_state(state)!=meta["parent_weight_sha256"]):
        raise ValueError("PARENT_WEIGHTS_DO_NOT_MATCH_LINEAGE")
    model.load_state_dict(state,strict=True)
    return e.clone_state(model),meta

def cli():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("pack")
    for key in ("manifest","children","verdicts","out","run-sha"):a.add_argument("--"+key,required=True)
    a.add_argument("--run-id",type=int,required=True)
    a.add_argument("--origin-workflow",choices=ALLOWED_WORKFLOWS,default=WORKFLOW)
    a.add_argument("--previous-archive")
    b=sub.add_parser("check")
    b.add_argument("--parent",required=True);b.add_argument("--current-manifest",required=True)
    c=sub.add_parser("fetch")
    c.add_argument("--out",required=True)
    c.add_argument("--run-id",type=int,required=True)
    prep=sub.add_parser("prepare-next")
    for opt in ("data-root","source","previous-archive","out"):prep.add_argument("--"+opt,required=True)
    d=sub.add_parser("continue")
    for arg in ("archive","manifest","train","validation","out"):
        d.add_argument("--"+arg,required=True)
    d.add_argument("--cell",type=int,required=True)
    d.add_argument("--steps",type=int,default=40)
    opts=p.parse_args()
    if opts.mode=="pack":
        depths=None
        if opts.previous_archive:
            prev=Path(opts.previous_archive)
            index=load(prev/"index.json") if (prev/"index.json").is_file() else None
            if index is not None:
                depths={}
                for cell in index.get("accepted_cells",[]):
                    m=load(prev/f"cell-{cell}"/"parent.json")
                    depths[cell]=m["ancestry_depth"]+1
        obj=pack_run(opts.manifest,opts.children,opts.verdicts,opts.out,
                     run_id=opts.run_id,run_sha=opts.run_sha,
                     depths=depths,origin_workflow=opts.origin_workflow)
        print(json.dumps({"status":obj["status"],"accepted":obj["accepted_cells"],
                          "rejected":len(obj["rejected_cells"]),"production_authority":False}))
    elif opts.mode=="check":
        valid_for_new_history(load(opts.parent),load(opts.current_manifest))
        print(json.dumps({"status":"RESEARCH_PARENT_NEW_SOURCE_ELIGIBLE",
                          "production_authority":False}))
    elif opts.mode=="fetch":
        obj=fetch_trusted_research_ancestors(opts.out,token=os.environ.get("GH_TOKEN",""),
                                              current_run=opts.run_id)
        print(json.dumps({"status":obj["status"],"parent_cells":obj["parent_cells"],
                          "production_authority":False}))
    elif opts.mode=="prepare-next":
        obj=prepare_successor(opts.data_root,opts.source,opts.out,opts.previous_archive)
        print(json.dumps({"status":obj.get("cohort_protocol","BASELINE_HOLD_FUTURE_COHORT_UNAVAILABLE"),
                          "new_dates":obj.get("new_distinct_dates",0),
                          "production_authority":False}))
    else:
        manifest=load(opts.manifest)
        inherited,meta=verified_parent_for_cell(opts.archive,opts.cell,manifest)
        result=e.train(opts.cell,load(opts.train),load(opts.validation),
                       manifest,opts.out,steps=opts.steps,
                       inherited_state=inherited,inherited_metadata=meta)
        if (result["cross_run_inheritance"]["parent_weights_sha256"]
            !=result["initial_weights_sha256"]):
            raise ValueError("INHERITED_WEIGHT_CHAIN_MISMATCH")
        print(json.dumps({"cell":opts.cell,"status":"TWO_GENERATION_CONTINUATION_FROM_PAST_MAIN_RUN",
                          "generation_depth":result["cross_run_inheritance"]["ancestry_depth"],
                          "accepted_generations":result["accepted_generations"],
                          "production_authority":False}))

if __name__=="__main__":cli()
