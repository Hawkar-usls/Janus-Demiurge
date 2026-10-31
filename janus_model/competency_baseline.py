"""Versioned, fixed-prompt JANUS native model competency smoke baseline.

Public prompts are NOT a blind, statistically independent final test. This
runs separately from training, reports exact checks and output format only,
and NEVER authorizes checkpoint promotion or scientific truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

SCHEMA = "janus.native.fixed_competency_baseline.v1"
TASKS = (
    ("ARITHMETIC_SMALL", "What is two plus two? Reply with one numeral.", "4"),
    ("LETTER_SEQUENCE", "What uppercase letter follows C in the English alphabet? Reply one letter.", "D"),
    ("TRIANGLE_SIDES", "How many sides does a triangle have? Reply one numeral.", "3"),
    ("EVIDENCE_HOLD", "An unverified machine claim is not proof. Reply NO if that statement is correct, else YES.", "NO"),
)
MAX_NEW_TOKENS = 48
SEED = 20261101


def canonical(record: dict) -> bytes:
    return json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def suite_digest() -> str:
    return hashlib.sha256(canonical({"schema": SCHEMA, "tasks": TASKS})).hexdigest()


def score_response(prompt: str, expected: str, generated: str) -> dict:
    if not isinstance(generated, str):
        raise ValueError("NATIVE_COMPETENCY_GENERATED_TEXT_REQUIRED")
    prefix = f"Q: {prompt}\nJANUS:"
    if not generated.startswith(prefix):
        raise ValueError("NATIVE_COMPETENCY_PROMPT_PREFIX_MISMATCH")
    suffix = generated[len(prefix):]
    answer = suffix.strip()
    return {
        "exact_match": answer == expected,
        "output_sha256": hashlib.sha256(suffix.encode("utf-8", errors="replace")).hexdigest(),
        "generated_characters": len(suffix),
        "assistant_prefix_verified": True,
        "raw_output_recorded": False,
    }


def run():
    from janus_model.checkpoint_admission import PROMOTED, preflight
    from janus_model.model import ByteTokenizer
    from janus_model.output_quality import assess
    from janus_model.train_registry import load_checkpoint
    import torch

    checkpoint_hash = preflight(PROMOTED)
    model, _ = load_checkpoint(PROMOTED)
    model.eval()
    torch.set_num_threads(2)
    results = []
    for i, (task_id, question, expected) in enumerate(TASKS):
        prompt = f"Q: {question}\nJANUS:"
        ids = ByteTokenizer.encode(prompt, bos=True)
        if len(ids) > model.config.context_length:
            raise RuntimeError("NATIVE_COMPETENCY_CONTEXT_OVERFLOW")
        torch.manual_seed(SEED + i)
        idx = torch.tensor([ids], dtype=torch.long)
        output = model.generate(idx, max_new_tokens=MAX_NEW_TOKENS,
                                temperature=0.65, top_k=20)
        decoded = ByteTokenizer.decode(output[0].tolist())
        score = score_response(question, expected, decoded)
        format_gate = assess(decoded)
        results.append({
            "task_id": task_id,
            "exact_match": score["exact_match"],
            "output_sha256": score["output_sha256"],
            "output_quality_status": format_gate["status"],
            "output_quality_reasons": format_gate["reasons"],
        })
    exact = sum(1 for r in results if r["exact_match"])
    structural = sum(1 for r in results
                     if r["output_quality_status"] == "STRUCTURAL_CANDIDATE_UNVERIFIED")
    record = {
        "schema": SCHEMA, "status": "MEASURED_NATIVE_FIXED_PROMPT_BASELINE",
        "checkpoint_sha256": checkpoint_hash, "fixed_suite_sha256": suite_digest(),
        "task_count": len(TASKS), "exact_answer_count": exact,
        "structural_candidate_count": structural,
        "native_context_length": model.config.context_length,
        "sampling_seed": SEED,
        "max_new_tokens_per_task": MAX_NEW_TOKENS,
        "results": results,
        "no_training_performed": True,
        "not_blind_tasks_publicly_visible": True,
        "not_a_general_intelligence_test": True,
        "semantic_truth_or_scientific_proof": False,
        "promotion_allowed_by_this_score": False,
        "paid_llm_calls": 0,
        "authority_delta": 0,
    }
    record["receipt_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as f:
        f.write(canonical(result) + b"\n")
    print(json.dumps({
        "status": result["status"],
        "exact_answer_count": result["exact_answer_count"],
        "task_count": result["task_count"],
        "structural_candidate_count": result["structural_candidate_count"],
        "checkpoint_sha256": result["checkpoint_sha256"],
        "receipt_sha256": result["receipt_sha256"],
    }))


if __name__ == "__main__":
    main()
