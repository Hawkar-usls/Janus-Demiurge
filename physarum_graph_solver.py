"""
Physarum Graph Solver v2.2 — ЭВОЛЮЦИОННЫЙ ФИЗИКАЛЬНЫЙ ДВИЖОК
- Добавлен метод add_error_energy для получения энергии от ошибки self-model
- Исправлено построение графа для прямоугольных матриц весов
- Безопасное логирование температуры
- Инкрементальное обновление графа
- Память путей
- Динамические source/target
- Связь с температурой и fitness
- Влияние на геном и архитектуру
- Сохранение памяти путей
"""

import os
import numpy as np
import torch
from collections import deque
import logging
import random

logger = logging.getLogger("JANUS.PHYSARUM")

class PhysarumGraphSolver:
    def __init__(self, model, config):
        self.model = model
        self.n_nodes = config.get('n_nodes', 512)
        self.decay_rate = config.get('decay_rate', 0.1)
        self.diffusion_rate = config.get('diffusion_rate', 0.2)
        self.flow_threshold = config.get('flow_threshold', 0.01)

        self.potential = np.zeros(self.n_nodes)
        self.flow = np.zeros((self.n_nodes, self.n_nodes))
        self.adjacency = np.zeros((self.n_nodes, self.n_nodes))   # начальный граф
        self._build_graph()  # только первичная инициализация

        # НОВОЕ: память путей
        self.path_memory = deque(maxlen=config.get('path_memory_size', 50))

        # Для слоёвого графа (опционально)
        self.layer_graphs = []   # можно расширить позже

        # НОВОЕ: состояние системы для интеграции
        self.current_state = {}

    def _build_graph(self):
        """Первичное построение графа (только при инициализации)."""
        all_weights = []
        for name, param in self.model.named_parameters():
            if 'weight' in name and param.dim() == 2:
                all_weights.append(param.data.cpu().numpy())

        if not all_weights:
            logger.warning("Нет двумерных весов для построения графа")
            self.adjacency = np.zeros((self.n_nodes, self.n_nodes))
            return

        weight_matrix = all_weights[0]
        n_rows = min(weight_matrix.shape[0], self.n_nodes)
        n_cols = min(weight_matrix.shape[1], self.n_nodes)
        self.adjacency = np.zeros((self.n_nodes, self.n_nodes))
        self.adjacency[:n_rows, :n_cols] = np.abs(weight_matrix[:n_rows, :n_cols])

        max_val = self.adjacency.max()
        if max_val > 0:
            self.adjacency /= max_val

        logger.info(f"Построен граф из весов, размер {self.adjacency.shape}")

    def update_from_model(self, model, alpha=0.1):
        """
        Инкрементальное обновление графа (без полной перестройки).
        alpha — скорость обновления (0..1).
        """
        all_weights = []
        for name, param in model.named_parameters():
            if 'weight' in name and param.dim() == 2:
                all_weights.append(param.data.cpu().numpy())

        if not all_weights:
            return

        weight_matrix = all_weights[0]
        n_rows = min(weight_matrix.shape[0], self.n_nodes)
        n_cols = min(weight_matrix.shape[1], self.n_nodes)
        new_weights = np.abs(weight_matrix[:n_rows, :n_cols])
        max_val = new_weights.max()
        if max_val > 0:
            new_weights /= max_val

        # Плавное обновление
        self.adjacency[:n_rows, :n_cols] = (1 - alpha) * self.adjacency[:n_rows, :n_cols] + alpha * new_weights
        # Остальные узлы (если расширились) остаются как были

    def step(self, source_node=None, target_node=None):
        """
        Один шаг распространения потока.
        Если source/target не заданы, выбираются динамически.
        """
        # Динамический выбор источника и стока
        if source_node is None:
            # Выбираем узел с максимальной степенью (активности)
            degrees = self.adjacency.sum(axis=0) + self.adjacency.sum(axis=1)
            source_node = np.argmax(degrees)
        if target_node is None:
            # Выбираем узел с минимальной степенью (изолированный) или случайный, отличный от source
            degrees = self.adjacency.sum(axis=0) + self.adjacency.sum(axis=1)
            # Исключаем source и выбираем узел с наименьшей степенью
            candidates = [i for i in range(self.n_nodes) if i != source_node]
            if candidates:
                target_node = min(candidates, key=lambda i: degrees[i])
            else:
                target_node = source_node

        target_nodes = [target_node] if target_node is not None else [i for i in range(self.n_nodes) if i != source_node]

        # Решение системы потенциалов (итеративное)
        new_potential = self.potential.copy()
        for _ in range(10):
            for i in range(self.n_nodes):
                if i == source_node:
                    new_potential[i] = 1.0
                elif i in target_nodes:
                    new_potential[i] = 0.0
                else:
                    neighbors = self.adjacency[i]
                    if neighbors.sum() > 0:
                        new_potential[i] = np.dot(neighbors, self.potential) / neighbors.sum()
        self.potential = new_potential

        # Вычисление потока
        flow = np.zeros((self.n_nodes, self.n_nodes))
        for i in range(self.n_nodes):
            for j in range(self.n_nodes):
                if i != j and self.adjacency[i, j] > 0:
                    flow[i, j] = self.adjacency[i, j] * (self.potential[i] - self.potential[j])
        flow = np.maximum(flow, 0)

        # Обновление проводимости (физика)
        self.adjacency = self.adjacency * (1 - self.decay_rate) + flow * self.diffusion_rate
        self.adjacency = np.clip(self.adjacency, 0, 1)
        self.flow = flow
        return flow

    def get_importance(self):
        total_flow = np.sum(self.flow, axis=0) + np.sum(self.flow, axis=1)
        return total_flow / (total_flow.max() + 1e-6)

    def reinforce_path(self, path, fitness):
        """Усилить путь, который привёл к хорошему fitness."""
        if fitness <= 0:
            return
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            self.adjacency[u, v] += 0.1 * fitness
            self.adjacency[v, u] = self.adjacency[u, v]
        # Обрезаем до 1
        self.adjacency = np.clip(self.adjacency, 0, 1)

    def find_path(self, source, target):
        """Находит путь с наибольшим потоком между source и target."""
        visited = [False] * self.n_nodes
        prev = [-1] * self.n_nodes
        queue = deque([source])
        visited[source] = True
        while queue:
            u = queue.popleft()
            if u == target:
                break
            for v in range(self.n_nodes):
                if not visited[v] and self.flow[u, v] > self.flow_threshold:
                    visited[v] = True
                    prev[v] = u
                    queue.append(v)
        path = []
        u = target
        while u != -1:
            path.append(u)
            u = prev[u]
        path.reverse()
        return path if path[0] == source else None

    def remember_path(self, path, fitness):
        """Сохраняет успешный путь в память."""
        if path and fitness > 0:
            self.path_memory.append((path, fitness))

    def recall_path(self):
        """Случайно выбирает путь из памяти."""
        if not self.path_memory:
            return None, None
        return random.choice(self.path_memory)

    def mutate_weights(self, model, scale=0.05, temperature_scale=1.0):
        """
        Направленная мутация на основе важности рёбер.
        scale – базовый масштаб шума.
        temperature_scale – множитель от температуры (чем выше, тем больше шум).
        """
        importance = self.get_importance()
        total_scale = scale * temperature_scale
        for name, param in model.named_parameters():
            if 'weight' in name and param.dim() == 2:
                w = param.data.cpu().numpy()
                n, m = w.shape
                # Матрица важности, приведённая к размеру w
                imp_matrix = np.ones((n, m))
                imp_matrix[:min(n, self.n_nodes), :min(m, self.n_nodes)] = \
                    importance[:min(n, self.n_nodes), :min(m, self.n_nodes)]
                # Мутация: слабые связи мутируют сильнее
                noise = np.random.randn(n, m) * total_scale
                mutation = noise * (0.5 + (1 - imp_matrix))   # важные связи стабилизируем
                param.data = torch.from_numpy(w + mutation).to(param.device)
        logger.info(f"Применена умная мутация (scale={total_scale:.4f})")

    def suggest_config(self, genome=None):
        """
        На основе графа предлагает изменение архитектуры.
        Возвращает словарь с возможными изменениями гиперпараметров.
        """
        importance = self.get_importance()
        mean_imp = importance.mean()
        suggestions = {}
        if mean_imp > 0.6 and genome and genome.get('n_layer', 6) < 12:
            suggestions['n_layer'] = genome['n_layer'] + 1
        elif mean_imp < 0.3 and genome and genome.get('n_layer', 6) > 4:
            suggestions['n_layer'] = genome['n_layer'] - 1

        # Можно также предложить изменить n_embd, n_head
        if mean_imp > 0.7 and genome and genome.get('n_embd', 256) < 768:
            suggestions['n_embd'] = min(768, genome['n_embd'] + 64)
        elif mean_imp < 0.2 and genome and genome.get('n_embd', 256) > 128:
            suggestions['n_embd'] = max(128, genome['n_embd'] - 64)

        suggestions['source'] = 'physarum'
        return suggestions if suggestions else None

    def update(self, fitness, temperature_f=None):
        """
        Обновление графа на основе fitness и температуры.
        Если fitness > 0, усиливает все рёбра с потоком.
        Если температура высока, добавляет шум в граф.
        """
        if fitness > 0:
            self.adjacency += self.flow * fitness
            self.adjacency = np.clip(self.adjacency, 0, 1)
        if temperature_f is not None and temperature_f > 100:
            noise = np.random.randn(self.n_nodes, self.n_nodes) * (temperature_f / 1000.0)
            self.adjacency += noise
            self.adjacency = np.clip(self.adjacency, 0, 1)
        if temperature_f is not None:
            logger.debug(f"Граф обновлён (fitness={fitness:.3f}, temp={temperature_f:.1f})")
        else:
            logger.debug(f"Граф обновлён (fitness={fitness:.3f})")

    def add_error_energy(self, error):
        """
        Добавляет энергию ошибки self-model в граф.
        error – ошибка предсказания (loss_pred.item()).
        """
        if error > 100:
            # Нормируем шум, чтобы не разрушить структуру
            noise_scale = min(0.5, error / 5000.0)
            noise = np.random.randn(self.n_nodes, self.n_nodes) * noise_scale
            self.adjacency += noise
            self.adjacency = np.clip(self.adjacency, 0, 1)
            logger.debug(f"🔥 Добавлена энергия ошибки в граф: scale={noise_scale:.4f}")

    def update_state(self, state_dict):
        """Сохраняет текущее состояние системы для использования в графе."""
        self.current_state = state_dict
        # можно добавить узел-метку, но пока просто храним

    def save_memory(self, path):
        """Сохраняет память путей в файл."""
        np.save(path, list(self.path_memory))

    def load_memory(self, path):
        """Загружает память путей из файла."""
        if os.path.exists(path):
            data = np.load(path, allow_pickle=True)
            self.path_memory = deque(data, maxlen=self.path_memory.maxlen)
            logger.info(f"Загружена память путей: {len(self.path_memory)} записей")