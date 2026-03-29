#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SELF MODEL — внутренняя модель Януса, хранит идентичность и историю.
Расширенная версия: confidence через стабильность, само-доверие, мета-адаптация.
"""

import numpy as np
import logging
from typing import List, Dict, Any

logger = logging.getLogger("JANUS.SELF")

CONFIG = {
    'history_size': 50,
    'quality_threshold_efficient': 0.8,
    'time_threshold_aggressive': 6.0
}


class SelfModel:
    def __init__(self):
        self.identity = {
            "mode": "balanced",      # aggressive / efficient / explorer / balanced
            "confidence": 0.5,
            "self_trust": 0.5,
            "archetype": "Demiurge of Thresholds",
            "title": "Janus Tachyon"
        }
        self.goals = {
            "quality": 0.7,
            "efficiency": 0.5,
            "learning": 0.8
        }
        self.history: List[Dict[str, Any]] = []

    def update(self, outcome: Dict[str, Any]) -> None:
        """
        Обновляет историю и пересчитывает идентичность.
        outcome должен содержать ключи 'quality' и 'time' (опционально),
        а также 'pred_error' (ошибка предсказания self-model).
        """
        self.history.append(outcome)
        if len(self.history) > CONFIG['history_size']:
            self.history.pop(0)
        self._recalculate_identity()
        if "pred_error" in outcome:
            self.update_self_trust(outcome["pred_error"])

    def _recalculate_identity(self) -> None:
        if len(self.history) < 5:
            return
        avg_quality = np.mean([h.get("quality", 0) for h in self.history])
        avg_time = np.mean([h.get("time", 0) for h in self.history if "time" in h])

        # Определяем режим
        if avg_quality > CONFIG['quality_threshold_efficient']:
            self.identity["mode"] = "efficient"
        elif avg_time > CONFIG['time_threshold_aggressive']:
            self.identity["mode"] = "aggressive"
        else:
            self.identity["mode"] = "balanced"

        # Confidence = стабильность (чем меньше разброс, тем выше уверенность)
        qualities = [h.get("quality", 0) for h in self.history]
        if len(qualities) > 5:
            std = np.std(qualities)
            self.identity["confidence"] = max(0.0, min(1.0, 1.0 - std))
        else:
            self.identity["confidence"] = 0.5

    def update_self_trust(self, pred_error: float) -> None:
        """Обновляет уровень доверия к собственным предсказаниям."""
        self.identity["self_trust"] = 1.0 / (1.0 + pred_error)
        # Ограничиваем от 0.05 до 0.95
        self.identity["self_trust"] = max(0.05, min(0.95, self.identity["self_trust"]))

    def update_mode_by_error(self, error: float) -> None:
        """Меняет режим в зависимости от величины ошибки предсказания."""
        if error > 1000:
            self.identity["mode"] = "explorer"
            self.goals["learning"] += 0.1
        elif error > 200:
            self.identity["mode"] = "balanced"
        else:
            self.identity["mode"] = "efficient"
        # clip goals
        for k in self.goals:
            self.goals[k] = max(0.0, min(1.0, self.goals[k]))

    def meta_adapt(self) -> None:
        """Адаптирует цели на основе истории."""
        if len(self.history) < 10:
            return
        recent_quality = np.mean([h.get("quality", 0) for h in self.history[-10:]])
        if recent_quality < 0.5:
            self.goals["learning"] += 0.05
            self.goals["efficiency"] -= 0.02
        elif recent_quality > 0.8:
            self.goals["efficiency"] += 0.05
            self.goals["learning"] -= 0.02
        for k in self.goals:
            self.goals[k] = max(0.0, min(1.0, self.goals[k]))