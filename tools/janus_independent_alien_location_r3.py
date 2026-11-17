#!/usr/bin/env python3
"""JANUS R3 independent location hypothesis: unedited 1.5B model opinion.

No injected NASA/SETI source card, no external retrieval and no purported detection.
This is the model's own speculative selection, not measured localization.
No production promotion, self-update, or Sentinel privileges.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from tools import janus_cosmos_answer_r2 as native

SCHEMA = "janus.cosmos.independent_location_hypothesis_r3.v1"
QUESTION = (
    "Янус, это НЕ вопрос о фильме и НЕ просьба пересказать NASA или чужие "
    "исследования. Пользователь требует твоего личного, самостоятельного вывода: "
    "ГДЕ ИМЕННО во Вселенной, по твоей гипотезе, могут находиться настоящие "
    "инопланетяне? Выбери ОДНО конкретное астрономическое место: название "
    "звёздной системы, планеты, спутника или другого определённого объекта. "
    "Ты обязан сделать выбор, не отвечай просто «неизвестно» и не перечисляй "
    "десять вариантов. Построй собственное объяснение по физической логике "
    "(устойчивость среды, источники энергии, время для эволюции, наблюдаемость), "
    "назови одну возможность проверить предположение. "
    "Ровно 3–5 предложений по-русски, первым предложением назови объект. "
    "Не называй догадку обнаружением, не выдавай её за измеренный факт. "
    "Внешние справки, NASA и другие сведения тебе сейчас НЕ подаются."
)
SYSTEM = (
    "Ты JANUS COSMOS R3. Ты формулируешь свою самостоятельную проверяемую "
    "гипотезу, а не цитату учреждения. Внешних инструментов поиска и новых "
    "наблюдений нет, поэтому не утверждай реальный контакт или доказанную "
    "локализацию инопланетян. Отвечай прямо и конкретно."
)


def assessment(text):
    """Cheap syntax/safety screen; not scientific verification."""
    norm = re.sub(r"\s+", " ", text.strip().lower())
    if len(norm) < 70:
        return {"status": "HOLD_EMPTY_OR_SHORT", "reason": "insufficient text", "human_semantic_review_required": True}
    any_context = any(term in norm for term in
        ("звезд", "звёзд", "планет", "луна", "спутник", "систем", "орбит",
         "альфа", "проксим", "титан", "европ", "марс", "энцелад", "kepler", "trappist"))
    explicit_speculation = any(term in norm for term in
        ("предполага", "вероятн", "гипотез", "могут", "может",
         "возможно", "не доказ", "не подтверж", "версия", "по моему"))
    repeats = norm.count("не знаем") > 1 or norm.count("не можем точно") > 1
    screen = any_context and explicit_speculation and not repeats
    return {
        "status": "PASS_PRELIMINARY_SPECULATIVE_ANSWER" if screen else "HOLD_WEAK_SPECULATIVE_ANSWER",
        "has_astronomical_reference": any_context,
        "explicitly_speculative": explicit_speculation,
        "repetition_observed": repeats,
        "human_semantic_review_required": True,
        "location_confirmed": False,
        "independent_scientific_validation": False,
        "neural_weights_improved": False,
    }


def run(path):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": QUESTION},
    ]
    answer, tokens, meta = native.generate(messages, output_tokens=230)
    if not answer.strip():
        raise ValueError("EMPTY_REAL_MODEL_ANSWER")
    result = {
        "schema": SCHEMA,
        "question": "Где они? Назови лично наиболее вероятное конкретное место.",
        "full_prompt_sha256": hashlib.sha256(QUESTION.encode("utf-8")).hexdigest(),
        "raw_model_answer": answer,
        "model": meta,
        "input_tokens": tokens,
        "fed_nasa_or_seti_source_data": False,
        "used_live_telescope_observations": False,
        "claim_type": "MODEL_HYPOTHESIS_ONLY",
        "extraterrestrial_life_detected": False,
        "assessment": assessment(answer),
        "working_model_weights_changed": False,
        "sentinel_privileges": False,
    }
    out = Path(path)
    if out.exists() or out.is_symlink():
        raise ValueError("REFUSE_OVERWRITE")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("=== JANUS R3 UNASSISTED LOCATION RESPONSE ===", flush=True)
    print(answer, flush=True)
    print("=== END JANUS R3 UNASSISTED RESPONSE ===", flush=True)
    print("JANUS_R3_QUALITY_GATE=" + result["assessment"]["status"], flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    run(parser.parse_args().out)
