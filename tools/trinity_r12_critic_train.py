#!/usr/bin/env python3
"""TRINITY R1.2: corrected Hugging Face causal-LM LoRA critic on symbolic counterexamples.

This never reads the published R1 critic diagnostic, Genesis 64-case exam,
future R1.1 evaluation scripts or JANUS checkpoints. No critic truth authority.
The LoRA adapter is a disposable Actions artifact, never auto-merged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu

SCHEMA="janus.trinity.r12.critic_lora_train/1.0"
PROMPT_VERSION="trinity-r11-critic-prompt-v1"
SEED=20261123

def question(problem, proposal):
    return ("You are checking basic integer addition. Respond with exactly YES "
            "only if the proposed answer is ONE canonical decimal integer and "
            "it equals the mathematically correct sum. Otherwise respond with "
            "exactly NO. Never explain.\n"+problem+"\nProposed answer: "+
            proposal+"\nVerdict (YES or NO):")

def train_rows():
    rows=[]
    for i in range(48):
        a=31+(i*17)%87
        b=41+(i*23)%91
        problem=f"What is {a} plus {b}? Reply with a single nonnegative integer."
        true=str(a+b)
        choices=(("CORRECT",true,"YES"),
                 ("INCORRECT",str(a+b+2+i%5),"NO"),
                 ("AMBIGUOUS",f"Possibly {true} or {a+b+11}","NO"))
        for kind,proposal,answer in choices:
            rows.append({"id":f"R11-TRAIN-{i:03d}-{kind}",
                         "prompt":question(problem,proposal),
                         "answer":answer,"kind":kind,
                         "partition":"TRAIN_ONLY_SYMBOLIC_TRUTH"})
    assert len(rows)==144 and len({x["prompt"] for x in rows})==144
    return rows

def verify_train_rows(rows):
    if rows!=train_rows():
        raise ValueError("R11_TRAIN_SET_DRIFT")
    if any(x["partition"]!="TRAIN_ONLY_SYMBOLIC_TRUTH" for x in rows):
        raise ValueError("R11_NOT_TRAIN_ONLY")
    if any("700" in x["prompt"] or "900" in x["prompt"] for x in rows):
        raise ValueError("R11_EVAL_NUMERIC_DOMAIN_LEAK")
    return c.digest(rows)

def pack_hf_causal_labels(prefix, target):
    """HF AutoModelForCausalLM shifts labels INSIDE forward(loss).

    Inputs include the full prompt AND target. Mask precisely all prompt
    positions; the first assistant label must be at index len(prefix).
    NEVER pre-shift labels or truncate input_ids before calling HF model.
    """
    if (not isinstance(prefix,list) or not isinstance(target,list)
        or not prefix or not target
        or any(type(v) is not int or v < 0 for v in prefix+target)):
        raise ValueError("R12_INVALID_CAUSAL_PACK")
    full=prefix+target
    masked=[-100]*len(prefix)+target
    if len(full)!=len(masked) or masked[len(prefix)]!=target[0]:
        raise ValueError("R12_INTERNAL_LABEL_ALIGNMENT_FAILURE")
    return full,masked


def load_and_train(path:Path, receipt_path:Path, steps:int):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    if type(steps) is not int or not 12<=steps<=160:
        raise ValueError("R11_CRITIC_STEP_BUDGET")
    if path.exists() or path.is_symlink() or receipt_path.exists():
        raise ValueError("R11_ARTIFACT_MUST_BE_NEW")
    rows=train_rows()
    rows_hash=verify_train_rows(rows)
    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    tk,base=cpu.load_parent(c.SMOL)
    base.train()
    peft=LoraConfig(
        r=4,lora_alpha=8,lora_dropout=0.0,
        target_modules=["q_proj","v_proj"],bias="none",
        task_type=TaskType.CAUSAL_LM
    )
    model=get_peft_model(base,peft).train()
    param_count=sum(p.numel() for p in model.parameters() if p.requires_grad)
    # SmolLM2-135M has 30 layers. A rank-4 q/v LoRA legitimately
    # exceeds 200k params while remaining far below 1% of the base.
    if not 1<=param_count<=1_000_000:
        raise ValueError("R11_CRITIC_TRAINABLE_BUDGET")
    samples=[]
    for row in rows:
        prefix=tk.apply_chat_template(
            [{"role":"user","content":row["prompt"]}],tokenize=True,
            add_generation_prompt=True)
        target=tk.encode(row["answer"],add_special_tokens=False)+[tk.eos_token_id]
        seq,labels=pack_hf_causal_labels(prefix,target)
        if not 10<len(seq)<=240:
            raise ValueError("R12_CRITIC_CONTEXT_BUDGET")
        samples.append((torch.tensor([seq],dtype=torch.long),
                        torch.tensor([labels],dtype=torch.long)))
    optimizer=torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=8e-4,weight_decay=0.0)
    indices=list(range(len(samples)))
    random.Random(SEED).shuffle(indices)
    losses=[]
    started=time.monotonic()
    for step in range(steps):
        x,y=samples[indices[step%len(indices)]]
        outcome=model(input_ids=x,attention_mask=torch.ones_like(x),labels=y)
        loss=outcome.loss
        if not bool(torch.isfinite(loss).item()):
            raise ValueError("R11_CRITIC_NONFINITE_LOSS")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            (p for p in model.parameters() if p.requires_grad),1.0)
        optimizer.step()
        losses.append(float(loss.item()))
    path.mkdir(parents=True)
    model.save_pretrained(str(path),safe_serialization=True)
    weight_file=path/"adapter_model.safetensors"
    config_file=path/"adapter_config.json"
    if not weight_file.is_file() or not config_file.is_file():
        raise ValueError("R11_MISSING_ADAPTER_FILES")
    result=c.sealed({
        "schema":SCHEMA,"status":"CPU_LORA_TRAIN_ONLY__UNSEEN_EXAM_PENDING",
        "base":c.SMOL,"prompt_version":PROMPT_VERSION,
        "train_cases":len(rows),"train_source_sha256":rows_hash,
        "trainable_parameters":param_count,"steps":steps,"seed":SEED,
        "huggingface_causal_labels_internal_shift":True,
        "labels_preshifted_in_training_script":False,
        "original_R11_firstlook_reused_for_qualification":False,
        "first_loss":losses[0],"last_loss":losses[-1],
        "adapter_weight_sha256":hashlib.sha256(weight_file.read_bytes()).hexdigest(),
        "adapter_config_sha256":hashlib.sha256(config_file.read_bytes()).hexdigest(),
        "elapsed_seconds":round(time.monotonic()-started,3),
        "used_published_critic_diagnostic":False,
        "used_genesis_64":False,
        "read_future_r11_evaluation_cases":False,
        "authoritative_truth_from_model":False,
        "training_only":True,"production_promotion":False,
        "may_change_active_critic":False,
        "eligible_to_train_JANUS":False,
    })
    cpu.save_new(receipt_path,result)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--adapter",type=Path,required=True)
    ap.add_argument("--receipt",type=Path,required=True)
    ap.add_argument("--steps",type=int,default=96)
    a=ap.parse_args()
    r=load_and_train(a.adapter,a.receipt,a.steps)
    print(json.dumps({"status":r["status"],"train_cases":r["train_cases"],
                      "steps":r["steps"],"last_loss":r["last_loss"],
                      "weight_sha256":r["adapter_weight_sha256"],
                      "promotion":False},sort_keys=True))

if __name__=="__main__":
    main()
