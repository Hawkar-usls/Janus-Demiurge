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


def train_one(lock,mode,parent,lapis_dir,ledger,out_dir):
    import torch
    import torch.nn.functional as F
    from safetensors.torch import load_file

    validate_lock(lock)
    source_sha,lapis_rows,memory,old=source_verified_training(
        lock,lapis_dir,ledger)
    schedule=make_schedule(mode,lapis_rows,memory,old,lock)
    torch.manual_seed(lock["seed"])
    start=time.monotonic()
    tk,model=load_g2(parent)
    names=[name for name,p in model.named_parameters() if p.requires_grad]
    parameters=[p for p in model.parameters() if p.requires_grad]
    if (not names or any("lora_" not in name for name in names)
            or sum(p.numel() for p in parameters)>350000):
        raise ValueError("NATIVE_BASE_WEIGHT_UNFROZEN")
    teacher={}
    if mode=="replay":
        model.eval()
        for row in old:
            _,ids,labels=tokens(tk,row)
            with torch.no_grad():
                outputs=model(input_ids=ids,attention_mask=torch.ones_like(ids))
                mask=labels[:,1:]!=-100
                teacher[row["prompt"]]=outputs.logits[:,:-1,:][mask].detach().clone()
        model.train()
    optimizer=torch.optim.AdamW(parameters,lr=lock["learning_rate"])
    losses=[]
    for sample in schedule:
        _,inputs,labels=tokens(tk,sample)
        optimizer.zero_grad(set_to_none=True)
        out=model(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                  labels=labels)
        loss=out.loss
        if sample["source_lane"]=="old" and mode=="replay":
            mask=labels[:,1:]!=-100
            student=out.logits[:,:-1,:][mask]
            if student.shape!=teacher[sample["prompt"]].shape:
                raise ValueError("DISTILLATION_TOKEN_MASK_DRIFT")
            temperature=lock["parent_distill_temperature"]
            loss=loss+(lock["parent_distill_lambda"]*temperature*temperature) * (
                F.kl_div(
                    F.log_softmax(student/temperature,dim=-1),
                    F.softmax(teacher[sample["prompt"]]/temperature,dim=-1),
                    reduction="batchmean"))
        if not bool(torch.isfinite(loss)):
            raise ValueError("NONFINITE_REHEARSAL_LOSS")
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(parameters,1.0)
        if not math.isfinite(float(norm)):
            raise ValueError("BAD_REPLAY_GRADIENT")
        optimizer.step()
        losses.append(round(float(loss.detach()),7))
    directory=Path(out_dir)
    if directory.exists():
        raise ValueError("REFUSE_CHECKPOINT_OVERWRITE")
    directory.mkdir(parents=True)
    model.save_pretrained(directory,safe_serialization=True)
    weights=directory/"adapter_model.safetensors"
    if not weights.is_file() or weights.stat().st_size>6000000:
        raise ValueError("NO_SAVED_LORA_TENSORS")
    weight_sha=hashlib.sha256(weights.read_bytes()).hexdigest()
    if weight_sha==state.GEN2_SHA or not any(bool(torch.count_nonzero(x)) for x in
            load_file(weights,device="cpu").values()):
        raise ValueError("UNMODIFIED_OR_EMPTY_DESCENDANT")
    receipt=state.sealed({
        "schema":TRAIN_SCHEMA,
        "mode":mode,"lock_sha256":state.digest(lock),
        "parent_model_sha256":state.GEN2_SHA,
        "parent_lineage_sha256":state.GEN2_LINEAGE,
        "new_repo_source_sha256":source_sha,
        "new_repo_commit":lock["new_train_source"]["commit"],
        "source_verified_memory_sha256":state.digest(memory),
        "old_replay_sha256":state.digest(old),
        "schedule_sha256":state.digest([
            {"key":x["key"],"lane":x["source_lane"]} for x in schedule]),
        "training_steps":len(losses),
        "new_source_steps":sum(x["source_lane"]=="new" for x in schedule),
        "legacy_replay_steps":sum(x["source_lane"]=="old" for x in schedule),
        "memory_replay_steps":sum(x["source_lane"]=="memory" for x in schedule),
        "parent_distillation_used":mode=="replay",
        "teacher_logits_from_parent_only":mode=="replay",
        "trainable_lora_parameters":sum(p.numel() for p in parameters),
        "loss_trace":losses,
        "training_wall_seconds":round(time.monotonic()-start,4),
        "adapter_sha256":weight_sha,
        "exam_data_seen_during_training":False,
        "native_janus_weight_updates":False,
        "sentinel_dispatch":False,
        "model_promotion":False,
    })
    state.store(directory/"lineage.json",receipt)
    return receipt


def candidate_check(path,lock,mode,lapis_sha):
    root=Path(path)
    evidence=state.check(read_locked(root/"lineage.json"))
    weights=root/"adapter_model.safetensors"
    if (not weights.is_file() or weights.stat().st_size>6000000 or
            evidence.get("schema")!=TRAIN_SCHEMA or evidence.get("mode")!=mode or
            evidence.get("lock_sha256")!=state.digest(lock) or
            evidence.get("parent_model_sha256")!=state.GEN2_SHA or
            evidence.get("new_repo_source_sha256")!=lapis_sha or
            evidence.get("training_steps")!=lock["max_steps_per_candidate"] or
            evidence.get("model_promotion") is not False or
            hashlib.sha256(weights.read_bytes()).hexdigest()!=evidence.get("adapter_sha256")):
        raise ValueError("TAMPERED_OR_NONCOMPARABLE_CANDIDATE_"+mode)
    return evidence


def inference_tokens(tk,row):
    # Read-only evaluation has no backpropagation.
    return tokens(tk,row)


def evaluate_one(tk,model,rows):
    import torch
    outcomes=[]
    model.eval()
    for row in rows:
        prefix,ids,labels=inference_tokens(tk,row)
        with torch.inference_mode():
            loss=model(input_ids=ids,attention_mask=torch.ones_like(ids),
                       labels=labels).loss
            prediction=model.generate(
                prefix,attention_mask=torch.ones_like(prefix),
                max_new_tokens=32,do_sample=False,
                pad_token_id=tk.eos_token_id)
        guess=tk.decode(prediction[0,prefix.shape[1]:],
                        skip_special_tokens=True).strip()
        val=float(loss)
        if not math.isfinite(val):
            raise ValueError("NONFINITE_PAIRED_EXAM_NLL")
        outcomes.append({
            "key":row["key"],
            "nll":val,
            "correct":guess==row["answer"],
            "reply":guess[:100],
        })
    return outcomes


def summarize(rows):
    return {
        "count":len(rows),
        "exact_correct":sum(row["correct"] for row in rows),
        "mean_token_nll":round(sum(row["nll"] for row in rows)/len(rows),7),
    }


def exam(lock,parent,naive,replay,payload,commitment,memory_ledger):
    import torch
    from peft import PeftModel

    validate_lock(lock)
    validate_commitment(lock,payload,commitment)
    _,lapis_checksum=frozen_source_verify_payload(lock,payload)
    n=candidate_check(naive,lock,"naive",lapis_checksum)
    r=candidate_check(replay,lock,"replay",lapis_checksum)
    if (n["training_steps"]!=r["training_steps"] or
            n["new_repo_commit"]!=r["new_repo_commit"] or
            n["new_repo_source_sha256"]!=r["new_repo_source_sha256"]):
        raise ValueError("UNEQUAL_TRAINING_BUDGET_OR_SOURCE")
    memory=approved_memory(memory_ledger)
    if state.digest(memory)!=(n["source_verified_memory_sha256"]):
        raise ValueError("PARENT_MEMORY_MOVED_BETWEEN_TRAIN_AND_EXAM")
    rehearsal=[
        {"key":x["key"],
         "prompt":state.question(x["source_repo"],x["key"],True),
         "answer":x["answer"]}
        for x in memory
    ]
    cohorts={
        "prospective_fresh_legacy":payload["fresh_legacy_routes"],
        "prospective_new_repository":payload["other_repo_unseen"],
        "source_paraphrases":payload["source_paraphrase"],
        "known_memory_paraphrases":rehearsal,
    }
    state.check_model(parent,state.GEN2_SHA,state.GEN2_LINEAGE)
    torch.set_num_threads(4)
    tk,base=v46.tokenizer_and_base({})
    base.config.use_cache=True
    model=PeftModel.from_pretrained(base,str(parent),is_trainable=False).eval()
    start=time.monotonic()
    results={}
    for mode,root in (("parent",parent),("naive",naive),("replay",replay)):
        if mode!="parent":
            model.load_adapter(str(root),adapter_name=mode,is_trainable=False)
            model.set_adapter(mode)
        results[mode]={}
        for cohort,rows in cohorts.items():
            results[mode][cohort]=summarize(evaluate_one(tk,model,rows))
    route_p=results["parent"]["prospective_fresh_legacy"]["exact_correct"]
    route_n=results["naive"]["prospective_fresh_legacy"]["exact_correct"]
    route_r=results["replay"]["prospective_fresh_legacy"]["exact_correct"]
    new_p=results["parent"]["source_paraphrases"]["exact_correct"]
    new_r=results["replay"]["source_paraphrases"]["exact_correct"]
    cosmos_p=results["parent"]["prospective_new_repository"]["exact_correct"]
    cosmos_r=results["replay"]["prospective_new_repository"]["exact_correct"]
    mem_p=results["parent"]["known_memory_paraphrases"]["exact_correct"]
    mem_r=results["replay"]["known_memory_paraphrases"]["exact_correct"]
    thresholds=lock["exam"]
    dev_pass=(
        route_r>=route_p-thresholds["legacy_exact_allowed_drop"] and
        route_r>=route_n+thresholds["legacy_replay_must_beat_baseline_by"] and
        new_r>=new_p+thresholds["source_paraphrase_exact_gain_min"] and
        cosmos_r>=cosmos_p-thresholds["external_repo_exact_allowed_drop"] and
        mem_r>=mem_p
    )
    return state.sealed({
        "schema":EXAM_SCHEMA,
        "label":("PASS_INTERNAL_PROSPECTIVE_REPLAY_RETAINED" if dev_pass else
                 "HOLD_REPLAY_DID_NOT_CLEAR_PREDECLARED_GATES"),
        "lock_sha256":state.digest(lock),
        "exam_commitment_sha256":commitment["sha256"],
        "exam_payload_sha256":payload["sha256"],
        "source_repo_sha256":lapis_checksum,
        "parent_weights_sha256":state.GEN2_SHA,
        "naive_weights_sha256":n["adapter_sha256"],
        "replay_weights_sha256":r["adapter_sha256"],
        "training_steps_matched":True,
        "train_seconds":{"naive":n["training_wall_seconds"],
                         "replay":r["training_wall_seconds"]},
        "evaluation_seconds":round(time.monotonic()-start,4),
        "comparative_results":results,
        "route_retention_delta_replay_minus_naive":route_r-route_n,
        "route_retention_delta_replay_minus_parent":route_r-route_p,
        "changed_exact_new_source":new_r-new_p,
        "new_repo_exact_delta":cosmos_r-cosmos_p,
        "known_memory_exact_delta":mem_r-mem_p,
        "prospective_internal_separate_job":True,
        "holdout_repos_available_to_training_job":False,
        "external_independent_exam":False,
        "automatic_model_admission":False,
        "native_janus_modified":False,
        "sentinel_dispatch":False,
    })


def frozen_source_verify_payload(lock,payload):
    if (payload.get("source_commit_sha")!=lock["new_train_source"]["commit"]
            or payload.get("other_repo_commit_sha")!=
               lock["prospective_holdout_source"]["commit"]):
        raise ValueError("PROSPECTIVE_SOURCE_COMMIT_CHANGED")
    for category in ("source_paraphrase","other_repo_unseen"):
        spec=(lock["new_train_source"] if category=="source_paraphrase" else
              lock["prospective_holdout_source"])
        rows=payload[category]
        if len(rows)!=len(spec["keys"]):
            raise ValueError("CHANGED_PROSPECTIVE_FIELDS")
        for row,key in zip(rows,spec["keys"]):
            prompt=(state.question(spec["repo"],key,True) if
                category=="source_paraphrase" else state.question(spec["repo"],key))
            if row.get("key")!=key or row.get("prompt")!=prompt:
                raise ValueError("UNTRUSTED_PROSPECTIVE_QUESTION")
    # Saved SHA-256 from exact source bytes; this is the same hash checked by
    # candidate lineage, not an attempt to treat test labels as external truth.
    seen=set()
    for row in payload["fresh_legacy_routes"]:
        import re
        m=re.search(r"Decode tag ([KL]-[0-9a-f]{8})\.",row.get("prompt",""))
        if not m or m.group(1) in seen or v46.oracle_a(m.group(1))!=row["answer"]:
            raise ValueError("BAD_FRESH_ROUTE_ORACLE")
        seen.add(m.group(1))
    return payload["other_repo_sha256"],payload["source_sha256"]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("cmd",choices=("freeze","train","exam"))
    parser.add_argument("--lock",default=LOCK_PATH)
    parser.add_argument("--lapis")
    parser.add_argument("--cosmos")
    parser.add_argument("--state")
    parser.add_argument("--parent")
    parser.add_argument("--mode",choices=("naive","replay"))
    parser.add_argument("--naive")
    parser.add_argument("--replay")
    parser.add_argument("--payload")
    parser.add_argument("--commitment")
    parser.add_argument("--out")
    parser.add_argument("--commit-out")
    args=parser.parse_args()
    lock=validate_lock(read_locked(args.lock))
    if args.cmd=="freeze":
        if not args.lapis or not args.cosmos or not args.out or not args.commit_out:
            raise ValueError("FREEZE_MUST_HAVE_BOTH_PINNED_REPOSITORIES")
        payload,commitment=prepare_exam(lock,args.lapis,args.cosmos)
        state.store(args.out,payload)
        state.store(args.commit_out,commitment)
        print(json.dumps({"pretrained_exam_commit_sha":commitment["sha256"],
                          "exam_payload_sha":payload["sha256"],
                          "cohort_sizes":commitment["cohort_sizes"]},indent=2))
    elif args.cmd=="train":
        if not args.lapis or not args.state or not args.parent or not args.mode or not args.out:
            raise ValueError("PARENT_TRAIN_SOURCE_AND_OUTPUT_REQUIRED")
        ledger=read_locked(Path(args.state)/
            "research/essence/peer_v48_state/ledger.json")
        result=train_one(lock,args.mode,args.parent,args.lapis,ledger,args.out)
        print(json.dumps({k:v for k,v in result.items() if k!="loss_trace"},indent=2))
    else:
        if not all((args.state,args.parent,args.naive,args.replay,args.payload,
                    args.commitment,args.out)):
            raise ValueError("PROSPECTIVE_PAIRED_EXAM_REQUIRES_BOTH_CANDIDATES")
        state.verify_ledger(read_locked(Path(args.state)/
            "research/essence/peer_v48_state/ledger.json"))
        result=exam(lock,args.parent,args.naive,args.replay,read_locked(args.payload),
                    read_locked(args.commitment),
                    read_locked(Path(args.state)/
                        "research/essence/peer_v48_state/ledger.json"))
        state.store(args.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2)[:18000])


if __name__=="__main__":
    main()
