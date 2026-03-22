#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REGRET ENGINE — вычисляет сожаление о принятом решении.
"""

import logging

logger = logging.getLogger("JANUS.REGRET")

class RegretEngine:
    def compute(self, real_score, counterfactuals):
        """
        real_score: реальный score
        counterfactuals: список предсказаний альтернатив
        Возвращает величину сожаления (0..1)
        """
        best_alt = max([c.get("score", 0) for c in counterfactuals], default=real_score)
        regret = max(0.0, best_alt - real_score)
        return regret