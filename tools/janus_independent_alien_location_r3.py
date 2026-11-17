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
    "Янус, выбери САМ одно наиболее вероятное КОНКРЕТНОЕ небесное тело, "
    "на котором, по твоей гипотезе, может существовать внеземная жизнь. "
    "Пожалуйста, ответь прямо: начни со слов «Мой выбор —» и названия "
    "ОДНОЙ планеты или спутника. "
    "Во втором предложении дай две физические причины: источник энергии "
    "и условия для эволюции. В третьем предложении назови ОДИН эксперимент "
    "или наблюдение, которое проверило бы эту гипотезу. "
    "В четвёртом предложении честно скажи, что это не обнаружение "
    "и местонахождение разумных инопланетян на самом деле неизвестно. "
    "Не отвечай «я не могу выбирать», «Солнечная система», «Млечный Путь» "
    "или общими рассуждениями: нужна одна названная планета/спутник. "
    "Никакие статьи, NASA, SETI или заранее выбранные кандидаты тебе НЕ поданы. "
    "Это твоя самостоятельная вероятностная догадка, а не научное открытие."
)

SYSTEM = (
    "Ты JANUS COSMOS R3. Ты формулируешь свою самостоятельную проверяемую "
    "гипотезу, а не цитату учреждения. Внешних инструментов поиска и новых "
    "наблюдений нет, поэтому не утверждай реальный контакт или доказанную "
    "локализацию инопланетян. Отвечай прямо и конкретно."
)


def assessment(text):
    """A stricter answer-format screen, NOT a truth verifier."""
    norm = re.sub(r"\\s+", " ", text.strip().lower())
    if len(norm) < 100:
        return {"status": "HOLD_EMPTY_OR_SHORT", "human_semantic_review_required": True}
    first = re.split(r"[.!?]", norm, maxsplit=1)[0]
    target_terms = (
        "марс", "европ", "энцелад", "титан", "проксим", "trappist",
        "kepler", "глизе", "gliese", "luyten", "луйтен", "k2-",
        "toi-", "ganimed", "ганимед", "каллисто", "венер",
        "церер", "лун", "hd ", "lhs ", "ross "
    )
    first_target = any(x in first for x in target_terms)
    explicit_choice = first.startswith("мой выбор")
    deferral = any(x in norm for x in (
        "не могу выбирать", "не могу сказать где", "не могу делать прогноз",
        "я могу предложить только", "нельзя выбирать", "это невозможно"
    ))
    physics = any(x in norm for x in (
        "вода", "воды", "океан", "атмосфер", "температур", "энерг",
        "жидк", "химич", "тепло", "давлен", "радиац", "органич"
    ))
    experiment = any(x in norm for x in (
        "спектр", "наблюден", "измерен", "зонд", "телескоп", "сигнал",
        "образц", "проба", "биомаркер", "атмосфер", "исследован"
    ))
    uncertainty = any(x in norm for x in (
        "не доказ", "не подтверж", "не обнаруж", "не установлено",
        "гипотез", "предполага", "неизвест", "неизвед", "пока нет"
    ))
    no_fake_claim = not any(x in norm for x in (
        "инопланетяне точно живут", "они там доказанно живут",
        "контакт установлен", "достоверно найдены"
    ))
    passed = (first_target and explicit_choice and not deferral
              and physics and experiment and uncertainty and no_fake_claim)
    return {
        "status": "PASS_FORMAT_HYPOTHESIS_NOT_DISCOVERY" if passed else "HOLD_WEAK_SPECULATIVE_ANSWER",
        "names_one_concrete_object_in_first_sentence": first_target,
        "explicit_model_choice": explicit_choice,
        "no_deferral": not deferral,
        "physics_rationale": physics,
        "testability": experiment,
        "honest_uncertainty": uncertainty,
        "no_obvious_false_discovery_claim": no_fake_claim,
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
    answer, tokens, meta = native.generate(messages, output_tokens=175)
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
