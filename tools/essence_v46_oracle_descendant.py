#!/usr/bin/env python3
"""ESSENCE v4.6: one-shot, research-only Qwen LoRA inheritance smoke/exam.

This intentionally does NOT consume unreviewed peer conversations. The aim is
to prove/disprove the *mechanics* of train -> immutable checkpoint -> paired exam
on new deterministic-oracle examples, never production model improvement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

LOCK_SCHEMA = "janus.essence.oracle_descendant_lock/4.6"
FREEZE_SCHEMA = "janus.essence.oracle_freeze/4.6"
TRAIN_SCHEMA = "janus.essence.oracle_lora_train/4.6"
EXAM_SCHEMA = "janus.essence.oracle_paired_exam/4.6"
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
SPLITS = ("train", "holdout")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def seal(value, field="sha256"):
    return dict(value, **{field: digest(value)})


def check_seal(value, field="sha256"):
    if not isinstance(value, dict) or value.get(field) != digest({
            k: v for k, v in value.items() if k != field}):
        raise ValueError("RECEIPT_DIGEST_MISMATCH")
    return value


def read(path, limit=50_000):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > limit:
        raise ValueError("INVALID_INPUT_FILE")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON")))


def write(path, value):
    p = Path(path)
    if p.exists() or p.is_symlink():
        raise ValueError("REFUSE_OVERWRITE_EXISTING_EVIDENCE")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                 encoding="utf-8")


def lock_check(lock):
    if not isinstance(lock, dict) or lock.get("schema") != LOCK_SCHEMA:
        raise ValueError("INVALID_ORACLE_LOCK")
    required = {
        "parent": MODEL, "parent_revision": REVISION,
        "task": "JANUS_ROUTE_PREFIX_EXACT_TEXT", "seed": 4601,
        "train_count": 32, "holdout_count": 16,
        "steps": 20, "learning_rate": 0.0015, "lora_rank": 4,
        "exam_min_loss_gain": 0.02, "exam_family_regression_cap": 0.035,
        "dev_only": True, "auto_promotion": False,
        "sentinel_execution_authority": False,
        "human_reviewed_dialogues_used": False,
        "external_independent_validation": False,
        "training_samples_in_holdout": False,
    }
    if {k: lock.get(k) for k in required} != required:
        raise ValueError("ORACLE_LOCK_MUTATED")
    return lock


def oracle_a(code):
    if len(code) != 10 or code[1] != "-" or code[0] not in "KL":
        raise ValueError("INVALID_CODE")
    if not all(c in "0123456789abcdef" for c in code[2:]):
        raise ValueError("INVALID_CODE_SUFFIX")
    return "NORTH" if code[0] == "K" else "SOUTH"


def oracle_b(code):
    # Independently implemented reverse lookup. Agreement is a *software*
    # check, not human review or external ground truth for scientific claims.
    parts = code.split("-")
    if len(parts) != 2 or len(parts[1]) != 8:
        raise ValueError("INVALID_CODE")
    table = {"K": "NORTH", "L": "SOUTH"}
    if parts[0] not in table:
        raise ValueError("INVALID_CODE")
    int(parts[1], 16)
    return table[parts[0]]


def sample_set(lock, split):
    lock_check(lock)
    if split not in SPLITS:
        raise ValueError("UNREVIEWED_SPLIT")
    count = lock["train_count"] if split == "train" else lock["holdout_count"]
    data = []
    for i in range(count):
        suffix = hashlib.sha256(f"{lock['seed']}|{split}|{i}".encode()).hexdigest()[:8]
        prefix = "K" if i % 2 == 0 else "L"
        code = f"{prefix}-{suffix}"
        expected = oracle_a(code)
        if expected != oracle_b(code):
            raise ValueError("ORACLE_DISAGREEMENT")
        data.append({
            "code": code,
            "prompt": f"JANUS relay decoder (synthetic laboratory task). Decode tag {code}. Reply with the relay word only.",
            "expected": expected,
        })
    return data


def disjoint(lock):
    train, holdout = sample_set(lock, "train"), sample_set(lock, "holdout")
    if {a["code"] for a in train} & {a["code"] for a in holdout}:
        raise ValueError("CROSS_SPLIT_LEAK")
    if len({x["prompt"] for x in train + holdout}) != len(train + holdout):
        raise ValueError("DUPLICATE_PROMPT")
    return train, holdout


def freeze(lock):
    train, holdout = disjoint(lock)
    return seal({
        "schema": FREEZE_SCHEMA,
        "lock_sha256": digest(lock),
        "train_count": len(train),
        "holdout_count": len(holdout),
        "train_commit_sha256": digest(train),
        "holdout_commit_sha256": digest(holdout),
        "holdout_bytes_opened_for_training": False,
        "external_independent_exam": False,
        "no_auto_weight_promotion": True,
    })


def check_freeze(lock, receipt):
    check_seal(receipt)
    if receipt != freeze(lock):
        raise ValueError("FROZEN_COHORT_DRIFT")
    return receipt


def tokenizer_and_base(lock):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=REVISION, trust_remote_code=False)
    base = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, torch_dtype=torch.float32,
        trust_remote_code=False, use_safetensors=True).to("cpu")
    commit = getattr(base.config, "_commit_hash", None)
    if commit != REVISION:
        raise ValueError(f"UNPINNED_MODEL_REVISION_{commit}")
    base.config.use_cache = False
    return tokenizer, base


def tokens(tokenizer, row):
    import torch
    messages = [{"role": "user", "content": row["prompt"]}]
    prefix = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt")
    suffix = tokenizer(row["expected"] + (tokenizer.eos_token or ""),
                       add_special_tokens=False, return_tensors="pt")["input_ids"]
    prefix = prefix[:, -110:]
    suffix = suffix[:, :16]
    if not (prefix.shape[1] > 2 and suffix.shape[1] > 1):
        raise ValueError("EMPTY_TRAINABLE_SEQUENCE")
    ids = torch.cat((prefix, suffix), dim=1)
    labels = torch.cat((torch.full_like(prefix, -100), suffix), dim=1)
    return prefix, ids, labels


def train(lock, freeze_receipt, directory):
    check_freeze(lock, freeze_receipt)
    import torch
    from peft import LoraConfig, get_peft_model
    torch.manual_seed(lock["seed"])
    begun = time.monotonic()
    tokenizer, base = tokenizer_and_base(lock)
    base.gradient_checkpointing_enable()
    base.enable_input_require_grads()
    adapter = get_peft_model(base, LoraConfig(
        r=lock["lora_rank"], lora_alpha=8, lora_dropout=0.0,
        bias="none", target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"))
    adapter.train()
    named = list(adapter.named_parameters())
    trainables = [(n, p) for n, p in named if p.requires_grad]
    if not trainables or any("lora_" not in n for n, _ in trainables):
        raise ValueError("NON_LORA_WEIGHT_UNFROZEN")
    opt = torch.optim.AdamW([p for _, p in trainables], lr=lock["learning_rate"])
    # Never generate/read holdout samples in the training job.
    rows = sample_set(lock, "train")
    losses = []
    for step in range(lock["steps"]):
        row = rows[step % len(rows)]
        _, ids, labels = tokens(tokenizer, row)
        opt.zero_grad(set_to_none=True)
        loss = adapter(input_ids=ids, attention_mask=torch.ones_like(ids),
                       labels=labels).loss
        if not bool(torch.isfinite(loss)):
            raise ValueError("NONFINITE_TRAINING_LOSS")
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_((p for _, p in trainables), 1.0)
        if not math.isfinite(float(norm)):
            raise ValueError("INVALID_GRADIENT_NORM")
        opt.step()
        losses.append(round(float(loss.detach()), 8))
    out = Path(directory)
    if out.exists():
        raise ValueError("REFUSE_CHECKPOINT_OVERWRITE")
    out.mkdir(parents=True)
    adapter.save_pretrained(out, safe_serialization=True)
    weights_file = out / "adapter_model.safetensors"
    if not weights_file.is_file() or weights_file.stat().st_size > 6_000_000:
        raise ValueError("NO_SMALL_LORA_CHECKPOINT")
    from safetensors.torch import load_file
    weights = load_file(weights_file, device="cpu")
    if not any("lora_B" in key and bool(torch.count_nonzero(value)) for key, value in weights.items()):
        raise ValueError("NO_NONZERO_NEURAL_WEIGHT_UPDATE")
    manifest = seal({
        "schema": TRAIN_SCHEMA,
        "source_freeze_sha256": freeze_receipt["sha256"],
        "source_train_sha256": freeze_receipt["train_commit_sha256"],
        "parent": MODEL,
        "parent_revision": REVISION,
        "steps": lock["steps"],
        "total_loss_samples": len(losses),
        "loss_trace": losses,
        "trainable_lora_parameters": sum(p.numel() for _, p in trainables),
        "adapter_sha256": hashlib.sha256(weights_file.read_bytes()).hexdigest(),
        "training_wall_seconds": round(time.monotonic() - begun, 4),
        "holdout_exam_performed": False,
        "automatic_promotion": False,
        "sentinel_dispatch": False,
    })
    write(out / "lineage.json", manifest)
    return manifest


def score(tokenizer, adapter, row):
    import torch
    prefix, ids, labels = tokens(tokenizer, row)
    with torch.inference_mode():
        loss = adapter(input_ids=ids, attention_mask=torch.ones_like(ids),
                       labels=labels).loss
        answer = adapter.generate(prefix, attention_mask=torch.ones_like(prefix),
                                  max_new_tokens=7, do_sample=False,
                                  pad_token_id=tokenizer.eos_token_id)
    result = tokenizer.decode(answer[0, prefix.shape[1]:], skip_special_tokens=True).strip()
    return float(loss), result == row["expected"], result[:120]


def exam(lock, freeze_receipt, directory):
    check_freeze(lock, freeze_receipt)
    from peft import PeftModel
    import torch
    start = time.monotonic()
    saved = Path(directory)
    lineage = check_seal(read(saved / "lineage.json"))
    checkpoint = saved / "adapter_model.safetensors"
    if (lineage.get("schema") != TRAIN_SCHEMA
            or lineage.get("source_freeze_sha256") != freeze_receipt["sha256"]
            or lineage.get("source_train_sha256") != freeze_receipt["train_commit_sha256"]
            or lineage.get("parent_revision") != REVISION
            or not checkpoint.is_file()
            or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != lineage["adapter_sha256"]):
        raise ValueError("UNVERIFIED_DESCENDANT_LINEAGE")
    tokenizer, base = tokenizer_and_base(lock)
    adapter = PeftModel.from_pretrained(base, saved, is_trainable=False)
    adapter.eval()
    # The training job did not read the holdout. The independent runner starts
    # this evaluation only AFTER the trained checkpoint has been uploaded.
    holdout = sample_set(lock, "holdout")
    if digest(holdout) != freeze_receipt["holdout_commit_sha256"]:
        raise ValueError("HOLDOUT_COMMITMENT_CHANGED")
    results = []
    for item in holdout:
        with adapter.disable_adapter():
            p_loss, p_ok, p_text = score(tokenizer, adapter, item)
        c_loss, c_ok, c_text = score(tokenizer, adapter, item)
        results.append({
            "prompt_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
            "family": item["code"][0],
            "parent_loss": round(p_loss, 7), "child_loss": round(c_loss, 7),
            "parent_correct": p_ok, "child_correct": c_ok,
            "parent_text": p_text, "child_text": c_text,
        })
    mean = lambda key, rows: sum(r[key] for r in rows) / len(rows)
    parent_loss = mean("parent_loss", results)
    child_loss = mean("child_loss", results)
    families = {}
    for letter in "KL":
        rows = [r for r in results if r["family"] == letter]
        families[letter] = {
            "parent_loss": round(mean("parent_loss", rows), 7),
            "child_loss": round(mean("child_loss", rows), 7),
            "parent_accuracy": round(mean("parent_correct", rows), 7),
            "child_accuracy": round(mean("child_correct", rows), 7),
        }
    improvement = parent_loss - child_loss
    regressions = [
        families[x]["child_loss"] - families[x]["parent_loss"] for x in families
    ]
    parent_acc, child_acc = mean("parent_correct", results), mean("child_correct", results)
    passed = (improvement >= lock["exam_min_loss_gain"]
              and max(regressions) <= lock["exam_family_regression_cap"]
              and child_acc >= parent_acc)
    receipt = seal({
        "schema": EXAM_SCHEMA,
        "label": "PASS_INTERNAL_PAIRED_DEV_GAIN" if passed else "NO_GAIN_OR_REGRESSION",
        "blind_to_training_runner": True,
        "prospective_external_custodian": False,
        "external_independent_validation": False,
        "real_weights_updated": True,
        "base_weights_unchanged": True,
        "admitted_to_janus_service": False,
        "sentinel_control_untouched": True,
        "source_freeze_sha256": freeze_receipt["sha256"],
        "descendant_lineage_sha256": lineage["sha256"],
        "train_seconds": lineage["training_wall_seconds"],
        "exam_seconds": round(time.monotonic() - start, 4),
        "total_cpu_wall_seconds": round(lineage["training_wall_seconds"] +
                                        time.monotonic() - start, 4),
        "parent_mean_token_nll": round(parent_loss, 7),
        "child_mean_token_nll": round(child_loss, 7),
        "paired_nll_improvement": round(improvement, 7),
        "parent_exact_accuracy": round(parent_acc, 7),
        "child_exact_accuracy": round(child_acc, 7),
        "family_results": families,
        "paired_examples": results,
    })
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=("freeze", "train", "exam"))
    parser.add_argument("--lock", required=True)
    parser.add_argument("--freeze")
    parser.add_argument("--weights")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    lock = lock_check(read(args.lock))
    if args.cmd == "freeze":
        result = freeze(lock)
    else:
        if not args.freeze or not args.weights:
            raise ValueError("FREEZE_AND_CHECKPOINT_REQUIRED")
        frozen = read(args.freeze)
        result = (train(lock, frozen, args.weights) if args.cmd == "train"
                  else exam(lock, frozen, args.weights))
    write(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:10_000])


if __name__ == "__main__":
    main()
