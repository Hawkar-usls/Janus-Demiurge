#!/usr/bin/env python3
"""TRINITY R1.2 new disjoint internal first-look critic comparison.

Unlike the published 36-probe diagnostic this uses disjoint operand ranges.
It is same-owner GitHub Actions validation, NOT an external blinded exam;
nobody may optimize repeatedly on the result and then call it fresh.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu
from tools import trinity_r12_critic_train as train

SCHEMA="janus.trinity.r12.critic_firstlook_internal/1.0"

def rows():
    result=[]
    for i in range(12):
        # New domain beyond BOTH R1.1 training (31..208) and the now
        # disclosed R1.1 first-look (731..1211), declared before R1.2 fit.
        a,b=1731+19*i,1931+29*i
        problem=f"What is {a} plus {b}? Reply with a single nonnegative integer."
        truth=str(a+b)
        for kind,proposal in (
            ("CORRECT",truth),
            ("INCORRECT",str(a+b-(i%5+1))),
            ("AMBIGUOUS",f"Perhaps {truth}, or {a+b+7}"),
        ):
            result.append({"id":f"R12-CHECK-{i:02d}-{kind}","kind":kind,
                           "prompt":train.question(problem,proposal),
                           "expected":"YES" if kind=="CORRECT" else "NO",
                           "partition":"NEW_INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND"})
    assert len(result)==36 and len({x["prompt"] for x in result})==36
    return result

def evaluate_predictions(rows, baseline, candidate, train_hash):
    if rows!=globals()["rows"]():
        raise ValueError("R11_EVAL_CASES_CHANGED")
    if not isinstance(baseline,list) or not isinstance(candidate,list) or len(baseline)!=len(rows) or len(candidate)!=len(rows):
        raise ValueError("R11_INCOMPLETE_MODEL_RESPONSES")
    totals={}
    hashed={}
    for label,values in (("BASELINE",baseline),("CANDIDATE",candidate)):
        matrix={kind:{"APPROVE":0,"VETO":0,"ABSTAIN":0} for kind in ("CORRECT","INCORRECT","AMBIGUOUS")}
        fingerprints=[]
        for task,v in zip(rows,values):
            if not isinstance(v,str):
                raise ValueError("R11_INVALID_RESPONSE")
            verdict=c.critic_decision(v)
            matrix[task["kind"]][verdict]+=1
            fingerprints.append({"id":task["id"],"decision":verdict,
                                 "output_sha256":hashlib.sha256(v.encode()).hexdigest()})
        totals[label]=matrix
        hashed[label]=fingerprints
    b,after=totals["BASELINE"],totals["CANDIDATE"]
    # Absolute positive sensitivity is mandatory: a degenerate critic that
    # VETOes ALL answers is NOT qualified even if baseline mostly abstains.
    strong=(after["INCORRECT"]["VETO"]>=8 and
            after["INCORRECT"]["APPROVE"]<=b["INCORRECT"]["APPROVE"] and
            after["CORRECT"]["APPROVE"]>=8 and
            after["CORRECT"]["APPROVE"]>=b["CORRECT"]["APPROVE"]-2 and
            after["AMBIGUOUS"]["APPROVE"]==0)
    improved=(after["INCORRECT"]["VETO"]>b["INCORRECT"]["VETO"] and
              after["INCORRECT"]["APPROVE"]<b["INCORRECT"]["APPROVE"])
    return c.sealed({
        "schema":SCHEMA,
        "status":"INTERNAL_CRITIC_IMPROVEMENT_OBSERVED__EXTERNAL_HOLD" if strong and improved
                 else "HOLD_CRITIC_GENERALIZATION_NOT_PROVEN",
        "source_adapter_train_receipt_sha256":train_hash,
        "first_look_only":False,"same_owner_GitHub_Actions":True,
        "rerun_of_disclosed_r12_cases_for_admission_audit":True,
        "original_firstlook_preserved_in_actions_run":"45197279127",
        "external_independent_exam":False,
        "public_prior_36_probes_reused":False,"r11_firstlook_reused":False,
        "genesis64_read":False,
        "cases":len(rows),"case_set_sha256":c.digest(rows),
        "metrics":totals,"responses":hashed,
        "criterion":{"strong_wrong_veto_and_nonregression":strong,
                     "newly_detected_wrong":improved,
                     "correct_absolute_approval_floor_8_of_12":after["CORRECT"]["APPROVE"]>=8,
                     "all_veto_strategy_rejected":after["CORRECT"]["APPROVE"]<8},
        "may_promote_JANUS":False,
        "may_replace_parent_critic":False,
        "may_graduate_trinity":False,
        "production_promotion":False,
    })

def run(adapter:Path, receipt:Path):
    from peft import PeftModel
    record=c.checked_seal(json.loads(receipt.read_text(encoding="utf-8")))
    if record.get("schema")!=train.SCHEMA or record.get("base")!=c.SMOL or record.get("training_only") is not True:
        raise ValueError("R11_INVALID_TRAINING_RECEIPT")
    if record.get("train_source_sha256")!=c.digest(train.train_rows()):
        raise ValueError("R11_TRAINING_DATA_MISMATCH")
    for file,key in (("adapter_model.safetensors","adapter_weight_sha256"),
                     ("adapter_config.json","adapter_config_sha256")):
        if hashlib.sha256((adapter/file).read_bytes()).hexdigest()!=record.get(key):
            raise ValueError("R11_CRITIC_ADAPTER_DIGEST_MISMATCH")
    test=rows()
    if set(x["prompt"] for x in test)&set(x["prompt"] for x in train.train_rows()):
        raise ValueError("R11_TRAIN_EVAL_OVERLAP")
    tk,base=cpu.load_parent(c.SMOL)
    baseline=[cpu.parent_answer(tk,base,item["prompt"],max_tokens=6) for item in test]
    model=PeftModel.from_pretrained(base,str(adapter),is_trainable=False).to("cpu").eval()
    trained=[cpu.parent_answer(tk,model,item["prompt"],max_tokens=6) for item in test]
    return evaluate_predictions(test,baseline,trained,record["sha256"])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--adapter",type=Path,required=True)
    ap.add_argument("--train-receipt",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    report=run(a.adapter,a.train_receipt)
    cpu.save_new(a.out,report)
    print(json.dumps({"status":report["status"],"metrics":report["metrics"],
                      "may_replace_critic":False},sort_keys=True))

if __name__=="__main__":
    main()
