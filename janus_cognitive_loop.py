#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JANUS COGNITIVE LOOP v1.0
Главный когнитивный цикл:
- Интеграция SelfModel + Graph + Fitness + Error
- Управление режимами (explore/exploit)
- Связь с внешними агентами (Cardputer / Titan)
"""

import logging
import numpy as np
import random
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("JANUS.COGNITIVE")

# ======================================================================
# МОДЕЛЬ СЕБЯ (SELF MODEL)
# ======================================================================
class SelfModel:
    def __init__(self):
        self.identity = {
            "mode": "balanced",
            "confidence": 0.5,
            "self_trust": 0.5,
            "goals": []
        }
        self.history = []  # история (quality, time, pred_error)

    def update(self, outcome: Dict[str, float]):
        """Обновляет идентичность на основе исхода."""
        self.history.append(outcome)
        if len(self.history) > 100:
            self.history.pop(0)

        # Простейший анализ: меняем режим в зависимости от качества
        recent_quality = np.mean([h["quality"] for h in self.history[-20:]])
        recent_error = np.mean([h.get("pred_error", 0) for h in self.history[-20:]])

        if recent_error > 500:
            self.identity["mode"] = "explorer"
            self.identity["confidence"] *= 0.8
            self.identity["self_trust"] *= 0.9
        elif recent_quality > 0.8:
            self.identity["mode"] = "efficient"
            self.identity["confidence"] = min(1.0, self.identity["confidence"] + 0.1)
            self.identity["self_trust"] = min(1.0, self.identity["self_trust"] + 0.05)
        elif recent_quality < 0.3:
            self.identity["mode"] = "aggressive"
            self.identity["confidence"] = max(0.1, self.identity["confidence"] - 0.1)
            self.identity["self_trust"] = max(0.2, self.identity["self_trust"] - 0.1)
        else:
            self.identity["mode"] = "balanced"
            self.identity["confidence"] = 0.5
            self.identity["self_trust"] = 0.5

    def update_mode_by_error(self, error: float):
        """Изменяет режим в зависимости от ошибки предсказания."""
        if error > 500:
            self.identity["mode"] = "explorer"
            self.identity["confidence"] *= 0.8
        elif error < 50:
            self.identity["mode"] = "efficient"
            self.identity["confidence"] = min(1.0, self.identity["confidence"] + 0.05)
        else:
            self.identity["mode"] = "balanced"

    def __repr__(self):
        return f"SelfModel(mode={self.identity['mode']}, conf={self.identity['confidence']:.2f}, trust={self.identity['self_trust']:.2f})"


# ======================================================================
# ГРАФ ПАМЯТИ (HRAIN GRAPH ENGINE) – упрощённая версия
# ======================================================================
class HrainGraphEngine:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.next_id = 0

    def add_node(self, label: str, attrs: Dict = None, energy: float = 1.0) -> int:
        """Добавляет узел, возвращает его id."""
        node_id = self.next_id
        self.next_id += 1
        self.nodes[node_id] = {
            "label": label,
            "attrs": attrs or {},
            "energy": energy,
            "last_active": 0
        }
        return node_id

    def add_edge(self, from_id: int, to_id: int, label: str = "link", weight: float = 1.0):
        """Добавляет ребро."""
        key = (from_id, to_id)
        self.edges[key] = {"label": label, "weight": weight, "strength": 1.0}

    def get_active_subgraph(self, top_k: int = 10) -> List[int]:
        """Возвращает список id узлов с наибольшей энергией."""
        sorted_nodes = sorted(self.nodes.items(), key=lambda x: x[1]["energy"], reverse=True)
        return [nid for nid, _ in sorted_nodes[:top_k]]

    def update(self, events: List[Dict]) -> List[Dict]:
        """
        Обновляет граф на основе событий.
        Возвращает список изменений (для логирования).
        """
        diffs = []
        for ev in events:
            ev_type = ev.get("type")
            if ev_type == "node_activate":
                node_id = ev.get("node_id")
                if node_id in self.nodes:
                    self.nodes[node_id]["energy"] += ev.get("delta", 0.1)
                    diffs.append(ev)
            elif ev_type == "edge_boost":
                from_id = ev.get("from")
                to_id = ev.get("to")
                key = (from_id, to_id)
                if key in self.edges:
                    self.edges[key]["strength"] += ev.get("delta", 0.1)
                    diffs.append(ev)
        # простое затухание энергии
        for nid in self.nodes:
            self.nodes[nid]["energy"] *= 0.99
        return diffs

    def random_exploration(self):
        """Добавляет случайные связи для исследования."""
        # если есть узлы, добавляем случайное ребро
        if len(self.nodes) < 2:
            return
        ids = list(self.nodes.keys())
        from_id = random.choice(ids)
        to_id = random.choice([i for i in ids if i != from_id])
        self.add_edge(from_id, to_id, "explore", weight=0.5)

    def __repr__(self):
        return f"HrainGraphEngine(nodes={len(self.nodes)}, edges={len(self.edges)})"


# ======================================================================
# ОСНОВНОЙ КОГНИТИВНЫЙ ЦИКЛ
# ======================================================================
class JanusCognitiveLoop:
    def __init__(self):
        self.self_model = SelfModel()
        self.graph = HrainGraphEngine()

        # Глобальные параметры
        self.global_state = {
            "mode": "balanced",
            "tick": 0,
            "last_fitness": 0.0,
            "best_fitness": -1e9
        }

        # Геном (глобальный)
        self.genome = {
            "mutation_rate": 0.2,
            "exploration": 0.3,
            "learning_rate": 0.001
        }

        # Инициализация базового узла "self" в графе
        self.self_node = self.graph.add_node("self", attrs={"type": "core"})

    # ==================================================================
    # 🧮 FITNESS
    # ==================================================================
    def compute_fitness(self, metrics: Dict[str, Any]) -> float:
        """Универсальный fitness (можно расширять)"""
        loss = metrics.get("loss", 1.0)
        entropy = metrics.get("entropy", 0.0)
        temp = metrics.get("temp_f", 0.0) if "temp_f" in metrics else metrics.get("temperature", 0.0)
        np_solved = metrics.get("np_solved", False)

        loss_term = 1.0 / (1.0 + loss)
        entropy_penalty = entropy * 2.0
        temp_penalty = temp / 100.0
        np_bonus = 1.0 if np_solved else 0.0

        fitness = loss_term + np_bonus - entropy_penalty - temp_penalty
        return float(fitness)

    # ==================================================================
    # 🧠 SELF-MODEL ОБНОВЛЕНИЕ
    # ==================================================================
    def update_self_model(self, fitness: float, pred_error: float, metrics: Dict):
        outcome = {
            "quality": fitness,
            "time": metrics.get("step_time_ms", 0),
            "pred_error": pred_error
        }
        self.self_model.update(outcome)
        self.self_model.update_mode_by_error(pred_error)

    # ==================================================================
    # 🧬 ГЕНОМ (ЭВОЛЮЦИЯ)
    # ==================================================================
    def evolve_genome(self, fitness: float):
        pressure = abs(fitness - self.global_state["best_fitness"])

        # адаптация mutation_rate
        self.genome["mutation_rate"] = min(
            0.5,
            max(0.05, self.genome["mutation_rate"] + pressure * 0.1)
        )

        # случайная мутация
        if np.random.rand() < self.genome["mutation_rate"]:
            self.genome["learning_rate"] *= np.random.uniform(0.8, 1.2)
            self.genome["exploration"] += np.random.uniform(-0.05, 0.05)

        # clamp
        self.genome["learning_rate"] = np.clip(self.genome["learning_rate"], 1e-5, 0.01)
        self.genome["exploration"] = np.clip(self.genome["exploration"], 0.0, 1.0)

    # ==================================================================
    # ⚡ РЕАКЦИЯ НА ERROR (ключевая штука)
    # ==================================================================
    def handle_prediction_error(self, error: float):
        if error > 500:
            logger.info(f"🌀 HIGH ERROR → EXPLORATION BOOST (error={error:.1f})")

            self.genome["mutation_rate"] *= 1.5
            self.genome["exploration"] += 0.1
            self.genome["mutation_rate"] = min(0.5, self.genome["mutation_rate"])
            self.genome["exploration"] = min(1.0, self.genome["exploration"])

            # усиливаем граф (хаос = поиск)
            self.inject_graph_noise(error)

            # резко падает доверие
            self.self_model.identity["self_trust"] *= 0.5

    def inject_graph_noise(self, error: float):
        """Добавляет случайные связи в граф для поиска."""
        for _ in range(min(10, int(error / 100))):
            self.graph.random_exploration()

    # ==================================================================
    # 🌐 ГРАФ
    # ==================================================================
    def update_graph(self, events: List[Dict]) -> List[Dict]:
        return self.graph.update(events)

    def sync_graph_with_self(self):
        """Передаём состояние сознания в граф."""
        # Обновляем узел "self" новыми атрибутами
        self.graph.nodes[self.self_node]["attrs"] = {
            "mode": self.self_model.identity["mode"],
            "confidence": self.self_model.identity["confidence"],
            "self_trust": self.self_model.identity["self_trust"]
        }
        self.graph.nodes[self.self_node]["energy"] += 0.1  # небольшая активация

        # связываем с активными узлами
        active = self.graph.get_active_subgraph(10)
        for nid in active:
            if nid != self.self_node:
                self.graph.add_edge(self.self_node, nid, "influence", weight=0.5)

    def reinforce_action(self, action: Dict):
        """Усиливает узел, соответствующий действию, в графе."""
        target = action.get("target")
        if not target:
            return
        # Ищем узел с меткой, похожей на target
        for nid, data in self.graph.nodes.items():
            if data["label"] == target:
                self.graph.add_edge(self.self_node, nid, "action_path", weight=0.5)
                self.graph.nodes[nid]["energy"] += 0.2
                return

    # ==================================================================
    # 🔁 ГЛАВНЫЙ ШАГ (ОДИН ЦИКЛ)
    # ==================================================================
    def step(self, metrics: Dict[str, Any], pred_error: float, events: List[Dict]) -> Dict:
        self.global_state["tick"] += 1

        # 1. fitness
        fitness = self.compute_fitness(metrics)

        # 2. обновление лучшего
        if fitness > self.global_state["best_fitness"]:
            self.global_state["best_fitness"] = fitness

        # 3. self-model
        self.update_self_model(fitness, pred_error, metrics)

        # 4. error → поведение
        self.handle_prediction_error(pred_error)

        # 5. геном
        self.evolve_genome(fitness)

        # 6. граф
        diffs = self.update_graph(events)
        self.sync_graph_with_self()

        # 7. режим системы
        self.global_state["mode"] = self.self_model.identity["mode"]

        # 8. выбор действия (пример)
        action = self.decide_action()

        # 9. запись действия в граф
        self.reinforce_action(action)

        return {
            "fitness": fitness,
            "mode": self.global_state["mode"],
            "genome": self.genome,
            "self": self.self_model.identity,
            "diffs": diffs,
            "action": action
        }

    # ==================================================================
    # 🧠 ПРИНЯТИЕ РЕШЕНИЙ (на основе self-model и графа)
    # ==================================================================
    def decide_action(self) -> Dict[str, Any]:
        mode = self.self_model.identity["mode"]
        confidence = self.self_model.identity["confidence"]
        trust = self.self_model.identity["self_trust"]

        # если нет доверия — всегда исследуем
        if trust < 0.2:
            return self._random_action()

        # если высокая уверенность — эксплуатируем
        if confidence > 0.8:
            return self._best_action()

        if mode == "explorer":
            return self._random_action()
        elif mode == "efficient":
            return self._best_action()
        elif mode == "aggressive":
            return self._high_risk_action()
        else:
            return self._balanced_action()

    def _random_action(self) -> Dict:
        return {"type": "explore", "target": "random"}

    def _best_action(self) -> Dict:
        # здесь можно получить из графа наиболее перспективный узел
        active = self.graph.get_active_subgraph(3)
        if active:
            target = self.graph.nodes[active[0]]["label"]
        else:
            target = "optimize"
        return {"type": "exploit", "target": target}

    def _high_risk_action(self) -> Dict:
        # агрессивный режим: увеличиваем мутацию, идём в рискованный путь
        return {"type": "mutate", "target": "high_risk"}

    def _balanced_action(self) -> Dict:
        # сбалансированный режим: комбинируем
        if np.random.rand() < 0.5:
            return self._random_action()
        else:
            return self._best_action()

# ======================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ (можно убрать, если импортируется)
# ======================================================================
if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    loop = JanusCognitiveLoop()

    # Эмуляция метрик
    metrics = {"loss": 0.5, "entropy": 0.2, "temp_f": 35.0, "np_solved": False}
    pred_error = 100.0
    events = [{"type": "node_activate", "node_id": 0, "delta": 0.5}]

    for i in range(10):
        result = loop.step(metrics, pred_error, events)
        print(f"Step {i}: {result}")
        time.sleep(1)