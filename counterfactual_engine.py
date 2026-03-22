#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COUNTERFACTUAL ENGINE — мышление «а если бы…»
Генерирует альтернативные варианты и учится на них.
"""

import random
import logging
from typing import Dict, Any, List

logger = logging.getLogger("JANUS.COUNTERFACTUAL")

CONFIG = {
    'steps_range': (0.7, 1.3),
    'steps_min': 10,
    'steps_max': 100,
    'seed_mutation': (-100, 100),
    'prompt_len_range': (0.8, 1.2),
    'default_weight': 0.3
}


class CounterfactualEngine:
    def __init__(self, tachyon):
        self.tachyon = tachyon

    def generate_variants(self, features: Dict[str, Any], n: int = 5) -> List[Dict[str, Any]]:
        """Генерирует n альтернативных наборов признаков, мутируя исходные."""
        variants = []
        for _ in range(n):
            f = features.copy()
            # мутируем параметры
            if 'steps' in f:
                f['steps'] = int(f['steps'] * random.uniform(*CONFIG['steps_range']))
                f['steps'] = max(CONFIG['steps_min'], min(CONFIG['steps_max'], f['steps']))
            if 'seed_mod' in f:
                f['seed_mod'] = (f['seed_mod'] + random.randint(*CONFIG['seed_mutation'])) % 1000
            if 'prompt_len' in f:
                f['prompt_len'] = int(f['prompt_len'] * random.uniform(*CONFIG['prompt_len_range']))
            variants.append(f)
        return variants

    def simulate(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Возвращает список словарей с features и предсказаниями для альтернатив."""
        variants = self.generate_variants(features)
        predictions = []
        for v in variants:
            pred = self.tachyon.predict_outcome(v)
            if pred:
                predictions.append({'features': v, 'prediction': pred})
        return predictions

    def learn_from_counterfactuals(self, real_features: Dict[str, Any],
                                   real_outcome: Dict[str, Any],
                                   weight: float = CONFIG['default_weight']) -> None:
        """
        Обучает Tachyon на альтернативах, используя предсказания как псевдо-метки.
        """
        sims = self.simulate(real_features)
        for sim in sims:
            self.tachyon.learn(sim['features'], sim['prediction'], weight=weight)

    def evaluate_decision(self, real_outcome: Dict[str, Any],
                          sims: List[Dict[str, Any]]) -> bool:
        """Сравнивает реальный исход с альтернативами."""
        real_score = real_outcome.get('score', 0)
        for sim in sims:
            if sim['prediction'].get('score', 0) > real_score:
                return True
        return False