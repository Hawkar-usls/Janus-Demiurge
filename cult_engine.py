#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CULT ENGINE — специальные группы (культы), которые активно влияют на мир.
"""

import random
import logging
from typing import Dict, Any

logger = logging.getLogger("JANUS.CULT")

CONFIG = {
    'cult_spawn_chance': 0.05,
    'beliefs': ["P_EQUALS_NP", "P_NOT_EQUALS_NP", "CHAOS", "BALANCE"],
    'effects': {
        'P_EQUALS_NP': {'instability': 0.05, 'resource': 0.02, 'chaos': 0.0},
        'P_NOT_EQUALS_NP': {'instability': 0.0, 'resource': 0.05, 'chaos': -0.02},
        'CHAOS': {'instability': 0.1, 'resource': -0.05, 'chaos': 0.1},
        'BALANCE': {'instability': -0.02, 'resource': 0.01, 'chaos': 0.0}
    }
}


class Cult:
    def __init__(self, name: str, belief: str):
        self.name = name
        self.belief = belief
        self.power = 1.0   # сила влияния

    def act(self, world: Any) -> None:
        """Культ воздействует на параметры мира в соответствии со своей верой."""
        effect = CONFIG['effects'].get(self.belief, {})
        # безопасное изменение атрибутов
        if hasattr(world, 'global_instability'):
            world.global_instability += effect.get('instability', 0.0)
        if hasattr(world, 'resource_level'):
            world.resource_level += effect.get('resource', 0.0)
        if hasattr(world, 'chaos'):
            world.chaos += effect.get('chaos', 0.0)

        logger.debug(f"Культ {self.name} ({self.belief}) влияет на мир")


class CultEngine:
    def __init__(self):
        self.cults: List[Cult] = []

    def spawn_cult(self, belief: str) -> None:
        """Создаёт новый культ на основе веры."""
        name = f"Cult_of_{belief}_{random.randint(1,999)}"
        self.cults.append(Cult(name, belief))
        logger.info(f"🔥 Появился новый культ: {name} (вера: {belief})")

    def update(self, world: Any) -> None:
        """Обновляет все культы и порождает новые."""
        for cult in self.cults:
            cult.act(world)

        # шанс появления нового культа
        if random.random() < CONFIG['cult_spawn_chance']:
            belief = random.choice(CONFIG['beliefs'])
            self.spawn_cult(belief)