# janus_genesis/needs.py
import random

class NeedsSystem:
    """Система потребностей агентов (голод, жажда, энергия, гигиена, туалет)."""

    def __init__(self):
        self.decay_rates = {
            "hunger": 0.02,
            "thirst": 0.03,
            "energy": 0.01,
            "hygiene": 0.015,
            "bladder": 0.025
        }

    def init_agent(self, agent):
        """Добавляет агенту словарь потребностей."""
        agent.needs = {
            "hunger": 1.0,
            "thirst": 1.0,
            "energy": 1.0,
            "hygiene": 1.0,
            "bladder": 1.0
        }

    def update(self, agent):
        """Обновляет потребности агента за один тик."""
        for need in agent.needs:
            agent.needs[need] -= self.decay_rates.get(need, 0.01)
            # не даём уйти в минус
            if agent.needs[need] < 0:
                agent.needs[need] = 0

        self._apply_effects(agent)

    def _apply_effects(self, agent):
        """Применяет штрафы от низких потребностей."""
        if agent.needs["hunger"] < 0.2:
            agent.score -= 0.1
        if agent.needs["thirst"] < 0.2:
            agent.score -= 0.2
        if agent.needs["energy"] < 0.2:
            # можно замедлить обучение, но пока штраф к score
            agent.score -= 0.15
        if agent.needs["hygiene"] < 0.2:
            # повышает шанс болезни
            pass  # болезни будут обрабатываться отдельно
        if agent.needs["bladder"] < 0.1:
            agent.needs["hygiene"] -= 0.3