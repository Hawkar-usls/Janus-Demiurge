#!/usr/bin/env python3
"""ESSENCE v4.5: frozen Qwen-base LoRA descendant, human-evidence gated.

Trust boundary: this is a research-only trainable adapter; it never updates
the native JANUS checkpoint, Sentinel, deployment or production router.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

CORPUS_SCHEMA = "janus.open_llm.corpus_record.v1"
LABEL_SCHEMA = "janus.open_llm.review_labels.v1"
LOCK_SCHEMA = "janus.essence.qwen_peer_shadow_lock.v4.5"
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
PINNED_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
MIN_PAIRS = 32
MIN_ISSUES = 8
MAX_FILES = 500
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path, limit=90_000):
    file = Path(path)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > limit:
        raise ValueError("UNSAFE_JSON_INPUT")
    return json.loads(file.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON")))


def inspect_record(record):
    if record.get("schema") != CORPUS_SCHEMA:
        raise ValueError("CORPUS_SCHEMA_MISMATCH")
    digest = record.get("record_sha256")
    if digest != sha({k: v for k, v in record.items() if k != "record_sha256"}):
        raise ValueError("CORPUS_RECORD_TAMPER")
    if (record.get("quality_is_independent_evidence") is not False
            or record.get("model_weight_change") is not False
            or record.get("auto_promotion_authority") is not False
            or record.get("source_binding", {}).get("kind") != "ISSUE_AND_BOT_REPLY_DIGEST_MATCH"):
        raise ValueError("CORPUS_AUTHORITY_NOT_RESEARCH_ONLY")
    dialogue = record.get("dialogue", {})
    if (dialogue.get("sha256") != record.get("source_sha256")
            or sha({k: v for k, v in dialogue.items() if k != "sha256"}) != dialogue.get("sha256")):
        raise ValueError("CORPUS_SOURCE_DIGEST_CHANGED")
    req = dialogue.get("request", {})
    if (req.get("request_sha256") != sha({k: v for k, v in req.items() if k != "request_sha256"})
            or req.get("execution_authority") != "TEXT_ONLY"
            or req.get("requested_by") != "Hawkar-usls"):
        raise ValueError("CORPUS_REQUEST_UNTRUSTED")
    return dialogue


def read_corpus(directory):
    files = sorted(Path(directory).glob("records/*.json"))
    if len(files) > MAX_FILES:
        raise ValueError("TOO_MANY_CORPUS_RECORDS")
    records = []
    source_shas = set()
    for file in files:
        if file.is_symlink():
            raise ValueError("SYMLINK_CORPUS_RECORD")
        record = read_json(file)
        inspect_record(record)
        if record["source_sha256"] in source_shas:
            raise ValueError("DUPLICATE_SOURCE_RECORD")
        source_shas.add(record["source_sha256"])
        records.append(record)
    return records


def inspect_lock(lock):
    if (lock.get("schema") != LOCK_SCHEMA or lock.get("base_model") != MODEL
            or lock.get("base_revision") != PINNED_REVISION
            or lock.get("max_steps") != 8 or lock.get("learning_rate") != 0.0001
            or lock.get("seed") != 4501 or lock.get("lora_rank") != 4
            or lock.get("production_admission") is not False
            or lock.get("sentinel_dispatch_allowed") is not False):
        raise ValueError("UNREVIEWED_SHADOW_TRAIN_LOCK")
    return lock


def select_examples(records, review_labels):
    if review_labels.get("schema") != LABEL_SCHEMA:
        raise ValueError("UNREVIEWED_REVIEW_SCHEMA")
    selected = []
    seen_prompt = set()
    for record in records:
        d = record["dialogue"]
        status = (review_labels.get("labels") or {}).get(d["sha256"], {})
        if status.get("status") != "APPROVED_FOR_SHADOW_TRAINING":
            continue
        reviews = status.get("human_review_sources") or []
        answer = status.get("reference_answer")
        if (not isinstance(reviews, list) or len(set(reviews)) < 2 or
                any(not isinstance(u, str) or not u.startswith("https://") for u in reviews)
                or status.get("independent_evidence") is not True
                or not isinstance(answer, str) or not 10 <= len(answer) <= 700):
            raise ValueError("MISSING_INDEPENDENT_HUMAN_VERIFIED_REFERENCE")
        req = d["request"]
        prompt_hash = hashlib.sha256(req["prompt"].encode()).hexdigest()
        if prompt_hash in seen_prompt:
            raise ValueError("DUPLICATE_TRAIN_PROMPT")
        seen_prompt.add(prompt_hash)
        selected.append({
            "issue_number": req["issue_number"],
            "prompt": req["prompt"],
            "reference_answer": answer,
            "dialogue_sha256": d["sha256"],
            "source_run_id": record["source_run_id"],
        })
    return sorted(selected, key=lambda x: x["dialogue_sha256"])


def preflight(records, labels, lock):
    inspect_lock(lock)
    examples = select_examples(records, labels)
    issues = {x["issue_number"] for x in examples if x["issue_number"] is not None}
    modes = {r["dialogue"]["request"]["mode"] for r in records
             if r["source_sha256"] in {x["dialogue_sha256"] for x in examples}}
    blockers = []
    if len(examples) < MIN_PAIRS:
        blockers.append("HOLD_NEED_32_INDEPENDENTLY_REVIEWED_PAIRS")
    if len(issues) < MIN_ISSUES:
        blockers.append("HOLD_NEED_8_DISTINCT_ISSUES")
    if "council" not in modes:
        blockers.append("HOLD_NEED_REVIEWED_PEER_DIALOGUE")
    commitment = lock.get("independent_exam_commitment_sha256")
    custodian = lock.get("independent_custodian")
    if not isinstance(commitment, str) or not HEX64.fullmatch(commitment):
        blockers.append("HOLD_PROSPECTIVE_EXAM_NOT_FROZEN")
    if not isinstance(custodian, str) or not custodian.strip():
        blockers.append("HOLD_INDEPENDENT_CUSTODIAN_MISSING")
    payload = {
        "schema": "janus.essence.peer_shadow_preflight.v4.5",
        "corpus_source_count": len(records),
        "reviewed_training_pairs": len(examples),
        "distinct_reviewed_issues": len(issues),
        "train_set_sha256": sha(examples),
        "lock_sha256": sha(lock),
        "training_allowed": not blockers,
        "blockers": blockers,
        "production_promotion_allowed": False,
        "native_janus_checkpoint_modified": False,
        "sentinel_dispatch_allowed": False,
        "claimed_independent_validation": False,
    }
    payload["receipt_sha256"] = sha(payload)
    return payload, examples


def shadow_train(examples, lock, outdir):
    """Train only LoRA weights; no decoder/tool actions, no hidden-test reading."""
    gate = inspect_lock(lock)
    if not examples:
        raise ValueError("EMPTY_SHADOW_TRAIN_SET")
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(gate["seed"])
    torch.set_num_threads(4)
    start = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=PINNED_REVISION,
                                              trust_remote_code=False)
    base = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=PINNED_REVISION, torch_dtype=torch.float32,
        trust_remote_code=False, use_safetensors=True
    ).to("cpu")
    if getattr(base.config, "_commit_hash", None) != PINNED_REVISION:
        raise ValueError("PARENT_HF_REVISION_CHANGED")
    base.gradient_checkpointing_enable()
    base.enable_input_require_grads()
    lora = LoraConfig(r=4, lora_alpha=8, lora_dropout=0.0, bias="none",
                      target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM")
    child = get_peft_model(base, lora)
    child.train()
    optimizer = torch.optim.AdamW((p for p in child.parameters() if p.requires_grad),
                                   lr=gate["learning_rate"])
    losses = []
    for step in range(gate["max_steps"]):
        row = examples[step % len(examples)]
        prefix = tokenizer.apply_chat_template([
            {"role": "system", "content": "Answer accurately and say when uncertain."},
            {"role": "user", "content": row["prompt"]},
        ], add_generation_prompt=True, tokenize=True, return_tensors="pt")
        response = tokenizer(row["reference_answer"] + (tokenizer.eos_token or ""),
                             add_special_tokens=False, return_tensors="pt")["input_ids"]
        prefix = prefix[:, -128:]
        response = response[:, :128]
        if response.shape[1] < 2:
            raise ValueError("EMPTY_REFERENCE_TOKENS")
        tokens = torch.cat((prefix, response), dim=1)
        labels = torch.cat((torch.full_like(prefix, -100), response), dim=1)
        optimizer.zero_grad(set_to_none=True)
        result = child(input_ids=tokens, attention_mask=torch.ones_like(tokens),
                       labels=labels)
        loss = result.loss
        if not bool(torch.isfinite(loss)):
            raise ValueError("NONFINITE_CHILD_LOSS")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(child.parameters(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    child.save_pretrained(out, safe_serialization=True)
    safes = sorted(out.glob("*.safetensors"))
    if not safes:
        raise ValueError("NO_SAFETENSOR_ADAPTER_WRITTEN")
    manifest = {
        "schema": "janus.essence.qwen_peer_lora_shadow.v4.5",
        "parent_model": MODEL,
        "parent_revision": PINNED_REVISION,
        "max_steps": gate["max_steps"],
        "completed_steps": len(losses),
        "train_set_sha256": sha(examples),
        "file_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in safes},
        "elapsed_seconds": time.monotonic() - start,
        "losses": losses,
        "production_authority": False,
        "independent_exam_completed": False,
        "descendant_quality_gain": "UNKNOWN",
        "native_janus_weights_modified": False,
    }
    manifest["manifest_sha256"] = sha(manifest)
    (out / "JANUS_SHADOW_LINEAGE.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--train-dir", default=None)
    args = parser.parse_args()
    records = read_corpus(args.corpus)
    labels = read_json(args.labels)
    lock = read_json(args.lock)
    gate, examples = preflight(records, labels, lock)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    if not gate["training_allowed"]:
        print("SHADOW_TRAIN_HOLD " + ", ".join(gate["blockers"]))
        return
    if args.train_dir is None:
        print("DATA_READY_SHADOW_TRAIN_NOT_REQUESTED")
        return
    print(json.dumps(shadow_train(examples, lock, args.train_dir), indent=2))


if __name__ == "__main__":
    main()
