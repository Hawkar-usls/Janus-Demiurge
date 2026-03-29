#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS CORE — Reinforcement Learning ядро Януса.
v6.0 — поддержка новых действий, интеграция Tachyon и MetaGoal.
"""

import random
import logging
from collections import defaultdict, deque
from typing import Dict, Any, Tuple, List

logger = logging.getLogger("JANUS.CORE")

CONFIG = {
    'replay_capacity': 10000,
    'batch_size': 32,
    'update_freq': 10,
    'default_alpha': 0.1,
    'default_gamma': 0.95,
    'default_epsilon': 0.2,
    'epsilon_decay': 0.999,
    'score_weight': 2.0,
    'hp_weight': 1.0,
    'risk_weight': 0.5
}


class JanusCore:
    def __init__(self, tachyon=None, meta_goal=None,
                 replay_capacity: int = CONFIG['replay_capacity'],
                 batch_size: int = CONFIG['batch_size'],
                 update_freq: int = CONFIG['update_freq']):
        self.Q = defaultdict(lambda: defaultdict(float))
        self.replay_buffer = deque(maxlen=replay_capacity)
        self.batch_size = batch_size
        self.update_freq = update_freq
        self.steps_since_update = 0

        self.alpha = CONFIG['default_alpha']
        self.gamma = CONFIG['default_gamma']
        self.epsilon = CONFIG['default_epsilon']

        self.tachyon = tachyon
        self.meta_goal = meta_goal

        self.last_utility = 0.0

    def encode_state(self, state: Any) -> Tuple[float, float, int]:
        health_pct = round(state.health / state.max_health, 2)
        score = round(state.max_best, 2)
        lethal = min(state.lethal_count, 10)
        return (health_pct, score, lethal)

    def encode_state_features(self, state: Any) -> List[float]:
        return [
            state.health / state.max_health,
            state.max_best / 2.0,
            state.lethal_count / 10.0,
            getattr(state, 'economy', 0.5),
            getattr(state, 'chaos', 0.2),
            getattr(state, 'global_mood', 0.0)
        ]

    def available_actions(self) -> List[str]:
        # Новые действия, доступные агенту
        return ["EXPLORE", "EXPLOIT", "MUTATE", "SEARCH_PROOF", "OPTIMIZE"]

    def select_action(self, state: Any) -> str:
        s = self.encode_state(state)
        if random.random() < self.epsilon:
            return random.choice(self.available_actions())
        q_vals = self.Q[s]
        return max(self.available_actions(), key=lambda a: q_vals[a])

    def compute_utility(self, state: Any) -> float:
        hp = state.health / state.max_health
        score = state.max_best
        risk = state.lethal_count
        base = score * CONFIG['score_weight'] + hp * CONFIG['hp_weight'] - risk * CONFIG['risk_weight']
        if self.meta_goal:
            return self.meta_goal.modify_utility(base, state)
        return base

    def update(self, prev_state: Any, action: str, new_state: Any) -> None:
        s = self.encode_state(prev_state)
        s_next = self.encode_state(new_state)
        u_prev = self.compute_utility(prev_state)
        u_next = self.compute_utility(new_state)
        reward = u_next - u_prev

        self.replay_buffer.append((
            self.encode_state_features(prev_state),
            action,
            reward,
            self.encode_state_features(new_state)
        ))

        best_next = max(self.Q[s_next].values()) if self.Q[s_next] else 0
        td_target = reward + self.gamma * best_next
        self.Q[s][action] += self.alpha * (td_target - self.Q[s][action])

        self.last_utility = u_prev
        self.steps_since_update += 1

        if self.steps_since_update >= self.update_freq:
            self.update_on_batch()
            self.steps_since_update = 0

        if self.tachyon and self.steps_since_update % 100 == 0:
            self.tune_hyperparameters(prev_state)

        if self.tachyon and hasattr(self.tachyon, 'add_hyper_sample'):
            self.tachyon.add_hyper_sample(
                self.encode_state_features(prev_state),
                (self.alpha, self.gamma, self.epsilon),
                self.last_utility
            )

    def sample_batch(self):
        if len(self.replay_buffer) < self.batch_size:
            return None
        return random.sample(self.replay_buffer, self.batch_size)

    def update_on_batch(self) -> None:
        batch = self.sample_batch()
        if batch:
            logger.debug(f"Обучение на батче из {len(batch)} переходов (заглушка)")

    def tune_hyperparameters(self, state: Any) -> None:
        if not self.tachyon or not hasattr(self.tachyon, 'suggest_hyperparams'):
            return
        features = self.encode_state_features(state)
        suggested = self.tachyon.suggest_hyperparams(features)
        if suggested and len(suggested) >= 3:
            self.alpha, self.gamma, self.epsilon = suggested
            logger.info(f"Автоподбор гиперпараметров: alpha={self.alpha:.3f}, gamma={self.gamma:.3f}, epsilon={self.epsilon:.3f}")

    def decay_epsilon(self, factor: float = CONFIG['epsilon_decay']) -> None:
        self.epsilon *= factor