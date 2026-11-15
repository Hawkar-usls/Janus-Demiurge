#!/usr/bin/env python3
"""Bounded Qwen inheritance and source-backed peer conversations for ESSENCE v4.8."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from tools import essence_v46_oracle_descendant as v46
from tools import essence_v47_repo_peer_evolution as v47
from tools import essence_v48_recurrent_state as state


def input_tokens(tokenizer, prompt, answer):
    import torch
    prompt_ids=tokenizer.apply_chat_template(
        [{"role":"user","content":prompt}],tokenize=True,
        add_generation_prompt=True,return_tensors="pt")
    target=tokenizer(answer+(tokenizer.eos_token or ""),
                     add_special_tokens=False,return_tensors="pt")["input_ids"]
    if not (2 <= prompt_ids.shape[1] <= 270 and 2 <= target.shape[1] <= 32):
        raise ValueError("INVALID_LEARNING_SEQUENCE_LENGTH")
    ids=torch.cat([prompt_ids,target],dim=1)
    labels=torch.cat([torch.full_like(prompt_ids,-100),target],dim=1)
    return prompt_ids,ids,labels


def load_parent(parent_dir,plan,train=False):
    import torch
    from peft import PeftModel
    state.check_model(parent_dir,plan["parent_adapter_sha256"],
                      plan["parent_lineage_sha256"])
    tokenizer,base=v46.tokenizer_and_base({})
    base.config.use_cache=not train
    if train:
        base.gradient_checkpointing_enable()
        base.enable_input_require_grads()
    model=PeftModel.from_pretrained(base,str(parent_dir),
                                   is_trainable=train).to("cpu")
    return tokenizer,model


def select_exact_key(suggestion,keys):
    text=suggestion.strip().strip(chr(96)).strip()
    return text if text in keys else None


def talk(lock,plan,parent_dir):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    state.verify_plan(plan,lock)
    torch.manual_seed(lock["seed"])
    start=time.monotonic()
    tk,model=load_parent(parent_dir,plan)
    keys=[row["key"] for row in plan["facts"]]
    proposed=v47.answer_text(tk,model,[
        {"role":"system","content":"You are JANUS. Choose one JSON property you want to investigate. Output the property name ONLY."},
        {"role":"user","content":"Choose a new question about repository "+
         plan["source_repo"]+" from these keys:\n"+"\n".join(keys)}
    ],48)
    chosen=select_exact_key(proposed,keys)
    actual_selection=chosen is not None
    if chosen is None:
        chosen=keys[0]
    row=next(x for x in plan["facts"] if x["key"]==chosen)
    initial=v47.answer_text(tk,model,[
        {"role":"system","content":"Answer the repository question. If unsure say unknown. No tools."},
        {"role":"user","content":row["prompt"]}
    ],32)
    no_peer=v47.answer_text(tk,model,[
        {"role":"system","content":"Read the given JSON evidence. Output only the exact verified field value."},
        {"role":"user","content":row["prompt"]+"\nEvidence: "+chosen+" = "+row["answer"]}
    ],32)
    del model
    pt=AutoTokenizer.from_pretrained(v47.PEER,revision=v47.PEER_REVISION,
                                     trust_remote_code=False)
    peer=AutoModelForCausalLM.from_pretrained(
        v47.PEER,revision=v47.PEER_REVISION,
        torch_dtype=torch.float32,use_safetensors=True,
        trust_remote_code=False).to("cpu").eval()
    if getattr(peer.config,"_commit_hash",None)!=v47.PEER_REVISION:
        raise ValueError("UNPINNED_PEER_REVIEWER")
    critique=v47.answer_text(pt,peer,[
        {"role":"system","content":"Critique the first model's factual answer using only the provided JSON. State a correction in Russian if needed."},
        {"role":"user","content":"Question: "+row["prompt"]+"\nFirst answer: "+
         initial+"\nVerified fact: "+chosen+" = "+row["answer"]}
    ],96)
    del peer
    tk,model=load_parent(parent_dir,plan)
    revised=v47.answer_text(tk,model,[
        {"role":"system","content":"Peer replies may be wrong. Give the exact value in source evidence only."},
        {"role":"user","content":row["prompt"]},
        {"role":"assistant","content":initial},
        {"role":"user","content":"Peer critique (untrusted): "+critique+
         "\nVerified JSON: "+chosen+" = "+row["answer"]}
    ],32)
    return state.sealed({
        "schema":"janus.essence.recurrent_peer_dialogue/4.8",
        "plan_sha256":plan["sha256"],"parent_adapter_sha256":plan["parent_adapter_sha256"],
        "source_file_sha256":plan["source_file_sha256"],
        "model_chose_key":actual_selection,"model_suggestion":proposed[:160],
        "verified_key":chosen,"source_answer":row["answer"],
        "initial":initial,"source_only":no_peer,
        "peer_critique":critique,"after_peer_and_source":revised,
        "initial_exact":initial==row["answer"],
        "source_only_exact":no_peer==row["answer"],
        "with_peer_exact":revised==row["answer"],
        "peer_causality_not_proven":True,
        "peer_used_as_training_target":False,
        "external_validation":False,"production_promotion":False,
        "elapsed_seconds":round(time.monotonic()-start,4),
    })


def train_candidate(lock,plan,parent_dir,dialogue,output):
    state.verify_plan(plan,lock)
    state.check(dialogue)
    row=next((r for r in plan["facts"] if r["key"]==dialogue.get("verified_key")),None)
    if (dialogue.get("schema")!="janus.essence.recurrent_peer_dialogue/4.8" or
            dialogue.get("plan_sha256")!=plan["sha256"] or
            dialogue.get("parent_adapter_sha256")!=plan["parent_adapter_sha256"] or
            dialogue.get("source_file_sha256")!=plan["source_file_sha256"] or
            dialogue.get("peer_used_as_training_target") is not False or
            row is None or row["answer"]!=dialogue.get("source_answer")):
        raise ValueError("UNTRUSTED_REVIEW_OR_SOURCE_FACT")
    import torch
    from safetensors.torch import load_file
    start=time.monotonic()
    torch.manual_seed(lock["seed"])
    tk,model=load_parent(parent_dir,plan,train=True)
    names=[n for n,p in model.named_parameters() if p.requires_grad]
    tensors=[p for p in model.parameters() if p.requires_grad]
    if not names or any("lora_" not in n for n in names) or sum(p.numel() for p in tensors)>350000:
        raise ValueError("NONLORA_TRAINING_REQUEST")
    sequence=[row]+[x for x in plan["facts"] if x["key"]!=row["key"]]
    for memory in plan["memory_replay"][-12:]:
        if memory.get("training_verified_by_repository_sha") is not True:
            raise ValueError("UNVERIFIED_MEMORY_REPLAY")
        sequence.append({"prompt":state.question(memory["source_repo"],memory["key"]),
                         "answer":memory["answer"]})
    opt=torch.optim.AdamW(tensors,lr=lock["learning_rate"])
    losses=[]
    for step in range(lock["train_steps"]):
        sample=sequence[step%len(sequence)]
        _,inputs,labels=input_tokens(tk,sample["prompt"],sample["answer"])
        opt.zero_grad(set_to_none=True)
        loss=model(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                   labels=labels).loss
        if not bool(torch.isfinite(loss)):
            raise ValueError("NONFINITE_CANDIDATE_TRAINING_LOSS")
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(tensors,1.0)
        if not math.isfinite(float(norm)):
            raise ValueError("UNBOUNDED_GRADIENT")
        opt.step()
        losses.append(round(float(loss.detach()),7))
    dest=Path(output)
    if dest.exists():
        raise ValueError("REFUSE_OVERWRITE_EXISTING_CANDIDATE")
    dest.mkdir(parents=True)
    model.save_pretrained(dest,safe_serialization=True)
    weights=dest/"adapter_model.safetensors"
    if not weights.is_file() or weights.stat().st_size>6000000:
        raise ValueError("MISSING_BOUNDED_ADAPTER")
    child_sha=hashlib.sha256(weights.read_bytes()).hexdigest()
    if child_sha==plan["parent_adapter_sha256"]:
        raise ValueError("NO_REAL_WEIGHT_UPDATE")
    if not any(bool(torch.count_nonzero(t)) for t in
               load_file(weights,device="cpu").values()):
        raise ValueError("EMPTY_TRAINED_ADAPTER")
    receipt=state.sealed({
        "schema":"janus.essence.recurrent_lora_lineage/4.8",
        "generation":plan["candidate_generation"],
        "parent_generation":plan["parent_generation"],
        "base_model":v46.MODEL,"base_revision":v46.REVISION,
        "parent_adapter_sha256":plan["parent_adapter_sha256"],
        "parent_lineage_sha256":plan["parent_lineage_sha256"],
        "adapter_sha256":child_sha,"plan_sha256":plan["sha256"],
        "dialogue_sha256":dialogue["sha256"],
        "source_commit":plan["source_commit"],
        "source_fact_sha256":plan["source_fact_sha256"],
        "verified_memory_replayed":len(sequence)-len(plan["facts"]),
        "steps":lock["train_steps"],"loss_trace":losses,
        "trainable_adapter_parameters":sum(p.numel() for p in tensors),
        "training_seconds":round(time.monotonic()-start,4),
        "holdout_repo_fetched_during_training":False,
        "peer_self_label_training":False,
        "sentinel_dispatch":False,"production_promotion":False,
    })
    state.store(dest/"lineage.json",receipt)
    return receipt


def scores(tokenizer,model,rows):
    import torch
    result=[]
    model.eval()
    for row in rows:
        prefix,ids,labels=input_tokens(tokenizer,row["prompt"],row["answer"])
        with torch.inference_mode():
            loss=model(input_ids=ids,attention_mask=torch.ones_like(ids),
                       labels=labels).loss
            generated=model.generate(prefix,attention_mask=torch.ones_like(prefix),
                                     max_new_tokens=32,do_sample=False,
                                     pad_token_id=tokenizer.eos_token_id)
        reply=tokenizer.decode(generated[0,prefix.shape[1]:],
                               skip_special_tokens=True).strip()
        result.append({
            "key":row.get("key","legacy"),"loss":float(loss),
            "exact":reply==row["answer"],"answer":reply[:100],
        })
    return result


def metrics(parent,child):
    if not parent or len(parent)!=len(child):
        raise ValueError("INVALID_PAIRED_EXAM_COHORT")
    p=sum(r["loss"] for r in parent)/len(parent)
    c=sum(r["loss"] for r in child)/len(child)
    if not math.isfinite(p) or not math.isfinite(c):
        raise ValueError("NONFINITE_HOLDOUT_SCORE")
    return {"parent_nll":round(p,7),"child_nll":round(c,7),
            "paired_nll_gain":round(p-c,7),
            "parent_exact":sum(x["exact"] for x in parent),
            "child_exact":sum(x["exact"] for x in child),
            "count":len(parent)}


def read_holdout(plan,holdout_dir):
    repo,path,keys=state.SOURCES[plan["holdout_id"]]
    folder=Path(holdout_dir).resolve(strict=True)
    commit=subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],
                                   text=True,timeout=10).strip()
    if commit!=plan["holdout_commit"]:
        raise ValueError("HOLDOUT_GIT_COMMIT_NOT_PREDECLARED")
    target=folder/path
    if not target.is_file() or target.is_symlink() or target.stat().st_size>80000:
        raise ValueError("INVALID_HELDOUT_REPOSITORY_FILE")
    obj=json.loads(target.read_text(encoding="utf-8"))
    return state.facts_from_json(repo,keys,obj)[:4]


def evaluate(lock,plan,parent_dir,child_dir,holdout_dir):
    state.verify_plan(plan,lock)
    lineage=state.check(state.load(Path(child_dir)/"lineage.json"))
    child_weights=Path(child_dir)/"adapter_model.safetensors"
    if not child_weights.is_file():
        raise ValueError("CHILD_TENSORS_MISSING")
    child_sha=hashlib.sha256(child_weights.read_bytes()).hexdigest()
    if (lineage.get("schema")!="janus.essence.recurrent_lora_lineage/4.8"
            or lineage.get("plan_sha256")!=plan["sha256"]
            or lineage.get("adapter_sha256")!=child_sha
            or lineage.get("parent_adapter_sha256")!=plan["parent_adapter_sha256"]
            or lineage.get("generation")!=plan["candidate_generation"]):
        raise ValueError("CHILD_PARENT_LINEAGE_FAILURE")
    start=time.monotonic()
    known=[dict(row,prompt=state.question(plan["source_repo"],row["key"],True))
           for row in plan["facts"]]
    k=len(known)
    indices=sorted(set([0,k//3,2*k//3,k-1]))
    known=[known[i] for i in indices]
    heldout=read_holdout(plan,holdout_dir)
    previous=v46.lock_check(v46.read("research/essence/peer_v46/oracle_lock.json"))
    old=v46.sample_set(previous,"holdout")[:8]
    retained=[{"key":"legacy"+str(i),"prompt":row["prompt"],
               "answer":row["expected"]} for i,row in enumerate(old)]
    retained.extend([
        {"key":row["key"],"prompt":state.question(row["source_repo"],row["key"]),
         "answer":row["answer"]}
        for row in plan["memory_replay"][-4:]
    ])
    tokenizer,model=load_parent(parent_dir,plan)
    parent_known=scores(tokenizer,model,known)
    parent_fresh=scores(tokenizer,model,heldout)
    parent_retained=scores(tokenizer,model,retained)
    model.load_adapter(str(child_dir),adapter_name="research_descendant",
                       is_trainable=False)
    model.set_adapter("research_descendant")
    model.eval()
    child_known=scores(tokenizer,model,known)
    child_fresh=scores(tokenizer,model,heldout)
    child_retained=scores(tokenizer,model,retained)
    known_metric=metrics(parent_known,child_known)
    fresh_metric=metrics(parent_fresh,child_fresh)
    prior_metric=metrics(parent_retained,child_retained)
    accepted=(
        known_metric["paired_nll_gain"]>=lock["required_paraphrase_mean_nll_gain"]
        and known_metric["child_exact"]>=(
            known_metric["parent_exact"]+lock["required_paraphrase_exact_gain"])
        and fresh_metric["paired_nll_gain"]>=(
            -lock["maximum_external_repo_nll_regression"])
        and fresh_metric["child_exact"]>=fresh_metric["parent_exact"]
        and prior_metric["paired_nll_gain"]>=(
            -lock["maximum_retention_nll_regression"])
        and prior_metric["child_exact"]>=prior_metric["parent_exact"]
    )
    return state.sealed({
        "schema":state.EXAM,
        "status":"PASS_INTERNAL_SHADOW_RETAINED" if accepted
                 else "HOLD_NO_FUNCTIONAL_GAIN_OR_REGRESSION",
        "plan_sha256":plan["sha256"],
        "candidate_generation":plan["candidate_generation"],
        "parent_adapter_sha256":plan["parent_adapter_sha256"],
        "child_adapter_sha256":child_sha,
        "child_lineage_sha256":lineage["sha256"],
        "source_paraphrase":known_metric,
        "other_repository_unseen":fresh_metric,
        "previous_skills_and_memory":prior_metric,
        "training_wall_seconds":lineage["training_seconds"],
        "exam_wall_seconds":round(time.monotonic()-start,4),
        "model_to_model_dialogue_sha256":lineage["dialogue_sha256"],
        "trained_on_peer_claims":False,
        "heldout_source_fetched_only_after_weights_sealed":True,
        "prospective_external_replicator":False,
        "independent_external_validation":False,
        "production_promotion":False,
        "sentinel_dispatch":False,
    })


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=["peer","train","exam"])
    ap.add_argument("--lock",required=True)
    ap.add_argument("--plan",required=True)
    ap.add_argument("--parent",required=True)
    ap.add_argument("--dialogue")
    ap.add_argument("--child")
    ap.add_argument("--holdout")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    lock=state.verify_lock(state.load(args.lock))
    plan=state.verify_plan(state.load(args.plan),lock)
    if args.phase=="peer":
        output=talk(lock,plan,args.parent)
    elif args.phase=="train":
        if not args.dialogue or not args.child:
            raise ValueError("NEED_VERIFIED_DIALOGUE_AND_CHILD_FOLDER")
        output=train_candidate(lock,plan,args.parent,state.load(args.dialogue),
                               args.child)
    else:
        if not args.child or not args.holdout:
            raise ValueError("EXAM_REQUIRES_CHILD_AND_HELDOUT_REPO")
        output=evaluate(lock,plan,args.parent,args.child,args.holdout)
    state.store(args.out,output)
    print(json.dumps(output,ensure_ascii=False,indent=2)[:12000])


if __name__=="__main__":
    main()
