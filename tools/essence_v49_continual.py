#!/usr/bin/env python3
"""ESSENCE v4.9: one-shot prospective, equal-cost naive vs continual Qwen LoRA.

No production or Sentinel powers. Test cohort is generated and SHA-committed
before training, in another Actions job; this is internally prospective,
NOT an independent external custodian or cryptographically private exam.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
import subprocess
import time
from pathlib import Path

from tools import essence_v46_oracle_descendant as v46
from tools import essence_v48_recurrent_state as state

SCHEMA = "janus.essence.continual_prospective_lock/4.9"
EXAM_SCHEMA = "janus.essence.continual_prospective_exam/4.9"
TEST_SCHEMA = "janus.essence.continual_exam_payload/4.9"
TRAIN_SCHEMA = "janus.essence.continual_candidate/4.9"
LOCK_PATH = "research/essence/peer_v49/FROZEN_PROSPECTIVE_LOCK.json"


def validate_lock(l):
    mandatory = {
        "schema": SCHEMA, "status": "FIRST_PROSPECTIVE_INTERNAL_PAIRED_TRIAL_FROZEN",
        "base_model": v46.MODEL, "base_revision": v46.REVISION,
        "parent_generation": 2,
        "parent_tensor_sha256": state.GEN2_SHA,
        "parent_lineage_sha256": state.GEN2_LINEAGE,
        "legacy_oracle": "JANUS_ROUTE_PREFIX_EXACT_TEXT",
        "legacy_eval_fresh_count": 16, "legacy_train_replay_count": 8,
        "memory_replay_count": 8, "max_steps_per_candidate": 40,
        "seed": 4901, "learning_rate": .00035,
        "baseline_schedule": ["new", "new", "new", "new"],
        "replay_schedule": ["new", "new", "old", "memory"],
        "parent_distill_on_old": True,
        "parent_distill_temperature": 2.0,
        "parent_distill_lambda": .4, "max_model_response_tokens": 32,
        "no_training_access_to_exam_payload": True,
        "prospective_exam_generated_before_training": True,
        "human_independent_custodian": False,
        "automated_research_model_acceptance": False,
        "production_model_updates": False, "native_janus_weight_changes": False,
        "sentinel_A_B_C_execution": False, "retune_after_exam": False,
    }
    for key,val in mandatory.items():
        if l.get(key) != val:
            raise ValueError("CHANGED_PREDECLARED_V49_LOCK_" + key)
    sources = {
        "new_train_source": {
            "repo": "Hawkar-usls/janus-lapis",
            "commit": "1d0ac3433b45296fa4d1636bf31ed25725663174",
            "path": "PROJECT_STATUS.json",
            "keys": ["schema_id","project","portfolio_class","last_reviewed",
                     "maturity","completion_status"]
        },
        "prospective_holdout_source": {
            "repo": "Hawkar-usls/Janus-Cosmos",
            "commit": "1582ba6f4d818d434ef65743dc6992e8b3645fab",
            "path": "PROJECT_STATUS.json",
            "keys": ["schema_id","project","repository","role",
                     "canonical_gate","canonical_status"]
        },
    }
    if any(l.get(k) != v for k,v in sources.items()):
        raise ValueError("SOURCE_COMMIT_OR_ALLOWED_KEYS_CHANGED")
    if l.get("exam") != {
        "source_paraphrase_exact_gain_min":1,
        "legacy_exact_allowed_drop":1,
        "external_repo_exact_allowed_drop":0,
        "legacy_replay_must_beat_baseline_by":1,
        "require_finite_paired_loss":True,
        "compare_equal_training_steps":True,
    }:
        raise ValueError("POSTHOC_EXAM_THRESHOLDS_CHANGED")
    return l


def read_locked(path,limit=100_000):
    return state.load(path,limit)


def frozen_source(directory, spec):
    root=Path(directory).resolve(strict=True)
    gitsha=subprocess.check_output(
        ["git","-C",str(root),"rev-parse","HEAD"],
        text=True,timeout=12).strip()
    if gitsha != spec["commit"]:
        raise ValueError("PROSPECTIVE_SOURCE_GIT_COMMIT_CHANGED")
    path=root/spec["path"]
    if (not path.is_file() or path.is_symlink() or
            not path.resolve().is_relative_to(root) or
            path.stat().st_size>65_000):
        raise ValueError("UNTRUSTED_SOURCE_PATH")
    content=path.read_bytes()
    obj=json.loads(content.decode("utf-8"))
    rows=state.facts_from_json(spec["repo"],spec["keys"],obj)
    if len(rows)!=len(spec["keys"]):
        raise ValueError("WRONG_SOURCE_ROW_COUNT")
    return hashlib.sha256(content).hexdigest(),rows


def new_route_questions(count):
    frozen_old=v46.lock_check(v46.read("research/essence/peer_v46/oracle_lock.json"))
    old=v46.sample_set(frozen_old,"train")+v46.sample_set(frozen_old,"holdout")
    used={x["code"] for x in old}
    result=[]
    for i in range(count):
        prefix="K" if i%2==0 else "L"
        while True:
            tag=prefix+"-"+secrets.token_hex(4)
            if tag not in used:
                used.add(tag)
                break
        expected=v46.oracle_a(tag)
        if v46.oracle_b(tag)!=expected:
            raise ValueError("TWO_OLD_ORACLES_DISAGREE")
        result.append({"key":"fresh-route-"+str(i),
            "prompt":f"JANUS relay decoder (synthetic laboratory task). Decode tag {tag}. Reply with the relay word only.",
            "answer":expected})
    return result


def prepare_exam(lock,lapis,cosmos):
    validate_lock(lock)
    lapis_sha,lapis_rows=frozen_source(lapis,lock["new_train_source"])
    cosmos_sha,cosmos_rows=frozen_source(cosmos,lock["prospective_holdout_source"])
    paraphrased=[
        {"key":r["key"],
         "prompt":state.question(lock["new_train_source"]["repo"],r["key"],True),
         "answer":r["answer"]}
        for r in lapis_rows
    ]
    # These sixteen random relay identifiers did not exist in the three
    # preceding v4.8 experiments. No train job receives this payload.
    fresh=new_route_questions(lock["legacy_eval_fresh_count"])
    payload=state.sealed({
        "schema":TEST_SCHEMA,
        "lock_sha256":state.digest(lock),
        "source_commit_sha":lock["new_train_source"]["commit"],
        "source_sha256":lapis_sha,
        "other_repo_commit_sha":lock["prospective_holdout_source"]["commit"],
        "other_repo_sha256":cosmos_sha,
        "source_paraphrase":paraphrased,
        "other_repo_unseen":cosmos_rows,
        "fresh_legacy_routes":fresh,
        "created_in_separate_pretraining_job":True,
        "outside_custodian":False,
        "training_job_access_authorized":False,
        "model_promotion":False,
    })
    commitment=state.sealed({
        "schema":"janus.essence.continual_pretraining_exam_commitment/4.9",
        "lock_sha256":state.digest(lock),
        "exam_payload_sha256":payload["sha256"],
        "source_commit_sha":lock["new_train_source"]["commit"],
        "other_repo_commit_sha":lock["prospective_holdout_source"]["commit"],
        "cohort_sizes":{"new_rephrased":len(paraphrased),
                        "other_repo":len(cosmos_rows),
                        "fresh_old_family":len(fresh)},
        "prospective_before_training":True,
        "not_externally_independent":True,
        "production_promotion":False,
    })
    return payload,commitment


def validate_commitment(lock,payload,commitment):
    state.check(payload)
    state.check(commitment)
    if (payload.get("schema") != TEST_SCHEMA or
            commitment.get("schema") !=
                "janus.essence.continual_pretraining_exam_commitment/4.9" or
            payload.get("lock_sha256")!=state.digest(lock) or
            commitment.get("lock_sha256")!=state.digest(lock) or
            commitment.get("exam_payload_sha256")!=payload["sha256"] or
            commitment.get("prospective_before_training") is not True or
            commitment.get("production_promotion") is not False or
            payload.get("training_job_access_authorized") is not False):
        raise ValueError("FROZEN_EXAM_PAYLOAD_OR_COMMITMENT_CHANGED")
    sizes=commitment["cohort_sizes"]
    for k,count in (("source_paraphrase",sizes["new_rephrased"]),
                    ("other_repo_unseen",sizes["other_repo"]),
                    ("fresh_legacy_routes",sizes["fresh_old_family"])):
        if len(payload.get(k,[]))!=count:
            raise ValueError("EXAM_COHORT_SIZE_TAMPER")
    return payload


def approved_memory(ledger):
    state.verify_ledger(ledger)
    seen=[]
    for item in ledger["memory"]:
        if (item.get("fact_digest")!=state.digest({
                k:v for k,v in item.items() if k!="fact_digest"}) or
                item.get("source_repo") not in (
                    "Hawkar-usls/Hrain","Hawkar-usls/Janus_Genesis") or
                item.get("key") not in ("schema_id","project","portfolio_class",
                                         "last_reviewed") or
                item.get("training_verified_by_repository_sha") is not True or
                not isinstance(item.get("answer"),str) or
                len(item["answer"])>62):
            raise ValueError("UNVERIFIED_G2_MEMORY")
        seen.append({"key":item["key"],
                     "prompt":state.question(item["source_repo"],item["key"]),
                     "answer":item["answer"],
                     "source_repo":item["source_repo"]})
    if len(seen)!=8:
        raise ValueError("EXACT_EIGHT_MEMORY_RECORDS_REQUIRED")
    return seen


def old_rehearsal(lock):
    v=v46.lock_check(v46.read("research/essence/peer_v46/oracle_lock.json"))
    all_rows=v46.sample_set(v,"train")
    rows=all_rows[:lock["legacy_train_replay_count"]]
    return [{"key":r["code"],"prompt":r["prompt"],"answer":r["expected"]}
            for r in rows]


def make_schedule(mode,lapis_rows,memory,old,lock):
    if mode not in ("naive","replay"):
        raise ValueError("UNKNOWN_NEURAL_TRAINING_MODE")
    rounds=lock["max_steps_per_candidate"]
    names=lock["baseline_schedule"] if mode=="naive" else lock["replay_schedule"]
    collections={"new":lapis_rows,"memory":memory,"old":old}
    index={"new":0,"memory":0,"old":0}
    training=[]
    for step in range(rounds):
        lane=names[step%len(names)]
        rows=collections[lane]
        item=rows[index[lane]%len(rows)]
        index[lane]+=1
        training.append(dict(item,source_lane=lane))
    if len(training)!=rounds:
        raise ValueError("UNBALANCED_COMPUTE_COMPARISON")
    return training


def load_g2(parent):
    import torch
    from peft import PeftModel
    state.check_model(parent,state.GEN2_SHA,state.GEN2_LINEAGE)
    tokenizer,base=v46.tokenizer_and_base({})
    base.config.use_cache=False
    base.gradient_checkpointing_enable()
    base.enable_input_require_grads()
    model=PeftModel.from_pretrained(base,str(parent),is_trainable=True).to("cpu")
    return tokenizer,model


def tokens(tokenizer,row):
    import torch
    p=tokenizer.apply_chat_template(
        [{"role":"user","content":row["prompt"]}],
        tokenize=True,add_generation_prompt=True,return_tensors="pt")
    a=tokenizer(row["answer"]+(tokenizer.eos_token or ""),
                add_special_tokens=False,return_tensors="pt")["input_ids"]
    if p.shape[1]>270 or not 2<=a.shape[1]<=32:
        raise ValueError("OVERLONG_OR_EMPTY_SUPERVISED_EXAMPLE")
    ids=torch.cat((p,a),dim=1)
    labels=torch.cat((torch.full_like(p,-100),a),dim=1)
    return p,ids,labels


def source_verified_training(lock,lapis_dir,ledger):
    source_sha,lapis_rows=frozen_source(lapis_dir,lock["new_train_source"])
    memory=approved_memory(ledger)
    old=old_rehearsal(lock)
    if {v["prompt"] for v in lapis_rows}&{v["prompt"] for v in old+memory}:
        raise ValueError("REPLAY_TRAIN_SPLIT_OVERLAP")
    return source_sha,lapis_rows,memory,old
