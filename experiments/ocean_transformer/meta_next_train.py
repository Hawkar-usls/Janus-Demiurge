#!/usr/bin/env python3
"""JANUS Ocean: next new JSON added to Meta Registry. Chronology-first research.

Only public Git metadata (commit timestamps, added .json paths), no JSON contents.
Predicts category of next commit introducing JSON, not exact file or secret data.
Neural forecasting must exceed majority and first-order Markov baselines.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import time

import torch
import torch.nn.functional as F
from janus_model.model import JanusTinyTransformer, JanusModelConfig, parameter_count
from experiments.ocean_transformer.ocean_r3_registry_bridge import chronology_allowed, QUARANTINE, QUALITY

torch.set_num_threads(1)
CONTEXT=16
VOCAB=48
CFG=JanusModelConfig(vocab_size=VOCAB, context_length=CONTEXT,
                     d_model=32,n_heads=4,n_layers=1,ff_mult=2,dropout=0.)
SEED=2026110614
MAX_LABELS=30
SKIP_PREFIXES=("JANUS-META-NEXT-", "JANUS-AIR-ALERT-")
REMOTE="https://github.com/Hawkar-usls/janus-meta-registry.git"
MODEL_DIR="experiments/ocean_transformer"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))


def git(*args, cwd=None, timeout=180):
    p=subprocess.run(["git",*args],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError(f"git {args[0]} failed: {p.stderr[:300]}")
    return p.stdout


def classify(path):
    parts=path.split("/")
    parent="/".join(parts[:-1]) or "_root"
    filename=parts[-1].removesuffix(".json")
    tokens=re.findall(r"[A-Za-z][A-Za-z0-9]{1,16}",filename)
    ignore={"janus","v1","v2","v3","json","registry","meta","state","report","data"}
    salient=next((t.lower() for t in tokens if t.lower() not in ignore),"misc")
    return parent+"/"+salient


def collect(args):
    started=time.monotonic()
    # Bounded partial history: objects without blobs, read only, no checkout.
    target=Path(args.checkout)
    if target.exists():raise RuntimeError("REFUSE_OVERWRITE_GIT_DIR")
    try:
        git("clone","--quiet","--depth=5000","--filter=blob:none","--no-checkout",
            "--single-branch",REMOTE,str(target),timeout=240)
    except RuntimeError as exc:
        # Limited fallback for low-capacity Git runners.
        if target.exists(): raise
        raise
    head=git("rev-parse","HEAD",cwd=target).strip()
    stream=git("log","--first-parent","--diff-filter=A","--format=%x1e%H%x1f%cI",
               "--name-only","--","*.json",cwd=target,timeout=240)
    events=[]
    for block in stream.split("\x1e"):
        if not block.strip():continue
        rows=block.strip().splitlines()
        header=rows[0].split("\x1f")
        if len(header)!=2:continue
        commit, timestamp=header
        paths=sorted(set(s.strip() for s in rows[1:] if s.strip().lower().endswith(".json")))
        # Explicitly exclude our own model feedback from prospective targets.
        paths=[p for p in paths if chronology_allowed(p)]
        if not paths:continue
        cats=sorted({classify(p) for p in paths})
        events.append({"commit":commit, "timestamp":timestamp, "first_path":paths[0],
                       "representative_label":classify(paths[0]),
                       "paths_added":len(paths), "category_count":len(cats)})
    events.reverse()
    if len(events)<160:raise RuntimeError(f"TOO_FEW_JSON_ADDITION_COMMITS_{len(events)}")
    # All classifier categories fixed using training portion only: no holdout vocabulary leak.
    train_stop=int(len(events)*0.70)
    frequent=Counter(x["representative_label"] for x in events[:train_stop])
    labels=[key for key,_ in sorted(frequent.items(),key=lambda kv:(-kv[1],kv[0]))[:MAX_LABELS]]
    classes=labels+["OTHER"]
    mapping={c:i for i,c in enumerate(classes)}
    sample=[mapping.get(x["representative_label"],len(labels)) for x in events]
    unique=sorted({x["representative_label"] for x in events})
    out={
        "schema":"janus.meta_next.snapshot.v1","created_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_repository":"Hawkar-usls/janus-meta-registry",
        "source_head":head,"collection":"bounded last 5000 first-parent commits",
        "event_definition":"each commit that added JSON; first lexicographic newly added file; category from directory + salient filename prefix",
        "excludes_generated_experiment_records":list(SKIP_PREFIXES)+[QUARANTINE,QUALITY],
        "events_count":len(events),"unique_observed_categories":len(unique),
        "train_cutoff_idx":train_stop,"labels":classes,
        "sequence":sample,"events":events,
        "limitations":[
            "Commit-date ordering differs from user intent or file creation time.",
            "Multiple JSON files in same commit have no temporal order; representative path is lexicographically first.",
            "This dataset only includes latest 5000 first-parent commits, not full 2026 history.",
            "Prediction is category of next JSON-adding commit, not exact filename/content.",
            "Commit histories can be rebased; source HEAD recorded and no future commits entered training."
        ],
        "collection_seconds":round(time.monotonic()-started,2),
    }
    save(args.output,out)
    print(json.dumps({"head":head,"n_events":len(events),"classes":len(classes),"n_unique":len(unique),
                      "first_date":events[0]["timestamp"],"last_date":events[-1]["timestamp"],
                      "snapshot_sha256":sha(args.output)},indent=2))


def make_model():
    torch.manual_seed(SEED);return JanusTinyTransformer(CFG)


def split(obj):
    seq=obj["sequence"];n=len(seq)
    tr=int(n*.70);val=int(n*.85)
    # i predicts event index i from 16 prior events, and split on target index.
    train=list(range(CONTEXT,tr))
    valid=list(range(tr+CONTEXT,val))
    test=list(range(val+CONTEXT,n))
    if min(len(train),len(valid),len(test))<20:raise RuntimeError("SHORT_META_SPLIT")
    return seq,train,valid,test


def inputs(seq,indices):
    x=torch.tensor([seq[i-CONTEXT:i] for i in indices],dtype=torch.long)
    y=torch.tensor([seq[i] for i in indices],dtype=torch.long)
    return x,y


@torch.no_grad()
def model_logits(model,seq,inds,batch=256):
    model.eval();out=[]
    for k in range(0,len(inds),batch):
        x,_=inputs(seq,inds[k:k+batch])
        out.append(model(x)[0][:,-1,:])
    return torch.cat(out)


def worker(args):
    start=time.monotonic();obj=read(args.snapshot)
    seq,tr,_,_=split(obj)
    c=len(obj["labels"])
    anchors=tr[args.worker::args.workers]
    if len(anchors)<14:raise RuntimeError("INSUFFICIENT_META_SHARD")
    model=make_model();optim=torch.optim.AdamW(model.parameters(),lr=.004)
    rng=random.Random(110201+args.worker*53)
    count=0
    for it in range(args.steps):
        if count>=70 and time.monotonic()-start>args.budget:break
        picks=rng.choices(anchors,k=args.batch)
        x,y=inputs(seq,picks)
        model.train();optim.zero_grad(set_to_none=True)
        logits,_=model(x)
        loss=F.cross_entropy(logits[:,-1,:c],y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1)
        optim.step();count+=1
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ck=out/"weights.pt"
    torch.save({"state":{k:v.cpu() for k,v in model.state_dict().items()},"cfg":CFG.to_dict(),
                "worker_id":args.worker,"snapshot_sha256":sha(args.snapshot),
                "samples":len(anchors)},ck)
    report={"schema":"janus.meta_next.river.v1","worker_id":args.worker,"workers":args.workers,
            "training_anchor_count":len(anchors),"steps":count,"seconds":round(time.monotonic()-start,3),
            "snapshot_sha256":sha(args.snapshot),"weights_sha256":sha(ck)}
    save(out/"river.json",report);print(json.dumps(report,indent=2))


def metrics(logits,seq,ids,c,t=1.):
    true=torch.tensor([seq[i] for i in ids],dtype=torch.long)
    probs=torch.softmax(logits[:,:c]/t,-1)
    ce=float(F.nll_loss(probs.clamp_min(1e-10).log(),true))
    accuracy=float((probs.argmax(-1)==true).float().mean())
    k=min(3,c)
    top3=float((probs.topk(k,-1).indices==true[:,None]).any(-1).float().mean())
    brier=float(((probs-F.one_hot(true,c).float())**2).sum(-1).mean())
    return {"n":len(ids),"accuracy":round(accuracy,6),"top3":round(top3,6),
            "log_loss":round(ce,6),"multiclass_brier":round(brier,6)}


def baseline(seq,train,test,c):
    trlabels=[seq[i] for i in train];major=Counter(trlabels).most_common(1)[0][0]
    trans=defaultdict(Counter)
    for i in train:
        trans[seq[i-1]][seq[i]]+=1
    def laplace(row, fallback=major):
        scores=[row.get(i,0)+1 for i in range(c)]
        return max(range(c),key=lambda i:(scores[i], i==fallback))
    markov=[laplace(trans.get(seq[i-1],{})) for i in test]
    return {"majority_label":major,
            "majority_accuracy":round(sum(seq[i]==major for i in test)/len(test),6),
            "copy_last_accuracy":round(sum(seq[i]==seq[i-1] for i in test)/len(test),6),
            "markov_accuracy":round(sum(seq[i]==pred for i,pred in zip(test,markov))/len(test),6)}


def aggregate(args):
    obj=read(args.snapshot)
    seq,tr,val,test=split(obj)
    c=len(obj["labels"])
    reports=list(Path(args.input).glob("*/river.json"))
    if len(reports)!=args.workers:raise RuntimeError("MISSING_META_RIVERS")
    zero=make_model();state=zero.state_dict()
    acc={k:torch.zeros_like(v,dtype=torch.float64) for k,v in state.items()}
    seen=set();weights=0;logs=[]
    for file in reports:
        j=read(file);idx=j["worker_id"]
        if idx in seen or idx not in range(args.workers) or j["workers"]!=args.workers or j["snapshot_sha256"]!=sha(args.snapshot):
            raise RuntimeError("BAD_META_RIVER")
        seen.add(idx)
        ck=file.parent/"weights.pt"
        if sha(ck)!=j["weights_sha256"]:raise RuntimeError("META_WEIGHT_DIGEST_MISMATCH")
        objw=torch.load(ck,map_location="cpu",weights_only=True)
        if objw["cfg"]!=CFG.to_dict() or objw["worker_id"]!=idx:raise RuntimeError("META_WEIGHT_CFG_MISMATCH")
        n=objw["samples"]
        if n<14:raise RuntimeError("META_SHARD_COUNT")
        for k in state:
            v=objw["state"][k]
            if v.shape!=state[k].shape or not bool(torch.isfinite(v).all()):raise RuntimeError("META_BAD_PARAMETER")
            acc[k]+=v.double()*n
        weights+=n;logs.append(j)
    if seen!=set(range(args.workers)):raise RuntimeError("MISSING_META_RIVER_IDS")
    merged={k:(v/weights).to(state[k].dtype) for k,v in acc.items()}
    model=make_model();model.load_state_dict(merged,strict=True)
    valid_logits=model_logits(model,seq,val)
    true_v=torch.tensor([seq[i] for i in val])
    temperatures=[.5,.65,.8,1.,1.25,1.5,2.]
    t_star=min(temperatures,key=lambda t:float(F.cross_entropy(valid_logits[:,:c]/t,true_v)))
    test_logits=model_logits(model,seq,test)
    measured=metrics(test_logits,seq,test,c,t_star)
    random_base=metrics(model_logits(zero,seq,test),seq,test,c,1.)
    baselines=baseline(seq,tr,test,c)
    with torch.no_grad():
        last=torch.tensor([seq[-CONTEXT:]])
        logits=model(last)[0][0,-1,:c]
        probs=torch.softmax(logits/t_star,dim=-1)
    ranked=sorted(range(c),key=lambda i:-float(probs[i]))
    now=datetime.now(timezone.utc)
    snapshot_head=obj["source_head"]
    forecast={
        "schema":"janus.meta_next.prediction.v1",
        "source_head_sha":snapshot_head,
        "issued_at_utc":now.isoformat(),
        "predicts":"category of next non-excluded commit adding a JSON file after source_head",
        "label_definition":obj["event_definition"],
        "top3":[{"category":obj["labels"][i],"probability":round(float(probs[i]),7)} for i in ranked[:3]],
        "distribution":{obj["labels"][i]:round(float(probs[i]),7) for i in range(c)},
        "baseline_majority_category":obj["labels"][baselines["majority_label"]],
        "status":"SEALED_PRE_EVENT__NOT_YET_OBSERVED",
        "limitations":"Not the exact file, contents, or author; if a new commit appears during aggregation the prediction is stale and should not be counted prospective.",
    }
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    save(out/"meta_next_precommit.json",forecast)
    ck=out/"meta_next_candidate.pt"
    torch.save({"state":model.state_dict(),"cfg":CFG.to_dict(),"calibration_temperature":t_star,
                "source_sha256":sha(args.snapshot),"production_promotion":False},ck)
    result={
        "schema":"janus.meta_next.train_result.v1",
        "workers_verified":len(seen),"events_count":len(seq),
        "train_event_indices":len(tr),"valid_event_indices":len(val),"test_event_indices":len(test),
        "classes":obj["labels"],
        "architecture":"JanusTinyTransformer autoregressive last 16 JSON addition categories",
        "parameters":parameter_count(model),"temperature":t_star,
        "test_model":measured,"test_untrained":random_base,"test_baselines":baselines,
        "winner_beats_majority":measured["accuracy"]>baselines["majority_accuracy"],
        "winner_beats_markov":measured["accuracy"]>baselines["markov_accuracy"],
        "workers":sorted(logs,key=lambda x:x["worker_id"]),
        "meta_head":snapshot_head,
        "source_snapshot_sha256":sha(args.snapshot),
        "candidate_weights_sha256":sha(ck),
        "prospective_prediction":forecast,
        "production_promotion":False,
        "status":"EXPERIMENTAL_FORECAST__NO_ASSURANCE_OF_NEXT_JSON_PREDICTION",
    }
    save(out/"meta_report.json",result)
    with open(os.environ.get("GITHUB_STEP_SUMMARY","/dev/null"),"a") as h:
        h.write("## JANUS Meta Next - actual JSON addition history\n\n")
        h.write(f"- JSON-addition commits: {len(seq)}; workers: {len(seen)}\n")
        h.write(f"- Test: {len(test)}, model accuracy: **{measured['accuracy']:.4f}**, majority: **{baselines['majority_accuracy']:.4f}**, Markov: **{baselines['markov_accuracy']:.4f}**\n")
        h.write(f"- Next category: **{forecast['top3'][0]['category']}** (p≈{forecast['top3'][0]['probability']:.3f})\n")
        h.write("- No exact JSON content prediction. No production checkpoint modified.\n")
    print(json.dumps({k:v for k,v in result.items() if k!="workers"},indent=2))


def cli():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("snapshot")
    a.add_argument("--checkout",default="/tmp/janus_meta_hist")
    a.add_argument("--output",default="data/janus_meta_additions_snapshot.json")
    w=sub.add_parser("worker")
    w.add_argument("--snapshot",required=True)
    w.add_argument("--workers",type=int,default=8)
    w.add_argument("--worker",type=int,required=True)
    w.add_argument("--steps",type=int,default=260)
    w.add_argument("--budget",type=float,default=35)
    w.add_argument("--batch",type=int,default=64)
    w.add_argument("--output",required=True)
    o=sub.add_parser("aggregate")
    o.add_argument("--snapshot",required=True);o.add_argument("--input",required=True)
    o.add_argument("--workers",type=int,default=8);o.add_argument("--output",required=True)
    args=p.parse_args()
    if args.cmd=="snapshot":collect(args)
    elif args.cmd=="worker":worker(args)
    else:aggregate(args)


if __name__=="__main__":
    cli()
