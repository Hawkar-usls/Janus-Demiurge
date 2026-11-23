#!/usr/bin/env python3
"""TRINITY R1.1: disposable JANUS 128/256/512 CPU shadow fine-tuning.

Same original SHA-pinned promoted checkpoint for every arm. Extending the
position table uses repeated old rows as INITIALIZATION, then trains a NEW
shadow model on separate symbolic train-only arithmetic examples. No Genesis
64-case exam reads, no production promotion, no autonomous curriculum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time

from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu
from tools import trinity_context_probe as context_probe

SCHEMA="janus.trinity.r11.student_shadow_training.v1"
SEED=20261123

def train_rows():
    rows=[]
    for i in range(48):
        a,b=101+(i*37)%283,113+(i*23)%307
        prompt=f"Compute {a} + {b}. Reply with the integer only."
        group="TRAIN_SHORT" if i<24 else "TRAIN_MEDIUM" if i<36 else "TRAIN_LONG"
        pad="" if i<24 else "n"*112 if i<36 else "m"*310
        prompt=(pad+"\n" if pad else "")+prompt
        rows.append({"id":f"R11-TRAIN-JANUS-{i:03d}","group":group,
                     "prompt":prompt,"answer":str(a+b),"partition":"TRAIN_ONLY"})
    if len(rows)!=48 or any(x["prompt"] in {t["prompt"] for t in c.curriculum()} for x in rows):
        raise ValueError("R11_STUDENT_DATA_INVALID")
    return rows

def run(length:int,out:Path,receipt_path:Path,steps:int):
    import torch
    from janus_model.model import ByteTokenizer
    from janus_model.train_registry import load_checkpoint,save_checkpoint,sha256_file
    if type(length) is not int or length not in context_probe.LENGTHS:
        raise ValueError("R11_STUDENT_CONTEXT_INVALID")
    if type(steps) is not int or not 12<=steps<=128:
        raise ValueError("R11_STUDENT_STEP_BUDGET")
    if out.exists() or out.is_symlink() or receipt_path.exists():
        raise ValueError("R11_SHADOW_OUTPUT_NOT_NEW")
    promoted=Path("janus_model/checkpoints/promoted.pt")
    if out.resolve()==promoted.resolve():
        raise ValueError("R11_CANNOT_REPLACE_PROMOTED_CHECKPOINT")
    state=json.loads(Path("janus_model/state/JANUS_MODEL_STATE.json").read_text())
    expected=state["checkpoint_sha256"]
    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    original,_=load_checkpoint(promoted,expected_sha256=expected)
    model=context_probe.expand(original,length)
    model.train()
    train_examples=train_rows()
    samples=[]
    for row in train_examples:
        prefix=ByteTokenizer.encode("Q:"+row["prompt"]+"\nJANUS:",bos=True)
        answer=ByteTokenizer.encode(row["answer"],eos=True)
        seq=prefix+answer
        if len(seq)-1>length: continue
        x=torch.tensor([seq[:-1]],dtype=torch.long)
        y=torch.tensor([[-100]*(len(prefix)-1)+answer],dtype=torch.long)
        samples.append((row["id"],x,y))
    if len(samples)<24:
        raise ValueError("R11_STUDENT_NO_FIT_TRAIN_SET")
    random.Random(SEED).shuffle(samples)
    optimizer=torch.optim.AdamW(model.parameters(),lr=2e-4,weight_decay=0.01)
    started=time.monotonic()
    losses=[]
    for step in range(steps):
        _,x,y=samples[step%len(samples)]
        _,loss=model(x,y)
        if not math.isfinite(float(loss.item())):
            raise ValueError("R11_STUDENT_NONFINITE_LOSS")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        optimizer.step()
        losses.append(float(loss.item()))
    save_checkpoint(out,model,{
        "shadow_only":True,"context_length":length,
        "original_promoted_sha256":expected,
        "no_genesis_exam_access":True,
        "training_data_sha256":c.digest(train_examples),
        "production_promotion":False,
    })
    child_sha=sha256_file(out)
    if child_sha==expected or sha256_file(promoted)!=expected:
        raise ValueError("R11_PARENT_CHECKPOINT_DRIFT")
    result=c.sealed({
        "schema":SCHEMA,
        "status":"SEALED_DISPOSABLE_JANUS_SHADOW__R11_INTERNAL_EXAM_PENDING",
        "base_checkpoint_sha256":expected,
        "shadow_checkpoint_sha256":child_sha,
        "context_length":length,
        "training_examples_total":len(train_examples),
        "training_examples_that_fit":len(samples),
        "training_source_sha256":c.digest(train_examples),
        "steps":steps,"seed":SEED,
        "initial_position_extension":"REPEAT_MODULO_128" if length>128 else "NONE",
        "first_loss":losses[0],"last_loss":losses[-1],
        "elapsed_seconds":round(time.monotonic()-started,3),
        "no_genesis_64_exam_read":True,
        "no_r11_internal_eval_read":True,
        "checkpoint_saved_only_to_artifact":True,
        "incumbent_checkpoint_unchanged":True,
        "training_performed":True,
        "independent_first_look":False,
        "may_promote_model":False,
        "may_self_approve_training":False,
        "production_promotion":False,
    })
    cpu.save_new(receipt_path,result)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--context",type=int,choices=context_probe.LENGTHS,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--steps",type=int,default=60)
    a=ap.parse_args()
    r=run(a.context,a.out,a.receipt,a.steps)
    print(json.dumps({"context":a.context,"trainable_rows":r["training_examples_that_fit"],
                      "first_loss":r["first_loss"],"last_loss":r["last_loss"],
                      "checkpoint_sha256":r["shadow_checkpoint_sha256"],
                      "promotion":False}))

if __name__=="__main__":
    main()
