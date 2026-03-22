#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swarm Optimizer — Роевой интеллект (PSO) для поиска гиперпараметров.
"""

import random
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

CONFIG = {
    'n_particles': 5,
    'inertia': 0.7,
    'cognitive': 1.5,
    'social': 1.5,
    'gain_range': (0.3, 2.0),
    'temp_range': (0.3, 2.0),
    'lr_range': (1e-4, 5e-3),
    'n_embd_options': [64, 128, 256],
    'n_head_options': [4, 8, 16],
    'n_layer_options': [2, 4, 6]
}


class SwarmOptimizer:
    def __init__(self,
                 n_particles: int = CONFIG['n_particles'],
                 inertia: float = CONFIG['inertia'],
                 cognitive: float = CONFIG['cognitive'],
                 social: float = CONFIG['social'],
                 gain_range: Tuple[float, float] = CONFIG['gain_range'],
                 temp_range: Tuple[float, float] = CONFIG['temp_range'],
                 lr_range: Tuple[float, float] = CONFIG['lr_range'],
                 n_embd_options: List[int] = CONFIG['n_embd_options'],
                 n_head_options: List[int] = CONFIG['n_head_options'],
                 n_layer_options: List[int] = CONFIG['n_layer_options']):
        self.n_particles = n_particles
        self.inertia = inertia
        self.cognitive = cognitive
        self.social = social
        self.gain_range = gain_range
        self.temp_range = temp_range
        self.lr_range = lr_range
        self.n_embd_options = n_embd_options
        self.n_head_options = n_head_options
        self.n_layer_options = n_layer_options

        self.positions: List[List[float]] = []
        self.velocities: List[List[float]] = []
        self.pbest_positions: List[List[float]] = []
        self.pbest_values: List[float] = []
        self.gbest_position: Optional[List[float]] = None
        self.gbest_value: float = -float('inf')

        self._init_particles()
        self._current_idx = 0

    def _random_config(self) -> List[float]:
        return [
            random.uniform(*self.gain_range),
            random.uniform(*self.temp_range),
            random.uniform(*self.lr_range),
            random.choice(self.n_embd_options),
            random.choice(self.n_head_options),
            random.choice(self.n_layer_options)
        ]

    def _init_particles(self) -> None:
        for _ in range(self.n_particles):
            pos = self._random_config()
            self.positions.append(pos)
            self.velocities.append([random.uniform(-0.1, 0.1) for _ in range(6)])
            self.pbest_positions.append(pos.copy())
            self.pbest_values.append(-float('inf'))

    def ask(self, mood_influence: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, Any], int]:
        """
        Возвращает следующую конфигурацию для оценки и индекс частицы.
        mood_influence может изменять параметры движения.
        """
        inertia = self.inertia
        cognitive = self.cognitive
        social = self.social
        if mood_influence:
            inertia *= mood_influence.get('inertia_factor', 1.0)
            cognitive *= mood_influence.get('cognitive_factor', 1.0)
            social *= mood_influence.get('social_factor', 1.0)

        idx = self._current_idx
        self._current_idx = (self._current_idx + 1) % self.n_particles
        return self._particle_to_dict(self.positions[idx]), idx

    def tell(self, idx: int, value: float) -> None:
        """
        Сообщает результат оценки для частицы с индексом idx.
        value – композитный score (чем выше, тем лучше).
        """
        if value > self.pbest_values[idx]:
            self.pbest_values[idx] = value
            self.pbest_positions[idx] = self.positions[idx].copy()
        if value > self.gbest_value:
            self.gbest_value = value
            self.gbest_position = self.positions[idx].copy()

        # Обновляем скорость и позицию частицы
        r1, r2 = random.random(), random.random()
        for i in range(6):
            cognitive_vel = self.cognitive * r1 * (self.pbest_positions[idx][i] - self.positions[idx][i])
            social_vel = self.social * r2 * (self.gbest_position[i] - self.positions[idx][i])
            self.velocities[idx][i] = self.inertia * self.velocities[idx][i] + cognitive_vel + social_vel
            self.positions[idx][i] += self.velocities[idx][i]
            # Ограничиваем значения
            if i == 0:
                self.positions[idx][i] = np.clip(self.positions[idx][i], *self.gain_range)
            elif i == 1:
                self.positions[idx][i] = np.clip(self.positions[idx][i], *self.temp_range)
            elif i == 2:
                self.positions[idx][i] = np.clip(self.positions[idx][i], *self.lr_range)
            elif i == 3:
                self.positions[idx][i] = self._closest_option(self.positions[idx][i], self.n_embd_options)
            elif i == 4:
                self.positions[idx][i] = self._closest_option(self.positions[idx][i], self.n_head_options)
            elif i == 5:
                self.positions[idx][i] = self._closest_option(self.positions[idx][i], self.n_layer_options)

    @staticmethod
    def _closest_option(value: float, options: List[int]) -> int:
        return min(options, key=lambda x: abs(x - value))

    @staticmethod
    def _particle_to_dict(pos: List[float]) -> Dict[str, Any]:
        return {
            'gain': round(pos[0], 3),
            'temperature': round(pos[1], 3),
            'lr': round(pos[2], 5),
            'n_embd': int(pos[3]),
            'n_head': int(pos[4]),
            'n_layer': int(pos[5])
        }

    def get_best_config(self) -> Optional[Dict[str, Any]]:
        if self.gbest_position is None:
            return None
        return self._particle_to_dict(self.gbest_position)