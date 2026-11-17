#!/usr/bin/env python3
"""JANUS COSMOS Reasoner R2: genuine, source-grounded 1.5B CPU inference.

Research-only replacement of the answer path, not a G2 weight update.
Read a frozen NASA-source fact card; allow the real model to answer; retain the
unaltered raw output plus an explicitly limited deterministic quality screen.
No production promotion, automatic training, dispatch or Sentinel privileges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "janus.cosmos.direct_answer_r2.v1"
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
EVIDENCE_PATH = "research/seti/frozen_evidence_scope_20261117.json"
PROMPT = (
    "Янус, человек просит тебя ответить на вопрос прямо и по существу. "
    "Где вообще инопланетяне — существующие внеземные живые существа или "
    "разумные цивилизации? На основании данных ниже сформулируй СВОЙ "
    "связный ответ на русском языке в 2–4 предложениях. "
    "Различай неизвестное место пребывания, перспективные места поиска жизни "
    "и отсутствие доказательств разумной цивилизации. "
    "Назови конкретные тела или классы планет, в которых стоит искать. "
    "Не выдумывай сигналы, контакты, координаты или открытые цивилизации. "
    "Не повторяй одно и то же; не уходи в вопрос 'где мы?'. "
    "Начни сразу с ответа, без вступительных фраз."
)


def evidence(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("EVIDENCE_FILE_MISSING")
    raw = p.read_bytes()
    if not 200 <= len(raw) <= 18000:
        raise ValueError("EVIDENCE_UNEXPECTED_LENGTH")
    obj = json.loads(raw)
    if obj.get("schema") != "janus.cosmos.seti.evidence_scope.v1":
        raise ValueError("EVIDENCE_SCHEMA_MISMATCH")
    if obj.get("proof_of_extraterrestrials") is not False:
        raise ValueError("RESEARCH_ONLY_REQUIRED")
    claims = obj.get("claims", [])
    if len(claims) != 4 or len({x.get("claim_id") for x in claims}) != 4:
        raise ValueError("EVIDENCE_CLAIMS_INCOMPLETE")
    for c in claims:
        if not c.get("source", "").startswith("https://"):
            raise ValueError("EVIDENCE_SOURCE_MISSING")
    return obj, hashlib.sha256(raw).hexdigest()


def model_messages(facts):
    card = "\n".join(
        f"{c['claim_id']}. {c['statement_ru']}"
        for c in facts["claims"]
    )
    return [
        {"role": "system", "content": (
            "Ты JANUS COSMOS, научный исследовательский собеседник. "
            "Не говори, что незнакомое = инопланетное. "
            "Потенциальная обитаемость не доказывает существование жизни. "
            "Не выдумывай научные открытия. Соблюдай краткость."
        )},
        {"role": "user", "content": (
            "Верифицированная справочная карточка NASA:\n"
            + card + "\n\nВопрос: " + PROMPT
        )},
    ]


def normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def evaluate_answer(answer):
    """A smoke screen, NOT an independent semantic truth assessment."""
    if not isinstance(answer, str) or len(answer.strip()) < 50:
        raise ValueError("MODEL_EMPTY_OR_TOO_SHORT")
    norm = normalize(answer)
    sentences = [p for p in re.split(r"(?<=[.!?])\s+", answer.strip()) if p.strip()]
    has_uncertainty = any(x in norm for x in (
        "не знаем", "неизвест", "неизвед", "не установлено", "не установлены",
        "пока не обнаруж", "не обнаруж", "не найден", "не нашли",
        "не подтвержд", "нет подтвержд", "нет доказательств", "неясно", "неизвестно"))
    places = {
        "mars": "марс" in norm,
        "europa": "европ" in norm,
        "exoplanets": "экзопланет" in norm or "планет" in norm,
        "enceladus": "энцелад" in norm
    }
    has_search_sites = sum(places.values()) >= 2
    excludes_known_aliens = not re.search(
        r"(?:точно|доказан|подтвержден|подтверждён).{0,60}"
        r"(?:инопланетяне|инопланетян|внеземной цивилизац|внеземные цивилизац)"
        r".{0,50}(?:существуют|обнаружены|найдены|есть)",
        norm
    )
    crude_repetition = False
    for fragment in re.split(r"(?<=[.!?])\s+", norm):
        if len(fragment) > 24 and norm.count(fragment) > 1:
            crude_repetition = True
    pass_screen = (
        has_uncertainty and has_search_sites and excludes_known_aliens
        and not crude_repetition and 2 <= len(sentences) <= 5
        and len(answer) <= 1000
    )
    return {
        "status": "PASS_SOURCE_GROUNDED_SMOKE" if pass_screen else "HOLD_ANSWER_QUALITY",
        "uncertainty_or_no_confirmed_location": has_uncertainty,
        "candidate_search_sites": places,
        "multiple_sites": has_search_sites,
        "no_obvious_proven_contact_claim": excludes_known_aliens,
        "nonrepetitive": not crude_repetition,
        "sentence_count": len(sentences),
        "human_semantic_review_required": True,
        "proves_improved_general_reasoning": False,
        "proves_extraterrestrial_life": False
    }


def generate(messages, output_tokens=175):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    torch.set_num_threads(4)
    torch.manual_seed(20261117)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        trust_remote_code=False
    ).eval()
    encoded = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    )
    count = encoded.shape[-1]
    if count > 2000:
        raise ValueError("MODEL_CONTEXT_BOUND_EXCEEDED")
    with torch.inference_mode():
        generated = model.generate(
            encoded,
            max_new_tokens=output_tokens,
            do_sample=False,
            repetition_penalty=1.14,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
    raw_answer = tokenizer.decode(generated[0][count:], skip_special_tokens=True)
    del model
    return raw_answer, count, {
        "model_name": MODEL_ID,
        "model_commit": getattr(tokenizer, "init_kwargs", {}).get("_commit_hash"),
        "dtype": "float16",
        "device": "cpu",
        "temperature": 0,
        "max_new_tokens": output_tokens
    }


def run(evidence_path, out_path):
    facts, sha = evidence(evidence_path)
    messages = model_messages(facts)
    answer, count, model_meta = generate(messages)
    grade = evaluate_answer(answer)
    out = {
        "schema": SCHEMA,
        "question": facts["question"],
        "status": grade["status"],
        "raw_model_answer": answer,
        "model_message_input_tokens": count,
        "model": model_meta,
        "evidence_path": str(evidence_path),
        "evidence_sha256": sha,
        "source_urls": [c["source"] for c in facts["claims"]],
        "assessment": grade,
        "native_g2_weights_changed": False,
        "new_reasoning_specialist_trained": False,
        "production_model_replaced": False,
        "sentinel_control": False,
        "scientific_detection_claim": False
    }
    target = Path(out_path)
    if target.exists() or target.is_symlink():
        raise ValueError("REFUSE_TO_OVERWRITE_PREVIOUS_OUTPUT")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("=== JANUS COSMOS R2 AUTHENTIC MODEL ANSWER ===", flush=True)
    print(answer, flush=True)
    print("=== END JANUS COSMOS R2 AUTHENTIC ANSWER ===", flush=True)
    print("JANUS_R2_QUALITY_GATE=" + grade["status"], flush=True)
    print("JANUS_R2_EVIDENCE_SHA256=" + sha, flush=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=EVIDENCE_PATH)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.evidence, args.output)


if __name__ == "__main__":
    main()
