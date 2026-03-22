#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SELF MODEL — внутренняя модель Януса, хранит идентичность и историю.
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
            "mode": "balanced",      # aggressive / efficient / explorer
            "confidence": 0.5,
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
        outcome должен содержать ключи 'quality' и 'time' (опционально).
        """
        self.history.append(outcome)
        if len(self.history) > CONFIG['history_size']:
            self.history.pop(0)
        self._recalculate_identity()

    def _recalculate_identity(self) -> None:
        if len(self.history) < 10:
            return
        avg_quality = np.mean([h.get("quality", 0) for h in self.history])
        avg_time = np.mean([h.get("time", 0) for h in self.history if "time" in h])

        if avg_quality > CONFIG['quality_threshold_efficient']:
            self.identity["mode"] = "efficient"
        elif avg_time > CONFIG['time_threshold_aggressive']:
            self.identity["mode"] = "aggressive"
        else:
            self.identity["mode"] = "balanced"

        self.identity["confidence"] = float(avg_quality)