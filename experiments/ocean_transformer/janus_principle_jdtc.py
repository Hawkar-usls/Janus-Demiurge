#!/usr/bin/env python3
"""JANUS Principle / JDTC: two-phase history denoising + next-JSON forecasting.

Real chronological Git history; original JANUS Tiny Transformer; no future
labels available during training. Denoising uses masked past tokens only. The
second phase predicts the NEXT added JSON category using only preceding ones.
Independent future RNG and Retro Lab evaluation remain separate experiments.
Research-only; never alters production models or security-sensitive files.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time

import torch
import torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from janus_model.model import JanusTinyTransformer, JanusModelConfig, parameter_count
import meta_next_train as source

torch.set_num_threads(1)
CONTEXT=16
SEED=2026110607
CFG=JanusModelConfig(vocab_size=48,context_length=CONTEXT,d_model=48,
                     n_heads=4,n_layers=2,ff_mult=2,dropout=0.)
MASK_LEVELS=(.1,.25,.4,.6)
DEN_LAMBDA=.35
NEXT_LAMBDA=.65
TEMPERATURES=(.75,1.,1.25,1.5,2.)
BLENDS=(0.,.25,.5,.75,1.)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path,obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split(obj):
    seq,train,val,test=source.split(obj)
    nclass=len(obj["labels"])
    if nclass<2 or nclass>=CFG.vocab_size:
        raise RuntimeError("INVALID_CLASS_COUNT")
    if min(len(train),len(val),len(test))<40:
        raise RuntimeError("INSUFFICIENT_CHRONOLOGY")
    if max(seq)>=nclass:
        raise RuntimeError("TOKEN_LABEL_OUT_OF_RANGE")
    return seq,train,val,test,nclass


def model():
    torch.manual_seed(SEED)
    return JanusTinyTransformer(CFG)


def windows(seq,ids):
    x=torch.tensor([seq[i-CONTEXT:i] for i in ids],dtype=torch.long)
    y=torch.tensor([seq[i] for i in ids],dtype=torch.long)
    return x,y


def corrupt(x,mask_token,rate,rng):
    # Independent corruption from target / future RNG: no shared state.
    masked=torch.tensor([[rng.random()<rate for _ in range(CONTEXT)]
                         for _ in range(len(x))],dtype=torch.bool)
    for row in masked:
        if not bool(row.any()):
            row[rng.randrange(CONTEXT)]=True
    c=x.clone()
    c[masked]=mask_token
    return c,masked


def train_worker(args):
    start=time.monotonic()
    obj=load(args.snapshot)
    seq,train,val,test,c=split(obj)
    if not 0<=args.worker<args.workers or args.workers<1:
        raise RuntimeError("INVALID_WORKER")
    # Identical real historical training split across rivers; different bootstrap
    # samples and corruption kernels. No double-count of independent history.
    rng=random.Random(0x9011+args.worker*197)
    noise=MASK_LEVELS[args.worker%len(MASK_LEVELS)]
    net=model()
    opt=torch.optim.AdamW(net.parameters(),lr=.003,weight_decay=.0005)
    total=0
    running_loss=0
    for step in range(args.steps):
        if total>=70 and time.monotonic()-start>args.budget:
            break
        ids=rng.choices(train,k=args.batch)
        x,y=windows(seq,ids)
        corrupt_x,m=corrupt(x,c,noise,rng)
        net.train()
        opt.zero_grad(set_to_none=True)
        clean_logits,_=net(x)
        corrupted_logits,_=net(corrupt_x)
        next_loss=F.cross_entropy(clean_logits[:,-1,:c],y)
        masked_loss=F.cross_entropy(corrupted_logits[:,:,:c][m],x[m])
        loss=NEXT_LAMBDA*next_loss+DEN_LAMBDA*masked_loss
        if not torch.isfinite(loss):
            raise RuntimeError("NONFINITE_TRAINING_LOSS")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(),1.)
        opt.step()
        running_loss+=float(loss.detach())
        total+=1
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ck=out/"weights.pt"
    torch.save({"state":{k:v.detach().cpu() for k,v in net.state_dict().items()},
                "config":CFG.to_dict(),"worker":args.worker,
                "snapshot_sha256":sha(args.snapshot),"train_indices":len(train)},ck)
    rec={
        "schema":"janus.principle.jdtc.river.v1","worker":args.worker,
        "workers":args.workers,"noise_rate":noise,
        "training_instances_unique":len(train),
        "training_batches_sampled_with_replacement":total,
        "training_token_exposures":total*args.batch,
        "mean_joint_training_loss":round(running_loss/total,6),
        "snapshot_sha256":sha(args.snapshot),
        "weights_sha256":sha(ck),
        "seconds":round(time.monotonic()-start,3),
        "model_parameters":parameter_count(net),
        "independence_note":"40 workers share chronological training data, only bootstraps/noise are independent; NOT 40 independent trials"
    }
    dump(out/"river.json",rec)
    print(json.dumps(rec,indent=2))


@torch.no_grad()
def next_logits(net,seq,inds,c):
    net.eval()
    out=[]
    for start in range(0,len(inds),256):
        x,_=windows(seq,inds[start:start+256])
        logits,_=net(x)
        out.append(logits[:,-1,:c])
    return torch.cat(out)


@torch.no_grad()
def denoise_scores(net,seq,inds,c,rate=.4,seed=90093):
    # Fixed independent corruption only after models have finished training.
    rng=random.Random(seed)
    count=correct=0
    loss_sum=0.
    pred_all=[]
    truth_all=[]
    prior=Counter(seq[:min(inds)])
    # Training-only prior must be supplied separately by the aggregator,
    # so don't use this local convenience counter for scored baselines.
    net.eval()
    for pos in range(0,len(inds),256):
        x,_=windows(seq,inds[pos:pos+256])
        noisy,m=corrupt(x,c,rate,rng)
        logits,_=net(noisy)
        selected=logits[:,:,:c][m]
        originals=x[m]
        count+=len(originals)
        correct+=int((selected.argmax(-1)==originals).sum())
        loss_sum+=float(F.cross_entropy(selected,originals,reduction="sum"))
        pred_all.extend(selected.argmax(-1).tolist())
        truth_all.extend(originals.tolist())
    if count==0:
        raise RuntimeError("NO_DENOISE_TEST_MASKS")
    return {"n_masked":count,"accuracy":round(correct/count,6),
            "cross_entropy":round(loss_sum/count,6),
            "truth":truth_all}


def prediction_metrics(probs,truth):
    probs=probs.clamp_min(1e-12)
    truth=torch.as_tensor(truth,dtype=torch.long)
    c=probs.size(-1)
    return {
        "n":len(truth),
        "accuracy":round(float((probs.argmax(-1)==truth).float().mean()),6),
        "top3_accuracy":round(float((probs.topk(min(3,c),-1).indices==truth[:,None]).any(-1).float().mean()),6),
        "log_loss":round(float(F.nll_loss(probs.log(),truth)),6),
        "multiclass_brier":round(float(((probs-F.one_hot(truth,c).float())**2).sum(-1).mean()),6)
    }


def train_distribution(seq,train,c):
    counts=Counter(seq[i] for i in train)
    weights=torch.tensor([counts[k]+1 for k in range(c)],dtype=torch.float32)
    return weights/weights.sum()


def aggregate(args):
    obj=load(args.snapshot)
    seq,tr,va,te,c=split(obj)
    files=sorted(Path(args.input).glob("*/river.json"))
    if len(files)!=args.workers:
        raise RuntimeError("FAIL_CLOSED_MISSING_RIVERS")
    raw=model()
    state=raw.state_dict()
    agg={k:torch.zeros_like(v,dtype=torch.float64) for k,v in state.items()}
    seen=set()
    receipts=[]
    n=0
    for f in files:
        r=load(f)
        wid=r["worker"]
        if not 0<=wid<args.workers or wid in seen or r["workers"]!=args.workers or r["snapshot_sha256"]!=sha(args.snapshot):
            raise RuntimeError("MISMATCHED_RIVER")
        if r["noise_rate"]!=MASK_LEVELS[wid%len(MASK_LEVELS)]:
            raise RuntimeError("CORRUPTION_KERNEL_DRIFT")
        seen.add(wid)
        p=f.parent/"weights.pt"
        if sha(p)!=r["weights_sha256"]:
            raise RuntimeError("FAILED_WORKER_SHA_CHECK")
        checkpoint=torch.load(p,map_location="cpu",weights_only=True)
        if checkpoint["config"]!=CFG.to_dict() or checkpoint["worker"]!=wid or checkpoint["snapshot_sha256"]!=sha(args.snapshot):
            raise RuntimeError("WEIGHT_IDENTITY_FAILED")
        st=checkpoint["state"]
        if set(st)!=set(state):
            raise RuntimeError("MODEL_KEY_MISMATCH")
        weight=checkpoint["train_indices"]
        if weight!=len(tr):
            raise RuntimeError("BAD_TRAINING_PROVENANCE")
        for k in state:
            v=st[k]
            if v.shape!=state[k].shape or v.dtype!=state[k].dtype or not torch.isfinite(v).all():
                raise RuntimeError("BAD_WORKER_TENSOR")
            agg[k]+=v.double()*weight
        n+=weight
        receipts.append(r)
    if seen!=set(range(args.workers)):
        raise RuntimeError("MISSING_WORKERS")
    ocean=model()
    ocean.load_state_dict({k:(v/n).to(state[k].dtype) for k,v in agg.items()},strict=True)
    base=train_distribution(seq,tr,c)
    validation_logits=next_logits(ocean,seq,va,c)
    yval=torch.tensor([seq[i] for i in va],dtype=torch.long)
    best=(float("inf"),1.,0.)
    for temp in TEMPERATURES:
        probs=torch.softmax(validation_logits/temp,-1)
        for mix in BLENDS:
            blended=mix*probs+(1-mix)*base
            loss=float(F.nll_loss(blended.clamp_min(1e-12).log(),yval))
            if loss<best[0]:
                best=(loss,temp,mix)
    _,temp,mix=best
    ytest=[seq[i] for i in te]
    logits=next_logits(ocean,seq,te,c)
    probs_raw=torch.softmax(logits,dim=-1)
    probs_val_cal=mix*torch.softmax(logits/temp,dim=-1)+(1-mix)*base
    base_probs=base.repeat(len(te),1)

    clean_model=prediction_metrics(probs_raw,ytest)
    calibrated=prediction_metrics(probs_val_cal,ytest)
    freq=prediction_metrics(base_probs,ytest)
    initial=prediction_metrics(torch.softmax(next_logits(raw,seq,te,c),dim=-1),ytest)
    denoised=denoise_scores(ocean,seq,te,c)
    untrained_denoised=denoise_scores(raw,seq,te,c)
    den_baseline_mode=int(base.argmax())
    den_baseline_accuracy=round(sum(x==den_baseline_mode for x in denoised["truth"])/len(denoised["truth"]),6)

    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ck=out/"jdtc_candidate.pt"
    torch.save({"config":CFG.to_dict(),"state":ocean.state_dict(),
                "snapshot_sha256":sha(args.snapshot),"calibration_temperature":temp,
                "validation_model_blend":mix,"production_promotion":False},ck)
    # Prediction is a research candidate. Validate later whether the first
    # new JSON commit followed issuance, not merely the frozen source HEAD.
    with torch.no_grad():
        x=torch.tensor([seq[-CONTEXT:]],dtype=torch.long)
        z=ocean(x)[0][0,-1,:c]
        final=mix*torch.softmax(z/temp,dim=-1)+(1-mix)*base
        ranked=sorted(range(c),key=lambda i:-float(final[i]))
    prospective={
        "schema":"janus.principle.jdtc.next_registry_precommit.v1",
        "issued_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_meta_head":obj["source_head"],
        "source_meta_latest_addition":obj["events"][-1]["timestamp"],
        "source_snapshot_sha256":sha(args.snapshot),
        "model_checkpoint_sha256":sha(ck),
        "prediction_target":"class of first new eligible JSON-addition commit AFTER the issued_at time",
        "top3":[{"class":obj["labels"][i],"probability":round(float(final[i]),7)} for i in ranked[:3]],
        "predicted_top1":obj["labels"][ranked[0]],
        "status":"CANDIDATE_FUTURE_UNOBSERVED",
        "warnings":["If an eligible JSON addition happened after source HEAD but before prediction issuance, do not score it as prospective.","Other-category lumping can create artificially high top1 accuracy.","No actual backwards-time channel."]
    }
    dump(out/"next_meta_precommit.json",prospective)
    result={
        "schema":"janus.principle.jdtc.ocean.v1",
        "source":"real public JANUS Meta Registry JSON addition commit sequence",
        "source_head":obj["source_head"],
        "source_snapshot_sha256":sha(args.snapshot),
        "total_json_addition_events":len(seq),
        "class_count":c,
        "training_target_events":len(tr),
        "validation_target_events":len(va),
        "holdout_target_events":len(te),
        "model_class":"JanusTinyTransformer", "parameter_count":parameter_count(ocean),
        "two_phases":{
            "phase_one":"reconstruct masked PAST category tokens from causally preceding history",
            "phase_two":"predict NEXT JSON-addition category, with validation-calibrated mix",
            "history_corruption_rates":MASK_LEVELS,
            "phase_one_loss_fraction":DEN_LAMBDA,
            "phase_two_loss_fraction":NEXT_LAMBDA
        },
        "workers_expected":args.workers, "workers_integrity_verified":len(seen),
        "receipts":sorted(receipts,key=lambda x:x["worker"]),
        "holdout_phase_one_denoise":{
            "initial_untrained":{"accuracy":untrained_denoised["accuracy"],"cross_entropy":untrained_denoised["cross_entropy"]},
            "trained":{"accuracy":denoised["accuracy"],"cross_entropy":denoised["cross_entropy"]},
            "majority_baseline_accuracy":den_baseline_accuracy,
            "masked_targets":denoised["n_masked"],
            "retrospective_only":True
        },
        "holdout_phase_two_next_event":{
            "initial_untrained":initial,
            "trained_raw":clean_model,
            "validation_calibrated":calibrated,
            "train_only_frequency_baseline":freq,
            "validation_temperature":temp,
            "validation_model_blend":mix,
            "beats_baseline_logloss":calibrated["log_loss"]<freq["log_loss"],
            "beats_baseline_accuracy":calibrated["accuracy"]>freq["accuracy"]
        },
        "model_candidate_checkpoint_sha256":sha(ck),
        "prospective_forecast":prospective,
        "actual_independent_future_random_bytes_predicted":False,
        "physical_backward_channel_detected":False,
        "promotion_decision":"HOLD_DEVELOPMENT_ONLY",
        "cautions":[
            "Masked denoising measures reconstruction of already-recorded past, not prediction of future.",
            "40 River workers resample overlapping historical windows; worker count is not independent evidence count.",
            "Chronological holdout comes from the same Meta Registry; classifier has a broad OTHER class.",
            "Calibration is selected on validation only; final holdout is not used for fitting.",
            "A future-random target remains chance-level without a real physical B-to-A interface."
        ]
    }
    dump(out/"jdtc_report.json",result)
    with open(os.environ.get("GITHUB_STEP_SUMMARY","/dev/null"),"a") as f:
        f.write("## The Janus Principle — 40-river dual-phase audit\n\n")
        f.write(f"- Workers **{len(seen)}/{args.workers}**, distinct historical JSON events **{len(seq)}**\n")
        f.write(f"- Phase I masked past: learned CE **{denoised['cross_entropy']}** vs untrained **{untrained_denoised['cross_entropy']}**\n")
        f.write(f"- Phase I accuracy **{denoised['accuracy']}** vs baseline majority **{den_baseline_accuracy}**\n")
        f.write(f"- Phase II future-event heldout logloss **{calibrated['log_loss']}** vs frequency **{freq['log_loss']}**\n")
        f.write(f"- Phase II validation selected model mix **{mix}**\n")
        f.write("- Production: **NOT PROMOTED**. Retrocausal channel: **NOT ESTABLISHED**.\n")
    print(json.dumps({k:v for k,v in result.items() if k!="receipts"},indent=2))


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    w=sub.add_parser("worker")
    w.add_argument("--snapshot",required=True)
    w.add_argument("--worker",type=int,required=True)
    w.add_argument("--workers",type=int,default=40)
    w.add_argument("--steps",type=int,default=240)
    w.add_argument("--batch",type=int,default=32)
    w.add_argument("--budget",type=float,default=38)
    w.add_argument("--output",required=True)
    a=sub.add_parser("aggregate")
    a.add_argument("--snapshot",required=True)
    a.add_argument("--workers",type=int,default=40)
    a.add_argument("--input",required=True)
    a.add_argument("--output",required=True)
    args=p.parse_args()
    if args.mode=="worker":train_worker(args)
    else:aggregate(args)


if __name__=="__main__":
    main()
