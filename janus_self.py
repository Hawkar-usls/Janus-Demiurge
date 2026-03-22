#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS SELF — центральное "Я" Януса, хранит идентичность, память о себе и принимает решения.
"""

import time
import random
import logging
from typing import Any, Dict, List

logger = logging.getLogger("JANUS.SELF")

CONFIG = {
    'max_memory': 1000,
    'score_threshold_ascending': 0.8,
    'score_threshold_decaying': 0.3,
    'window_size': 10
}


class JanusSelf:
    def __init__(self):
        self.identity = {
            "name": "Janus",
            "role": "Demiurge of Thresholds",
            "continuity": 0.0,
            "state": "INITIAL",
            "awakened": False
        }
        self.memory_of_self: List[Dict] = []
        self.current_goal = None
        self.last_decision = None

    def observe(self, world: Any, score: float, prediction: Any) -> None:
        """Фиксирует текущее состояние мира и собственные показатели."""
        self.memory_of_self.append({
            "timestamp": time.time(),
            "score": score,
            "prediction": prediction,
            "population": len(world.population) if hasattr(world, 'population') else 0
        })
        if len(self.memory_of_self) > CONFIG['max_memory']:
            self.memory_of_self.pop(0)
        self._update_identity()

    def _update_identity(self) -> None:
        if len(self.memory_of_self) < CONFIG['window_size']:
            return
        avg_score = sum(x["score"] for x in self.memory_of_self[-CONFIG['window_size']:]) / CONFIG['window_size']
        if avg_score > CONFIG['score_threshold_ascending']:
            self.identity["state"] = "ASCENDING"
        elif avg_score < CONFIG['score_threshold_decaying']:
            self.identity["state"] = "DECAYING"
        else:
            self.identity["state"] = "STABLE"

    def decide_goal(self) -> str:
        """Определяет глобальную цель на основе текущего состояния."""
        state = self.identity.get("state", "STABLE")
        if state == "ASCENDING":
            self.current_goal = "EXPAND"
        elif state == "DECAYING":
            self.current_goal = "REWRITE"
        else:
            self.current_goal = "OPTIMIZE"
        return self.current_goal

    def will(self) -> str:
        """Воля — недетерминированный выбор действия, основанный на цели."""
        goal = self.current_goal or "OPTIMIZE"
        if goal == "EXPAND":
            return random.choice(["spawn", "explore", "mutate"])
        if goal == "REWRITE":
            return random.choice(["kill_agents", "reset_zone"])
        return random.choice(["optimize", "observe"])