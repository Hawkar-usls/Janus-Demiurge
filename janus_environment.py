#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS ENVIRONMENT — внешний мир, который меняется под влиянием действий Януса.
v6.0 — поддержка новых действий агента и интеграция с RL.
"""

import random
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("JANUS.ENV")

CONFIG = {
    'step_effects': {
        'EXPLORE': {'max_best': (0.01, 0.05), 'instability': 0.02, 'economy': 0.01, 'chaos': 0.01},
        'EXPLOIT': {'max_best': 0.08, 'health': -5, 'instability': -0.02, 'economy': 0.02},
        'MUTATE': {'max_best': (0.0, 0.1), 'health': -3, 'chaos': 0.05, 'economy': -0.02},
        'SEARCH_PROOF': {'max_best': 0.02, 'health': -2, 'instability': 0.03, 'chaos': 0.02},
        'OPTIMIZE': {'max_best': 0.03, 'health': -1, 'economy': 0.03, 'instability': -0.01},
        'SURVIVE': {'health': 5, 'instability': -0.01, 'economy': -0.01, 'chaos': -0.02},
        'REWRITE': {'lethal': -2, 'max_best': -0.02, 'chaos': -0.03, 'global_mood': 0.05}
    },
    'economy_threshold': 0.2,
    'chaos_threshold': 0.8,
    'global_mood_threshold_high': 0.5,
    'global_mood_threshold_low': -0.5,
    'random_event_chance': 0.05,
    'random_events': {
        'EARTHQUAKE': {'health': -10, 'chaos': 0.1, 'description': 'Землетрясение наносит урон'},
        'ECONOMIC_BOOM': {'economy': 0.2, 'max_best': 0.1, 'description': 'Экономический бум увеличил ресурсы'},
        'TECHNOLOGY_BREAKTHROUGH': {'max_best': 0.2, 'description': 'Технологический прорыв'},
        'WAR': {'health': -15, 'chaos': 0.2, 'economy': -0.1, 'description': 'Война опустошает земли'}
    }
}


class JanusEnvironment:
    def __init__(self, world_memory: Optional[Any] = None):
        self.global_instability = 0.2
        self.resource_level = 1.0
        self.economy = 0.7
        self.chaos = 0.1
        self.global_mood = 0.3

        self.world_memory = world_memory
        self.events: List[Dict] = []

    def step(self, state: Any, action: str) -> Tuple[Any, float]:
        """
        Применяет действие к состоянию и изменяет параметры среды.
        Возвращает (новое_состояние, награда).
        """
        self.events.clear()

        # Применяем эффекты действия
        effect = CONFIG['step_effects'].get(action, {})
        reward = 0.0
        for key, val in effect.items():
            if isinstance(val, tuple):
                delta = random.uniform(*val)
            else:
                delta = val
            if key == 'max_best':
                state.max_best += delta
                reward += delta * 10
            elif key == 'health':
                state.health += delta
                reward -= delta * 0.5
            elif key == 'lethal':
                state.lethal_count = max(0, state.lethal_count + delta)
                reward -= abs(delta) * 5
            elif key == 'instability':
                self.global_instability += delta
            elif key == 'resource':
                self.resource_level += delta
            elif key == 'economy':
                self.economy += delta
                reward += delta * 2
            elif key == 'chaos':
                self.chaos += delta
            elif key == 'global_mood':
                self.global_mood += delta
                reward += delta * 1

        # Нелинейные эффекты от переменных среды
        if self.economy < CONFIG['economy_threshold']:
            state.health -= 2
            self._add_event("FAMINE", "Экономика в упадке, начался голод")
            reward -= 1
        if self.chaos > CONFIG['chaos_threshold']:
            state.max_best -= 0.02
            self._add_event("CHAOS", "Хаос разрушает порядок, max_best снижается")
            reward -= 1
        if self.global_mood > CONFIG['global_mood_threshold_high']:
            state.health += 1
            reward += 0.5
        elif self.global_mood < CONFIG['global_mood_threshold_low']:
            state.health -= 1
            reward -= 0.5

        # Случайные события
        if random.random() < CONFIG['random_event_chance']:
            event_name = random.choice(list(CONFIG['random_events'].keys()))
            ev = CONFIG['random_events'][event_name]
            for key, val in ev.items():
                if key == 'description':
                    continue
                if key == 'health':
                    state.health += val
                    reward += val * 0.5
                elif key == 'economy':
                    self.economy += val
                elif key == 'chaos':
                    self.chaos += val
                elif key == 'max_best':
                    state.max_best += val
                    reward += val * 10
            self._add_event(event_name, ev['description'])

        # Базовое влияние мира
        state.health -= self.global_instability * 2
        reward -= self.global_instability * 0.5
        state.max_best += self.resource_level * 0.01
        reward += self.resource_level * 0.1

        # Случайный шум
        noise = random.uniform(-0.02, 0.02)
        state.max_best += noise
        reward += noise * 5

        # Ограничения
        state.health = max(0, min(state.health, state.max_health))
        state.max_best = max(0, min(state.max_best, 2.0))
        self.economy = max(0.0, min(1.0, self.economy))
        self.chaos = max(0.0, min(1.0, self.chaos))
        self.global_mood = max(-1.0, min(1.0, self.global_mood))

        # Запись событий в world_memory
        if self.world_memory and self.events:
            for ev in self.events:
                self.world_memory.record(ev['type'], ev['data'])

        return state, reward

    def _add_event(self, event_type: str, description: str) -> None:
        self.events.append({
            'type': event_type,
            'data': {'description': description, 'timestamp': None}
        })
        logger.debug(f"Событие среды: {event_type} — {description}")

    def pop_events(self) -> List[Dict]:
        events = self.events.copy()
        self.events.clear()
        return events