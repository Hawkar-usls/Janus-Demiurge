#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEANING ENGINE — глобальный смысл и мотивация цивилизации.
"""

import random
from typing import Any

CONFIG = {
    'global_goals': ["survival", "expansion", "wealth", "knowledge"],
    'update_chance': 0.01,
    'influence_factors': {
        'survival': {'risk_tolerance': 0.8},
        'expansion': {'aggression': 1.2},
        'wealth': {'greedy': 1.3},
        'knowledge': {'learning_rate': 1.2}
    }
}


class MeaningEngine:
    def __init__(self, world: Any):
        self.world = world
        self.current_goal = random.choice(CONFIG['global_goals'])

    def update(self) -> None:
        """Редко меняет глобальную цель."""
        if random.random() < CONFIG['update_chance']:
            self.current_goal = random.choice(CONFIG['global_goals'])

    def influence(self, agent: Any) -> None:
        """Влияет на параметры агента в соответствии с текущей целью."""
        factor = CONFIG['influence_factors'].get(self.current_goal, {})
        for attr, mult in factor.items():
            if hasattr(agent, attr):
                setattr(agent, attr, getattr(agent, attr) * mult)