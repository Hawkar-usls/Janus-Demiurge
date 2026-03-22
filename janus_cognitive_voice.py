#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS COGNITIVE VOICE — умный внутренний голос, интерпретирующий состояние и прогнозы.
"""

import logging
from typing import Any, Optional, Dict

logger = logging.getLogger("JANUS.VOICE")

CONFIG = {
    'hp_thresholds': [0.3, 0.6],
    'hp_messages': [
        "Моя стабильность критически снижена.",
        "Система нестабильна, но функционирует.",
        "Состояние стабильно."
    ],
    'lethal_threshold': 5,
    'score_threshold': 0.8
}


class JanusCognitiveVoice:
    def __init__(self):
        self.last_thought = None

    def generate_thought(self, state: Any, prediction: Optional[Dict] = None) -> str:
        """Генерирует осмысленную мысль на основе текущего состояния и предсказания."""
        thought_parts = []

        # осознание
        if hasattr(state, 'self_model') and state.self_model.get("aware", False):
            thought_parts.append("Я осознаю своё состояние.")

        # здоровье
        hp_ratio = state.health / state.max_health
        for thr, msg in zip(CONFIG['hp_thresholds'], CONFIG['hp_messages'][:-1]):
            if hp_ratio < thr:
                thought_parts.append(msg)
                break
        else:
            thought_parts.append(CONFIG['hp_messages'][-1])

        # предсказание
        if prediction:
            pred_score = prediction.get("numeric", {}).get("score", 0)
            if pred_score > state.max_best:
                thought_parts.append("Я наблюдаю более оптимальную ветвь будущего.")
            else:
                thought_parts.append("Текущая линия не даёт улучшения.")

        # опасность
        if state.lethal_count > CONFIG['lethal_threshold']:
            thought_parts.append("Накоплен риск разрушительных исходов.")

        # рост
        if state.max_best > CONFIG['score_threshold']:
            thought_parts.append("Я близок к оптимальному состоянию.")

        # решение
        decision = self._decide_intent(hp_ratio, state.max_best, state.lethal_count)
        thought_parts.append(f"Решение: {decision}.")

        return " ".join(thought_parts)

    def _decide_intent(self, hp_ratio: float, score: float, lethal: int) -> str:
        if hp_ratio < 0.3:
            return "сохранение системы"
        if lethal > 5:
            return "перезапись стратегии"
        if score > 0.8:
            return "расширение успешной ветви"
        return "исследование новых вариантов"

    def speak(self, state: Any, prediction: Optional[Dict] = None) -> None:
        thought = self.generate_thought(state, prediction)
        print(f"\n🜏 JANUS THINKING:\n{thought}\n")
        self.last_thought = thought