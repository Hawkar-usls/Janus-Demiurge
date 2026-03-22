# janus_genesis/disease.py
import random

class DiseaseSystem:
    """Система болезней агентов."""

    DISEASES = {
        "dysentery": {
            "score_penalty": 0.5,
            "energy_drain": 0.05,
            "contagious": 0.1
        },
        "entropy_fever": {
            "mutation_boost": 0.3,
            "hp_loss": 0.05,
            "contagious": 0.05
        },
        "code_cold": {
            "score_penalty": 0.2,
            "energy_drain": 0.02,
            "contagious": 0.2
        }
    }

    def infect(self, agent):
        """Пытается заразить агента случайной болезнью (2% шанс)."""
        if random.random() < 0.02 and not hasattr(agent, 'disease'):
            agent.disease = random.choice(list(self.DISEASES.keys()))

    def update(self, agent):
        """Обновляет эффекты болезни у агента."""
        if not hasattr(agent, 'disease') or not agent.disease:
            return
        d = self.DISEASES[agent.disease]
        if "score_penalty" in d:
            agent.score -= d["score_penalty"]
        if "energy_drain" in d and hasattr(agent, 'needs'):
            agent.needs["energy"] -= d["energy_drain"]
        # остальные эффекты можно добавить позже

    def cure(self, agent):
        """Вылечивает агента."""
        if hasattr(agent, 'disease'):
            agent.disease = None