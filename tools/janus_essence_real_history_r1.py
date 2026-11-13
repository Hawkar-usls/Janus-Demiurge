#!/usr/bin/env python3
"""ESSENCE real-history R1: sequential GitHub Actions failure forecasts.

Actual dated public CI records, not synthetic physics. Training and evaluation
run in DIFFERENT jobs. A reviewer sees a sealed chronological holdout that the
training job never downloads. No weight or gene may be promoted by this script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request

SCHEMA = "janus.essence.real_history_r1"
REPOS = ("Janus-Demiurge", "Janus_Genesis", "janus-meta-registry")
OWNER = "Hawkar-usls"
LOOKBACK = 8
SEED = 20261113


def canonical(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2) + "\n")


def read(path):
    p = Path(path)
    if p.stat().st_size > 4_000_000:
        raise ValueError("FILE_TOO_LARGE")
    obj = json.loads(p.read_text())
    if not isinstance(obj, dict):
        raise ValueError("OBJECT_REQUIRED")
    return obj


def iso_stamp(v):
    if not isinstance(v, str):
        raise ValueError("MISSING_TIMESTAMP")
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("NAIVE_TIME")
    return dt.astimezone(timezone.utc).isoformat()


def fetch_history(repo, token="", pages=3):
    if repo not in REPOS or pages not in (1, 2, 3):
        raise ValueError("UNTRUSTED_REPO_OR_PAGE")
    unique = {}
    hashes = []
    for page in range(1, pages + 1):
        url = (f"https://api.github.com/repos/{OWNER}/{repo}/actions/runs?"
               f"per_page=100&page={page}")
        headers = {"User-Agent": "JANUS-ESSENCE-Real-History-R1/1",
                   "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("GITHUB_RESPONSE_BOUNDS")
        hashes.append(hashlib.sha256(raw).hexdigest())
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
            raise ValueError("MALFORMED_GITHUB_HISTORY")
        for r in payload["workflow_runs"]:
            if (r.get("status") != "completed" or
                r.get("conclusion") not in ("success", "failure") or
                type(r.get("id")) is not int):
                continue
            unique[r["id"]] = {
                "run_id": r["id"], "timestamp": iso_stamp(r.get("created_at")),
                "label": 0 if r["conclusion"] == "success" else 1,
            }
        if len(payload["workflow_runs"]) < 100:
            break
    records = sorted(unique.values(), key=lambda z:(z["timestamp"], z["run_id"]))
    return records, hashes


def split_history(histories):
    """Separate chronological windows with eight-run embargo at BOTH boundaries."""
    sets = {k: [] for k in ("train", "validation", "holdout")}
    summary = []
    raw_ids = []
    for repo_idx, repo in enumerate(REPOS):
        records = histories[repo]
        if len(records) < 95:
            raise ValueError("TOO_FEW_REAL_RUNS")
        if len({r["run_id"] for r in records}) != len(records):
            raise ValueError("DUPLICATE_RUN")
        last_time = ""
        for r in records:
            if r["timestamp"] < last_time or r["label"] not in (0, 1):
                raise ValueError("INVALID_REAL_CHRONOLOGY")
            last_time = r["timestamp"]
            raw_ids.append([repo, r["run_id"], r["timestamp"], r["label"]])
        n = len(records)
        train_end, val_end = int(n * .62), int(n * .82)
        split_sizes = {k:0 for k in sets}
        for i in range(LOOKBACK, n):
            if i < train_end:
                which = "train"
            elif train_end + LOOKBACK <= i < val_end:
                which = "validation"
            elif i >= val_end + LOOKBACK:
                which = "holdout"
            else:
                continue
            window = records[i - LOOKBACK:i]
            x = [repo_idx + 2] + [z["label"] for z in window]
            sets[which].append({
                "repo": repo, "run_id": records[i]["run_id"],
                "timestamp": records[i]["timestamp"], "x": x,
                "y": records[i]["label"],
            })
            split_sizes[which] += 1
        summary.append({"repo": repo, "total_runs": n, "windows": split_sizes,
                        "train_cutoff": records[train_end - 1]["timestamp"],
                        "validation_cutoff": records[val_end - 1]["timestamp"]})
    if min(map(len, sets.values())) < 30:
        raise ValueError("INSUFFICIENT_TEMPORAL_SPLITS")
    ids = [r["repo"] + ":" + str(r["run_id"]) for rows in sets.values() for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("SPLIT_OVERLAP")
    provenance = {"schema": SCHEMA, "source": "GITHUB_ACTIONS_PUBLIC_RUNS",
                  "repositories": list(REPOS), "lookback": LOOKBACK,
                  "embargo": LOOKBACK, "summaries": summary,
                  "raw_run_sequence_sha256": digest(raw_ids),
                  "holdout_not_given_to_trainer": True,
                  "not_meta_registry_weight_training": True}
    psha = digest(provenance)
    return {k: {"schema": SCHEMA, "split": k, "provenance_sha256": psha,
                "rows": rows} for k, rows in sets.items()}, provenance


def prepare(folder, token=""):
    histories = {}
    api_pages = {}
    for repo in REPOS:
        histories[repo], api_pages[repo] = fetch_history(repo, token=token)
    splits, provenance = split_history(histories)
    provenance["api_response_page_sha256"] = api_pages
    provenance["current_repository_sha"] = os.environ.get("GITHUB_SHA")
    root = Path(folder)
    for split, obj in splits.items():
        write(root / (split + ".json"), obj)
    write(root / "provenance.json", provenance)
    print(json.dumps({k:len(v["rows"]) for k,v in splits.items()},sort_keys=True))


def load_split(path, which, psha=None):
    x = read(path)
    if x.get("schema") != SCHEMA or x.get("split") != which:
        raise ValueError("SPLIT_IDENTITY")
    if psha is not None and x.get("provenance_sha256") != psha:
        raise ValueError("SPLIT_SOURCE_MISMATCH")
    rows=x.get("rows")
    if not isinstance(rows,list) or not rows:
        raise ValueError("EMPTY_SPLIT")
    ids=set()
    for r in rows:
        if (r.get("repo") not in REPOS or type(r.get("run_id")) is not int or
            len(r.get("x",[])) != LOOKBACK+1 or
            r["x"][0] != REPOS.index(r["repo"])+2 or
            any(y not in (0,1) for y in r["x"][1:]) or r.get("y") not in (0,1) or
            not isinstance(r.get("timestamp"),str)):
            raise ValueError("UNTRUSTED_ROW")
        key=(r["repo"],r["run_id"])
        if key in ids: raise ValueError("DUPLICATE_SPLIT_ROW")
        ids.add(key)
    return x


def build_model(seed=SEED):
    import torch
    from janus_model.model import JanusModelConfig, JanusTinyTransformer
    torch.manual_seed(seed)
    cfg = JanusModelConfig(vocab_size=5,context_length=LOOKBACK+1,
                           d_model=16,n_heads=2,n_layers=1,ff_mult=2,dropout=0.0)
    return JanusTinyTransformer(cfg), cfg


def batch_tensors(rows):
    import torch
    return (torch.tensor([r["x"] for r in rows],dtype=torch.long),
            torch.tensor([r["y"] for r in rows],dtype=torch.long))


def score(model,rows):
    import torch
    import torch.nn.functional as F
    x,y=batch_tensors(rows)
    model.eval()
    with torch.no_grad():
        logits,_=model(x)
        logits=logits[:,-1,:2]
        p=torch.softmax(logits,dim=-1)[:,1]
        return {"n":len(rows),
                "brier":round(float(torch.mean((p-y.float())**2)),7),
                "nll":round(float(F.cross_entropy(logits,y)),7),
                "accuracy":round(float(torch.mean(((p>=0.5)==y.bool()).float())),7)}


def train(train_path,val_path,out_dir, *, steps=90):
    import torch
    import torch.nn.functional as F
    if not 16 <= steps <= 150:
        raise ValueError("UNBOUNDED_STEPS")
    torch.set_num_threads(1)
    tr=load_split(train_path,"train")
    val=load_split(val_path,"validation",tr["provenance_sha256"])
    train_ids={(r["repo"],r["run_id"]) for r in tr["rows"]}
    if train_ids.intersection((r["repo"],r["run_id"]) for r in val["rows"]):
        raise ValueError("TRAIN_VAL_LEAK")
    train_rows,val_rows=tr["rows"],val["rows"]
    tx,ty=batch_tensors(train_rows)
    result={"schema":SCHEMA,"provenance_sha256":tr["provenance_sha256"],
            "train_rows":len(train_rows),"validation_rows":len(val_rows),
            "train_positive_rate":sum(r["y"] for r in train_rows)/len(train_rows),
            "train_run_ids_sha256":digest(sorted(train_ids)),
            "model_family":"JanusTinyTransformer",
            "heldout_seen_by_trainer":False,"weights_production_authority":False,
            "variants":{}}
    root=Path(out_dir);root.mkdir(parents=True,exist_ok=True)
    for variant in ("baseline_no_replay","yaksa_bounded_replay"):
        model,cfg=build_model()
        optimizer=torch.optim.AdamW(model.parameters(),lr=0.007,weight_decay=0.001)
        generator=torch.Generator().manual_seed(SEED+33)
        replay=[]
        best=float("inf")
        best_state=None
        best_step=-1
        for i in range(steps):
            selected=torch.randint(len(train_rows),(48,),generator=generator)
            bx=tx[selected];by=ty[selected]
            if variant=="yaksa_bounded_replay" and replay and i%4==0:
                difficult=sorted(replay,key=lambda z:-z[0])[:8]
                bx=torch.cat((bx,torch.stack([z[1] for z in difficult])))
                by=torch.cat((by,torch.stack([z[2] for z in difficult])))
            model.train();optimizer.zero_grad(set_to_none=True)
            lg,_=model(bx)
            ex=F.cross_entropy(lg[:,-1,:2],by,reduction="none")
            loss=ex.mean()
            if not torch.isfinite(loss):
                raise ValueError("NONFINITE_LOSS")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True)
            optimizer.step()
            if any(not bool(torch.isfinite(p).all()) for p in model.parameters()):
                raise ValueError("NONFINITE_PARAMS")
            if variant=="yaksa_bounded_replay":
                hard=torch.topk(ex[:48].detach(),2).indices
                replay.extend((float(ex[j].detach()),bx[j].detach().clone(),
                               by[j].detach().clone()) for j in hard.tolist())
                replay=sorted(replay,key=lambda z:-z[0])[:64]
            if (i+1)%10==0:
                s=score(model,val_rows)
                if s["nll"]<best:
                    best=s["nll"];best_step=i+1
                    best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        if best_state is None:raise ValueError("NO_VALID_CHECKPOINT")
        model.load_state_dict(best_state)
        path=root/(variant+".pt")
        torch.save({"schema":SCHEMA,"variant":variant,
                    "provenance_sha256":tr["provenance_sha256"],
                    "config":cfg.to_dict(),"state":best_state,
                    "production_authority":False},path)
        result["variants"][variant]={"best_step":best_step,
                                     "validation":score(model,val_rows),
                                     "weights_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "replay_capacity":64 if variant.startswith("yaksa") else 0}
    write(root/"train_receipt.json",result)
    print(json.dumps({"train_rows":len(train_rows),"validation_rows":len(val_rows),
                      "variants":list(result["variants"])},sort_keys=True))


def baseline_stats(rows, prior):
    import math
    if not 0<=prior<=1:raise ValueError("BAD_PRIOR")
    def calc(probs):
        y=[r["y"] for r in rows]
        return {"n":len(y),
                "brier":round(sum((p-t)**2 for p,t in zip(probs,y))/len(y),7),
                "nll":round(-sum(t*math.log(max(p,1e-5))+
                               (1-t)*math.log(max(1-p,1e-5))
                               for p,t in zip(probs,y))/len(y),7),
                "accuracy":round(sum((p>=.5)==bool(t) for p,t in zip(probs,y))/len(y),7)}
    return {"train_prior":calc([max(.001,min(.999,prior))]*len(rows)),
            "persistence":calc([.9 if r["x"][-1] else .1 for r in rows])}


def verify(hold_path,train_receipt_path,weights_dir,out_path):
    import torch
    torch.set_num_threads(1)
    receipt=read(train_receipt_path)
    hold=load_split(hold_path,"holdout",receipt.get("provenance_sha256"))
    if receipt.get("heldout_seen_by_trainer") is not False or receipt.get("weights_production_authority") is not False:
        raise ValueError("TRAIN_RECEIPT_AUTHORITY")
    rows=hold["rows"]
    metrics={}
    for name in ("baseline_no_replay","yaksa_bounded_replay"):
        info=receipt["variants"][name]
        path=Path(weights_dir)/(name+".pt")
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info["weights_sha256"]:
            raise ValueError("CHECKPOINT_DIGEST")
        ck=torch.load(path,map_location="cpu",weights_only=True)
        if (ck.get("schema")!=SCHEMA or ck.get("variant")!=name or
            ck.get("provenance_sha256")!=hold["provenance_sha256"] or
            ck.get("production_authority") is not False):
            raise ValueError("CHECKPOINT_IDENTITY")
        model,cfg=build_model()
        if ck["config"]!=cfg.to_dict() or set(ck["state"])!=set(model.state_dict()):
            raise ValueError("MODEL_SHAPE")
        for key,value in ck["state"].items():
            if value.shape!=model.state_dict()[key].shape or not bool(torch.isfinite(value).all()):
                raise ValueError("BAD_WEIGHTS")
        model.load_state_dict(ck["state"],strict=True)
        metrics[name]=score(model,rows)
    prior=receipt["train_positive_rate"]
    baselines=baseline_stats(rows,prior)
    positives=sum(r["y"] for r in rows)
    minimums=len(rows)>=40 and positives>=5 and len(rows)-positives>=5
    yak=metrics["yaksa_bounded_replay"]
    plain=metrics["baseline_no_replay"]
    control=min(baselines["train_prior"]["brier"],baselines["persistence"]["brier"])
    eligible=(minimums and yak["brier"]+0.01<plain["brier"] and
              yak["brier"]+0.01<control and yak["nll"]<plain["nll"])
    result={"schema":SCHEMA,"heldout_provenance_sha256":hold["provenance_sha256"],
            "heldout_rows":len(rows),"heldout_failures":positives,
            "heldout_successes":len(rows)-positives,
            "heldout_run_ids_sha256":digest(sorted((r["repo"],r["run_id"]) for r in rows)),
            "baselines":baselines,"models":metrics,
            "gene_under_test":"Yaksa bounded replay versus same-model no-replay control",
            "source_reality":"OBSERVED_PUBLIC_GITHUB_ACTIONS_CONCLUSIONS",
            "history_scope":"LATEST_THREE_REPOS_NOT_WHOLE_META_REGISTRY",
            "gate":"RESEARCH_GAIN_OBSERVED_NEEDS_INDEPENDENT_REPLICATION" if eligible
                   else "HOLD_NO_INDEPENDENT_GENE_GAIN",
            "weights_updated_in_isolated_training":True,
            "production_promotion":False,"autonomous_code_installation":False,
            "full_autonomy_accepted":False}
    write(out_path,result)
    print(json.dumps({k:result[k] for k in ("heldout_rows","heldout_failures","gate")},sort_keys=True))


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("prepare");a.add_argument("--out",required=True)
    a=sub.add_parser("train");a.add_argument("--train",required=True);a.add_argument("--validation",required=True);a.add_argument("--out",required=True)
    a=sub.add_parser("verify");a.add_argument("--holdout",required=True);a.add_argument("--receipt",required=True);a.add_argument("--weights",required=True);a.add_argument("--out",required=True)
    args=p.parse_args()
    if args.action=="prepare":prepare(args.out,os.environ.get("GH_TOKEN",""))
    elif args.action=="train":train(args.train,args.validation,args.out)
    else:verify(args.holdout,args.receipt,args.weights,args.out)


if __name__=="__main__":
    main()
