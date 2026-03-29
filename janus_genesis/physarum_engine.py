#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHYSARUM ENGINE — многоголовый слизевик.
Реализует алгоритмы поиска кратчайших путей и оптимизации, вдохновлённые Physarum polycephalum.

Включает:
- Сетевую модель (Tero-Nakagaki): граф трубок с переменной проводимостью.
- Алгоритм частиц (Jeff Jones): роевое движение с хемотаксисом.

Используется для:
- Поиска перспективных областей гиперпараметров.
- Прокладки оптимальных маршрутов в мире Genesis.
- Баланса exploration/exploitation.
"""

import numpy as np
import random
import math
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger("JANUS")

class PhysarumNetwork:
    """
    Сетевая модель слизевика.
    Граф узлов (пища) и рёбер (трубки) с адаптивной проводимостью.
    Основана на уравнениях:
        Q = D * (p_i - p_j) / L                     (закон Пуазёйля)
        Σ Q = 0                                      (сохранение массы, кроме источников/стоков)
        dD/dt = f(|Q|) - decay * D                   (адаптация проводимости)
    """

    def __init__(self, nodes: List[Tuple[float, float]], decay=0.1, growth_factor=1.0):
        """
        nodes: список координат узлов (пищевых точек).
        decay: коэффициент распада трубок.
        growth_factor: масштаб роста проводимости от потока.
        """
        self.nodes = nodes
        self.n = len(nodes)
        self.decay = decay
        self.growth_factor = growth_factor
        # Матрица проводимостей D (n x n)
        self.D = np.zeros((self.n, self.n))
        # Длины рёбер L (евклидовы расстояния)
        self.L = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(i+1, self.n):
                dist = np.linalg.norm(np.array(nodes[i]) - np.array(nodes[j]))
                self.L[i, j] = self.L[j, i] = max(dist, 1e-6)
        # Инициализация проводимостей: слабые связи между всеми
        self.D = 0.01 * np.ones((self.n, self.n))
        np.fill_diagonal(self.D, 0)

    def set_source_sink(self, source_idx: int, sink_idx: int, inflow: float = 1.0):
        """
        Устанавливает источник (положительный) и сток (отрицательный) для вычисления потока.
        inflow: суммарный поток, втекающий в источник.
        """
        self.source = source_idx
        self.sink = sink_idx
        self.inflow = inflow

    def compute_flow(self) -> np.ndarray:
        """
        Решает систему уравнений для давлений p и потоков Q.
        Возвращает матрицу потоков Q.
        """
        # Построим матрицу A и вектор b для системы линейных уравнений A * p = b
        A = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(self.n):
                if i != j:
                    A[i, i] += self.D[i, j] / self.L[i, j]
                    A[i, j] -= self.D[i, j] / self.L[i, j]

        b = np.zeros(self.n)
        b[self.source] = self.inflow
        b[self.sink] = -self.inflow

        # Решаем систему, зафиксировав давление в стоке = 0
        reduced_n = self.n - 1
        A_reduced = np.delete(np.delete(A, self.sink, axis=0), self.sink, axis=1)
        b_reduced = np.delete(b, self.sink)

        try:
            p_reduced = np.linalg.solve(A_reduced, b_reduced)
        except np.linalg.LinAlgError:
            return np.zeros((self.n, self.n))

        p = np.zeros(self.n)
        p[:self.sink] = p_reduced[:self.sink]
        p[self.sink+1:] = p_reduced[self.sink:]

        Q = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(i+1, self.n):
                q = self.D[i, j] * (p[i] - p[j]) / self.L[i, j]
                Q[i, j] = q
                Q[j, i] = -q
        return Q

    def update_conductivity(self, Q: np.ndarray, dt: float = 0.01):
        """
        Обновляет проводимости по правилу: dD/dt = growth_factor * |Q| - decay * D.
        """
        for i in range(self.n):
            for j in range(i+1, self.n):
                flow_abs = abs(Q[i, j])
                delta = self.growth_factor * flow_abs - self.decay * self.D[i, j]
                self.D[i, j] += delta * dt
                self.D[j, i] = self.D[i, j]
                if self.D[i, j] < 1e-6:
                    self.D[i, j] = 1e-6
                    self.D[j, i] = 1e-6

    def step(self, source_idx: int, sink_idx: int, dt: float = 0.01) -> np.ndarray:
        self.set_source_sink(source_idx, sink_idx)
        Q = self.compute_flow()
        self.update_conductivity(Q, dt)
        return Q

    def get_path(self, source_idx: int, sink_idx: int, threshold: float = 0.1) -> List[int]:
        visited = [False] * self.n
        path = [source_idx]
        visited[source_idx] = True
        current = source_idx
        while current != sink_idx:
            candidates = [(j, self.D[current, j]) for j in range(self.n) if not visited[j] and self.D[current, j] > threshold]
            if not candidates:
                break
            next_node = max(candidates, key=lambda x: x[1])[0]
            path.append(next_node)
            visited[next_node] = True
            current = next_node
        return path


class PhysarumParticle:
    """Отдельная частица слизевика (псевдоподий)."""

    def __init__(self, x: float, y: float, angle: float = 0.0, speed: float = 1.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = speed

    def sense(self, environment: np.ndarray, sensor_angles: List[float], sensor_distance: float = 5.0) -> List[float]:
        values = []
        h, w = environment.shape
        for delta_angle in sensor_angles:
            theta = self.angle + delta_angle
            sx = self.x + sensor_distance * math.cos(theta)
            sy = self.y + sensor_distance * math.sin(theta)
            ix = int(round(sx))
            iy = int(round(sy))
            if 0 <= ix < w and 0 <= iy < h:
                values.append(environment[iy, ix])
            else:
                values.append(0.0)
        return values

    def move(self, rotation_angle: float):
        self.angle += rotation_angle
        self.angle %= (2 * math.pi)
        self.x += self.speed * math.cos(self.angle)
        self.y += self.speed * math.sin(self.angle)


class PhysarumSwarm:
    """
    Роевая модель слизевика (алгоритм Джеффа Джонса).
    Частицы движутся в среде, оставляя след и реагируя на градиенты.
    """

    def __init__(self, width: int, height: int, n_particles: int = 100,
                 sensor_angles=(-math.pi/4, 0, math.pi/4), sensor_distance: float = 5.0,
                 rotation_angle: float = math.pi/6, evaporation: float = 0.1):
        self.width = width
        self.height = height
        self.n_particles = n_particles
        self.sensor_angles = sensor_angles
        self.sensor_distance = sensor_distance
        self.rotation_angle = rotation_angle
        self.evaporation = evaporation

        self.particles = []
        for _ in range(n_particles):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            angle = random.uniform(0, 2*math.pi)
            self.particles.append(PhysarumParticle(x, y, angle))

        self.trail = np.zeros((height, width), dtype=float)

    def deposit_trail(self, amount: float = 1.0):
        for p in self.particles:
            ix = int(round(p.x))
            iy = int(round(p.y))
            if 0 <= ix < self.width and 0 <= iy < self.height:
                self.trail[iy, ix] += amount

    def evaporate(self):
        self.trail *= (1.0 - self.evaporation)

    def sense_and_move(self, environment: np.ndarray, attractant_weight: float = 1.0, trail_weight: float = 1.0):
        for p in self.particles:
            sensor_vals = []
            for delta in self.sensor_angles:
                env_vals = p.sense(environment, [delta], self.sensor_distance)[0]
                trail_vals = p.sense(self.trail, [delta], self.sensor_distance)[0]
                combined = attractant_weight * env_vals + trail_weight * trail_vals
                sensor_vals.append(combined)

            front = sensor_vals[1]
            left = sensor_vals[0]
            right = sensor_vals[2]

            if front >= left and front >= right:
                p.move(0)
            elif left > right:
                p.move(-self.rotation_angle)
            else:
                p.move(self.rotation_angle)

            p.x = max(0, min(self.width-1, p.x))
            p.y = max(0, min(self.height-1, p.y))

    def step(self, environment: np.ndarray, deposit: float = 1.0):
        self.deposit_trail(deposit)
        self.evaporate()
        self.sense_and_move(environment)

    def get_trail_map(self) -> np.ndarray:
        return self.trail.copy()


class PhysarumOptimizer:
    """
    Адаптер, позволяющий использовать слизевика для поиска оптимальных гиперпараметров.
    Представляет пространство параметров как двумерную карту (после PCA или t-SNE).
    """
    def __init__(self, memory, n_particles=50, width=100, height=100):
        self.memory = memory
        self.swarm = PhysarumSwarm(width, height, n_particles)
        self.width = width
        self.height = height
        self.fitness_map = np.zeros((height, width))

    def update_fitness_map(self, history):
        """
        Обновляет карту фитнеса на основе истории конфигураций.
        history: список словарей с ключами 'config' и 'score' (или просто конфигурации).
        """
        self.fitness_map.fill(0.0)
        for entry in history:
            # Если entry имеет ключ 'base_config', берём его, иначе считаем, что это сама конфигурация
            config = entry.get('base_config', entry)
            if not isinstance(config, dict):
                continue
            vec = np.array([
                config.get('lr', 0.001),
                config.get('gain', 1.0),
                config.get('temperature', 1.0),
                config.get('n_embd', 256) / 768.0,
                config.get('n_head', 8) / 16.0,
                config.get('n_layer', 6) / 12.0
            ])
            # Упрощённая проекция: берём первые два параметра
            proj = vec[:2]
            x = int((proj[0] + 1) * self.width / 2) if proj[0] < 1 else int(proj[0] * self.width)
            y = int((proj[1] + 1) * self.height / 2) if proj[1] < 1 else int(proj[1] * self.height)
            x = max(0, min(self.width-1, x))
            y = max(0, min(self.height-1, y))
            self.fitness_map[y, x] += entry.get('score', 0)

    def contract(self, factor=0.5):
        """
        Сжимает граф решений, оставляя только наиболее сильные связи.
        Используется в режиме CONTRACT для "кристаллизации" решения.
        """
        if not hasattr(self, 'swarm') or self.swarm is None:
            return
        # Уменьшаем радиус поиска или усиливаем испарение
        if hasattr(self.swarm, 'evaporation'):
            self.swarm.evaporation = max(0.5, self.swarm.evaporation * 1.5)
        if hasattr(self.swarm, 'sensor_distance'):
            self.swarm.sensor_distance = max(1, self.swarm.sensor_distance * factor)
        logger.info(f"🧬 Physarum CONTRACT: evaporation повышен, сенсоры уменьшены")

    def propose(self, memory, samples=10, thermal_eff=None):
        """
        Запускает несколько шагов слизевика и возвращает конфигурацию, соответствующую пику карты.
        Если thermal_eff > 0.9, активирует сжатие (contract).
        """
        self.update_fitness_map(memory.history[-200:])

        # Активация сжатия при высокой тепловой эффективности
        if thermal_eff is not None and thermal_eff > 0.9:
            self.contract(factor=0.7)

        for _ in range(10):
            self.swarm.step(self.fitness_map)
        trail = self.swarm.get_trail_map()
        max_pos = np.unravel_index(np.argmax(trail), trail.shape)
        best_y, best_x = max_pos

        # Поиск ближайшей реальной конфигурации в истории
        best_score = -float('inf')
        best_config = None
        for entry in memory.history[-200:]:
            config = entry.get('base_config', entry)
            if not isinstance(config, dict):
                continue
            vec = np.array([
                config.get('lr', 0.001),
                config.get('gain', 1.0),
                config.get('temperature', 1.0),
                config.get('n_embd', 256) / 768.0,
                config.get('n_head', 8) / 16.0,
                config.get('n_layer', 6) / 12.0
            ])
            proj = vec[:2]
            x = int((proj[0] + 1) * self.width / 2) if proj[0] < 1 else int(proj[0] * self.width)
            y = int((proj[1] + 1) * self.height / 2) if proj[1] < 1 else int(proj[1] * self.height)
            if (x, y) == (best_x, best_y):
                score = entry.get('score', -float('inf'))
                if score > best_score:
                    best_score = score
                    best_config = config.copy()
        return best_config