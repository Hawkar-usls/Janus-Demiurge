#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
META-CONSCIOUSNESS — самонаблюдение Януса.
"""

from typing import List, Optional

CONFIG = {
    'history_size': 50,
    'crisis_threshold': -5,
    'growth_threshold': 5
}


class MetaConsciousness:
    def __init__(self, world):
        self.world = world
        self.history_scores: List[float] = []

    def observe(self, score: float) -> None:
        """Получает текущий score (успех)."""
        self.history_scores.append(score)
        if len(self.history_scores) > CONFIG['history_size']:
            self.history_scores.pop(0)

    def analyze(self) -> Optional[str]:
        """Анализирует тренд и возвращает состояние."""
        if len(self.history_scores) < 10:
            return None
        trend = self.history_scores[-1] - self.history_scores[0]
        if trend < CONFIG['crisis_threshold']:
            return "crisis"
        if trend > CONFIG['growth_threshold']:
            return "growth"
        return "stable"