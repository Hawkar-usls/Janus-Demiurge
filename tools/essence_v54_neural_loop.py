#!/usr/bin/env python3
"""ESSENCE v5.4. Federated source-verified inherited Qwen LoRA generations.

This is an experiment, NOT a production model updater. Peer text never becomes
training truth. Training labels come from pinned source-repository JSON only.
A withheld TOPA file is opened by the exam job AFTER weights are sealed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import time
from pathlib import Path
from tools import essence_v48_recurrent_state as state
from tools import essence_v48_recurrent_neural as neural
from tools import essence_v46_oracle_descendant as oracle

SCHEMA = "janus.essence.v54.fresh_source_loop/5.4"
LEDGER = "janus.essence.v54.shadow_ledger/5.4"
PLAN = "janus.essence.v54.frozen_plan/5.4"
EXAM = "janus.essence.v54.paired_exam/5.4"
LINEAGE = "janus.essence.v54.real_lora_lineage/5.4"
LOCK_REL = "research/essence/peer_v54/FROZEN_LOCK.json"
STATE_REL = "research/essence/peer_v54_state/ledger.json"
SOURCE_PATH = "PROJECT_STATUS.json"
TRAIN = {
    "inaihr": ("Hawkar-usls/iNaiHR",
              ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "aura": ("Hawkar-usls/aura-oracle-tg",
             ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "simptomat": ("Hawkar-usls/Simptomat",
                  ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "scoby": ("Hawkar-usls/SCOBY-D0",
              ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
}
# Frozen one-to-one peer-heldout split. Nothing from these repos is read
# until an isolated examiner job opens the exact precommitted Git SHA.
HOLDOUTS = {
    "inaihr": ("Hawkar-usls/BFain",
               ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "aura": ("Hawkar-usls/Janus",
             ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "simptomat": ("Hawkar-usls/Janus_Genesis",
                  ("schema_id","project","repository","portfolio_class","last_reviewed","maturity")),
    "scoby": ("Hawkar-usls/Janus-HELIOS",
              ("schema","project","project_version","production_readiness")),
}

MEMORY_KEYS = ("schema_id","project","portfolio_class","last_reviewed")
LOCK = {
    "schema":SCHEMA,"mode":"RESEARCH_SHADOW_ONLY",
    "sources":list(TRAIN),
    "holdout_pairs":{sid:[repo,list(keys)] for sid,(repo,keys) in HOLDOUTS.items()},
    "parent_sha256":state.GEN2_SHA,"parent_lineage_sha256":state.GEN2_LINEAGE,
    "base_revision":state.REV,"steps":96,"learning_rate":0.00025,
    "max_attempts":24,"max_accepted_generations":6,
    "min_source_paraphrase_nll_gain":0.08,
    "min_source_paraphrase_exact_gain":1,
    "max_holdout_nll_regression":0.12,
    "max_retention_nll_regression":0.12,
    "holdout_exact_regression_allowed":0,
    "retained_exact_regression_allowed":0,
    "production_promotion":False,"sentinel_dispatch":False,
    "external_validation":False,"automatic_shadow_acceptance":True,
    "no_retry_same_source_facts":True,
    "claim_ceiling":"INTERNAL_PAIRED_SHADOW_ONLY",
}
MAX_BYTES=80000


def fail(condition, code):
    if not condition:
        raise ValueError(code)


def load_lock(path):
    obj=state.load(path)
    fail(obj==LOCK,"V54_FROZEN_LOCK_CHANGED")
    return obj


def checked(obj):
    return state.check(obj)


def sealed(obj):
    return state.sealed(obj)


def initial():
    return sealed({
        "schema":LEDGER,"current_generation":2,
        "current_adapter_sha256":state.GEN2_SHA,
        "current_lineage_sha256":state.GEN2_LINEAGE,
        "current_parent_path":"models/gen0002",
        "attempts":[],"admitted":[],
        "production_promotion":False,"sentinel_dispatch":False,
        "external_validation":False,
    })


def validate_ledger(obj):
    checked(obj)
    fail(obj.get("schema")==LEDGER and
         obj.get("production_promotion") is False and
         obj.get("sentinel_dispatch") is False and
         obj.get("external_validation") is False and
         isinstance(obj.get("attempts"),list) and
         isinstance(obj.get("admitted"),list) and
         len(obj["attempts"])<=LOCK["max_attempts"] and
         len(obj["admitted"])<=LOCK["max_accepted_generations"] and
         isinstance(obj.get("current_generation"),int) and
         2<=obj["current_generation"]<=8,
         "V54_UNTRUSTED_STATE")
    return obj


def ledger_at(folder):
    p=Path(folder)/STATE_REL
    return validate_ledger(state.load(p)) if p.exists() else initial()


def safe_source(root,repo):
    root=Path(root)
    f=root/SOURCE_PATH
    fail(f.is_file() and not f.is_symlink() and
         f.stat().st_size<=MAX_BYTES,"V54_UNSAFE_SOURCE")
    raw=f.read_bytes()
    obj=json.loads(raw.decode("utf-8"),
                   object_pairs_hook=lambda pairs: unique(pairs))
    fail(isinstance(obj,dict),"V54_INVALID_OBJECT")
    return hashlib.sha256(raw).hexdigest(),obj


def unique(pairs):
    obj={}
    for k,v in pairs:
        fail(k not in obj,"V54_DUPLICATE_JSON_KEY")
        obj[k]=v
    return obj


def rows(repo,doc,keys,paraphrase=False):
    out=[]
    for key in keys:
        value=doc.get(key)
        fail(type(value) in (str,bool,int),"V54_UNSUPPORTED_SOURCE_VALUE")
        answer=str(value).lower() if type(value)==bool else str(value)
        fail(1<=len(answer)<=62 and not state.SECRET.search(answer),
             "V54_UNSAFE_LABEL")
        prompt=(f"В PROJECT_STATUS.json репозитория {repo} найди свойство {key}. "
                "Напиши только его значение, без кавычек."
                if paraphrase else
                f"What is the exact value of {key} in {repo}/PROJECT_STATUS.json? "
                "Output only the value.")
        out.append({"key":key,"prompt":prompt,"answer":answer})
    return out


def git_head(folder):
    sha=subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],
                                text=True,timeout=10).strip()
    fail(bool(state.SHA1.fullmatch(sha)),"V54_UNVERIFIED_GIT_COMMIT")
    return sha


def verify_memory(ledger):
    state.verify_ledger(ledger)
    memory=[]
    for row in ledger["memory"]:
        if row.get("source_repo") not in ("Hawkar-usls/Hrain","Hawkar-usls/Janus_Genesis"):
            continue
        if row.get("key") not in MEMORY_KEYS:
            continue
        fail(row.get("fact_digest")==state.digest({
             k:v for k,v in row.items() if k!="fact_digest"}) and
             row.get("training_verified_by_repository_sha") is True and
             isinstance(row.get("answer"),str) and
             1<=len(row["answer"])<=62,"V54_UNVERIFIED_MEMORY")
        memory.append({"key":row["key"],"answer":row["answer"],
                       "prompt":state.question(row["source_repo"],row["key"]),
                       "source_repo":row["source_repo"],
                       "source_commit":row["source_commit"],
                       "source_file_sha256":row["source_file_sha256"],
                       "fact_digest":row["fact_digest"],
                       "training_verified_by_repository_sha":True})
    fail(len(memory)>=4,"V54_MEMORY_NOT_VERIFIED")
    return memory[-4:]


def plan(lock,ledger,roots,holdout_commits,memory):
    """Review new factual cohorts from peer repos; never read examination bytes."""
    fail(lock==LOCK,"V54_LOCK_DRIFT")
    validate_ledger(ledger)
    fail(isinstance(holdout_commits,dict) and set(holdout_commits)==set(HOLDOUTS)
         and all(isinstance(v,str) and bool(state.SHA1.fullmatch(v))
                 for v in holdout_commits.values()),"V54_UNFROZEN_HOLDOUTS")
    if len(ledger["attempts"])>=LOCK["max_attempts"] or len(ledger["admitted"])>=LOCK["max_accepted_generations"]:
        return sealed({"schema":PLAN,"action":"HOLD_BUDGET","lock_sha256":state.digest(lock)})
    seen={x["task_digest"] for x in ledger["attempts"]}
    used={(x["holdout_repo"],x["holdout_commit"])
          for x in ledger["attempts"]}
    for sid,(repo,keys) in TRAIN.items():
        directory=Path(roots)/sid
        source_sha,doc=safe_source(directory,repo)
        examples=rows(repo,doc,keys)
        task=state.digest({"source_id":sid,"rows":examples})
        hr,hkeys=HOLDOUTS[sid]
        hc=holdout_commits[sid]
        if task in seen or (hr,hc) in used:
            continue
        return sealed({
            "schema":PLAN,"action":"TRAIN_SHADOW",
            "lock_sha256":state.digest(lock),
            "prior_ledger_sha256":ledger["sha256"],
            "task_digest":task,
            "source_id":sid,"source_repo":repo,
            "source_path":SOURCE_PATH,"source_commit":git_head(directory),
            "source_sha256":source_sha,"source_rows":examples,
            "holdout_repo":hr,"holdout_commit":hc,
            "holdout_path":SOURCE_PATH,"holdout_keys":list(hkeys),
            "parent_generation":ledger["current_generation"],
            "parent_adapter_sha256":ledger["current_adapter_sha256"],
            "parent_lineage_sha256":ledger["current_lineage_sha256"],
            "parent_path":ledger["current_parent_path"],
            "memory_replay":memory,
            "production_promotion":False,"sentinel_dispatch":False,
            "external_validation":False,
        })
    return sealed({"schema":PLAN,"action":"NO_FRESH_PAIRED_SOURCE_FACTS",
                   "lock_sha256":state.digest(lock),
                   "production_promotion":False})

def verify_plan(p,lock,ledger=None):
    checked(p)
    fail(lock==LOCK and p.get("schema")==PLAN and
         p.get("action")=="TRAIN_SHADOW" and
         p.get("lock_sha256")==state.digest(lock),"V54_BAD_PLAN")
    sid=p.get("source_id")
    fail(sid in TRAIN,"V54_UNTRUSTED_SOURCE_ID")
    repo,keys=TRAIN[sid]
    fail(p.get("source_repo")==repo and p.get("source_path")==SOURCE_PATH and
         p.get("holdout_repo")==HOLDOUTS[sid][0] and
         p.get("holdout_keys")==list(HOLDOUTS[sid][1]) and
         p.get("holdout_path")==SOURCE_PATH and
         isinstance(p.get("source_commit"),str) and
         bool(state.SHA1.fullmatch(p["source_commit"])) and
         isinstance(p.get("holdout_commit"),str) and
         bool(state.SHA1.fullmatch(p["holdout_commit"])) and
         isinstance(p.get("source_sha256"),str) and
         bool(state.HEX.fullmatch(p["source_sha256"])) and
         p.get("task_digest")==state.digest({"source_id":sid,
                                            "rows":p.get("source_rows")}) and
         p.get("source_rows")==rows(repo,{
              r["key"]:r["answer"] for r in p["source_rows"]},keys) and
         p.get("production_promotion") is False and
         p.get("sentinel_dispatch") is False and
         p.get("external_validation") is False,"V54_INVALID_OR_ESCALATED_PLAN")
    memory=p.get("memory_replay")
    fail(isinstance(memory,list) and len(memory)==4,
         "V54_MEMORY_PLAN_INVALID")
    for item in memory:
        repo=item.get("source_repo")
        fail(isinstance(item,dict) and
             repo in ("Hawkar-usls/Hrain","Hawkar-usls/Janus_Genesis") and
             item.get("key") in MEMORY_KEYS and
             isinstance(item.get("answer"),str) and
             1<=len(item["answer"])<=62 and
             not state.SECRET.search(item["answer"]) and
             item.get("prompt")==state.question(repo,item["key"]) and
             item.get("training_verified_by_repository_sha") is True and
             isinstance(item.get("source_commit"),str) and
             bool(state.SHA1.fullmatch(item["source_commit"])) and
             isinstance(item.get("source_file_sha256"),str) and
             bool(state.HEX.fullmatch(item["source_file_sha256"])) and
             isinstance(item.get("fact_digest"),str) and
             state.source_fact_memory(repo,item["source_file_sha256"],
                         item["source_commit"],
                         {"key":item["key"],"answer":item["answer"]})["fact_digest"]
                 ==item["fact_digest"],
             "V54_UNVERIFIED_MEMORY_IN_PLAN")
    if ledger is not None:
        validate_ledger(ledger)
        fail(p.get("prior_ledger_sha256")==ledger["sha256"] and
             p.get("parent_generation")==ledger["current_generation"] and
             p.get("parent_adapter_sha256")==ledger["current_adapter_sha256"] and
             p.get("parent_lineage_sha256")==ledger["current_lineage_sha256"] and
             p.get("parent_path")==ledger["current_parent_path"] and
             p["task_digest"] not in {a["task_digest"] for a in ledger["attempts"]} and
             (p["holdout_repo"],p["holdout_commit"]) not in
                 {(a["holdout_repo"],a["holdout_commit"]) for a in ledger["attempts"]},
             "V54_STALE_PLAN")
    return p


def sample_legacy():
    lock=oracle.lock_check(oracle.read("research/essence/peer_v46/oracle_lock.json"))
    samples=oracle.sample_set(lock,"train")[:8]
    return [{"key":"legacy","prompt":r["prompt"],"answer":r["expected"]} for r in samples]


def train_candidate(p,lock,parent,source_root,child):
    verify_plan(p,lock)
    sha,doc=safe_source(source_root,p["source_repo"])
    fail(sha==p["source_sha256"] and
         git_head(source_root)==p["source_commit"] and
         rows(p["source_repo"],doc,TRAIN[p["source_id"]][1])==p["source_rows"],
         "V54_TRAIN_SOURCE_MISMATCH")
    import torch
    start=time.monotonic()
    torch.manual_seed(5401)
    tk,model=neural.load_parent(parent,p,train=True)
    weights=[x for name,x in model.named_parameters() if x.requires_grad]
    trainable=sum(t.numel() for t in weights)
    fail(weights and trainable<=350000 and all(
         "lora_" in name for name,v in model.named_parameters() if v.requires_grad),
         "V54_NON_LORA_TRAINING")
    old=sample_legacy()
    memory=p["memory_replay"]
    samples=[]
    for i in range(lock["steps"]):
        lane=i%4
        if lane in (0,2):
            row=p["source_rows"][(i//2)%len(p["source_rows"])]
        elif lane==1:
            row=old[(i//4)%len(old)]
        else:
            row=memory[(i//4)%len(memory)]
        samples.append(row)
    opt=torch.optim.AdamW(weights,lr=lock["learning_rate"])
    losses=[]
    for row in samples:
        _,inputs,labels=neural.input_tokens(tk,row["prompt"],row["answer"])
        opt.zero_grad(set_to_none=True)
        loss=model(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                   labels=labels).loss
        fail(bool(torch.isfinite(loss)),"V54_NONFINITE_TRAINING_LOSS")
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(weights,1.0)
        fail(math.isfinite(float(norm)),"V54_GRADIENT_EXPLODED")
        opt.step()
        losses.append(round(float(loss.detach()),7))
    child=Path(child)
    fail(not child.exists(),"V54_CANDIDATE_EXISTS")
    child.mkdir(parents=True)
    model.save_pretrained(child,safe_serialization=True)
    data=(child/"adapter_model.safetensors").read_bytes()
    fail(len(data)<=6_000_000 and len(data)>2000,"V54_BAD_TENSORS")
    tensor_sha=hashlib.sha256(data).hexdigest()
    fail(tensor_sha!=p["parent_adapter_sha256"],"V54_NO_NEURAL_UPDATE")
    lineage=sealed({
        "schema":LINEAGE,"generation":p["parent_generation"]+1,
        "parent_generation":p["parent_generation"],
        "parent_adapter_sha256":p["parent_adapter_sha256"],
        "parent_lineage_sha256":p["parent_lineage_sha256"],
        "adapter_sha256":tensor_sha,"plan_sha256":p["sha256"],
        "steps":lock["steps"],"loss_trace":losses,
        "training_seconds":round(time.monotonic()-start,3),
        "trainable_adapter_parameters":trainable,
        "source_repo":p["source_repo"],"source_sha256":p["source_sha256"],
        "holdout_repo_opened_during_training":False,
        "peer_text_used_as_ground_truth":False,
        "production_promotion":False,"sentinel_dispatch":False,
    })
    state.store(child/"lineage.json",lineage)
    return lineage


def gate(metrics):
    k,h,r=metrics["source_paraphrase"],metrics["unseen_federated"],metrics["retention"]
    vals=(k["parent_nll"],k["child_nll"],h["parent_nll"],h["child_nll"],
          r["parent_nll"],r["child_nll"])
    fail(all(math.isfinite(x) for x in vals),"V54_NONFINITE_EXAM")
    return (
        k["paired_nll_gain"]>=LOCK["min_source_paraphrase_nll_gain"] and
        k["child_exact"]>=k["parent_exact"]+LOCK["min_source_paraphrase_exact_gain"] and
        h["paired_nll_gain"]>=-LOCK["max_holdout_nll_regression"] and
        h["child_exact"]>=h["parent_exact"] and
        r["paired_nll_gain"]>=-LOCK["max_retention_nll_regression"] and
        r["child_exact"]>=r["parent_exact"])


def evaluate(p,lock,parent,child,holdout_root):
    verify_plan(p,lock)
    lineage=state.check(state.load(Path(child)/"lineage.json"))
    weights=Path(child)/"adapter_model.safetensors"
    fail(lineage.get("schema")==LINEAGE and
         lineage.get("plan_sha256")==p["sha256"] and
         lineage.get("parent_adapter_sha256")==p["parent_adapter_sha256"] and
         lineage.get("generation")==p["parent_generation"]+1 and
         weights.is_file() and not weights.is_symlink() and
         hashlib.sha256(weights.read_bytes()).hexdigest()==lineage["adapter_sha256"],
         "V54_UNTRUSTED_TRAINED_CHILD")
    fail(git_head(holdout_root)==p["holdout_commit"],"V54_HOLDOUT_COMMIT_DRIFT")
    holdout_sha,holdout=safe_source(holdout_root,p["holdout_repo"])
    known=rows(p["source_repo"],{
        x["key"]:x["answer"] for x in p["source_rows"]},
        TRAIN[p["source_id"]][1],paraphrase=True)[:6]
    unseen=rows(p["holdout_repo"],holdout,HOLDOUTS[p["source_id"]][1],
                paraphrase=True)[:4]
    retained=sample_legacy()[:4]+p["memory_replay"]
    start=time.monotonic()
    tk,model=neural.load_parent(parent,p,train=False)
    before=[neural.scores(tk,model,x) for x in (known,unseen,retained)]
    model.load_adapter(str(child),adapter_name="v54_candidate",is_trainable=False)
    model.set_adapter("v54_candidate")
    model.eval()
    after=[neural.scores(tk,model,x) for x in (known,unseen,retained)]
    # Restore the exact parent adapter after the candidate is examined.
    # This is a model-level rollback probe, not a production-service rollback.
    model.set_adapter("default")
    restored=[neural.scores(tk,model,x) for x in (known,unseen,retained)]
    fail(all(a["exact"]==b["exact"] and a["answer"]==b["answer"]
             and abs(a["loss"]-b["loss"])<0.0001
             for lane_a,lane_b in zip(before,restored)
             for a,b in zip(lane_a,lane_b)),
         "V54_PARENT_MODEL_ROLLBACK_FAILED")
    metric={k:neural.metrics(x,y) for k,x,y in zip(
        ("source_paraphrase","unseen_federated","retention"),before,after)}
    passed=gate(metric)
    return sealed({
        "schema":EXAM,"plan_sha256":p["sha256"],
        "source_sha256":p["source_sha256"],
        "holdout_commit":p["holdout_commit"],
        "holdout_repo":p["holdout_repo"],
        "holdout_source_sha256":holdout_sha,
        "holdout_rows_sha256":state.digest(unseen),
        "parent_restored_after_shadow_exam":True,
        "parent_adapter_sha256":p["parent_adapter_sha256"],
        "child_adapter_sha256":lineage["adapter_sha256"],
        "child_lineage_sha256":lineage["sha256"],
        "candidate_generation":lineage["generation"],
        "metrics":metric,
        "status":"PASS_INTERNAL_SHADOW" if passed else "HOLD_NOT_BETTER",
        "training_seconds":lineage["training_seconds"],
        "exam_seconds":round(time.monotonic()-start,3),
        "total_wall_seconds":round(time.monotonic()-start+lineage["training_seconds"],3),
        "heldout_seen_only_after_weight_seal":True,
        "external_validation":False,"production_promotion":False,
        "sentinel_dispatch":False,
    })


def publish(folder,p,lock,exam,child):
    folder=Path(folder)
    ledger=ledger_at(folder)
    verify_plan(p,lock,ledger)
    checked(exam)
    lineage=state.check(state.load(Path(child)/"lineage.json"))
    fail(exam.get("schema")==EXAM and
         exam.get("plan_sha256")==p["sha256"] and
         exam.get("source_sha256")==p["source_sha256"] and
         exam.get("holdout_commit")==p["holdout_commit"] and
         exam.get("holdout_repo")==p["holdout_repo"] and
         isinstance(exam.get("holdout_source_sha256"),str) and
         bool(state.HEX.fullmatch(exam["holdout_source_sha256"])) and
         isinstance(exam.get("holdout_rows_sha256"),str) and
         bool(state.HEX.fullmatch(exam["holdout_rows_sha256"])) and
         exam.get("parent_restored_after_shadow_exam") is True and
         exam.get("parent_adapter_sha256")==p["parent_adapter_sha256"] and
         exam.get("child_adapter_sha256")==lineage["adapter_sha256"] and
         exam.get("child_lineage_sha256")==lineage["sha256"] and
         exam.get("status")==("PASS_INTERNAL_SHADOW"
                 if gate(exam["metrics"]) else "HOLD_NOT_BETTER") and
         exam.get("production_promotion") is False and
         exam.get("sentinel_dispatch") is False and
         exam.get("external_validation") is False and
         exam.get("heldout_seen_only_after_weight_seal") is True,
         "V54_EXAM_OR_AUTHORITY_FORGED")
    fail(hashlib.sha256((Path(child)/"adapter_model.safetensors").read_bytes()).hexdigest()
         ==lineage["adapter_sha256"] and
         lineage.get("parent_adapter_sha256")==p["parent_adapter_sha256"],
         "V54_CHILD_NOT_INHERITED")
    fail(not any(a.get("holdout_repo")==p["holdout_repo"] and
                 a.get("holdout_rows_sha256")==exam["holdout_rows_sha256"]
                 for a in ledger["attempts"]),
         "V54_REUSED_HOLDOUT_FACTS")
    accepted=exam["status"]=="PASS_INTERNAL_SHADOW"
    if accepted:
        dest=folder/f"models/v54gen{p['parent_generation']+1:04d}"
        fail(not dest.exists(),"V54_GENERATION_COLLISION")
        shutil.copytree(child,dest)
        ledger["current_generation"]+=1
        ledger["current_adapter_sha256"]=lineage["adapter_sha256"]
        ledger["current_lineage_sha256"]=lineage["sha256"]
        ledger["current_parent_path"]=f"models/v54gen{ledger['current_generation']:04d}"
        ledger["admitted"].append({"generation":ledger["current_generation"],
             "parent_adapter_sha256":p["parent_adapter_sha256"],
             "adapter_sha256":lineage["adapter_sha256"],
             "lineage_sha256":lineage["sha256"],
             "source_repo":p["source_repo"],"exam_sha256":exam["sha256"],
             "external_validation":False})
    ledger["attempts"].append({
        "task_digest":p["task_digest"],"source_id":p["source_id"],
        "holdout_repo":p["holdout_repo"],
        "holdout_commit":p["holdout_commit"],
        "holdout_rows_sha256":exam["holdout_rows_sha256"],
        "holdout_source_sha256":exam["holdout_source_sha256"],
        "source_sha256":p["source_sha256"],"parent_generation":p["parent_generation"],
        "candidate_generation":p["parent_generation"]+1,
        "exam_sha256":exam["sha256"],"status":exam["status"],
        "shadow_accepted":accepted,"production_promotion":False,
    })
    new=sealed({k:v for k,v in ledger.items() if k!="sha256"})
    target=folder/STATE_REL
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(new,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    receipt=sealed({"schema":"janus.essence.v54.attempt/5.4",
        "plan_sha256":p["sha256"],"exam_sha256":exam["sha256"],
        "candidate_adapter_sha256":lineage["adapter_sha256"],
        "shadow_accepted":accepted,"current_generation":new["current_generation"],
        "production_promotion":False})
    path=target.parent/"attempts"/(p["task_digest"][:24]+".json")
    state.store(path,receipt)
    return new


def main():
    a=argparse.ArgumentParser()
    a.add_argument("phase",choices=("plan","train","exam","publish"))
    a.add_argument("--lock",default=LOCK_REL)
    a.add_argument("--state")
    a.add_argument("--sources")
    a.add_argument("--holdout-commits")
    a.add_argument("--plan")
    a.add_argument("--parent")
    a.add_argument("--source")
    a.add_argument("--child")
    a.add_argument("--holdout")
    a.add_argument("--exam")
    a.add_argument("--memory")
    a.add_argument("--out")
    x=a.parse_args()
    lock=load_lock(x.lock)
    if x.phase=="plan":
        memory=verify_memory(state.load(x.memory))
        obj=plan(lock,ledger_at(x.state),x.sources,state.load(x.holdout_commits),memory)
    else:
        p=verify_plan(state.load(x.plan),lock)
        if x.phase=="train":
            obj=train_candidate(p,lock,x.parent,x.source,x.child)
        elif x.phase=="exam":
            obj=evaluate(p,lock,x.parent,x.child,x.holdout)
        else:
            obj=publish(x.state,p,lock,state.load(x.exam),x.child)
    if x.out:
        out=Path(x.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps({"phase":x.phase,"status":obj.get("status",obj.get("action","OK")),
                      "generation":obj.get("current_generation",
                                          obj.get("candidate_generation")),
                      "production_promotion":False},sort_keys=True))


if __name__=="__main__":
    main()
