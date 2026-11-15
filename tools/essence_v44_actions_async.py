#!/usr/bin/env python3
"""ESSENCE v4.4: GitHub-only async, resumable, SHA-locked inference queue.

GitHub-hosted Actions runners cannot run a truly persistent 24/7 service.
This module implements a bounded event-driven logical worker: cron wakes it
every 5 minutes (best effort), workflow_dispatch can request immediate
inference, Github branch commits persist immutable results across runners.
Idle pulses are cheap, do not install torch and do not write commits.

Never imports untrusted code from the data branch; never accepts a model
path from a request; never updates production model weights. Frozen G4
Physarum is shadow-only, and the better 14-step fixed baseline is active.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time

SCHEMA="janus.essence.actions_resumable_worker/4.4"
REQUEST="janus.essence.github_async_request/4.4"
RESULT="janus.essence.github_async_result/4.4"
PLAN="janus.essence.github_async_plan/4.4"
CONFIG="janus.essence.github_async_state_config/4.4"
HEX24=re.compile(r"[0-9a-fA-F]{48}\Z")
REQUEST_ID=re.compile(r"[a-z][a-z0-9-]{2,40}\Z")
SHA40=re.compile(r"[0-9a-f]{40}\Z")
RUN_ID=re.compile(r"[1-9][0-9]{0,20}\Z")
MAX_BATCH=4
MAX_INBOX_SCAN=1000
MAX_REQUEST_BYTES=512
EXPECTED={
 "baseline14":"a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174",
 "physarum":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
}
# NOTE: The source file contains no system credentials and never opens sockets.


def require(condition,code):
    if not condition:
        raise ValueError(code)


def canonical(data):
    return json.dumps(data,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def seal(data):
    return dict(data,receipt_sha256=digest(data))


def immutable(path,data):
    target=Path(path)
    require(not target.exists() and not target.is_symlink(),
            "IMMUTABLE_RECEIPT_COLLISION")
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as f:
        json.dump(data,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")


def load_small_json(path,max_bytes=MAX_REQUEST_BYTES):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and
            2<=p.stat().st_size<=max_bytes,"UNSAFE_JSON_FILE")
    return json.loads(p.read_text("utf-8"),
                      parse_constant=lambda _:
                      (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def validate_config(root):
    config=load_small_json(Path(root)/"config.json",2048)
    require(config.get("schema")==CONFIG and
            config.get("data_branch")=="essence-actions-state" and
            config.get("active_sha256")==EXPECTED["baseline14"] and
            config.get("shadow_sha256")==EXPECTED["physarum"] and
            config.get("training_allowed") is False and
            config.get("production_authority") is False and
            config.get("continuous_hosted_process_claim") is False and
            config.get("max_requests_per_wakeup")==MAX_BATCH,
            "DATA_BRANCH_CONFIG_TAMPERED")
    return config


def validate_hex(value):
    require(type(value) is str and HEX24.fullmatch(value) is not None,
            "MUST_SUPPLY_EXACTLY_24_BYTES_AS_48_HEX_DIGITS")
    return bytes.fromhex(value)


def validate_request(obj,filename):
    require(isinstance(obj,dict) and
            set(obj)=={"schema","request_id","input_hex"} and
            obj["schema"]==REQUEST and
            isinstance(obj["request_id"],str) and
            REQUEST_ID.fullmatch(obj["request_id"]) is not None and
            filename==obj["request_id"]+".json",
            "REJECTED_UNTRUSTED_REQUEST_SCHEMA_OR_PATH")
    data=validate_hex(obj["input_hex"])
    return obj["request_id"],data


def choose_pending(state_root):
    directory=Path(state_root)/"inbox"
    results=Path(state_root)/"results"
    require(not directory.is_symlink() and not results.is_symlink(),
            "UNSAFE_ASYNC_QUEUE_DIRECTORY")
    directory.mkdir(parents=True,exist_ok=True)
    results.mkdir(parents=True,exist_ok=True)
    paths=sorted(directory.glob("*.json"))
    require(len(paths)<=MAX_INBOX_SCAN,"QUEUE_OVERFLOW_OPERATOR_REVIEW_REQUIRED")
    unprocessed=[p for p in paths if not (results/p.name).exists()]
    return unprocessed[:MAX_BATCH],len(unprocessed)


def prepare(state_root,mode,input_hex,run_id,attempt,source_sha,out):
    validate_config(state_root)
    require(mode in ("pulse","infer"),"INVALID_ACTIONS_MODE")
    require(type(run_id) is str and RUN_ID.fullmatch(run_id) and
            type(attempt) is str and RUN_ID.fullmatch(attempt) and
            type(source_sha) is str and SHA40.fullmatch(source_sha),
            "UNTRUSTED_ACTIONS_RUN_ID")
    selected=[]
    pending=0
    needs_models=False
    if mode=="pulse":
        paths,pending=choose_pending(state_root)
        for p in paths:
            selected.append({"file":p.name,"sha256":hashlib.sha256(
                p.read_bytes()).hexdigest() if p.stat().st_size<=MAX_REQUEST_BYTES
                else "OVERSIZED"})
            if p.stat().st_size<=MAX_REQUEST_BYTES:
                try:
                    validate_request(load_small_json(p),p.name)
                    needs_models=True
                except (ValueError,KeyError,TypeError,UnicodeError,
                        json.JSONDecodeError):
                    pass
    else:
        validate_hex(input_hex)
        needs_models=True
    plan={
        "schema":PLAN,"mode":mode,"run_id":run_id,
        "run_attempt":attempt,"source_commit_sha":source_sha,
        "selected":selected,"pending_before":pending,
        "needs_models":needs_models,"stage_only":True,
        "active_model":"baseline14",
        "candidate_shadow_only":True,
        "production_authority":False,
    }
    immutable(out,plan)
    return plan


def real_models(baseline_path,physarum_path):
    import torch
    from tools.essence_v43_staging_rollback import read_checkpoint
    torch.set_num_threads(1)
    models={
        "baseline14":read_checkpoint(baseline_path,"baseline14",torch),
        "physarum":read_checkpoint(physarum_path,"physarum",torch),
    }
    return torch,models


def infer(torch,models,raw):
    require(len(raw)==24,"INVALID_MODEL_INPUT_LENGTH")
    x=torch.tensor([list(raw)],dtype=torch.long)
    outputs={}
    for label in ("baseline14","physarum"):
        start_wall=time.perf_counter_ns()
        start_cpu=time.process_time_ns()
        with torch.inference_mode():
            tensor=models[label](x)
        logits=tensor[0,-1].tolist()
        wall_ns=time.perf_counter_ns()-start_wall
        cpu_ns=time.process_time_ns()-start_cpu
        require(len(logits)==256 and all(math.isfinite(v) for v in logits),
                "NONFINITE_NETWORK_PREDICTION")
        packed=struct.pack("<256f",*logits)
        outputs[label]={
            "checkpoint_sha256":EXPECTED[label],
            "next_byte":max(range(256),key=lambda i:logits[i]),
            "logits_sha256":hashlib.sha256(packed).hexdigest(),
            "forward_cpu_ns":cpu_ns,
            "forward_wall_ns":wall_ns,
            "returned_as_live_production_prediction":False,
        }
    return outputs


def result_receipt(request_id,raw,run_id,attempt,models,torch,*,source_sha):
    scores=infer(torch,models,raw)
    return seal({
        "schema":RESULT,
        "request_id":request_id,
        "request_input_sha256":hashlib.sha256(raw).hexdigest(),
        "run_id":run_id,"run_attempt":attempt,
        "source_commit_sha":source_sha,
        "status":"PASS_FROZEN_G4_RESEARCH_INFERENCE",
        "routing":"BASELINE14_ACTIVE_PHYSARUM_SHADOW_ONLY",
        "active_model":"baseline14","candidate_shadow_only":True,
        "frozen_models":scores,
        "production_authority":False,
        "external_independent_validation":False,
        "raw_request_bytes_in_receipt":False,
    })


def rejected_receipt(name,raw_digest,run_id,attempt,source_sha,reason):
    return seal({
        "schema":RESULT,
        "request_id":name,
        "request_source_file_sha256":raw_digest,
        "run_id":run_id,"run_attempt":attempt,
        "source_commit_sha":source_sha,
        "status":"REJECTED_REQUEST_FAIL_CLOSED",
        "reason":reason,"production_authority":False,
        "candidate_shadow_only":True,
        "raw_request_bytes_in_receipt":False
    })


def execute(state_root,plan_path,output,baseline_path,physarum_path,input_hex=""):
    plan=load_small_json(plan_path,8192)
    require(plan["schema"]==PLAN and
            plan["active_model"]=="baseline14" and
            plan["production_authority"] is False and
            plan["candidate_shadow_only"] is True and
            len(plan["selected"])<=MAX_BATCH,
            "UNAUTHORIZED_ASYNC_PLAN")
    validate_config(state_root)
    run_id=plan["run_id"]
    attempt=plan["run_attempt"]
    source_sha=plan["source_commit_sha"]
    mode=plan["mode"]
    state=Path(state_root)
    target=state/"results"
    target.mkdir(parents=True,exist_ok=True)
    torch,models=(real_models(baseline_path,physarum_path)
                  if plan["needs_models"] else (None,None))
    accepted=0
    rejected=0
    already_complete=0
    processed=[]
    if mode=="infer":
        raw=validate_hex(input_hex)
        name=f"dispatch-{run_id}-{attempt}"
        dst=target/(name+".json")
        immutable(dst,result_receipt(name,raw,run_id,attempt,models,torch,
                                     source_sha=source_sha))
        accepted=1
        processed.append(name)
    else:
        for item in plan["selected"]:
            filename=item["file"]
            p=state/"inbox"/filename
            require(p.is_file() and not p.is_symlink(),
                    "REQUEST_REMOVED_WHILE_RUNNING")
            name=filename.removesuffix(".json")
            dst=target/filename
            if dst.exists():
                already_complete+=1
                continue
            body=p.read_bytes()
            if item["sha256"]=="OVERSIZED":
                require(len(body)>MAX_REQUEST_BYTES,
                        "INBOX_CONTENT_CHANGED_FROM_PREPARE")
                rec=rejected_receipt(name,hashlib.sha256(body).hexdigest(),
                                     run_id,attempt,source_sha,
                                     "OVERSIZED_QUEUE_REQUEST")
                rejected+=1
            else:
                require(hashlib.sha256(body).hexdigest()==item["sha256"],
                        "REQUEST_CHANGED_DURING_RUN")
                try:
                    rid,raw=validate_request(load_small_json(p),filename)
                    require(models is not None,"MISSING_MODEL_FOR_VALID_REQUEST")
                    rec=result_receipt(rid,raw,run_id,attempt,models,torch,
                                       source_sha=source_sha)
                    accepted+=1
                except (ValueError,KeyError,TypeError,UnicodeError,
                        json.JSONDecodeError) as e:
                    # A malformed request is accounted for once and cannot
                    # keep a queued job stuck forever.
                    rec=rejected_receipt(name,item["sha256"],run_id,attempt,
                                         source_sha,str(e)[:120])
                    rejected+=1
            immutable(dst,rec)
            processed.append(name)
    event=seal({
        "schema":SCHEMA,
        "run_id":run_id,"run_attempt":attempt,
        "source_commit_sha":source_sha,
        "mode":mode,
        "status":("WORK_PROCESSED" if accepted or rejected else
                  "IDLE_NO_WORK_PROCESSED"),
        "selected_count":len(plan["selected"]),
        "accepted_count":accepted,"rejected_count":rejected,
        "already_complete_count":already_complete,
        "queued_before":plan["pending_before"],
        "queued_remaining_estimate":max(0,plan["pending_before"]-
                                       accepted-rejected-already_complete),
        "processed_request_ids":processed,
        "worker_os_persistent":False,
        "process_terminates_after_this_job":True,
        "github_cron_best_effort":True,
        "checkpoint_sha256_control14":EXPECTED["baseline14"],
        "checkpoint_sha256_physarum":EXPECTED["physarum"],
        "candidate_shadow_only":True,
        "production_authority":False,
        "external_independent_validation":False,
    })
    immutable(output,event)
    if accepted or rejected:
        immutable(state/"events"/(run_id+"-"+attempt+".json"),event)
    return event


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("prepare")
    q.add_argument("--state-dir",required=True)
    q.add_argument("--mode",choices=("pulse","infer"),required=True)
    q.add_argument("--input-hex",default="")
    q.add_argument("--run-id",required=True)
    q.add_argument("--attempt",required=True)
    q.add_argument("--source-sha",required=True)
    q.add_argument("--out",required=True)
    q=sub.add_parser("execute")
    q.add_argument("--state-dir",required=True)
    q.add_argument("--plan",required=True)
    q.add_argument("--out",required=True)
    q.add_argument("--baseline14-dir",required=True)
    q.add_argument("--physarum-dir",required=True)
    q.add_argument("--input-hex",default="")
    args=p.parse_args()
    if args.cmd=="prepare":
        result=prepare(args.state_dir,args.mode,args.input_hex,
                       args.run_id,args.attempt,args.source_sha,args.out)
        print(json.dumps({"needs_models":result["needs_models"],
                          "pending":result["pending_before"],
                          "selected":len(result["selected"]),
                          "mode":result["mode"]},sort_keys=True))
    else:
        result=execute(args.state_dir,args.plan,args.out,
                       args.baseline14_dir,args.physarum_dir,args.input_hex)
        print(json.dumps({
            "status":result["status"],
            "accepted":result["accepted_count"],
            "rejected":result["rejected_count"],
            "run_id":result["run_id"],
            "receipt_sha256":result["receipt_sha256"],
            "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
