#!/usr/bin/env python3
"""ESSENCE v1.9 / GRADIRNYA: bounded real-gradient offspring and isolated verifier.

Only public dated JSON key structures are features. Training never receives the
test partition. Real PyTorch weights are updated for two generations, with a
validation-only survival decision and complete inherited state/receipts. The
sealed test is opened once by a different CI job; not an external laboratory.
No trained or quantized checkpoint can promote a production model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import torch
import torch.nn.functional as F
from tools import janus_essence_real_json_train as r

torch.set_num_threads(1)
SCHEMA="janus.essence.gradirnya/1.9"
BUNDLE="janus.essence.gradirnya_split/1.9"
LINEAGE="janus.essence.gradirnya_lineage/1.9"
SHA=re.compile(r"^[0-9a-f]{40}$")
GENERATIONS=2
MAX_STEPS=80

def sha(raw): return hashlib.sha256(raw).hexdigest()
def seal(obj): return sha(r.canonical(obj))
def stable_state(state):
    dig=hashlib.sha256()
    for name,v in sorted(state.items()):
        if not isinstance(name,str) or not isinstance(v,torch.Tensor) or not v.is_floating_point() or not torch.isfinite(v).all():
            raise ValueError("UNTRUSTED_WEIGHT_TENSOR")
        t=v.detach().cpu().contiguous()
        dig.update(name.encode()+b"\0"+str(tuple(t.shape)).encode()+b"\0")
        dig.update(t.numpy().tobytes())
    return dig.hexdigest()

def clone_state(model):
    return {k:v.detach().cpu().clone() for k,v in model.state_dict().items()}

def atomic_json(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError("IMMUTABLE_RESEARCH_RECEIPT")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")

def read_json(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>5_000_000:
        raise ValueError("UNTRUSTED_SPLIT_FILE")
    return json.loads(p.read_text(),parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))

def split_packet(kind,rows,source_sha,descriptor_sha):
    if kind not in ("train","validation","holdout") or not SHA.fullmatch(source_sha):
        raise ValueError("BAD_SPLIT_OR_SOURCE")
    body={"schema":BUNDLE,"kind":kind,"source_commit":source_sha,
          "dataset_sha256":descriptor_sha,"rows":rows}
    body["packet_sha256"]=seal(body)
    return body

def check_packet(packet,kind,source_sha,descriptor_sha=None):
    if (not isinstance(packet,dict) or packet.get("schema")!=BUNDLE
        or packet.get("kind")!=kind or packet.get("source_commit")!=source_sha
        or descriptor_sha is not None and packet.get("dataset_sha256")!=descriptor_sha
        or packet.get("packet_sha256")!=seal({k:v for k,v in packet.items() if k!="packet_sha256"})):
        raise ValueError("SPLIT_DIGEST_OR_SOURCE_MISMATCH")
    rows=packet.get("rows")
    if not isinstance(rows,list) or not 12<=len(rows)<=4200:raise ValueError("INVALID_SPLIT_SIZE")
    ids=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"date","identity","x","label"}:raise ValueError("INVALID_ROW_SHAPE")
        if (not isinstance(row["date"],str) or not re.fullmatch(r"20\d\d-\d\d-\d\d",row["date"])
            or not isinstance(row["identity"],str) or not re.fullmatch(r"[0-9a-f]{64}",row["identity"])
            or row["identity"] in ids or type(row["label"]) is not int or not 0<=row["label"]<len(r.LABELS)
            or not isinstance(row["x"],list) or len(row["x"])!=r.CONFIG.context_length
            or any(type(v) is not int or not 0<=v<256 for v in row["x"])):
            raise ValueError("INVALID_SPLIT_ROW")
        ids.add(row["identity"])
    return rows

def prepare(data_root,source_sha,out):
    if not SHA.fullmatch(source_sha):raise ValueError("UNPINNED_REGISTRY_COMMIT")
    groups,desc=r.collect(data_root)
    root=Path(out)
    if root.exists():raise FileExistsError("PREPARATION_ALREADY_EXISTS")
    packets={k:split_packet(k,groups[k],source_sha,desc["dataset_sha256"]) for k in ("train","validation","holdout")}
    for k in packets:
        check_packet(packets[k],k,source_sha,desc["dataset_sha256"])
    manifest={"schema":SCHEMA,"source_commit":source_sha,
              "dataset_sha256":desc["dataset_sha256"],
              "split_sha256":{k:v["packet_sha256"] for k,v in packets.items()},
              "split_sizes":{k:len(v["rows"]) for k,v in packets.items()},
              "split_dates":{k:[min(row["date"] for row in v["rows"]),max(row["date"] for row in v["rows"])] for k,v in packets.items()},
              "test_data_in_training_artifact":False,"external_custodian":False,
              "training_task":"PUBLIC_META_REGISTRY_KEY_CLASSIFICATION",
              "production_authority":False}
    if not (manifest["split_dates"]["train"][1]<manifest["split_dates"]["validation"][0]
        <manifest["split_dates"]["validation"][1]<manifest["split_dates"]["holdout"][0]):
        raise ValueError("CHRONOLOGICAL_SPLIT_NOT_STRICT")
    manifest["receipt_sha256"]=seal(manifest)
    for k,p in packets.items():atomic_json(root/(k+".json"),p)
    atomic_json(root/"manifest.json",manifest)
    return manifest

def validate_manifest(m,source_sha):
    if (not isinstance(m,dict) or m.get("schema")!=SCHEMA or m.get("source_commit")!=source_sha
        or m.get("receipt_sha256")!=seal({k:v for k,v in m.items() if k!="receipt_sha256"})
        or m.get("production_authority") is not False
        or m.get("test_data_in_training_artifact") is not False
        or m.get("external_custodian") is not False):
        raise ValueError("UNTRUSTED_SPLIT_MANIFEST")
    return m

def train(cell,train_packet,val_packet,manifest,out,steps=40):
    if type(cell) is not int or not 0<=cell<6 or type(steps) is not int or not 20<=steps<=MAX_STEPS:
        raise ValueError("BOUNDED_MICROCORE_TRAINING_ONLY")
    source=manifest["source_commit"]
    validate_manifest(manifest,source)
    train_rows=check_packet(train_packet,"train",source,manifest["dataset_sha256"])
    val_rows=check_packet(val_packet,"validation",source,manifest["dataset_sha256"])
    if (train_packet["packet_sha256"]!=manifest["split_sha256"]["train"]
        or val_packet["packet_sha256"]!=manifest["split_sha256"]["validation"]
        or {x["identity"] for x in train_rows}&{x["identity"] for x in val_rows}
        or max(x["date"] for x in train_rows)>=min(x["date"] for x in val_rows)):
        raise ValueError("TRAIN_VALIDATION_LEAK")
    model=r.model_for(cell)
    initial=clone_state(model)
    initial_sha=stable_state(initial)
    parent_eval=r.evaluate(model,val_rows)
    x,y=r.tensor_data(train_rows)
    g=torch.Generator().manual_seed(20261114 + cell*113)
    generations=[]
    incumbent_sha=initial_sha
    accepted=0
    for number in (1,2):
        before=r.evaluate(model,val_rows)
        parent_state=clone_state(model)
        optimizer=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.0005)
        best=None
        best_loss=float("inf")
        for i in range(steps):
            model.train()
            indices=torch.randint(0,len(x),(min(48,len(x)),),generator=g)
            optimizer.zero_grad(set_to_none=True)
            logits=model(x[indices])[0][:,-1,:len(r.LABELS)].float()
            loss=F.cross_entropy(logits,y[indices])
            if not torch.isfinite(loss):raise ValueError("NONFINITE_GRADIENT_LOSS")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True)
            optimizer.step()
            if (i+1)%10==0 or i==steps-1:
                metric=r.evaluate(model,val_rows)
                if metric["nll"]<best_loss:
                    best_loss=metric["nll"];best=clone_state(model)
        if best is None:raise ValueError("NO_DESCENDANT_CANDIDATE")
        candidate_sha=stable_state(best)
        model.load_state_dict(best)
        after=r.evaluate(model,val_rows)
        gain=before["nll"]-after["nll"]
        survives=(gain>=0.0001 and after["accuracy"]>=before["accuracy"]-0.02
                  and candidate_sha!=incumbent_sha)
        if not survives:model.load_state_dict(parent_state)
        else:accepted+=1
        generations.append({"generation":number,"parent_weights_sha256":incumbent_sha,
                            "proposed_weights_sha256":candidate_sha,
                            "retained_weights_sha256":stable_state(model.state_dict()),
                            "validation_before":before,"validation_after":after,
                            "validation_nll_gain":round(gain,6),"gradient_steps":steps,
                            "selection":"RESEARCH_ACCEPTED" if survives else "HOLD_REJECTED",
                            "holdout_was_visible":False})
        incumbent_sha=stable_state(model.state_dict())
    if not all(row["parent_weights_sha256"]==(initial_sha if i==0 else generations[i-1]["retained_weights_sha256"]) for i,row in enumerate(generations)):
        raise ValueError("BROKEN_GENERATIONAL_LINEAGE")
    result={"schema":LINEAGE,"source_commit":source,"dataset_sha256":manifest["dataset_sha256"],
            "manifest_sha256":manifest["receipt_sha256"],"cell":cell,"role":r.CELL_ROLES[cell],
            "train_sha256":train_packet["packet_sha256"],"validation_sha256":val_packet["packet_sha256"],
            "holdout_sha256":manifest["split_sha256"]["holdout"],
            "initial_weights_sha256":initial_sha,"final_weights_sha256":incumbent_sha,
            "generations":generations,"accepted_generations":accepted,
            "initial_validation":parent_eval,"final_validation":r.evaluate(model,val_rows),
            "true_gradient_training":True,"model_weights_modified_in_memory":accepted>0,
            "training_saw_holdout":False,"external_independent_test":False,
            "release_permission":False,"production_authority":False}
    dest=Path(out)
    dest.mkdir(parents=True,exist_ok=False)
    weights={"schema":LINEAGE,"cell":cell,"source_commit":source,
             "initial_state":initial,"final_state":clone_state(model),
             "production_authority":False}
    torch.save(weights,dest/"offspring.pt")
    result["offspring_file_sha256"]=sha((dest/"offspring.pt").read_bytes())
    result["receipt_sha256"]=seal(result)
    atomic_json(dest/"lineage.json",result)
    return result

def verify(cell,holdout,manifest,receipt,checkpoint):
    source=manifest["source_commit"]
    validate_manifest(manifest,source)
    test_rows=check_packet(holdout,"holdout",source,manifest["dataset_sha256"])
    if (holdout["packet_sha256"]!=manifest["split_sha256"]["holdout"]
        or not all(manifest["split_dates"]["validation"][1]<row["date"] for row in test_rows)):
        raise ValueError("HOLDOUT_BINDING_OR_DATE_MISMATCH")
    if (receipt.get("schema")!=LINEAGE or receipt.get("cell")!=cell
        or receipt.get("source_commit")!=source
        or receipt.get("manifest_sha256")!=manifest["receipt_sha256"]
        or receipt.get("holdout_sha256")!=holdout["packet_sha256"]
        or receipt.get("receipt_sha256")!=seal({k:v for k,v in receipt.items() if k!="receipt_sha256"})
        or receipt.get("production_authority") is not False
        or receipt.get("training_saw_holdout") is not False):
        raise ValueError("LINEAGE_OR_HOLDOUT_RECEIPT_TAMPERED")
    p=Path(checkpoint)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>12_000_000 or sha(p.read_bytes())!=receipt["offspring_file_sha256"]:
        raise ValueError("OFFSPRING_SHA_MISMATCH")
    bundle=torch.load(p,map_location="cpu",weights_only=True)
    if (bundle.get("schema")!=LINEAGE or bundle.get("cell")!=cell or bundle.get("source_commit")!=source
        or bundle.get("production_authority") is not False):
        raise ValueError("OFFSPRING_UNTRUSTED_HEADER")
    baseline=r.model_for(cell)
    original=bundle["initial_state"];final=bundle["final_state"]
    reference=baseline.state_dict()
    if (set(original)!=set(reference) or set(final)!=set(reference)
        or any(original[k].shape!=reference[k].shape or final[k].shape!=reference[k].shape for k in reference)
        or stable_state(original)!=receipt["initial_weights_sha256"]
        or stable_state(final)!=receipt["final_weights_sha256"]):
        raise ValueError("OFFSPRING_TENSOR_LINEAGE_MISMATCH")
    baseline.load_state_dict(original,strict=True)
    b=r.evaluate(baseline,test_rows)
    baseline.load_state_dict(final,strict=True)
    c=r.evaluate(baseline,test_rows)
    label_baseline=r.baseline([],[]) if False else None  # No train labels ever supplied here.
    delta=round(b["nll"]-c["nll"],6)
    gate=("RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN" if delta>=0.02 and c["accuracy"]>=b["accuracy"]
          else "HOLD_HISTORICAL_DATE_HOLDOUT_NO_CONFIRMED_GAIN")
    result={"schema":"janus.essence.gradirnya_verifier/1.9","cell":cell,"role":r.CELL_ROLES[cell],
            "source_commit":source,"lineage_sha256":receipt["receipt_sha256"],
            "holdout_sha256":holdout["packet_sha256"],"heldout_rows":len(test_rows),
            "initial":b,"descendant":c,"nll_reduction":delta,"gate":gate,
            "independent_ci_job":True,"externally_custodied_test":False,
            "truly_future_unseen_dataset":False,"statistically_replicated_hardware":False,
            "live_production_rollback":False,"automatic_production_promotion":False,
            "research_artifact_only":True}
    result["receipt_sha256"]=seal(result)
    return result

def cli():
    a=argparse.ArgumentParser()
    sub=a.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("prepare");p.add_argument("--data-root",required=True);p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    p=sub.add_parser("train");p.add_argument("--train",required=True);p.add_argument("--validation",required=True);p.add_argument("--manifest",required=True);p.add_argument("--cell",type=int,required=True);p.add_argument("--steps",type=int,default=40);p.add_argument("--out",required=True)
    p=sub.add_parser("verify");p.add_argument("--holdout",required=True);p.add_argument("--manifest",required=True);p.add_argument("--cell",type=int,required=True);p.add_argument("--lineage",required=True);p.add_argument("--weights",required=True);p.add_argument("--out",required=True)
    opt=a.parse_args()
    if opt.cmd=="prepare":
        result=prepare(opt.data_root,opt.source,opt.out)
        print(json.dumps({"status":"FROZEN_DATE_SPLITS","sizes":result["split_sizes"]}))
    elif opt.cmd=="train":
        result=train(opt.cell,read_json(opt.train),read_json(opt.validation),
                     read_json(opt.manifest),opt.out,opt.steps)
        print(json.dumps({"cell":opt.cell,"accepted_generations":result["accepted_generations"],"production_authority":False}))
    else:
        result=verify(opt.cell,read_json(opt.holdout),read_json(opt.manifest),
                      read_json(opt.lineage),opt.weights)
        atomic_json(opt.out,result)
        print(json.dumps({"cell":opt.cell,"gate":result["gate"],"production_authority":False}))

if __name__=="__main__":cli()
