#!/usr/bin/env python3
"""JANUS SENTINEL tiny causal Transformer for real GitHub Actions telemetry.

Purpose is research-only failure-risk ranking. It cannot authorize, reject or
expand a dispatch; core guard enforces exact peer targets/cooldown/state CAS.
Real training uses dated completed GitHub Actions runs; chronological train,
calibration, then test cohorts. Internal Brier comparison against a constant
baseline; no external lab proof. Does not learn from task/private code.

Shared checkpoint is immutable-by-Git-history and identically used by A,B.
C NEVER imports or depends on Torch: deterministic emergency recovery.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request

SCHEMA="janus.sentinel.transformer_checkpoint/1.0"
REPO="Hawkar-usls/Janus-Demiurge"
MAX_RUNS=800
SEQ=9
WIDTH=16
VOCAB=160
RESEARCH_STEPS=30
EVENTS={"push":0,"schedule":1,"workflow_dispatch":2,"pull_request":3,
        "repository_dispatch":3}
TEMPERATURES=(0.5,0.75,1.0,1.25,1.5,2.0,2.5,3.0,4.0)


def require(ok,error):
    if not ok:
        raise ValueError(error)


def canonical(o):
    return json.dumps(o,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def digest(o):
    return hashlib.sha256(canonical(o)).hexdigest()


def timepoint(s):
    require(type(s) is str and len(s)<50,"BAD_SOURCE_TIMESTAMP")
    val=datetime.fromisoformat(s.replace("Z","+00:00"))
    require(val.tzinfo is not None,"NAIVE_SOURCE_TIMESTAMP")
    return val.astimezone(timezone.utc)


def rows_from_github(payload,now):
    require(isinstance(payload,list) and len(payload)<=MAX_RUNS,
            "UNTRUSTED_GITHUB_DATA")
    out=[]
    seen=set()
    for x in payload:
        if not isinstance(x,dict):continue
        rid=x.get("id")
        wid=x.get("workflow_id")
        if not (type(rid) is int and type(wid) is int and rid>0 and wid>0
                and rid not in seen and x.get("head_branch")=="main"
                and x.get("status")=="completed"
                and x.get("conclusion") in ("success","failure")
                and x.get("event") in EVENTS and
                type(x.get("run_attempt",1)) is int and
                x.get("run_attempt",1)==1):
            continue
        try:
            start=timepoint(x["run_started_at"])
            end=timepoint(x["updated_at"])
            created=timepoint(x["created_at"])
        except (KeyError,ValueError,TypeError):
            continue
        sec=(end-start).total_seconds()
        if not (0<=sec<=6*3600 and created<=start<=end<=now):
            continue
        seen.add(rid)
        out.append({
            "id":rid,"workflow_id":wid,
            "event":x["event"],
            "created_at":created.isoformat(),
            "elapsed_s":round(sec,1),
            "label":int(x["conclusion"]=="failure"),
        })
    return sorted(out,key=lambda v:(v["created_at"],v["id"]))


def token_for_past(x):
    dur=0 if x["elapsed_s"]<30 else 1 if x["elapsed_s"]<120 else 2 if x["elapsed_s"]<600 else 3
    return 1+x["label"]*16+dur*4+EVENTS[x["event"]]


def token_for_target(x):
    # Workflow family is pre-run information; 64 fixed hash buckets.
    return 64+(int(x["workflow_id"])%64)


def examples(rows):
    require(isinstance(rows,list),"INVALID_SOURCE_ROWS")
    out=[]
    for i in range(8,len(rows)):
        history=rows[i-8:i]
        context=[token_for_past(r) for r in history]
        context.append(token_for_target(rows[i]))
        out.append((context,rows[i]["label"],rows[i]["id"],
                    rows[i]["created_at"]))
    return out


def net(torch):
    nn=torch.nn
    class TinySentinel(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok=nn.Embedding(VOCAB,WIDTH)
            self.pos=nn.Embedding(SEQ,WIDTH)
            self.attention=nn.MultiheadAttention(WIDTH,2,dropout=0.0,
                                                 batch_first=True)
            self.layernorm=nn.LayerNorm(WIDTH)
            self.fc=nn.Linear(WIDTH,1)
        def forward(self,idx):
            n=idx.shape[1]
            require(n==SEQ,"INVALID_SENTINEL_SEQUENCE")
            z=self.tok(idx)+self.pos(torch.arange(n,device=idx.device))[None,:,:]
            mask=torch.triu(torch.ones((n,n),dtype=torch.bool,
                                       device=idx.device),diagonal=1)
            attended,_=self.attention(z,z,z,attn_mask=mask,need_weights=False)
            z=self.layernorm(z+attended)
            return self.fc(z[:,-1,:]).flatten()
    return TinySentinel()


def brier(y,probs):
    return sum((float(a)-float(b))**2 for a,b in zip(y,probs))/len(y)


def ece(y,probs,bins=5):
    total=len(y)
    error=0.
    for i in range(bins):
        inds=[j for j,p in enumerate(probs) if
              (i/bins<=p<(i+1)/bins) or (i==bins-1 and p==1.)]
        if inds:
            a=sum(y[j] for j in inds)/len(inds)
            p=sum(probs[j] for j in inds)/len(inds)
            error+=(len(inds)/total)*abs(a-p)
    return error


def sigmoid(z):
    return 1/(1+math.exp(-max(-30,min(30,z))))


def score_probs(logits,t):
    return [sigmoid(float(z)/t) for z in logits]


def train(rows,*,epochs=RESEARCH_STEPS):
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(1731)
    dataset=examples(rows)
    n=len(dataset)
    require(n>=96,"INSUFFICIENT_REAL_ACTIONS_HISTORY")
    # Chronological and non-overlapping labels. Eight previous outcomes are
    # allowed as context, never the label of the current run.
    first=int(n*.65)
    second=int(n*.82)
    require(first>=60 and second-first>=16 and n-second>=16,
            "INVALID_CHRONOLOGICAL_SPLITS")
    train_rows=dataset[:first]
    calib_rows=dataset[first:second]
    test_rows=dataset[second:]
    label_train=[v[1] for v in train_rows]
    require(sum(label_train)>=5 and len(label_train)-sum(label_train)>=5,
            "INSUFFICIENT_FAILURES_OR_SUCCESSES")
    def arrays(block):
        return (torch.tensor([v[0] for v in block],dtype=torch.long),
                torch.tensor([v[1] for v in block],dtype=torch.float32))
    x,y=arrays(train_rows)
    m=net(torch)
    optim=torch.optim.AdamW(m.parameters(),lr=0.002,weight_decay=.001)
    positive=min(8.0,(len(label_train)-sum(label_train))/sum(label_train))
    for epoch in range(epochs):
        m.train()
        optim.zero_grad()
        logits=m(x)
        loss=torch.nn.functional.binary_cross_entropy_with_logits(
              logits,y,pos_weight=torch.tensor(positive))
        require(bool(torch.isfinite(loss)),"NONFINITE_TRANSFORMER_TRAINING")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(m.parameters(),1.0)
        optim.step()
    m.eval()
    with torch.inference_mode():
        cx,cy=arrays(calib_rows)
        tx,ty=arrays(test_rows)
        cl=m(cx).tolist()
        tl=m(tx).tolist()
    cy=[int(v[1]) for v in calib_rows]
    ty=[int(v[1]) for v in test_rows]
    temperature=min(TEMPERATURES,key=lambda t:brier(cy,score_probs(cl,t)))
    calibrated=score_probs(tl,temperature)
    prior=(sum(label_train)+1)/(len(label_train)+2)
    benchmark=brier(ty,[prior]*len(ty))
    test_brier=brier(ty,calibrated)
    test_ece=ece(ty,calibrated)
    status=("RESEARCH_INTERNAL_HOLDOUT_GAIN" if
            test_brier+0.001<benchmark and test_ece<=0.2 else
            "RESEARCH_TRAINED_NO_PROSPECTIVE_GAIN")
    weights={name:value.detach().cpu().tolist()
             for name,value in sorted(m.state_dict().items())}
    meta={
        "schema":SCHEMA,"model_type":"CAUSAL_ATTENTION_SHARED_A_B",
        "status":status,"torch_runtime":"2.5.1_cpu",
        "model_width":WIDTH,"sequence_len":SEQ,"vocab":VOCAB,
        "weights":weights,
        "source":"REAL_COMPLETED_GITHUB_ACTIONS",
        "first_train_id":train_rows[0][2],
        "last_train_id":train_rows[-1][2],
        "last_calibration_id":calib_rows[-1][2],
        "last_test_id":test_rows[-1][2],
        "last_test_utc":test_rows[-1][3],
        "cohort_sizes":{"train":len(train_rows),
                        "calibration":len(calib_rows),
                        "chronological_test":len(test_rows)},
        "failure_count_train":sum(label_train),
        "temperature":temperature,
        "source_rows":len(rows),
        "train_epochs":epochs,
        "test_brier":test_brier,
        "constant_prior_brier":benchmark,
        "test_ece":test_ece,
        "research_internal_gain":status=="RESEARCH_INTERNAL_HOLDOUT_GAIN",
        "production_authority":False,
        "dispatch_authority":False,
        "external_independent_validation":False,
    }
    meta["checkpoint_sha256"]=digest(meta)
    return meta


def check_checkpoint(data):
    require(isinstance(data,dict) and data.get("schema")==SCHEMA and
            data.get("model_type")=="CAUSAL_ATTENTION_SHARED_A_B" and
            data.get("model_width")==WIDTH and
            data.get("sequence_len")==SEQ and
            data.get("production_authority") is False and
            data.get("dispatch_authority") is False and
            type(data.get("temperature")) in (int,float) and
            0.25<=data["temperature"]<=4.0 and
            data.get("checkpoint_sha256")==digest({
                 k:v for k,v in data.items() if k!="checkpoint_sha256"}),
            "UNTRUSTED_RESEARCH_TRANSFORMER_CHECKPOINT")
    return data


def score_checkpoint(data,history,target_workflow_id):
    import torch
    torch.set_num_threads(1)
    check_checkpoint(data)
    require(type(target_workflow_id) is int and target_workflow_id>0 and
            isinstance(history,list) and len(history)>=8,
            "INVALID_SENTINEL_PREDICTION_CONTEXT")
    m=net(torch)
    state=m.state_dict()
    tensors=data.get("weights")
    require(set(tensors)==set(state),"RESEARCH_TENSOR_SCHEMA_MISMATCH")
    converted={}
    for name,v in state.items():
        z=torch.tensor(tensors[name],dtype=v.dtype)
        require(z.shape==v.shape and bool(torch.isfinite(z).all()),
                "UNTRUSTED_TRANSFORMER_WEIGHTS")
        converted[name]=z
    m.load_state_dict(converted,strict=True)
    m.eval()
    context=[token_for_past(v) for v in history[-8:]] + [
             64+(target_workflow_id%64)]
    with torch.inference_mode():
        logit=float(m(torch.tensor([context],dtype=torch.long))[0])
    value=sigmoid(logit/data["temperature"])
    require(math.isfinite(value) and 0<=value<=1,
            "TRANSFORMER_NONFINITE_RISK")
    return value


def read_research_score(path):
    """Read and verify checkpoint metadata only; core never grants model power."""
    p=Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    require(p.stat().st_size<=1000000 and not p.is_symlink(),
            "UNSAFE_SENTINEL_MODEL_METADATA")
    meta=check_checkpoint(json.loads(p.read_text("utf-8")))
    return {"status":meta["status"],
            "checkpoint_sha256":meta["checkpoint_sha256"],
            "chronological_test_brier":meta["test_brier"],
            "baseline_brier":meta["constant_prior_brier"],
            "test_ece":meta["test_ece"],
            "temperature":meta["temperature"],
            "calibrated":True,
            "model_has_dispatch_authority":False}


def fetch_real(token,maxpages=6):
    require(type(token) is str and 16<len(token)<4096,"MISSING_GITHUB_TOKEN")
    out=[]
    for page in range(1,maxpages+1):
        path=(f"https://api.github.com/repos/{REPO}/actions/runs"
              f"?branch=main&per_page=100&page={page}")
        headers={
          "Authorization":"Bearer "+token,
          "Accept":"application/vnd.github+json",
          "X-GitHub-Api-Version":"2022-11-28",
          "User-Agent":"JANUS-SENTINEL-Transformer/1.0",
        }
        with urllib.request.urlopen(urllib.request.Request(path,headers=headers),
                                    timeout=18) as response:
            chunk=response.read(1_000_001)
            require(len(chunk)<=1_000_000,"TOO_MANY_GITHUB_RUNS_BYTES")
            value=json.loads(chunk)
        require(isinstance(value,dict) and
                isinstance(value.get("workflow_runs"),list) and
                len(value["workflow_runs"])<=100,"UNTRUSTED_RUNS_PAGE")
        out.extend(value["workflow_runs"])
        if len(value["workflow_runs"])<100:break
    return rows_from_github(out,datetime.now(timezone.utc))


def predict_recent_risk(path,observed,token):
    """Actual A/B inference on same saved network; no dispatch permissions."""
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size<=1000000,"UNSAFE_NEURAL_CHECKPOINT")
    meta=check_checkpoint(json.loads(path.read_text("utf-8")))
    history=fetch_real(token,maxpages=1)
    require(len(history)>=8,"NOT_ENOUGH_CURRENT_GITHUB_RUN_HISTORY")
    result={}
    for role in ("A","B","C","WORKER"):
        runs=observed.get(role,[])
        if not runs or type(runs[0].get("workflow_id")) is not int:
            result[role]={"status":"INSUFFICIENT_WORKFLOW_HISTORY"}
            continue
        risk=score_checkpoint(meta,history[-8:],runs[0]["workflow_id"])
        result[role]={"status":"RESEARCH_CALIBRATED_FORECAST",
                      "risk_of_next_workflow_failure":round(risk,6),
                      "checkpoint_sha256":meta["checkpoint_sha256"],
                      "no_dispatch_authority":True}
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--previous",default="")
    args=p.parse_args()
    previous=None
    if args.previous and Path(args.previous).is_file():
        previous=check_checkpoint(json.loads(Path(args.previous).read_text()))
    rows=fetch_real(os.getenv("GH_TOKEN",""))
    candidate=train(rows)
    if previous is not None:
        # Never let a periodically retrained model replace a parent using
        # an already-seen/older test window. Freeze it only as a research
        # candidate. A truly prospective independent selection gate is
        # needed for future activation.
        parent_test=timepoint(previous["last_test_utc"])
        child_test=timepoint(candidate["last_test_utc"])
        candidate["parent_checkpoint_sha256"]=previous["checkpoint_sha256"]
        candidate["replaces_previous"]=False
        candidate["prospective_after_parent"]=child_test>parent_test
        candidate["status"]="RESEARCH_RETRAINED_CANDIDATE_NOT_ADMITTED"
        candidate["checkpoint_sha256"]=digest({
            k:v for k,v in candidate.items() if k!="checkpoint_sha256"})
    dest=Path(args.out)
    require(not dest.exists(),"IMMUTABLE_TRANSFORMER_REPORT_REQUIRED")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(candidate,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":candidate["status"],
                      "source_rows":len(rows),
                      "test_brier":candidate["test_brier"],
                      "baseline_brier":candidate["constant_prior_brier"],
                      "temperature":candidate["temperature"],
                      "checkpoint_sha256":candidate["checkpoint_sha256"],
                      "replaces_previous":candidate.get("replaces_previous",False)},
                     sort_keys=True))


if __name__=="__main__":
    main()
