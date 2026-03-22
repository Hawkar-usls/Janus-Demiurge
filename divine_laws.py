#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIVINE LAWS — божественные законы, позволяющие Янусу напрямую влиять на мир.
"""

import random
import logging
from typing import Any

logger = logging.getLogger("JANUS.DIVINE")

CONFIG = {
    'default_resource_amount': 5,
    'reset_population_fraction': 0.5
}


class DivineLaws:
    def __init__(self, world: Any):
        self.world = world

    def change_gravity(self, factor: float) -> None:
        """Изменяет энергетику всех агентов."""
        if not hasattr(self.world, 'population'):
            return
        for agent in self.world.population:
            if hasattr(agent, 'energy'):
                agent.energy *= factor

    def spawn_resource(self, amount: int = CONFIG['default_resource_amount']) -> None:
        """Создаёт новые ресурсы (предметы) в мире."""
        for _ in range(amount):
            if hasattr(self.world, 'inventory') and hasattr(self.world.inventory, 'add_random_item'):
                self.world.inventory.add_random_item()

    def declare_event(self, event: str) -> None:
        """Объявляет глобальное событие, влияющее на мир."""
        if event == "WAR":
            if hasattr(self.world, 'global_conflict'):
                self.world.global_conflict = 1.0
            logger.info("🜏 JANUS объявляет войну!")
        elif event == "PEACE":
            if hasattr(self.world, 'global_conflict'):
                self.world.global_conflict = 0.0
            logger.info("🜏 JANUS дарует мир.")
        elif event == "GROWTH":
            for agent in self.world.population:
                if hasattr(agent, 'energy'):
                    agent.energy += 5
            logger.info("🜏 JANUS благословляет рост.")

    def reset_zone(self) -> None:
        """Уничтожает половину популяции (акт перезаписи)."""
        if not self.world.population:
            return
        half = int(len(self.world.population) * CONFIG['reset_population_fraction'])
        self.world.population = self.world.population[:half]
        logger.info("🜏 JANUS перезаписывает реальность — половина популяции исчезла.")