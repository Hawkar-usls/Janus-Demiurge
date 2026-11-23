#!/usr/bin/env python3
"""TRINITY R1.4 real CPU study of two separated roles, never a parent graduation.

Mode TRAIN: pinned Qwen proposes 24 fresh TRAIN_ONLY numeric answers; a
deterministic oracle verifies. Pinned SmolLM supplies non-authoritative
format explanations. Only already-verified Qwen answers become a *candidate*
train-source receipt. No student weights are changed.

Mode FIFTH: pinned SmolLM gives its format observations on precommitted
64 fifth cases. Deterministic oracle is checked against immutable independent
reference labels; a format-only classifier is a weak paired baseline.
Neither train data nor student exams are accessed in fifth mode.

The new fifth cases are NOT externally blind, and deterministic exact math
is not ML generalization. No model generated code is executed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu
from tools import trinity_r14_verified_oracle as o

def run_train_only():
    tasks=o.train_only_cases()
    tk,qwen=cpu.load_parent(c.QWEN)
    proposals=[cpu.parent_answer(tk,qwen,t["prompt"],max_tokens=16) for t in tasks]
    del tk,qwen
    tk,smol=cpu.load_parent(c.SMOL)
    notes=[cpu.parent_answer(tk,smol,o.advisory_prompt(t["prompt"],answer),max_tokens=36)
           for t,answer in zip(tasks,proposals)]
    rows=[{"id":t["id"],"teacher_proposal":answer,"smollm_advisory":note}
          for t,answer,note in zip(tasks,proposals,notes)]
    result=o.verified_train_source(rows)
    result.update({
        "qwen":c.QWEN,"smollm":c.SMOL,
        "real_cpu_qwen_generation":True,
        "real_cpu_smollm_format_explanation":True,
        "teacher_proposals_count":len(tasks),
        "not_yet_used_to_train_student":True,
        "independent_criticism_not_proven":True,
        "student_checkpoint_sha256":None,
        "no_genesis_exam_read":True,
    })
    result["sha256"]=o.digest(result)
    return result

def run_fifth(root:Path):
    cases=o.read_fifth(root)
    tk,model=cpu.load_parent(c.SMOL)
    notes=[cpu.parent_answer(tk,model,o.advisory_prompt(
               r["prompt"],r["proposed_answer"]),max_tokens=36)
           for r in cases]
    result=o.compare_fifth(cases,notes)
    result.update({
        "model":c.SMOL,
        "model_use":"ADVISORY_EXPLANATION_OF_FORMAT_ONLY",
        "real_cpu_smollm_generation":True,
        "real_cpu_qwen_not_called_on_fifth":True,
        "reference_is_frozen_before_inference":True,
        "fifth_ever_used_to_train_student":False,
        "external_custodian_present":False,
        "parent_surpassed":False,
        "gradutation_approved":False,
        "student_weights_modified":False,
    })
    result["sha256"]=o.digest({k:v for k,v in result.items() if k!="sha256"})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["train","fifth"],required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--repo-root",type=Path,default=Path("."))
    args=p.parse_args()
    report=run_train_only() if args.mode=="train" else run_fifth(args.repo_root)
    cpu.save_new(args.out,report)
    print(json.dumps({
        "mode":args.mode,
        "status":report.get("status","TRAIN_SOURCE_VERIFIED_NOT_APPLIED"),
        "qualified_train_rows":report.get("accepted_count",None),
        "oracle_reference_agreement":report.get("oracle_matches_frozen_reference",None),
        "all_model_promotions_disabled":True,
        "sha256":report["sha256"]
    },sort_keys=True))


if __name__=="__main__":
    main()
