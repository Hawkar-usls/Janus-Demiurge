#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Swarm Optimizer — PSO scheduling on a monotonic spiral, not a logical ring."""

import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from spiral_evolution import fingerprint_payload

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
        self.spiral_turn = 0
        self.particle_turns = [0 for _ in range(self.n_particles)]
        self.lineage: List[Dict[str, Any]] = []
        self._pending_turn: Dict[int, Dict[str, Any]] = {}

    def _random_config(self) -> List[float]:
        return [
            random.uniform(*self.gain_range), random.uniform(*self.temp_range),
            random.uniform(*self.lr_range), random.choice(self.n_embd_options),
            random.choice(self.n_head_options), random.choice(self.n_layer_options)
        ]

    def _init_particles(self) -> None:
        for _ in range(self.n_particles):
            pos = self._random_config()
            self.positions.append(pos)
            self.velocities.append([random.uniform(-0.1, 0.1) for _ in range(6)])
            self.pbest_positions.append(pos.copy())
            self.pbest_values.append(-float('inf'))

    def ask(self, mood_influence: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, Any], int]:
        """Return next physical slot, while logical time always ascends."""
        idx = self._current_idx
        self._current_idx = (self._current_idx + 1) % self.n_particles
        turn = self.spiral_turn
        self.spiral_turn += 1
        self.particle_turns[idx] += 1
        self._pending_turn[idx] = {
            "spiral_turn": turn,
            "particle_turn": self.particle_turns[idx],
            "particle_idx": idx,
            "state_before": self.positions[idx].copy(),
            "parent_fingerprint": fingerprint_payload(self.positions[idx]),
            "mood_influence": mood_influence or {},
        }
        return self._particle_to_dict(self.positions[idx]), idx

    def tell(self, idx: int, value: float) -> None:
        before_best = self.pbest_values[idx]
        before_global = self.gbest_value
        improved_personal = value > self.pbest_values[idx]
        improved_global = value > self.gbest_value
        if improved_personal:
            self.pbest_values[idx] = value
            self.pbest_positions[idx] = self.positions[idx].copy()
        if improved_global:
            self.gbest_value = value
            self.gbest_position = self.positions[idx].copy()
        if self.gbest_position is None:
            self.gbest_position = self.positions[idx].copy()

        r1, r2 = random.random(), random.random()
        for i in range(6):
            cognitive_vel = self.cognitive * r1 * (self.pbest_positions[idx][i] - self.positions[idx][i])
            social_vel = self.social * r2 * (self.gbest_position[i] - self.positions[idx][i])
            self.velocities[idx][i] = self.inertia * self.velocities[idx][i] + cognitive_vel + social_vel
            self.positions[idx][i] += self.velocities[idx][i]
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

        event = self._pending_turn.pop(idx, {
            "spiral_turn": self.spiral_turn,
            "particle_turn": self.particle_turns[idx],
            "particle_idx": idx,
            "state_before": self.positions[idx].copy(),
            "parent_fingerprint": None,
        })
        event.update({
            "score": value,
            "previous_personal_best": before_best,
            "previous_global_best": before_global,
            "improved_personal": improved_personal,
            "improved_global": improved_global,
            "state_after": self.positions[idx].copy(),
            "lesson": (
                "PROMOTE_OBSERVED_IMPROVEMENT" if improved_personal or improved_global
                else "PRESERVE_NONIMPROVING_TURN_AS_SEARCH_CONSTRAINT"
            ),
        })
        event["fingerprint"] = fingerprint_payload(event)
        self.lineage.append(event)

    @staticmethod
    def _closest_option(value: float, options: List[int]) -> int:
        return min(options, key=lambda x: abs(x - value))

    @staticmethod
    def _particle_to_dict(pos: List[float]) -> Dict[str, Any]:
        return {
            'gain': round(float(pos[0]), 3),
            'temperature': round(float(pos[1]), 3),
            'lr': round(float(pos[2]), 5),
            'n_embd': int(pos[3]),
            'n_head': int(pos[4]),
            'n_layer': int(pos[5])
        }

    def get_best_config(self) -> Optional[Dict[str, Any]]:
        return self._particle_to_dict(self.gbest_position) if self.gbest_position is not None else None

    def get_spiral_state(self) -> Dict[str, Any]:
        return {
            "spiral_turn": self.spiral_turn,
            "physical_slot": self._current_idx,
            "particle_turns": self.particle_turns,
            "lineage_events": len(self.lineage),
            "logical_ring": False,
        }
