# janus_genesis/tachyon_evolution.py
"""
Tachyon Evolution — предсказание будущего мира через быстрые симуляции.
"""

import copy
import random
import logging
from typing import List, Any

logger = logging.getLogger("JANUS.TACHYON_EVOLUTION")

CONFIG = {
    'simulation_depth': 20,
    'simulation_runs': 5,
    'evaluation_weights': {'population': 1.0, 'institutions': 5.0, 'memes': 2.0, 'economy': 0.1}
}


class TachyonEvolutionEngine:
    def __init__(self, world: Any):
        self.world = world
        self.simulation_depth = CONFIG['simulation_depth']
        self.simulation_runs = CONFIG['simulation_runs']

    def clone_world(self) -> Any:
        """Создаёт копию мира для симуляции, используя специализированный метод."""
        if hasattr(self.world, 'clone_for_simulation'):
            return self.world.clone_for_simulation()
        else:
            # fallback: глубокое копирование (может не сработать)
            return copy.deepcopy(self.world)

    def simulate(self, action: str) -> float:
        """Симулирует будущее после действия."""
        scores = []
        for _ in range(self.simulation_runs):
            sim_world = self.clone_world()
            # Применяем действие
            from .strategic_actions import StrategicExecutor
            executor = StrategicExecutor()
            executor.execute(action, sim_world)
            for _ in range(self.simulation_depth):
                sim_world.update()
            score = self.evaluate(sim_world)
            scores.append(score)
        return sum(scores) / len(scores) if scores else 0.0

    def evaluate(self, world: Any) -> float:
        """Оценивает состояние мира."""
        population = len(world.population)
        institutions = len(world.institutions.institutions) if hasattr(world, 'institutions') else 0
        memes = len(world.memes.memes) if hasattr(world, 'memes') else 0
        economy = sum(world.economy.resources.values()) if hasattr(world, 'economy') else 0
        w = CONFIG['evaluation_weights']
        return (population * w['population'] +
                institutions * w['institutions'] +
                memes * w['memes'] +
                economy * w['economy'])

    def choose_best_action(self, actions: List[str]) -> str:
        best_score = -float('inf')
        best_action = None
        for action in actions:
            score = self.simulate(action)
            logger.debug(f"Действие {action}: прогноз {score:.2f}")
            if score > best_score:
                best_score = score
                best_action = action
        return best_action