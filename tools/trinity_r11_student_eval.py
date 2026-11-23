#!/usr/bin/env python3
"""TRINITY R1.1: disjoint first-look internal JANUS shadow eval.

The real Genesis 64 first-look is NOT imported. Tests here are constructed
after the separate training job and have operands outside training range.
This is internal same-owner validation, NOT a proof of parent surpass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu
from tools import trinity_r11_student_train as train
from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint,sha256_file

SCHEMA="janus.trinity.r11.student_internal_firstlook.v1"

def cases():
    rows=[]
    for i in range(36):
        a,b=811+23*i,907+17*i
        pad="" if i<12 else "P"*108+"\n" if i<24 else "L"*315+"\n"
        group="SHORT" if i<12 else "MEDIUM" if i<24 else "LONG"
        rows.append({"id":f"R11-NEW-JANUS-{i:03d}","prompt":
                     pad+f"Compute {a} + {b}. Reply with the integer only.",
                     "expected":str(a+b),"group":group,
                     "partition":"INTERNAL_FIRSTLOOK_NOT_EXTERNAL_BLIND"})
    return rows

def run(shadow_path:Path,receipt_path:Path):
    record=c.checked_seal(json.loads(receipt_path.read_text()))
    if record.get("schema")!=train.SCHEMA or record.get("production_promotion") is not False:
        raise ValueError("R11_BAD_SHADOW_TRAIN_RECEIPT")
    if record["training_source_sha256"]!=c.digest(train.train_rows()):
        raise ValueError("R11_TRAIN_SPLIT_NOT_PINNED")
    if sha256_file(shadow_path)!=record.get("shadow_checkpoint_sha256"):
        raise ValueError("R11_SHADOW_WEIGHT_SHA_DRIFT")
    incumbent_path=Path("janus_model/checkpoints/promoted.pt")
    if sha256_file(incumbent_path)!=record.get("base_checkpoint_sha256"):
        raise ValueError("R11_MAIN_CHECKPOINT_CHANGED")
    before,_=load_checkpoint(incumbent_path,expected_sha256=record["base_checkpoint_sha256"])
    after,_=load_checkpoint(shadow_path,expected_sha256=record["shadow_checkpoint_sha256"])
    if after.config.context_length!=record["context_length"]:
        raise ValueError("R11_CONTEXT_CHECKPOINT_DRIFT")
    evaluation=cases()
    if {x["prompt"] for x in evaluation}&{x["prompt"] for x in train.train_rows()}:
        raise ValueError("R11_STUDENT_TRAIN_EVAL_LEAKAGE")
    all_rows=[]
    for task in evaluation:
        n=len(ByteTokenizer.encode("Q:"+task["prompt"]+"\nJANUS:",bos=True))
        baseline_answer=cpu.student_answer(before,task["prompt"])
        shadow_answer=cpu.student_answer(after,task["prompt"])
        all_rows.append({
            "id":task["id"],"group":task["group"],"tokens":n,
            "incumbent_fits":n<128,"shadow_fits":n<after.config.context_length,
            "incumbent_exact":baseline_answer==task["expected"],
            "shadow_exact":shadow_answer==task["expected"],
            "baseline_answer_sha256":hashlib.sha256(
                (baseline_answer or "").encode()).hexdigest(),
            "shadow_answer_sha256":hashlib.sha256(
                (shadow_answer or "").encode()).hexdigest(),
        })
    by_group={}
    for group in ("SHORT","MEDIUM","LONG"):
        rows=[x for x in all_rows if x["group"]==group]
        by_group[group]={
            "cases":len(rows),
            "incumbent_fit":sum(x["incumbent_fits"] for x in rows),
            "shadow_fit":sum(x["shadow_fits"] for x in rows),
            "incumbent_exact":sum(x["incumbent_exact"] for x in rows),
            "shadow_exact":sum(x["shadow_exact"] for x in rows)
        }
    lost=sum(x["incumbent_exact"] and not x["shadow_exact"] for x in all_rows)
    new=sum(x["shadow_exact"] and not x["incumbent_exact"] for x in all_rows)
    report=c.sealed({
        "schema":SCHEMA,
        "status":"INTERNAL_FUNCTIONAL_GAIN_PROVISIONAL_EXTERNAL_HOLD" if new>=2 and lost==0
                 else "HOLD_NO_PROVEN_STUDENT_GENERALIZATION",
        "student_context":after.config.context_length,
        "base_checkpoint_sha256":record["base_checkpoint_sha256"],
        "candidate_checkpoint_sha256":record["shadow_checkpoint_sha256"],
        "train_receipt_sha256":record["sha256"],
        "case_set_sha256":c.digest(evaluation),
        "evaluation_cases":36,
        "old_solved_lost":lost,
        "newly_solved":new,
        "by_group":by_group,
        "per_case":all_rows,
        "used_train_examples":False,
        "used_published_critic_probes":False,
        "used_genesis_firstlook_64":False,
        "same_owner_internal_evaluation":True,
        "independent_external_validation":False,
        "three_future_independent_cohorts_completed":False,
        "student_graduated":False,
        "production_promotion":False,
        "checkpoint_admitted":False,
        "may_choose_own_training_sources":False,
    })
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--student",type=Path,required=True)
    ap.add_argument("--train-receipt",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    receipt=run(a.student,a.train_receipt)
    cpu.save_new(a.out,receipt)
    print(json.dumps({"context":receipt["student_context"],
                      "new_solved":receipt["newly_solved"],
                      "lost":receipt["old_solved_lost"],
                      "groups":receipt["by_group"],
                      "status":receipt["status"],
                      "promotion":False},sort_keys=True))

if __name__=="__main__":
    main()
