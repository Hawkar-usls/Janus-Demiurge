#!/usr/bin/env python3
"""ESSENCE v4.1: first NEW frozen external-source paired exam of G4 Physarum.

Exam only; previously trained Physarum and control float32 checkpoints frozen
under v4.0 run 43650540561. Uses new source repositories NOT in the G3 exam.
No model update, no reused G3 holdout, and no external-replicator claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

from tools import essence_v38_inheritance as origin
from tools import essence_v37_codex_gpt as core
from tools import essence_v40_physarum_bridge as physarum
from tools import essence_v36_juxtapose_exact as exact

LOCK_SCHEMA="janus.essence.physarum_new_external_pair_lock/4.1"
EXAM_SCHEMA="janus.essence.physarum_new_external_pair_exam/4.1"
LOCK_PATH="research/essence/physarum_v41/locked_external_sources.json"
G4_RUN=43650540561
G4_COMMIT="70961a9c2faaa95fc7f9ff0c0f1d024a5b215b07"
G4_MANIFESTS={
    "control":"563bcf05a97c67f5723c4f5414bf7621197105eae654a8133a439c91fe4575f0",
    "physarum":"a8397385b2703d5cca7b15b9b12626960d8105e976f10b628451fe330dbcf003",
}
G4_WEIGHTS={
    "control":"a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b",
    "physarum":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f"
}
G3_OLD_SOURCE_PROJECTS={"psf/requests","pallets/click"}
NEW_SOURCE_PROJECTS=("encode/httpx","python-attrs/attrs")
HEX40=re.compile(r"^[0-9a-f]{40}$")
MIN_MEAN_GAIN=0.0001
MAX_FAMILY_REGRESSION=0.0001


def require(ok, code):
    if not ok:
        raise ValueError(code)


def seal(d):
    return origin.sealed(d)


def load_lock(path):
    d=origin.read_json(path)
    require(d.get("schema")==LOCK_SCHEMA and
            d.get("g4_source_run")==G4_RUN and
            d.get("g4_source_commit")==G4_COMMIT and
            d.get("manifests_sha256")==G4_MANIFESTS and
            d.get("weights_sha256")==G4_WEIGHTS and
            d.get("g3_sha256")==physarum.G3_WEIGHTS_SHA256 and
            d.get("frozen_after_g4_weights_sealed") is True and
            d.get("read_external_content_before_freeze") is False and
            d.get("not_external_scientific_replication") is True and
            d.get("production_authority") is False, "EXTERNAL_G4_LOCK_INVALID")
    require(d.get("exam_contract")=={
        "metric":"EQUAL_FILE_WEIGHT_MEAN_NEXT_BYTE_CROSS_ENTROPY",
        "minimum_mean_loss_decrease":MIN_MEAN_GAIN,
        "max_per_source_family_regression":MAX_FAMILY_REGRESSION,
        "no_reselection_after_first_exam":True,
        "negative_result_is_valid":True}, "POST_HOC_G4_METRIC_DRIFT")
    entries=d.get("sources")
    require(isinstance(entries,list) and len(entries)==4 and
            [v.get("repo") if isinstance(v,dict) else None for v in entries]
            ==["encode/httpx","encode/httpx","python-attrs/attrs",
               "python-attrs/attrs"],"INVALID_G4_EXTERNAL_SOURCES")
    known=set()
    for x in entries:
        require(isinstance(x,dict) and
                set(x)=={"repo","commit","path","git_blob_sha1","license"} and
                bool(HEX40.fullmatch(x["commit"])) and
                bool(HEX40.fullmatch(x["git_blob_sha1"])) and
                x["license"] in ("BSD-3-Clause","MIT") and
                x["path"].endswith(".py") and
                ".." not in x["path"].split("/") and
                x["path"].startswith(("httpx/","src/attr/")) and
                (x["repo"],x["path"]) not in known,
                "UNTRUSTED_G4_EXTERNAL_BLOB")
        known.add((x["repo"],x["path"]))
    return d


def verify_checkpoints(freeze_path, control_dir, physarum_dir, torch):
    freeze=origin.check_freeze(origin.read_json(freeze_path))
    require(freeze["receipt_sha256"]=="d1633f6c6172c46014a675b4cccf7c72a466ad959d4aa844120e73f3bc31cd56",
            "SOURCE_FREEZE_CHANGED")
    models={}
    for name,p in (("control",control_dir),("physarum",physarum_dir)):
        model,m=origin.load_checkpoint(p,torch,freeze)
        require(m["generation"]=="g4_"+name and
                m["manifest_sha256"]==G4_MANIFESTS[name] and
                m["weights_sha256"]==G4_WEIGHTS[name] and
                m["inherited_initial_weights_sha256"]==
                physarum.G3_WEIGHTS_SHA256 and
                m["parent_manifest_sha256"]==physarum.G3_MANIFEST_SHA256 and
                m["trained_steps"]==physarum.SIBLING_STEPS and
                m["production_authority"] is False,
                "G4_AUTHENTIC_SIBLING_NOT_FOUND")
        models[name]=model
    return freeze,models


def fetch_pinned(item):
    require(item["repo"] in NEW_SOURCE_PROJECTS,
            "UNTRUSTED_UPSTREAM_REPOSITORY")
    url=("https://raw.githubusercontent.com/"+item["repo"]+"/"+
         item["commit"]+"/"+item["path"])
    req=Request(url,headers={"User-Agent":"JANUS-G4-Physarum-NewHoldout/4.1",
                             "Accept":"application/octet-stream"})
    with urlopen(req,timeout=25) as resp:
        return resp.read(100001)


def verify_external(item,raw,prior_hashes):
    require(type(raw) is bytes and 2048<=len(raw)<=100000,
            "UNBOUNDED_OR_MISSING_G4_EXTERNAL_DATA")
    require(origin.blob_sha1(raw)==item["git_blob_sha1"],
            "G4_EXTERNAL_GIT_BLOB_TAMPER")
    sha=hashlib.sha256(raw).hexdigest()
    require(sha not in prior_hashes,"CROSS_SPLIT_OR_G3_HOLDOUT_LEAKAGE")
    return sha


def examine(lock,freeze_path,control_dir,physarum_dir,fetch=fetch_pinned):
    import torch
    torch.set_num_threads(1)
    require(load_lock(lock)==load_lock(lock),"INVALID_LOCK")  # explicit on-disk verification
    policy=load_lock(lock)
    freeze,models=verify_checkpoints(freeze_path,control_dir,physarum_dir,torch)
    exact_receipt=exact.field_search([[1,2],[-1,3],[2,-3]],80)
    require(exact_receipt["exact_verifier_has_veto"] is True and
            exact_receipt["coverage_ratio"]==1.0 and
            exact_receipt["production_authority"] is False,
            "JUXTAPOSE_VERIFIER_CHANGED")
    prevent={x["source_sha256"] for role in ("train","val")
             for x in freeze["roles"][role]}
    # Explicitly forbidden: reusing any G3 external exam files.
    known=set()
    files=[]
    for row in policy["sources"]:
        require(row["repo"] not in G3_OLD_SOURCE_PROJECTS,
                "OLD_G3_EXAM_REUSED")
        raw=fetch(row)
        digest=verify_external(row,raw,prevent|known)
        known.add(digest)
        tokens=torch.tensor(list(raw),dtype=torch.long)
        values={name:core.val_loss(torch,model,tokens)
                for name,model in models.items()}
        files.append({
            "repo":row["repo"],"path":row["path"],
            "git_commit":row["commit"],"git_blob_sha1":row["git_blob_sha1"],
            "sha256":digest,"bytes":len(raw),
            "control_loss":values["control"],
            "physarum_loss":values["physarum"]})
    require(len(files)==4 and len(known)==4,
            "INCOMPLETE_EXTERNAL_G4_EXAM")
    pairs=[]
    for repo in NEW_SOURCE_PROJECTS:
        subset=[x for x in files if x["repo"]==repo]
        require(len(subset)==2,"MISSING_NEW_REPO_FAMILY")
        pairs.append({
            "repo":repo,
            "control_mean_loss":sum(v["control_loss"] for v in subset)/2,
            "physarum_mean_loss":sum(v["physarum_loss"] for v in subset)/2
        })
    control=sum(x["control_loss"] for x in files)/4
    phys=sum(x["physarum_loss"] for x in files)/4
    gain=control-phys
    passed=gain>=MIN_MEAN_GAIN and all(
        x["physarum_mean_loss"]-x["control_mean_loss"] <=
        MAX_FAMILY_REGRESSION for x in pairs)
    return seal({
        "schema":EXAM,
        "status":("PASS_INTERNAL_PHYSARUM_GAIN_ON_NEW_EXTERNAL_SOURCES"
                  if passed else "NO_PHYSARUM_GAIN_ON_NEW_EXTERNAL_SOURCES"),
        "lock_sha256":origin.sha(policy),
        "g4_run_id":G4_RUN,
        "g4_checkpoint_manifest_sha256":G4_MANIFESTS,
        "g4_checkpoint_weights_sha256":G4_WEIGHTS,
        "files":files,"per_repository":pairs,
        "control_external_mean_file_loss":control,
        "physarum_external_mean_file_loss":phys,
        "physarum_loss_decrease":gain,
        "frozen_before_first_external_exam":True,
        "both_checkpoints_verified_before_external_bytes_fetched":True,
        "external_sources_new_not_g3_cohort":True,
        "scientific_external_replicator":False,
        "private_blind_custodian":False,
        "old_g3_exam_changed":False,
        "automatic_promotion":False,
        "production_authority":False,
    })


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--lock",default=LOCK_PATH)
    p.add_argument("--freeze",required=True)
    p.add_argument("--control-dir",required=True)
    p.add_argument("--physarum-dir",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=examine(a.lock,a.freeze,a.control_dir,a.physarum_dir)
    origin.immutable_json(a.out,result)
    print(json.dumps({
        "status":result["status"],
        "control_external_loss":result["control_external_mean_file_loss"],
        "physarum_external_loss":result["physarum_external_mean_file_loss"],
        "receipt_sha256":result["receipt_sha256"],
        "production_authority":False
    },sort_keys=True))


if __name__=="__main__":
    main()
