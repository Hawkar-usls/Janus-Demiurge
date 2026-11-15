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
