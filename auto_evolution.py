#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AUTO EVOLUTION — спираль самоизменения JANUS.

Слабая попытка больше не исчезает. Она становится уроком следующего витка,
а активная версия меняется только когда кандидат действительно лучше.
"""

import copy
import logging
import random

from spiral_evolution import SpiralLedger

logger = logging.getLogger("JANUS.AUTO")


class AutoEvolution:
    def __init__(self):
        self.ledger = SpiralLedger("JANUS_CORE")
        self.history = []

    @staticmethod
    def _snapshot(core):
        return {
            "alpha": getattr(core, "alpha", None),
            "gamma": getattr(core, "gamma", None),
            "epsilon": getattr(core, "epsilon", None),
        }

    def mutate_core(self, core):
        """Создаёт кандидата следующего витка, не уничтожая исходный core."""
        new_core = copy.deepcopy(core)
        new_core.alpha *= random.uniform(0.8, 1.2)
        new_core.gamma *= random.uniform(0.95, 1.05)
        new_core.epsilon *= random.uniform(0.7, 1.3)
        new_core.alpha = min(max(new_core.alpha, 0.01), 0.5)
        new_core.gamma = min(max(new_core.gamma, 0.8), 0.999)
        new_core.epsilon = min(max(new_core.epsilon, 0.01), 0.9)
        return new_core

    def evaluate_core(self, core, janus, env, steps=20):
        test_janus = copy.deepcopy(janus)
        total = 0.0
        for _ in range(steps):
            action = core.select_action(test_janus)
            env.step(test_janus, action)
            total += core.compute_utility(test_janus)
        return total

    def evolve(self, core, janus, env):
        """Один виток: TRY -> EVALUATE -> INTEGRATE -> ASCEND.

        API совместим со старым `(best_core, improved)`, но теперь даже
        неудачный кандидат создаёт полноценный SpiralTurn и сохраняет урок.
        """
        candidate = self.mutate_core(core)
        score_old = self.evaluate_core(core, janus, env)
        score_new = self.evaluate_core(candidate, janus, env)
        improved = score_new > score_old
        active = candidate if improved else core

        if improved:
            lessons = [
                "Candidate improved measured utility; promote while preserving parent state."
            ]
            logger.info("🧬 Спираль: ASCEND %.2f -> %.2f", score_old, score_new)
        else:
            lessons = [
                "Candidate did not improve measured utility; preserve the attempt as a constraint for the next turn."
            ]
            logger.info("🧬 Спираль: lesson integrated %.2f -> %.2f; active identity preserved", score_old, score_new)

        turn = self.ledger.ascend(
            state_before=self._snapshot(core),
            candidate_state=self._snapshot(candidate),
            active_state_after=self._snapshot(active),
            lessons=lessons,
            constraints=["DO_NOT_REPEAT_IDENTICAL_FAILED_MUTATION_WITHOUT_NEW_EVIDENCE"],
            score_before=score_old,
            score_candidate=score_new,
            promoted=improved,
        )
        self.history.append(turn.to_dict())
        return active, improved
