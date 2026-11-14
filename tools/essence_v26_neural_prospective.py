#!/usr/bin/env python3
"""ESSENCE v2.6: prospective neural model improvement on real GitHub Actions.

Research-only closed loop. A frozen challenger and its parent are evaluated
only on workflow runs CREATED AFTER the weights were sealed in a previous
GitHub run. Neither the model nor the evaluator may see future outcomes
before weights are frozen. Positive evidence is research-only; production
weights and services are not modified.

Prediction task: three bins of completed workflow elapsed-time *proxy*
(updated_at - run_started_at). Only pre-run information (workflow ID, event,
creation weekday/hour) is exposed to the neural net. This is NOT a measure
of actual workflow CPU runtime, nor an external laboratory certification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
import torch
from torch import nn
from torch.nn import functional as F

SCHEMA = "janus.essence.github_future_weights/2.6"
SOURCE = "Hawkar-usls/Janus-Demiurge"
BUCKETS = 64
CLASSES = 3
FETCH_PAGES = 8
MIN_HISTORY = 180
MIN_FUTURE = 48
MAX_HISTORY = FETCH_PAGES * 100
MAX_GENERATIONS = 4
SALT = "janus-research-duration-v1"
EVENTS = {"push":0,"workflow_dispatch":1,"schedule":2,
          "pull_request":3,"repository_dispatch":4}
torch.set_num_threads(1)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


def seal(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def at(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_GITHUB_TIMESTAMP")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_GITHUB_TIMESTAMP") from exc
    if t.tzinfo is None:
        raise ValueError("NAIVE_GITHUB_TIMESTAMP")
    return t.astimezone(timezone.utc)


def source_rows(data,now):
    """Accept API observations, never execute or trust run-provided content."""
    if not isinstance(data,list) or len(data)>MAX_HISTORY:
        raise ValueError("UNTRUSTED_API_HISTORY")
    seen=set()
    rows=[]
    for run in data:
        if not isinstance(run,dict):
            continue
        rid=run.get("id")
        wid=run.get("workflow_id")
        if (type(rid) is not int or type(wid) is not int or rid<=0 or wid<=0
            or rid in seen or run.get("head_branch")!="main"
            or run.get("status")!="completed"
            or run.get("conclusion") not in ("success","failure")
            or run.get("run_attempt")!=1):
            continue
        seen.add(rid)
        if not all(isinstance(run.get(k),str) for k in
                   ("created_at","run_started_at","updated_at","event")):
            continue
        created,started,updated=(at(run[k]) for k in
                                ("created_at","run_started_at","updated_at"))
        duration=(updated-started).total_seconds()
        if (created>now or updated>now or started<created
            or duration<3 or duration>7200):
            continue
        label=0 if duration<30 else 1 if duration<120 else 2
        rows.append({"id":rid,"workflow_id":wid,"event":run["event"],
                     "created_at":created.isoformat(),"label":label,
                     "elapsed_seconds":int(duration)})
    return sorted(rows,key=lambda x:(x["created_at"],x["id"]))


def api_runs(token):
    if not token or len(token)>4096:
        raise ValueError("MISSING_GITHUB_READ_TOKEN")
    rows=[]
    headers={"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28",
             "Authorization":"Bearer "+token,
             "User-Agent":"JANUS-ESSENCE-NeuralWitness/2.6"}
    for page in range(1,FETCH_PAGES+1):
        url=("https://api.github.com/repos/"+SOURCE+
             "/actions/runs?branch=main&per_page=100&page="+str(page))
        with urlopen(Request(url,headers=headers),timeout=30) as response:
            page_obj=json.load(response)
        batch=page_obj.get("workflow_runs") if isinstance(page_obj,dict) else None
        if not isinstance(batch,list) or len(batch)>100:
            raise ValueError("GITHUB_HISTORY_FORMAT_CHANGED")
        rows.extend(batch)
        if len(batch)<100:
            break
    return rows


def features(rows):
    x=[]
    y=[]
    for row in rows:
        ident=int(row["workflow_id"])
        ev=row["event"]
        dt=at(row["created_at"])
        i=int(hashlib.sha256((SALT+str(ident)).encode()).hexdigest(),16)%BUCKETS
        vector=[0.0]*(BUCKETS+5+4)
        vector[i]=1.0
        vector[BUCKETS+EVENTS.get(ev,4)]=1.0
        h=dt.hour+dt.minute/60
        w=dt.weekday()
        vector[-4:]=[math.sin(h*math.tau/24),math.cos(h*math.tau/24),
                     math.sin(w*math.tau/7),math.cos(w*math.tau/7)]
        x.append(vector)
        y.append(int(row["label"]))
    return torch.tensor(x,dtype=torch.float32),torch.tensor(y,dtype=torch.long)


def network():
    return nn.Sequential(nn.Linear(BUCKETS+9,24),nn.Tanh(),nn.Linear(24,CLASSES))


def new_parent():
    torch.manual_seed(2601)
    return network()


def state_of(model):
    return {k:{"shape":list(v.shape),"values":v.detach().cpu().flatten().tolist()}
            for k,v in model.state_dict().items()}


def load_state(packet):
    template=network()
    expected=template.state_dict()
    if not isinstance(packet,dict) or set(packet)!=set(expected):
        raise ValueError("MODEL_STATE_TOPOLOGY_MISMATCH")
    loaded={}
    for k,reference in expected.items():
        item=packet[k]
        if not isinstance(item,dict) or item.get("shape")!=list(reference.shape):
            raise ValueError("MODEL_WEIGHT_SHAPE_MISMATCH")
        values=item.get("values")
        if (not isinstance(values,list) or len(values)!=reference.numel()
            or not all(type(v) in (int,float) and math.isfinite(v) and
                       abs(v)<100000 for v in values)):
            raise ValueError("MODEL_WEIGHT_VALUES_INVALID")
        loaded[k]=torch.tensor(values,dtype=torch.float32).reshape(reference.shape)
    template.load_state_dict(loaded,strict=True)
    return template


def measure(model,rows):
    if not rows:
        raise ValueError("EMPTY_EVALUATION")
    x,y=features(rows)
    model.eval()
    with torch.no_grad():
        logits=model(x)
        losses=F.cross_entropy(logits,y,reduction="none").tolist()
        correct=(logits.argmax(-1)==y).float().mean().item()
    return {"n":len(rows),"nll":sum(losses)/len(losses),
            "accuracy":correct,"losses":losses}


def majority(train,target):
    counts=[1,1,1]
    for row in train:
        counts[row["label"]]+=1
    total=sum(counts)
    p=[c/total for c in counts]
    losses=[-math.log(p[row["label"]]) for row in target]
    majority_class=max(range(3),key=lambda i:counts[i])
    return {"nll":sum(losses)/len(losses),
            "accuracy":sum(row["label"]==majority_class for row in target)/len(target),
            "class":majority_class,"distribution":p}


def diverse(rows,*,minimum=48):
    counts=[sum(row["label"]==c for row in rows) for c in range(CLASSES)]
    return (len(rows)>=minimum and
            sum(c>=5 for c in counts)>=2 and
            max(counts)/len(rows)<=0.85)


def train_challenger(parent,history):
    if len(history)<MIN_HISTORY:
        raise ValueError("HOLD_TOO_FEW_REAL_TRAINING_RUNS")
    cut=int(len(history)*0.8)
    train,val=history[:cut],history[cut:]
    if not diverse(train,minimum=110) or not diverse(val,minimum=36):
        raise ValueError("HOLD_LOW_INFORMATION_TRAIN_VALIDATION")
    old=measure(parent,val)
    x,y=features(train)
    child=load_state(state_of(parent))
    optimizer=torch.optim.AdamW(child.parameters(),lr=0.024,weight_decay=0.0007)
    best=state_of(child)
    best_nll=old["nll"]
    torch.manual_seed(2602)
    for epoch in range(45):
        child.train()
        optimizer.zero_grad(set_to_none=True)
        loss=F.cross_entropy(child(x),y)
        if not torch.isfinite(loss):
            raise ValueError("NONFINITE_GRADIENT_LOSS")
        loss.backward()
        nn.utils.clip_grad_norm_(child.parameters(),1.0,error_if_nonfinite=True)
        optimizer.step()
        if epoch%3==2:
            metric=measure(child,val)
            if metric["nll"]<best_nll:
                best_nll=metric["nll"]
                best=state_of(child)
    child=load_state(best)
    after=measure(child,val)
    static=majority(train,val)
    if (after["nll"]>=old["nll"]-0.004
        or seal(state_of(child))==seal(state_of(parent))
        or after["nll"]>=static["nll"]-0.004):
        raise ValueError("HOLD_NO_INDEPENDENT_HISTORICAL_VALIDATION_GAIN")
    return child,{"training_rows":len(train),"validation_rows":len(val),
                  "source_rows_sha256":seal(history),
                  "training_data_first_created_at":train[0]["created_at"],
                  "training_data_last_created_at":train[-1]["created_at"],
                  "validation_last_created_at":val[-1]["created_at"],
                  "historical_parent_nll":old["nll"],
                  "historical_child_nll":after["nll"],
                  "historical_frozen_majority_nll":static["nll"],
                  "frozen_prior_class":static["class"],
                  "frozen_prior_distribution":static["distribution"],
                  "true_gradient_updates":45,
                  "external_independent_blind":False}


def empty():
    data={"schema":SCHEMA,"generation":0,"parent":None,
          "pending":None,"history":[],"status":"EMPTY",
          "research_only":True,"production_authority":False}
    return dict(data,state_sha256=seal(data))


def check(doc):
    if (not isinstance(doc,dict) or doc.get("schema")!=SCHEMA
        or doc.get("research_only") is not True
        or doc.get("production_authority") is not False
        or type(doc.get("generation")) is not int
        or not 0<=doc["generation"]<=MAX_GENERATIONS
        or doc.get("state_sha256")!=seal({k:v for k,v in doc.items()
                                        if k!="state_sha256"})):
        raise ValueError("SEALED_NEURAL_STATE_INVALID")
    if not isinstance(doc.get("history"),list) or len(doc["history"])>MAX_GENERATIONS+20:
        raise ValueError("INVALID_NEURAL_HISTORY")
    if doc.get("parent") is not None:
        load_state(doc["parent"])
    p=doc.get("pending")
    if p is not None:
        if not isinstance(p,dict):
            raise ValueError("INVALID_PENDING_TRIAL")
        if (p.get("parent_sha256")!=seal(doc["parent"]) or
            p.get("challenger_sha256")!=seal(p.get("challenger"))):
            raise ValueError("MUTATED_PARENT_CHILD_STATE_BINDING")
        load_state(p["challenger"])
        at(p["sealed_before"])
    return doc


def make_pending(parent,history,now):
    challenger,train_receipt=train_challenger(parent,history)
    original=state_of(parent)
    child_state=state_of(challenger)
    return {"parent_sha256":seal(original),
            "challenger":child_state,"challenger_sha256":seal(child_state),
            "sealed_before":now.isoformat(),
            "max_train_created_at":history[-1]["created_at"],
            "training":train_receipt,"status":"FROZEN_AWAITING_GITHUB_FUTURE"}


def future_decision(pending,parent,observed,now,*,published_at=None):
    if pending["parent_sha256"]!=seal(state_of(parent)):
        raise ValueError("PARENT_CROSS_RUN_DRIFT")
    freeze=at(pending["sealed_before"])
    publication=at(published_at) if published_at is not None else freeze
    if publication>now or publication<freeze:
        raise ValueError("INVALID_PUBLISHED_STATE_TIME")
    # A Git commit, not an unpersisted in-memory checkpoint, is the
    # reference for which outcomes count as genuinely prospective.
    cutoff=publication
    fresh=[r for r in observed if at(r["created_at"])>cutoff]
    if not diverse(fresh,minimum=MIN_FUTURE):
        return {"status":"HOLD_FUTURE_COHORT_NOT_YET_DIVERSE",
                "observed_new":len(fresh),
                "future_labels_visible_to_training":False},None
    child=load_state(pending["challenger"])
    a=measure(parent,fresh)
    b=measure(child,fresh)
    losses=[u-v for u,v in zip(a["losses"],b["losses"])]
    mean=sum(losses)/len(losses)
    sigma=math.sqrt(sum((v-mean)**2 for v in losses)/(len(losses)-1))
    lower=mean-1.645*sigma/math.sqrt(len(losses))
    frozen=pending["training"]["frozen_prior_distribution"]
    benchmark_nll=sum(-math.log(frozen[row["label"]]) for row in fresh)/len(fresh)
    benchmark_accuracy=sum(row["label"]==pending["training"]["frozen_prior_class"]
                           for row in fresh)/len(fresh)
    passes=(mean>=0.02 and lower>0.0 and
            b["accuracy"]>=a["accuracy"]-0.01 and
            b["nll"]<=benchmark_nll-0.005 and
            b["accuracy"]>=benchmark_accuracy-0.01)
    result={
        "status":"PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN" if passes else
                 "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN",
        "sample_count":len(fresh),
        "first_new_created_at":fresh[0]["created_at"],
        "frozen_weights_published_at":cutoff.isoformat(),
        "future_records_created_after_weights_git_commit":published_at is not None,
        "last_new_created_at":fresh[-1]["created_at"],
        "labels_from_independent_postfreeze_run_events":True,
        "source_fingerprint_sha256":seal(fresh),
        "frozen_parent_sha256":pending["parent_sha256"],
        "frozen_child_sha256":pending["challenger_sha256"],
        "parent_nll":a["nll"],"child_nll":b["nll"],
        "parent_accuracy":a["accuracy"],"child_accuracy":b["accuracy"],
        "frozen_train_prior_nll":benchmark_nll,
        "frozen_train_prior_accuracy":benchmark_accuracy,
        "paired_nll_gain":mean,"paired_one_sided_95pct_lower_bound":lower,
        "improvement_proven_under_registered_internal_thresholds":passes,
        "external_custodian":False,"production_authority":False,
        "training_saw_future_labels":False
    }
    result["receipt_sha256"]=seal(result)
    return result,child if passes else None


def step(state,observed,now,*,history_exhaustive=True,state_published_at=None):
    check(state)
    if now.tzinfo is None:
        raise ValueError("NAIVE_CYCLE_TIME")
    if not history_exhaustive:
        return state,{"status":"HOLD_INCOMPLETE_GITHUB_HISTORY"}
    if len(observed)<MIN_HISTORY:
        return state,{"status":"HOLD_INSUFFICIENT_GITHUB_HISTORY",
                      "available":len(observed)}
    next_state={k:v for k,v in state.items() if k!="state_sha256"}
    pending=state["pending"]
    permit_next_training=True
    if pending is not None:
        frozen=at(pending["sealed_before"])
        cutoff=at(state_published_at) if state_published_at else frozen
        if cutoff<frozen or cutoff>now:
            raise ValueError("INVALID_PUBLISHED_STATE_TIME")
        if observed and at(observed[0]["created_at"])>cutoff:
            return state,{"status":"HOLD_FUTURE_HISTORY_WINDOW_EXPIRED"}
        parent=load_state(state["parent"])
        verdict,descendant=future_decision(pending,parent,observed,now,
                                         published_at=state_published_at)
        if descendant is None and verdict["status"]=="HOLD_FUTURE_COHORT_NOT_YET_DIVERSE":
            return state,verdict
        accepted=descendant is not None
        if accepted:
            next_state["generation"]+=1
            next_state["parent"]=state_of(descendant)
        streak=0
        if accepted:
            for earlier in reversed(state["history"]):
                if earlier.get("accepted") is not True:
                    break
                streak+=1
            streak+=1
        next_state["history"]=(state["history"]+[{
            "sealed_before":pending["sealed_before"],
            "parent_sha256":pending["parent_sha256"],
            "child_sha256":pending["challenger_sha256"],
            "accepted":accepted,
            "consecutive_accepted_generations":streak,
            "two_consecutive_prospective_gains":streak>=2,
            "generation_after":next_state["generation"],
            "independent_future_verification":verdict
        }])[-(MAX_GENERATIONS+20):]
        next_state["pending"]=None
        if not accepted:
            # A failed prospective exam cannot launch another candidate on
            # the same now-consumed cohort; require a later source increment.
            permit_next_training=False
            verdict["next_training_hold"]="HOLD_REJECTED_TRIAL_REQUIRES_NEW_HISTORY"
        next_state["status"]="RESEARCH_GEN"+str(next_state["generation"])+(
            "_ACCEPTED" if accepted else "_HOLD")
    else:
        verdict={"status":"INITIAL_NEURAL_PARENT"}
        if state["parent"] is None:
            next_state["parent"]=state_of(new_parent())
        elif state["history"]:
            # Never repeatedly search for a lucky winner against an
            # already-inspected prospective cohort. At least 24 further
            # COMPLETED real jobs must appear after the last consumed trial.
            previous=state["history"][-1]
            examined=(previous.get("independent_future_verification") or {})
            consumed=examined.get("last_new_created_at")
            if not consumed:
                raise ValueError("INCOMPLETE_PREVIOUS_NEURAL_EXAM_RECORD")
            newly_seen=sum(at(row["created_at"])>at(consumed)
                           for row in observed)
            if newly_seen<24:
                permit_next_training=False
                verdict={"status":"HOLD_RETRAIN_REQUIRES_NEW_HISTORY",
                         "new_runs_since_last_exam":newly_seen}
            else:
                verdict={"status":"RETRAIN_ALLOWED_AFTER_NEW_HISTORY",
                         "new_runs_since_last_exam":newly_seen}
    if permit_next_training and next_state["generation"]<MAX_GENERATIONS:
        try:
            original=load_state(next_state["parent"])
            next_state["pending"]=make_pending(original,observed,now)
            next_state["status"]="FROZEN_AWAITING_FUTURE_COHORT"
            verdict["next_challenger_sha256"]=next_state["pending"]["challenger_sha256"]
        except ValueError as error:
            verdict["next_training_hold"]=str(error)
    next_state["state_sha256"]=seal(next_state)
    return next_state,verdict


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--state",required=True)
    p.add_argument("--receipt",required=True)
    p.add_argument("--state-committed-at",required=True,
                   help="Last committed Git state-branch HEAD author time")
    args=p.parse_args()
    state_path=Path(args.state)
    receipt_path=Path(args.receipt)
    if receipt_path.exists():
        raise FileExistsError("IMMUTABLE_RESEARCH_RECEIPT")
    doc=json.loads(state_path.read_text()) if state_path.is_file() else empty()
    now=datetime.now(timezone.utc)
    raw=api_runs(os.environ.get("GH_TOKEN",""))
    observed=source_rows(raw,now)
    cutoff=(at(args.state_committed_at) if doc.get("pending") is not None
            else now)
    new,decision=step(doc,observed,now,
        state_published_at=args.state_committed_at,
        history_exhaustive=(len(raw)<MAX_HISTORY or (
          doc.get("pending") is None or (
            observed and at(observed[0]["created_at"])<=cutoff)))
        )
    receipt={"schema":SCHEMA,"at":now.isoformat(),
             "source_repository":SOURCE,"input_count":len(raw),
             "usable_completed_runs":len(observed),
             "source_sha256":seal(observed),
             "old_state_sha256":doc["state_sha256"],
             "new_state_sha256":new["state_sha256"],
             "generation":new["generation"],
             "decision":decision,"production_authority":False}
    receipt["receipt_sha256"]=seal(receipt)
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    if new["state_sha256"]!=doc["state_sha256"]:
        state_path.parent.mkdir(parents=True,exist_ok=True)
        state_path.write_text(json.dumps(new,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":decision["status"],
        "generation":new["generation"],
        "changed":new["state_sha256"]!=doc["state_sha256"],
        "usable_runs":len(observed),"production_authority":False}))


if __name__=="__main__":
    main()
