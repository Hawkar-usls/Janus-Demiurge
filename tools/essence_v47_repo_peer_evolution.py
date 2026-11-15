#!/usr/bin/env python3
"""ESSENCE v4.7: inherit real Qwen LoRA weights, ask peer questions about JANUS,
verify answers against a frozen repository file, train from oracle facts only,
and compare frozen-parent versus descendant on a separate evaluation job.

Development research only. Model dialogue is UNTRUSTED, cannot edit files,
execute tools, train on its own unverified text, or command Sentinel A/B/C.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import time
from pathlib import Path

from tools import essence_v46_oracle_descendant as v46

SCHEMA = "janus.essence.repo_peer_generation/4.7"
PARENT_RUN = 43744199834
PARENT_LINEAGE_SHA = "6033aebc919988b782874fb59ac24a97679010640e9992c9a25f681709353184"
PARENT_ADAPTER_SHA = "ff2ee0257ef90d2ed7a19ba6de76456f8526709d7e9b76de06858d35bc2838db"
PEER = "HuggingFaceTB/SmolLM2-360M-Instruct"
PEER_REVISION = "a10cc1512eabd3dde888204e902eca88bddb4951"
SOURCE_PATH = "janus_model/JANUS_MODEL_MANIFEST-v1.json"
TRAIN_KEYS = (
    "model_id", "architecture.family", "architecture.tokenizer",
    "architecture.context_length", "architecture.n_heads", "architecture.n_layers",
    "training_source", "world_memory", "launcher",
    "modular_organism.repository_modules", "modular_organism.autonomous_merge",
    "authority.model_output_is_evidence",
)
UNSEEN_KEYS = (
    "architecture.d_model", "architecture.parameter_count", "checkpoint_path",
    "authority.checkpoint_promotion_requires_verification",
    "authority.general_intelligence_proven",
    "modular_organism.direct_cross_repo_brain_token",
)
MAX_STEPS = 24
SEED = 4701
LR = 0.0005
MAX_GENERATED = 100
TRAIN_THRESHOLD = 0.04
UNSEEN_REGRESSION_MAX = 0.08
RETENTION_REGRESSION_MAX = 0.15


def sha(x):
    return v46.digest(x)


def seal(x):
    return v46.seal(x)


def checked(x):
    return v46.check_seal(x)


def read_json(file):
    return v46.read(file, limit=150_000)


def write(file, obj):
    return v46.write(file, obj)


def validate_lock(lock):
    expected = {
        "schema": SCHEMA,
        "parent_model": v46.MODEL,
        "parent_model_revision": v46.REVISION,
        "parent_artifact_run_id": PARENT_RUN,
        "parent_manifest_sha256": PARENT_LINEAGE_SHA,
        "parent_adapter_sha256": PARENT_ADAPTER_SHA,
        "peer_model": PEER,
        "peer_model_revision": PEER_REVISION,
        "source_manifest": SOURCE_PATH,
        "train_keys": list(TRAIN_KEYS),
        "unseen_keys": list(UNSEEN_KEYS),
        "train_steps": MAX_STEPS,
        "lr": LR, "seed": SEED,
        "min_paraphrase_nll_gain": TRAIN_THRESHOLD,
        "max_unseen_nll_regression": UNSEEN_REGRESSION_MAX,
        "max_previous_generation_nll_regression": RETENTION_REGRESSION_MAX,
        "model_replies_are_ground_truth": False,
        "source_verification_required": True,
        "automatic_production_promotion": False,
        "native_janus_checkpoint_edit": False,
        "sentinel_dispatch": False,
        "independent_external_validation": False,
    }
    if {k:lock.get(k) for k in expected} != expected:
        raise ValueError("UNTRUSTED_OR_DRIFTED_PEER_TRAIN_LOCK")
    return lock


def source_bytes_and_json(root, lock):
    validate_lock(lock)
    root = Path(root).resolve(strict=True)
    path = root / SOURCE_PATH
    if (not path.is_file() or path.is_symlink() or
            not path.resolve().is_relative_to(root) or path.stat().st_size > 18_000):
        raise ValueError("UNTRUSTED_REPOSITORY_SOURCE_FILE")
    data = path.read_bytes()
    obj = json.loads(data.decode("utf-8"))
    if obj.get("schema") != "janus.native_model.manifest.v1":
        raise ValueError("UNRECOGNIZED_NATIVE_JANUS_MANIFEST")
    return hashlib.sha256(data).hexdigest(), obj


def value_at(obj, key):
    node = obj
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"ABSENT_REPOSITORY_KEY_{key}")
        node = node[part]
    if type(node) not in (int, str, bool) or (isinstance(node, str) and len(node) > 160):
        raise ValueError("UNSAFE_OR_UNBOUNDED_REPO_VALUE")
    return node


def expected_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def question(key, paraphrase=False):
    if paraphrase:
        return f"В исходном JANUS_MODEL_MANIFEST-v1.json найди свойство {key}. Напиши только его значение; строки без кавычек, true/false для логических полей."
    return f"Каково точное значение {key} в JANUS_MODEL_MANIFEST-v1.json? Выведи только значение (для строк без кавычек)."


def examples(obj, keys, paraphrase=False):
    return [{"key":k, "prompt":question(k,paraphrase),
             "answer":expected_text(value_at(obj,k))} for k in keys]


def freeze(root, lock):
    src, obj = source_bytes_and_json(root,lock)
    if len(set(TRAIN_KEYS+UNSEEN_KEYS)) != len(TRAIN_KEYS)+len(UNSEEN_KEYS):
        raise ValueError("CROSS_SPLIT_OVERLAPPING_SOURCE_FIELDS")
    train = examples(obj,TRAIN_KEYS)
    unseen = examples(obj,UNSEEN_KEYS)
    para = examples(obj,TRAIN_KEYS,True)
    assert len(train) == 12 and len(unseen) == 6 and len(para) == 12
    return seal({
        "schema": "janus.essence.repo_peer_source_lock/4.7",
        "source_manifest_sha256": src,
        "lock_sha256": sha(lock),
        "train_examples_sha256": sha(train),
        "unseen_exam_sha256": sha(unseen),
        "paraphrase_exam_sha256": sha(para),
        "train_count": len(train),
        "unseen_count": len(unseen),
        "paraphrase_count": len(para),
        "no_weight_update_in_freeze": True,
        "independent_external_exam": False,
        "repository_source_not_peer_opinion": True,
    })


def verify_freeze(root,lock,receipt):
    checked(receipt)
    if receipt != freeze(root,lock):
        raise ValueError("REPO_SOURCE_OR_HOLDOUT_COMMITMENT_DRIFT")
    return receipt


def verify_parent(directory):
    parent = Path(directory)
    manifest = checked(read_json(parent/"lineage.json"))
    weights = parent/"adapter_model.safetensors"
    if (manifest.get("sha256") != PARENT_LINEAGE_SHA or
            manifest.get("schema") != v46.TRAIN_SCHEMA or
            manifest.get("parent") != v46.MODEL or
            manifest.get("parent_revision") != v46.REVISION or
            manifest.get("automatic_promotion") is not False or
            manifest.get("sentinel_dispatch") is not False or
            manifest.get("adapter_sha256") != PARENT_ADAPTER_SHA or
            not weights.is_file() or weights.is_symlink() or
            weights.stat().st_size > 6_000_000 or
            hashlib.sha256(weights.read_bytes()).hexdigest() != PARENT_ADAPTER_SHA):
        raise ValueError("UNVERIFIED_PREVIOUS_GENERATION_CHECKPOINT")
    return manifest


def load_model(parent_dir, training):
    import torch
    from peft import PeftModel
    verify_parent(parent_dir)
    tokenizer, base = v46.tokenizer_and_base({})
    base.config.use_cache = not training
    if training:
        base.gradient_checkpointing_enable()
        base.enable_input_require_grads()
    model = PeftModel.from_pretrained(base, str(parent_dir),
                                     is_trainable=training).to("cpu")
    return tokenizer, model


def answer_text(tokenizer, model, conversation, maximum=MAX_GENERATED):
    import torch
    encoded=tokenizer.apply_chat_template(
        conversation, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    )
    if encoded.shape[1] > 650:
        raise ValueError("DIALOGUE_CONTEXT_EXCEEDS_LIMIT")
    model.eval()
    with torch.inference_mode():
        output=model.generate(encoded, attention_mask=torch.ones_like(encoded),
                              max_new_tokens=maximum, do_sample=False,
                              pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(output[0,encoded.shape[1]:],
                            skip_special_tokens=True).strip()[:900]


def field_choice(text):
    # Only keys in a reviewed allowlist; no model-generated paths are ever opened.
    matches=[(text.find(key), key) for key in TRAIN_KEYS if key in text]
    matches=[t for t in matches if t[0]>=0]
    return min(matches)[1] if matches else None


def peer_dialogue(root,lock,frozen,parent_dir):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    verify_freeze(root,lock,frozen)
    verified_src,obj=source_bytes_and_json(root,lock)
    torch.manual_seed(SEED)
    start=time.monotonic()
    tokenizer,model=load_model(parent_dir,False)
    choice=answer_text(tokenizer,model,[
        {"role":"system","content":"You are a JANUS research apprentice. Pick ONE field whose precise value you want to check. Output the field name only. Never claim to know it."},
        {"role":"user","content":"Pick a field to investigate in the JANUS model manifest:\n"+"\n".join(TRAIN_KEYS)}
    ],35)
    key=field_choice(choice)
    fallback = key is None
    if key is None:
        key=TRAIN_KEYS[0]
    prompt=question(key)
    initial=answer_text(tokenizer,model,[
        {"role":"system","content":"Answer a question about JANUS. If uncertain say unknown. No tools or execution."},
        {"role":"user","content":prompt}
    ],55)
    source_value=expected_text(value_at(obj,key))
    del model
    # Model-to-model information transfer: peer sees source evidence. Its
    # critique can be informative, but only the repository field is truth.
    reviewer_tokenizer=AutoTokenizer.from_pretrained(PEER,revision=PEER_REVISION,
                                                      trust_remote_code=False)
    reviewer=AutoModelForCausalLM.from_pretrained(
        PEER,revision=PEER_REVISION,torch_dtype=torch.float32,
        use_safetensors=True,trust_remote_code=False).to("cpu").eval()
    reviewer_sha=getattr(reviewer.config,"_commit_hash",None)
    if reviewer_sha!=PEER_REVISION:
        raise ValueError("PEER_MODEL_REVISION_DRIFT")
    peer=answer_text(reviewer_tokenizer,reviewer,[
        {"role":"system","content":"You are a small fact-checking peer. Inspect the given repository evidence. State whether the learner answer is correct, and offer one short correction in Russian. This is not scientific proof."},
        {"role":"user","content":"Question: "+prompt+"\nLearner answer: "+initial+
         "\nRead-only repository evidence: "+key+" = "+source_value}
    ],100)
    del reviewer
    # Fresh inherited parent used for the final answer after reviewer critique.
    tokenizer,model=load_model(parent_dir,False)
    revised=answer_text(tokenizer,model,[
        {"role":"system","content":"You are JANUS research apprentice. Peer replies are not authority; cite provided repository evidence. Reply with only the verified value."},
        {"role":"user","content":prompt},
        {"role":"assistant","content":initial},
        {"role":"user","content":"Peer review (untrusted): "+peer+"\nVerified source field: "+
         key+" = "+source_value+"\nRevise if needed."},
    ],50)
    return seal({
        "schema":"janus.essence.source_grounded_peer_dialogue/4.7",
        "base_model":v46.MODEL, "parent_adapter_sha256":PARENT_ADAPTER_SHA,
        "peer_model":PEER,"peer_revision":PEER_REVISION,
        "source_manifest_sha256":verified_src,
        "source_freeze_sha256":frozen["sha256"],
        "learner_question_selection":choice,
        "model_chose_valid_source_key":not fallback,
        "selected_verified_key":key, "question":prompt,
        "initial_reply":initial, "peer_review":peer,"revised_reply":revised,
        "source_ground_truth":source_value,
        "initial_exact_match":initial.strip()==source_value,
        "revised_exact_match":revised.strip()==source_value,
        "peer_output_used_as_training_target":False,
        "training_teacher":"REPOSITORY_JSON_FIELD_ONLY",
        "verified_source_overrides_peer":True,
        "independent_external_validation":False,
        "elapsed_seconds":round(time.monotonic()-start,4),
    })


def train(root,lock,frozen,parent_dir,dialogue,output_dir):
    import torch
    from safetensors.torch import load_file
    verify_freeze(root,lock,frozen)
    checked(dialogue)
    if (dialogue.get("schema")!="janus.essence.source_grounded_peer_dialogue/4.7" or
            dialogue.get("source_freeze_sha256")!=frozen["sha256"] or
            dialogue.get("parent_adapter_sha256")!=PARENT_ADAPTER_SHA or
            dialogue.get("peer_output_used_as_training_target") is not False or
            dialogue.get("selected_verified_key") not in TRAIN_KEYS):
        raise ValueError("UNTRUSTED_PEER_DIALOGUE_OR_LINEAGE")
    _,obj=source_bytes_and_json(root,lock)
    if dialogue.get("source_ground_truth")!=expected_text(
            value_at(obj,dialogue["selected_verified_key"])):
        raise ValueError("REVIEWER_CLAIM_MISMATCH_REPOSITORY")
    rows=examples(obj,TRAIN_KEYS)
    if sha(rows)!=frozen["train_examples_sha256"]:
        raise ValueError("TRAIN_SPLIT_CHANGED_AFTER_FREEZE")
    # No use of peer-generated target text in gradient updates.
    ordered=[next(row for row in rows if row["key"]==dialogue["selected_verified_key"])]
    ordered += [r for r in rows if r["key"]!=dialogue["selected_verified_key"]]
    torch.manual_seed(SEED)
    timer=time.monotonic()
    tokenizer,model=load_model(parent_dir,True)
    trainables=[p for p in model.parameters() if p.requires_grad]
    if not trainables or sum(p.numel() for p in trainables)>350_000:
        raise ValueError("UNEXPECTED_UNFROZEN_PARENT_PARAMETERS")
    opt=torch.optim.AdamW(trainables,lr=LR)
    losses=[]
    for step in range(MAX_STEPS):
        row=ordered[step % len(ordered)]
        _,tokens,labels=v46.tokens(tokenizer,{"prompt":row["prompt"],
                                               "expected":row["answer"]})
        opt.zero_grad(set_to_none=True)
        loss=model(input_ids=tokens,attention_mask=torch.ones_like(tokens),
                   labels=labels).loss
        if not bool(torch.isfinite(loss)):
            raise ValueError("NONFINITE_PEER_CHILD_LOSS")
        loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(trainables,1.0)
        if not math.isfinite(float(norm)):
            raise ValueError("INVALID_PEER_CHILD_GRADIENT")
        opt.step()
        losses.append(round(float(loss.detach()),7))
    output=Path(output_dir)
    if output.exists():
        raise ValueError("REFUSE_OVERWRITE_DESCENDANT")
    output.mkdir(parents=True)
    model.save_pretrained(output,safe_serialization=True)
    weights=output/"adapter_model.safetensors"
    if not weights.is_file() or weights.stat().st_size>6_000_000:
        raise ValueError("MISSING_ADAPTER_WEIGHTS")
    child_bytes=weights.read_bytes()
    child_sha=hashlib.sha256(child_bytes).hexdigest()
    if child_sha==PARENT_ADAPTER_SHA:
        raise ValueError("NO_LEARNED_ADAPTER_CHANGE")
    loaded=load_file(weights,device="cpu")
    if not loaded or not any(bool(torch.count_nonzero(t)) for t in loaded.values()):
        raise ValueError("ALL_ADAPTER_TENSORS_ZERO")
    lineage=seal({
        "schema":"janus.essence.inherited_repo_peer_lora/4.7",
        "parent_model":v46.MODEL,"parent_revision":v46.REVISION,
        "parent_adapter_sha256":PARENT_ADAPTER_SHA,
        "parent_lineage_sha256":PARENT_LINEAGE_SHA,
        "source_freeze_sha256":frozen["sha256"],
        "source_manifest_sha256":frozen["source_manifest_sha256"],
        "verified_dialogue_sha256":dialogue["sha256"],
        "teacher_sha256":sha(rows),
        "teacher_source":"REPOSITORY_FACTS_NOT_PEER_OPINIONS",
        "train_steps":MAX_STEPS,"trainable_adapter_parameters":sum(p.numel() for p in trainables),
        "adapter_sha256":child_sha,"train_loss":losses,
        "train_seconds":round(time.monotonic()-timer,4),
        "holdout_seen_during_training":False,
        "automatic_promotion":False,"native_janus_updated":False,
        "sentinel_dispatch":False,
    })
    write(output/"lineage.json",lineage)
    return lineage


def score_rows(tokenizer,model,rows):
    scored=[]
    for row in rows:
        loss,exact,result=v46.score(tokenizer,model,{
            "prompt":row["prompt"],"expected":row["answer"]})
        scored.append({"key":row["key"],"loss":round(loss,7),
                       "exact":bool(exact),"text":result[:120]})
    return scored


def exam(root,lock,frozen,parent_dir,child_dir):
    from peft import PeftModel
    verify_freeze(root,lock,frozen)
    verify_parent(parent_dir)
    lineage=checked(read_json(Path(child_dir)/"lineage.json"))
    weights=Path(child_dir)/"adapter_model.safetensors"
    if (lineage.get("schema")!="janus.essence.inherited_repo_peer_lora/4.7"
            or lineage.get("parent_adapter_sha256")!=PARENT_ADAPTER_SHA
            or lineage.get("source_freeze_sha256")!=frozen["sha256"]
            or lineage.get("adapter_sha256")!=hashlib.sha256(weights.read_bytes()).hexdigest()):
        raise ValueError("INVALID_CHILD_FOR_PAIRED_EXAM")
    _,obj=source_bytes_and_json(root,lock)
    para=examples(obj,TRAIN_KEYS,True)
    unseen=examples(obj,UNSEEN_KEYS)
    if sha(para)!=frozen["paraphrase_exam_sha256"] or sha(unseen)!=frozen["unseen_exam_sha256"]:
        raise ValueError("EXAM_COHORT_DRIFT")
    token,model=load_model(parent_dir,False)
    started=time.monotonic()
    parent_para=score_rows(token,model,para)
    parent_unseen=score_rows(token,model,unseen)
    v46_lock=v46.read("research/essence/peer_v46/oracle_lock.json")
    old=v46.sample_set(v46.lock_check(v46_lock),"holdout")[:8]
    old=[{"key":"legacy-"+str(i),"prompt":row["prompt"],"answer":row["expected"]}
         for i,row in enumerate(old)]
    parent_ret=score_rows(token,model,old)
    # New child adapter shares exactly the same frozen Qwen base tensor bytes.
    model.load_adapter(str(child_dir),adapter_name="janus_gen2",is_trainable=False)
    model.set_adapter("janus_gen2")
    model.eval()
    child_para=score_rows(token,model,para)
    child_unseen=score_rows(token,model,unseen)
    child_ret=score_rows(token,model,old)
    def stats(parent,child):
        p=sum(r["loss"] for r in parent)/len(parent)
        c=sum(r["loss"] for r in child)/len(child)
        return {"parent_nll":round(p,7),"child_nll":round(c,7),
                "nll_gain":round(p-c,7),
                "parent_exact":sum(r["exact"] for r in parent),
                "child_exact":sum(r["exact"] for r in child),
                "count":len(parent)}
    paraphrase=stats(parent_para,child_para)
    unseen_stats=stats(parent_unseen,child_unseen)
    retention=stats(parent_ret,child_ret)
    passed=(paraphrase["nll_gain"]>=TRAIN_THRESHOLD
            and unseen_stats["nll_gain"]>=-UNSEEN_REGRESSION_MAX
            and retention["nll_gain"]>=-RETENTION_REGRESSION_MAX
            and paraphrase["child_exact"]>=paraphrase["parent_exact"]
            and unseen_stats["child_exact"]>=unseen_stats["parent_exact"]
            and retention["child_exact"]>=retention["parent_exact"])
    return seal({
        "schema":"janus.essence.repo_peer_paired_exam/4.7",
        "status":"PASS_INTERNAL_REPO_PEER_SHADOW_GAIN" if passed else "NO_GAIN_OR_REGRESSION",
        "parent_adapter_sha256":PARENT_ADAPTER_SHA,
        "child_adapter_sha256":lineage["adapter_sha256"],
        "lineage_sha256":lineage["sha256"],"source_freeze_sha256":frozen["sha256"],
        "paraphrase_test":paraphrase,"unseen_fact_test":unseen_stats,
        "previous_generation_retention":retention,
        "training_wall_seconds":lineage["train_seconds"],
        "peer_dialogue_and_exam_wall_seconds":round(time.monotonic()-started,4),
        "independent_examiner":False,"external_replication":False,
        "automatic_weight_promotion":False,"production_model_modified":False,
        "sentinel_dispatch":False,
    })


def main():
    p=argparse.ArgumentParser()
    p.add_argument("phase",choices=["freeze","peer","train","exam"])
    p.add_argument("--lock",default="research/essence/peer_v47/repo_lock.json")
    p.add_argument("--root",default=".")
    p.add_argument("--freeze")
    p.add_argument("--parent")
    p.add_argument("--dialogue")
    p.add_argument("--child")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    lock=validate_lock(read_json(args.lock))
    if args.phase=="freeze":
        result=freeze(args.root,lock)
    else:
        if not args.freeze:
            raise ValueError("FROZEN_DATASET_REQUIRED")
        frozen=read_json(args.freeze)
        if args.phase=="peer":
            if not args.parent:
                raise ValueError("PARENT_REQUIRED")
            result=peer_dialogue(args.root,lock,frozen,args.parent)
        elif args.phase=="train":
            if not args.parent or not args.dialogue or not args.child:
                raise ValueError("PARENT_AND_DIALOGUE_REQUIRED")
            result=train(args.root,lock,frozen,args.parent,
                         read_json(args.dialogue),args.child)
        else:
            if not args.parent or not args.child:
                raise ValueError("PARENT_CHILD_REQUIRED")
            result=exam(args.root,lock,frozen,args.parent,args.child)
    write(args.out,result)
    print(json.dumps(result,ensure_ascii=False,indent=2)[:12_000])


if __name__=="__main__":
    main()
