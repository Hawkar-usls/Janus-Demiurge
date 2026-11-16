#!/usr/bin/env python3
"""ESSENCE v5.7: genuine LoRA functional-skill experiment, NOT production.

Teach pinned G3 on mathematically verified deterministic training questions,
then open a DISJOINT previously unused generated functional cohort in another
GitHub Actions job. Protect previously measured repository/legacy skills.
No arbitrary execution of model text, production promotion or Sentinel writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
import shutil
import time
from pathlib import Path
from tools import essence_v48_recurrent_state as state
from tools import essence_v48_recurrent_neural as neural
from tools import essence_v55_neural_loop as v55

VERSION="janus.essence.v57.functional_oracle_generation/5.7"
PLAN="janus.essence.v57.functional_plan/5.7"
LINEAGE="janus.essence.v57.functional_lora_lineage/5.7"
EXAM="janus.essence.v57.fresh_functional_exam/5.7"
LEDGER="janus.essence.v57.functional_shadow_ledger/5.7"
LOCK_PATH="research/essence/functional_v57/FROZEN_LOCK.json"
STATE_PATH="research/essence/functional_v57_state/ledger.json"
PARENT_PATH="models/v54gen0003"
CHILD_PATH="models/v57funcgen0004"
PARENT_SHA="bc05f07916cab24ae4fe814971b1de7e4b60a948bad1e99df19bbad720b2ef8d"
PARENT_LINEAGE="9f8d54a6e3d497a46a12d3a27752caa710900e1c5b4a506f6477812d35162025"

LOCK={
 "schema":VERSION,"mode":"FROZEN_ONE_ATTEMPT_FUNCTIONAL_REPLAY",
 "parent_generation":3,"parent_adapter_sha256":PARENT_SHA,
 "parent_lineage_sha256":PARENT_LINEAGE,
 "parent_model_path":PARENT_PATH,
 "base_model_revision":"7ae557604adf67be50417f59c2c2f167def9a775",
 "training_seed":57011,"replay_seed":57005,"heldout_seed":57071,
 "training_count":96,"replay_count":72,"heldout_count":48,"steps":256,
 "learning_rate":0.00018,
 "minimum_new_heldout_exact_answers":3,
 "maximum_heldout_answers_lost":0,
 "minimum_heldout_paired_nll_gain":0.01,
 "maximum_retention_nll_regression":0.12,
 "old_skills_exact_regression_allowed":0,
 "replay_legacy_cases":4,"replay_verified_memory_cases":4,
 "functional_replay_ratio":"2_of_8",
 "attempt_budget":1,"no_holdout_training":True,
 "no_retry_same_exam":True,"production_promotion":False,
 "sentinel_dispatch":False,"external_validation":False,
 "claim_ceiling":"SAME_OWNER_PROSPECTIVE_FUNCTIONAL_REPLAY_RESEARCH_ONLY",
}


def require(ok,msg):
    if not ok: raise ValueError("V57_"+msg)


def checked(x):
    return state.check(x)


def sealed(x):
    return state.sealed(x)


def locked(path=LOCK_PATH):
    d=state.load(path)
    require(d==LOCK,"FROZEN_LOCK_CHANGED")
    return d


def rows(seed,count,split):
    """Deterministic exact-label oracle, deduplicated without leaking exam cases."""
    require(split in ("train","heldout","replay"),"BAD_DATA_SPLIT")
    require((split=="train" and seed==LOCK["training_seed"] and count==LOCK["training_count"])
            or (split=="replay" and seed==LOCK["replay_seed"] and count==LOCK["replay_count"])
            or (split=="heldout" and seed==LOCK["heldout_seed"] and count==LOCK["heldout_count"]),
            "UNREGISTERED_ORACLE_SEED")
    rng=random.Random(seed)
    result=[];seen=set()
    for i in range(count):
        kind=i%6
        for retry in range(128):
            lo,hi=(11,89) if split!="heldout" else (111,189)
            a=rng.randint(lo,hi);b=rng.randint(lo,hi)
            if kind==0:
                prompt=f"Compute {a} plus {b}. Return only the integer."
                value=a+b;group="addition"
            elif kind==1:
                prompt=f"Compute {a+b} minus {b}. Return only the integer."
                value=a;group="subtraction"
            elif kind==2:
                factor=rng.randint(11,19) if split!="heldout" else rng.randint(21,29)
                prompt=f"Compute {a} multiplied by {factor}. Return only the integer."
                value=a*factor;group="multiplication"
            elif kind==3:
                div=rng.randint(6,17) if split!="heldout" else rng.randint(18,33)
                prompt=f"What is the remainder of {a+b} divided by {div}? Return only the integer."
                value=(a+b)%div;group="modulus"
            elif kind==4:
                prompt=f"What is the greatest common divisor of {a} and {b}? Return only the integer."
                value=math.gcd(a,b);group="gcd"
            else:
                direct=rng.randint(14,46) if split!="heldout" else rng.randint(30,80)
                hop=rng.randint(3,26) if split!="heldout" else rng.randint(7,40)
                second=rng.randint(4,28) if split!="heldout" else rng.randint(9,45)
                prompt=(f"Directed weighted graph: A to C costs {direct}; "
                        f"A to B costs {hop}; B to C costs {second}. "
                        "What is the shortest route cost from A to C? Return only the integer.")
                value=min(direct,hop+second);group="shortest_path"
            if prompt not in seen:
                break
        else:
            raise ValueError("V57_ORACLE_DEDUP_BUDGET_EXHAUSTED")
        seen.add(prompt)
        result.append({"key":f"{split[:1]}{i:03d}_{group}",
                       "prompt":prompt,"answer":str(value),"category":group})
    require(len(result)==count and len(seen)==count and
            all(1<=len(r["answer"])<=12 and len(r["prompt"])<255 for r in result),
            "NONUNIQUE_OR_INVALID_ORACLE")
    return result

def frozen_memory(folder):
    p=Path(folder)/"research/essence/peer_v48_state/ledger.json"
    memory=v55.verify_memory(state.load(p))
    require(len(memory)==4,"MEMORY_REPLAY_UNVERIFIED")
    return memory


def plan(state_root,code_root):
    locked(Path(code_root)/LOCK_PATH)
    rec=Path(state_root)/STATE_PATH
    if rec.exists():
        checked(state.load(rec))
        return sealed({"schema":PLAN,"action":"ALREADY_ATTEMPTED",
                       "production_promotion":False})
    state.check_model(Path(state_root)/PARENT_PATH,PARENT_SHA,PARENT_LINEAGE)
    memory=frozen_memory(state_root)
    training=rows(LOCK["training_seed"],LOCK["training_count"],"train")
    replay=rows(LOCK["replay_seed"],LOCK["replay_count"],"replay")
    require(not {x["prompt"] for x in training}.intersection(
            x["prompt"] for x in replay),"REPLAY_TRAIN_OVERLAP")
    # Never instantiate heldout task bytes in this phase.
    return sealed({"schema":PLAN,"action":"TRAIN_SHADOW",
        "lock_sha256":state.digest(LOCK),
        "parent_generation":3,"parent_adapter_sha256":PARENT_SHA,
        "parent_lineage_sha256":PARENT_LINEAGE,
        "parent_path":PARENT_PATH,
        "training_rows_sha256":state.digest(training),
        "replay_rows_sha256":state.digest(replay),
        "training_count":len(training),"replay_count":len(replay),
        "training_seed":LOCK["training_seed"],"replay_seed":LOCK["replay_seed"],
        "heldout_seed":LOCK["heldout_seed"],
        "heldout_count":LOCK["heldout_count"],
        "memory_replay":memory,
        "production_promotion":False,"sentinel_dispatch":False,
        "holdout_rows_not_generated":True,"external_validation":False})


def verify_plan(p):
    checked(p)
    require(p.get("schema")==PLAN and p.get("action")=="TRAIN_SHADOW"
       and p.get("lock_sha256")==state.digest(LOCK)
       and p.get("parent_generation")==3
       and p.get("parent_adapter_sha256")==PARENT_SHA
       and p.get("parent_lineage_sha256")==PARENT_LINEAGE
       and p.get("parent_path")==PARENT_PATH
       and p.get("training_seed")==LOCK["training_seed"]
       and p.get("training_count")==LOCK["training_count"]
       and p.get("replay_seed")==LOCK["replay_seed"]
       and p.get("replay_count")==LOCK["replay_count"]
       and p.get("replay_rows_sha256")==state.digest(
           rows(LOCK["replay_seed"],LOCK["replay_count"],"replay"))
       and p.get("heldout_seed")==LOCK["heldout_seed"]
       and p.get("heldout_count")==LOCK["heldout_count"]
       and p.get("training_rows_sha256")==state.digest(
           rows(LOCK["training_seed"],LOCK["training_count"],"train"))
       and p.get("memory_replay") is not None
       and len(p["memory_replay"])==4
       and p.get("holdout_rows_not_generated") is True
       and p.get("production_promotion") is False
       and p.get("sentinel_dispatch") is False
       and p.get("external_validation") is False,
       "UNTRUSTED_PLAN")
    for x in p["memory_replay"]:
        # The original complete memory row SHA was verified at source freeze.
        # The plan contains only a safe projection, not the full hash preimage.
        require(x.get("training_verified_by_repository_sha") is True and
                x.get("source_repo") in ("Hawkar-usls/Hrain","Hawkar-usls/Janus_Genesis") and
                isinstance(x.get("fact_digest"),str) and
                bool(state.HEX.fullmatch(x["fact_digest"])) and
                isinstance(x.get("answer"),str) and
                1<=len(x["answer"])<=62,
                "UNVERIFIED_MEMORY")
    return p


def legacy():
    return v55.sample_legacy()[:4]


def train(p,parent,child):
    verify_plan(p)
    state.check_model(parent,PARENT_SHA,PARENT_LINEAGE)
    import torch
    started=time.monotonic()
    torch.manual_seed(57011)
    tk,model=neural.load_parent(parent,p,train=True)
    trainable=[v for name,v in model.named_parameters() if v.requires_grad]
    params=sum(v.numel() for v in trainable)
    require(trainable and params<=350000 and all(
            "lora_" in name for name,v in model.named_parameters()
            if v.requires_grad),"UNRESTRICTED_TRAINING")
    training=rows(LOCK["training_seed"],LOCK["training_count"],"train")
    replay=rows(LOCK["replay_seed"],LOCK["replay_count"],"replay")
    require(state.digest(replay)==p["replay_rows_sha256"],"REPLAY_DRIFT")
    old=legacy()+p["memory_replay"]
    schedule=[];fresh=0;rehearsed=0;old_count=0
    for i in range(LOCK["steps"]):
        lane=i%8
        if lane in (0,1,2,3):
            schedule.append(training[fresh%len(training)])
            fresh+=1
        elif lane in (4,5):
            schedule.append(replay[rehearsed%len(replay)])
            rehearsed+=1
        else:
            schedule.append(old[old_count%len(old)])
            old_count+=1
    require(fresh>=len(training) and rehearsed>=60 and old_count>=60,
            "INSUFFICIENT_FUNCTIONAL_REPLAY")
    opt=torch.optim.AdamW(trainable,lr=LOCK["learning_rate"])
    losses=[]
    for row in schedule:
        _,ids,labels=neural.input_tokens(tk,row["prompt"],row["answer"])
        opt.zero_grad(set_to_none=True)
        loss=model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels).loss
        require(bool(torch.isfinite(loss)),"NONFINITE_TRAINING_LOSS")
        loss.backward()
        n=torch.nn.utils.clip_grad_norm_(trainable,1.0)
        require(math.isfinite(float(n)),"GRADIENT_EXPLODED")
        opt.step()
        losses.append(round(float(loss.detach()),7))
    child=Path(child)
    require(not child.exists(),"CANDIDATE_ALREADY_EXISTS")
    child.mkdir(parents=True)
    model.save_pretrained(child,safe_serialization=True)
    tensor=(child/"adapter_model.safetensors").read_bytes()
    require(2000<len(tensor)<=6_000_000,"INVALID_ADAPTER_BYTES")
    adapter_sha=hashlib.sha256(tensor).hexdigest()
    require(adapter_sha!=PARENT_SHA,"NO_WEIGHT_UPDATE")
    lineage=sealed({"schema":LINEAGE,
       "generation":4,"parent_generation":3,
       "parent_adapter_sha256":PARENT_SHA,
       "parent_lineage_sha256":PARENT_LINEAGE,
       "adapter_sha256":adapter_sha,"plan_sha256":p["sha256"],
       "trainable_adapter_parameters":params,
       "training_steps":LOCK["steps"],
       "loss_trace":losses,
       "training_seconds":round(time.monotonic()-started,3),
       "training_oracle_sha256":p["training_rows_sha256"],
       "functional_replay_sha256":p["replay_rows_sha256"],
       "functional_replay_examples":rehearsed,
       "old_skills_examples":old_count,
       "heldout_rows_used_in_training":False,
       "production_promotion":False,"sentinel_dispatch":False,
       "external_validation":False})
    state.store(child/"lineage.json",lineage)
    return lineage


def gate(metrics,gained,lost):
    unseen,ret=metrics["fresh_functional"],metrics["old_skill_retention"]
    require(all(math.isfinite(v) for v in
       (unseen["parent_nll"],unseen["child_nll"],
        ret["parent_nll"],ret["child_nll"])),"NONFINITE_EXAM")
    return (gained>=LOCK["minimum_new_heldout_exact_answers"]
       and lost<=LOCK["maximum_heldout_answers_lost"]
       and unseen["child_exact"]>unseen["parent_exact"]
       and unseen["paired_nll_gain"]>=LOCK["minimum_heldout_paired_nll_gain"]
       and ret["child_exact"]>=ret["parent_exact"]
       and ret["paired_nll_gain"]>=-LOCK["maximum_retention_nll_regression"])


def exam(p,parent,child):
    verify_plan(p)
    state.check_model(parent,PARENT_SHA,PARENT_LINEAGE)
    lineage=checked(state.load(Path(child)/"lineage.json"))
    weights=Path(child)/"adapter_model.safetensors"
    require(weights.is_file() and not weights.is_symlink()
       and hashlib.sha256(weights.read_bytes()).hexdigest()==lineage["adapter_sha256"]
       and lineage.get("plan_sha256")==p["sha256"]
       and lineage.get("schema")==LINEAGE
       and lineage.get("parent_adapter_sha256")==PARENT_SHA
       and lineage.get("generation")==4
       and lineage.get("functional_replay_sha256")==p["replay_rows_sha256"]
       and lineage.get("heldout_rows_used_in_training") is False,
       "UNVERIFIED_FUNCTIONAL_OFFSPRING")
    # Only the examiner constructs heldout questions; never training.
    unseen=rows(LOCK["heldout_seed"],LOCK["heldout_count"],"heldout")
    training=rows(LOCK["training_seed"],LOCK["training_count"],"train")
    replay=rows(LOCK["replay_seed"],LOCK["replay_count"],"replay")
    require(not {x["prompt"] for x in unseen}.intersection(
          x["prompt"] for x in training+replay),"TRAIN_EXAM_OVERLAP")
    retained=legacy()+p["memory_replay"]
    started=time.monotonic()
    tk,model=neural.load_parent(parent,p,train=False)
    parent_score=[neural.scores(tk,model,x) for x in (unseen,retained)]
    model.load_adapter(str(child),adapter_name="functional_candidate",is_trainable=False)
    model.set_adapter("functional_candidate")
    candidate_score=[neural.scores(tk,model,x) for x in (unseen,retained)]
    model.set_adapter("default")
    restored=neural.scores(tk,model,retained[:2])
    require(all(a["exact"]==b["exact"] and a["answer"]==b["answer"]
              and abs(a["loss"]-b["loss"])<.0001
              for a,b in zip(parent_score[1][:2],restored)),
            "PARENT_ROLLBACK_FAILED")
    gained=sum(not x["exact"] and y["exact"]
             for x,y in zip(parent_score[0],candidate_score[0]))
    lost=sum(x["exact"] and not y["exact"]
             for x,y in zip(parent_score[0],candidate_score[0]))
    metrics={key:neural.metrics(a,b) for key,a,b in zip(
       ("fresh_functional","old_skill_retention"),parent_score,candidate_score)}
    passed=gate(metrics,gained,lost)
    return sealed({"schema":EXAM,"plan_sha256":p["sha256"],
       "lineage_sha256":lineage["sha256"],
       "adapter_sha256":lineage["adapter_sha256"],
       "training_oracle_sha256":p["training_rows_sha256"],
       "functional_replay_sha256":p["replay_rows_sha256"],
       "heldout_oracle_sha256":state.digest(unseen),
       "heldout_exam_first_seen_in_separate_job":True,
       "parent_restored_after_exam":True,
       "metric":metrics,
       "newly_correct":gained,"previously_correct_lost":lost,
       "per_task":[{"id":row["key"],"category":row["category"],
           "parent_exact":a["exact"],"child_exact":b["exact"]}
           for row,a,b in zip(unseen,parent_score[0],candidate_score[0])],
       "status":"PASS_PROSPECTIVE_INTERNAL_FUNCTIONAL_GAIN"
           if passed else "HOLD_FUNCTIONAL_NOT_BETTER",
       "exam_seconds":round(time.monotonic()-started,3),
       "external_validation":False,
       "production_promotion":False,"sentinel_dispatch":False})


def publish(state_root,p,child,exam_receipt):
    verify_plan(p)
    state_root=Path(state_root)
    require(not (state_root/STATE_PATH).exists(),
            "ALREADY_TRIED_LOCKED_EXAM")
    checked(exam_receipt)
    require(len(exam_receipt.get("per_task",[]))==LOCK["heldout_count"],
            "INVALID_ORACLE_PER_TASK_AUDIT")
    lineage=checked(state.load(Path(child)/"lineage.json"))
    require(exam_receipt.get("schema")==EXAM
       and exam_receipt.get("plan_sha256")==p["sha256"]
       and exam_receipt.get("lineage_sha256")==lineage["sha256"]
       and exam_receipt.get("adapter_sha256")==lineage["adapter_sha256"]
       and exam_receipt.get("heldout_exam_first_seen_in_separate_job") is True
       and exam_receipt.get("parent_restored_after_exam") is True
       and exam_receipt.get("external_validation") is False
       and exam_receipt.get("production_promotion") is False
       and exam_receipt.get("sentinel_dispatch") is False
       and exam_receipt.get("status")==(
            "PASS_PROSPECTIVE_INTERNAL_FUNCTIONAL_GAIN" if
            gate(exam_receipt["metric"],exam_receipt["newly_correct"],
                 exam_receipt["previously_correct_lost"]) else
            "HOLD_FUNCTIONAL_NOT_BETTER"),
       "FORGED_FUNCTIONAL_EXAM")
    accepted=exam_receipt["status"]=="PASS_PROSPECTIVE_INTERNAL_FUNCTIONAL_GAIN"
    if accepted:
        dst=state_root/CHILD_PATH
        require(not dst.exists(),"CHILD_PATH_ALREADY_EXISTS")
        shutil.copytree(child,dst)
    d=sealed({"schema":LEDGER,
       "lock_sha256":state.digest(LOCK),"parent_generation":3,
       "parent_adapter_sha256":PARENT_SHA,
       "candidate_generation":4,
       "candidate_adapter_sha256":lineage["adapter_sha256"],
       "candidate_lineage_sha256":lineage["sha256"],
       "exam_sha256":exam_receipt["sha256"],
       "status":exam_receipt["status"],
       "functional_metrics":exam_receipt["metric"],
       "newly_correct":exam_receipt["newly_correct"],
       "previously_correct_lost":exam_receipt["previously_correct_lost"],
       "heldout_oracle_sha256":exam_receipt["heldout_oracle_sha256"],
       "per_task_category_outcomes":exam_receipt["per_task"],
       "shadow_accepted":accepted,
       "child_path":CHILD_PATH if accepted else None,
       "production_promotion":False,
       "sentinel_dispatch":False,"external_validation":False})
    state.store(state_root/STATE_PATH,d)
    return d


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=("plan","train","exam","publish"))
    ap.add_argument("--state")
    ap.add_argument("--code-root",default=".")
    ap.add_argument("--parent")
    ap.add_argument("--child")
    ap.add_argument("--plan")
    ap.add_argument("--exam")
    ap.add_argument("--out",required=True)
    x=ap.parse_args()
    if x.phase=="plan":
        result=plan(x.state,x.code_root)
    else:
        p=verify_plan(state.load(x.plan))
        if x.phase=="train":
            result=train(p,x.parent,x.child)
        elif x.phase=="exam":
            result=exam(p,x.parent,x.child)
        else:
            result=publish(x.state,p,x.child,state.load(x.exam))
    state.store(x.out,result)
    print(json.dumps({"phase":x.phase,
       "status":result.get("status",result.get("action","READY")),
       "production_promotion":False},sort_keys=True))


if __name__=="__main__":
    main()
