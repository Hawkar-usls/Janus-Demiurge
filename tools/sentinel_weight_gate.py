#!/usr/bin/env python3
"""SENTINEL prospective research-only neural weight challenge, not production.

A candidate is trained and immutable BEFORE the first unseen outcome is
eligible. Two non-overlapping forward sets of 64 genuine GH schedule/push
runs must BOTH improve paired Brier; failure/success and workflow diversity
are mandatory. All cohorts, including failed ones, are consumed once by
retiring the precommitted challenge via Git non-force CAS.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time

from tools import sentinel_transformer as m
from tools import sentinel_forward_calibrate as c

SCHEMA="janus.sentinel.prospective_neural_weight_gate/1.0"
MANIFEST="janus.sentinel.precommitted_weight_challenge/1.0"
MIN_GAIN=0.001
MAX_ECE=0.20
MAX_INFER_SECONDS=30


def require(ok,why):
    if not ok:raise ValueError(why)


def sign(data):
    return dict(data,receipt_sha256=hashlib.sha256(m.canonical(data)).hexdigest())


def check_manifest(obj):
    require(isinstance(obj,dict) and obj.get("schema")==MANIFEST and
            obj.get("production_authority") is False and
            obj.get("research_only") is True and
            type(obj.get("source_run_id")) is str and
            obj["source_run_id"].isdigit() and
            obj.get("candidate_file")==
            "sentinel/model/candidates/"+obj["source_run_id"]+".json" and
            isinstance(obj.get("candidate_checkpoint_sha256"),str) and
            isinstance(obj.get("parent_checkpoint_sha256"),str) and
            obj.get("receipt_sha256")==m.digest({
                k:v for k,v in obj.items() if k!="receipt_sha256"}),
            "UNTRUSTED_NEURAL_CHALLENGE_MANIFEST")
    return obj


def frozen_models(state):
    root=Path(state)
    manifest=root/"sentinel/model/pending-challenge.json"
    if not manifest.is_file():
        return None
    p=check_manifest(json.loads(manifest.read_text("utf-8")))
    parent=m.check_checkpoint(json.loads((root/"sentinel/model/checkpoint.json")
                                    .read_text("utf-8")))
    child_path=root/p["candidate_file"]
    require(child_path.is_file() and not child_path.is_symlink(),
            "MISSING_FROZEN_CANDIDATE")
    child=m.check_checkpoint(json.loads(child_path.read_text("utf-8")))
    require(parent["checkpoint_sha256"]==p["parent_checkpoint_sha256"]
            and child["checkpoint_sha256"]==p["candidate_checkpoint_sha256"]
            and child.get("parent_checkpoint_sha256")==parent["checkpoint_sha256"]
            and child.get("replaces_previous") is False
            and child.get("production_authority") is False
            and child.get("dispatch_authority") is False
            and m.canonical(parent["weights"])!=m.canonical(child["weights"]),
            "CHALLENGER_PARENT_OR_WEIGHT_MISMATCH")
    return p,parent,child


def freeze(state,freeze_utc,out,token):
    root=Path(out)
    require(not root.exists(),"CHALLENGE_FROZEN_OUTPUT_ALREADY_EXISTS")
    root.mkdir(parents=True)
    trio=frozen_models(state)
    if trio is None:
        info={"schema":SCHEMA,"status":"HOLD_NO_PRECOMMITTED_CHALLENGER",
              "needs_torch":False,"eligible":0,"production_authority":False}
    else:
        p,parent,child=trio
        require(m.timepoint(freeze_utc)>=m.timepoint(child["last_test_utc"]),
                "CHALLENGER_FROZEN_BEFORE_SOURCE_END")
        raw=m.fetch_real(token,maxpages=8)
        # No manual dispatches or controlled Sentinel-only injected failures
        # may count as prospective improvement evidence.
        rows=[x for x in raw if x["event"] in ("schedule","push")]
        eligible,_=c.eligible(rows,freeze_utc,None)
        (root/"source.json").write_text(json.dumps(rows,sort_keys=True)+"\n")
        info={"schema":SCHEMA,"status":("READY_128_UNSEEN" if
                 len(eligible)>=128 else "HOLD_NEED_MORE_NEW_RUNS"),
              "needs_torch":len(eligible)>=128,
              "eligible":len(eligible),"needed":128,
              "parent_checkpoint_sha256":parent["checkpoint_sha256"],
              "candidate_checkpoint_sha256":child["checkpoint_sha256"],
              "source_sha256":m.digest(rows),
              "production_authority":False}
    (root/"preflight.json").write_text(json.dumps(info,sort_keys=True,indent=2)+"\n")
    return info


def paired_gate(parent,child,examples,*,parent_prob=None,child_prob=None,
                inference_seconds=0.0):
    m.check_checkpoint(parent)
    m.check_checkpoint(child)
    require(len(examples)==128 and m.canonical(parent["weights"])!=
            m.canonical(child["weights"]),"NO_GENUINE_NEURAL_WEIGHT_CHANGE")
    calibration,test=c.test_diversity(examples)
    if parent_prob is None or child_prob is None:
        parent_prob,_=batched_probabilities(parent,examples)
        child_prob,inference_seconds=batched_probabilities(child,examples)
    require(len(parent_prob)==128 and len(child_prob)==128,
            "INVALID_PRECOMMITTED_PAIRED_SCORES")
    pairs=[]
    for start,end,segment in ((0,64,"confirmation_a"),
                              (64,128,"untouched_confirmation_b")):
        labels=[x[1] for x in examples[start:end]]
        before=m.brier(labels,parent_prob[start:end])
        after=m.brier(labels,child_prob[start:end])
        ece=m.ece(labels,child_prob[start:end])
        pairs.append({"split":segment,"n":64,"parent_brier":before,
                      "child_brier":after,"gain":before-after,
                      "child_ece":ece})
    accepted=all(v["gain"]>=MIN_GAIN and v["child_ece"]<=MAX_ECE
                 for v in pairs) and inference_seconds<=MAX_INFER_SECONDS
    return {"status":("PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN" if accepted
                       else "HOLD_NO_PAIRED_NEURAL_GAIN"),
            "accepted":accepted,"split_evidence":pairs,
            "candidate_inference_seconds":round(inference_seconds,4),
            "source_run_ids":[x[2] for x in examples],
            "last_evaluated_run_utc":examples[-1][3],
            "research_only":True,"production_authority":False,
            "external_independent_validation":False}


def batched_probabilities(checkpoint,examples):
    import torch
    torch.set_num_threads(1)
    net=m.net(torch)
    template=net.state_dict()
    weights=checkpoint["weights"]
    require(isinstance(weights,dict) and set(weights)==set(template),
            "NEURAL_TENSOR_SCHEMA_MISMATCH")
    tensors={}
    for name,target in template.items():
        candidate=torch.tensor(weights[name],dtype=target.dtype)
        require(candidate.shape==target.shape and
                bool(torch.isfinite(candidate).all()),
                "NEURAL_NONFINITE_OR_SHAPE_MISMATCH")
        tensors[name]=candidate
    net.load_state_dict(tensors,strict=True)
    net.eval()
    start=time.monotonic()
    with torch.inference_mode():
        logits=net(torch.tensor([x[0] for x in examples],
                                dtype=torch.long)).tolist()
    elapsed=time.monotonic()-start
    probs=m.score_probs(logits,checkpoint["temperature"])
    return probs,elapsed


def assess(state,freeze_utc,out):
    root=Path(out)
    require((root/"preflight.json").is_file() and
            not (root/"result.json").exists(),"CHALLENGE_NOT_FROZEN")
    info=json.loads((root/"preflight.json").read_text())
    trio=frozen_models(state)
    if trio is None:
        result={"schema":SCHEMA,"status":"HOLD_NO_PRECOMMITTED_CHALLENGER",
                "accepted":False,"consumed":False,
                "production_authority":False}
    else:
        p,parent,child=trio
        if not info["needs_torch"]:
            result={"schema":SCHEMA,"status":"HOLD_NEED_MORE_NEW_RUNS",
                    "accepted":False,"consumed":False,
                    "eligible":info["eligible"],"needed":128,
                    "production_authority":False}
        else:
            rows=json.loads((root/"source.json").read_text("utf-8"))
            require(m.digest(rows)==info["source_sha256"],
                    "FROZEN_ACTIONS_SOURCE_WAS_MODIFIED")
            selected,_=c.eligible(rows,freeze_utc,None)
            chosen=selected[:128]
            require(len(chosen)==128,"FROZEN_COHORT_DISAPPEARED")
            try:
                verdict=paired_gate(parent,child,chosen)
            except ValueError as error:
                verdict={"status":"HOLD_UNSUITABLE_PROSPECTIVE_NEURAL_COHORT",
                         "accepted":False,"error_code":str(error)[:100],
                         "research_only":True,"production_authority":False}
            result=dict(verdict,schema=SCHEMA,consumed=True,
                        parent_checkpoint_sha256=parent["checkpoint_sha256"],
                        candidate_checkpoint_sha256=child["checkpoint_sha256"],
                        future_source_sha256=info["source_sha256"],
                        last_target_id=chosen[-1][2],
                        last_target_utc=chosen[-1][3],
                        source_run_ids=[x[2] for x in chosen],
                        research_only=True,production_authority=False)
            if result["accepted"]:
                accepted=dict(child,status="PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN",
                    replaces_previous=True,
                    accepted_forward_receipt_sha256="PENDING_RECEIPT")
                accepted["checkpoint_sha256"]=m.digest({
                    k:v for k,v in accepted.items() if k!="checkpoint_sha256"})
                # Only create final active checkpoint after the receipt is sealed.
                (root/"accepted_unsealed.json").write_text(
                    json.dumps(accepted,sort_keys=True,indent=2)+"\n")
    result=sign(result)
    (root/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    if result.get("accepted"):
        active=json.loads((root/"accepted_unsealed.json").read_text())
        active["accepted_forward_receipt_sha256"]=result["receipt_sha256"]
        active["checkpoint_sha256"]=m.digest({
            k:v for k,v in active.items() if k!="checkpoint_sha256"})
        m.check_checkpoint(active)
        (root/"accepted.json").write_text(
            json.dumps(active,sort_keys=True,indent=2)+"\n")
        (root/"accepted_unsealed.json").unlink()
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=("freeze","assess"))
    p.add_argument("--state",required=True)
    p.add_argument("--freeze-utc",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    if args.command=="freeze":
        result=freeze(args.state,args.freeze_utc,args.out,
                      os.environ.get("GH_TOKEN",""))
    else:
        result=assess(args.state,args.freeze_utc,args.out)
    print(json.dumps({"status":result["status"],
                      "accepted":result.get("accepted",False),
                      "eligible":result.get("eligible"),
                      "needs_torch":result.get("needs_torch"),
                      "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
