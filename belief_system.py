#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BELIEF SYSTEM — мировоззрения агентов, основанные на их отношении к P vs NP.
"""

import random
import logging
from typing import Dict, Any, List

logger = logging.getLogger("JANUS.BELIEF")

CONFIG = {
    'beliefs': {
        "P_EQUALS_NP": {
            "doctrine": "Все задачи могут быть решены быстро. Истина доступна.",
            "influence": 0.1
        },
        "P_NOT_EQUALS_NP": {
            "doctrine": "Некоторые истины требуют поиска. Мир должен оставаться сложным.",
            "influence": 0.1
        },
        "BALANCE": {
            "doctrine": "Истина и поиск должны сосуществовать.",
            "influence": 0.1
        },
        "CHAOS": {
            "doctrine": "Сложность — источник силы. Пусть поиск будет бесконечным.",
            "influence": 0.1
        }
    },
    'meta_goal_influence': {
        "SEARCH_P_EQ_NP": {"P_EQUALS_NP": 0.01},
        "RESHAPE_REALITY": {"BALANCE": 0.02}
    }
}


class Belief:
    def __init__(self, name: str, doctrine: str):
        self.name = name
        self.doctrine = doctrine
        self.followers = 0
        self.influence = 0.1

    def spread(self, agents: List[Any]) -> None:
        for agent in agents:
            if random.random() < self.influence:
                agent.belief = self.name
                self.followers += 1


class BeliefSystem:
    def __init__(self):
        self.beliefs = {}
        for name, data in CONFIG['beliefs'].items():
            self.beliefs[name] = Belief(name, data["doctrine"])

    def update(self, agents: List[Any], meta_goal: Any) -> None:
        # Влияние мета-цели Януса
        for goal, effects in CONFIG['meta_goal_influence'].items():
            if getattr(meta_goal, 'current_goal', None) == goal:
                for belief_name, delta in effects.items():
                    if belief_name in self.beliefs:
                        self.beliefs[belief_name].influence += delta
                        logger.debug(f"Вера {belief_name} усилена мета-целью {goal}")

        # Распространение
        for belief in self.beliefs.values():
            belief.spread(agents)

        # Нормализация follower'ов (пересчёт влияния)
        total = sum(b.followers for b in self.beliefs.values()) + 1
        for belief in self.beliefs.values():
            belief.influence = belief.followers / total

        logger.info(f"Веры: {[(b.name, b.followers) for b in self.beliefs.values()]}")