#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO EVOLUTION — слой самоизменения Януса.
Позволяет Янусу мутировать свои гиперпараметры (alpha, gamma, epsilon)
и выбирать лучшую версию себя.
"""

import copy
import random
import logging

logger = logging.getLogger("JANUS.AUTO")

class AutoEvolution:
    def __init__(self):
        self.history = []  # можно хранить результаты эволюции

    def mutate_core(self, core):
        """Создаёт мутированную копию ядра."""
        new_core = copy.deepcopy(core)

        # мутации гиперпараметров
        new_core.alpha *= random.uniform(0.8, 1.2)
        new_core.gamma *= random.uniform(0.95, 1.05)
        new_core.epsilon *= random.uniform(0.7, 1.3)

        # ограничения
        new_core.alpha = min(max(new_core.alpha, 0.01), 0.5)
        new_core.gamma = min(max(new_core.gamma, 0.8), 0.999)
        new_core.epsilon = min(max(new_core.epsilon, 0.01), 0.9)

        return new_core

    def evaluate_core(self, core, janus, env, steps=20):
        """
        Оценивает качество ядра, прогоняя steps шагов в среде.
        Возвращает суммарную utility.
        """
        test_janus = copy.deepcopy(janus)   # копия состояния Януса
        total = 0.0
        for _ in range(steps):
            action = core.select_action(test_janus)
            env.step(test_janus, action)
            total += core.compute_utility(test_janus)
        return total

    def evolve(self, core, janus, env):
        """
        Один шаг эволюции: создаёт мутанта, сравнивает с текущим.
        Возвращает (лучшее_ядро, флаг_улучшения).
        """
        candidate = self.mutate_core(core)
        score_old = self.evaluate_core(core, janus, env)
        score_new = self.evaluate_core(candidate, janus, env)

        if score_new > score_old:
            logger.info(f"🧬 Эволюция: улучшение {score_old:.2f} -> {score_new:.2f}")
            return candidate, True
        else:
            logger.debug(f"🧬 Эволюция: мутация хуже ({score_new:.2f} <= {score_old:.2f})")
            return core, False