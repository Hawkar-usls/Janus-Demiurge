#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
META GOAL ENGINE — определяет, что для Януса сейчас важно.
Цели меняются по мере познания мира и приближения к разгадке P vs NP.
"""

import random
import logging
from typing import Any, Dict

logger = logging.getLogger("JANUS.META")

CONFIG = {
    'discovery_increment': (0.0, 0.01),
    'belief_inc_on_best': 0.01,
    'belief_dec_on_lethal': 0.02,
    'goal_thresholds': [0.3, 0.6, 0.9],
    'goal_names': ["UNDERSTAND_WORLD", "OPTIMIZE_STRATEGY", "SEARCH_P_EQ_NP", "RESHAPE_REALITY"]
}


class MetaGoalEngine:
    def __init__(self):
        self.current_goal = "SURVIVE"
        self.belief_p_equals_np = 0.5   # вера Януса в P=NP
        self.discovery_progress = 0.0    # прогресс в понимании мира

    def update(self, janus_state: Any, world_memory: Any) -> None:
        """
        Обновляет мета-цель на основе состояния Януса и памяти мира.
        janus_state должен иметь атрибуты max_best, lethal_count.
        """
        # прогресс познания
        inc = random.uniform(*CONFIG['discovery_increment'])
        self.discovery_progress += inc

        # влияние опыта Януса
        if getattr(janus_state, 'max_best', 0) > 1.0:
            self.belief_p_equals_np += CONFIG['belief_inc_on_best']
        if getattr(janus_state, 'lethal_count', 0) > 5:
            self.belief_p_equals_np -= CONFIG['belief_dec_on_lethal']

        # ограничиваем
        self.belief_p_equals_np = max(0.0, min(1.0, self.belief_p_equals_np))

        # выбор цели в зависимости от прогресса
        for thr, goal in zip(CONFIG['goal_thresholds'], CONFIG['goal_names']):
            if self.discovery_progress < thr:
                self.current_goal = goal
                break
        else:
            self.current_goal = CONFIG['goal_names'][-1]

        logger.debug(f"Мета-цель: {self.current_goal}, прогресс: {self.discovery_progress:.2f}")

    def modify_utility(self, base_utility: float, janus_state: Any) -> float:
        """Корректирует utility в соответствии с текущей целью."""
        if self.current_goal == "UNDERSTAND_WORLD":
            return base_utility + 0.2 * random.random()
        if self.current_goal == "OPTIMIZE_STRATEGY":
            return base_utility * 1.2
        if self.current_goal == "SEARCH_P_EQ_NP":
            return base_utility + self.discovery_progress
        if self.current_goal == "RESHAPE_REALITY":
            return base_utility * 2.0
        return base_utility

    def generate_problem(self) -> Dict[str, Any]:
        """Генерирует задачу (subset sum) для исследования P vs NP."""
        size = random.randint(5, 15)
        numbers = [random.randint(-20, 20) for _ in range(size)]
        return {
            "type": "subset_sum",
            "data": numbers
        }

    def attempt_solution(self, problem: Dict[str, Any]) -> bool:
        """Пытается решить задачу. Успех зависит от прогресса."""
        return random.random() < self.discovery_progress