"""
HRAIN DECISION CORE — использует активный подграф для выбора действий Януса.
"""

import random
from typing import Dict, List, Any, Optional

class HrainDecisionCore:
    def __init__(self, graph_engine, core_rl=None):
        self.graph = graph_engine
        self.core_rl = core_rl  # для гибридного выбора

    def suggest_action(self, state: Any, available_actions: List[str]) -> str:
        """
        Выбирает действие на основе активного подграфа.
        state – текущее состояние (может быть использовано для улучшения).
        available_actions – список допустимых действий.
        """
        # Получаем активные узлы (высокая энергия)
        active = self.graph.get_active_subgraph(top_k=10)
        if not active:
            # Если нет активных узлов, используем RL или случайность
            return random.choice(available_actions)

        # Агрегируем типы действий из активных узлов
        action_scores = {act: 0.0 for act in available_actions}
        for node_id, node in active.items():
            # Извлекаем из node['data'] возможные ассоциации с действиями
            if 'action' in node['data']:
                action = node['data']['action']
                if action in action_scores:
                    action_scores[action] += node['energy']
            # Если есть рёбра от активных узлов к узлам-действиям
            for key, edge in self.graph.edges.items():
                if key.startswith(node_id + '->') and edge['weight'] > 0.1:
                    dst = key.split('->')[1]
                    if dst in self.graph.nodes and self.graph.nodes[dst]['type'] == 'action':
                        action = dst
                        if action in action_scores:
                            action_scores[action] += edge['weight'] * node['energy']

        # Выбираем действие с максимальным score
        best_action = max(action_scores, key=action_scores.get, default=random.choice(available_actions))
        return best_action

    def record_action_outcome(self, action: str, outcome: Dict):
        """
        Записывает результат действия в граф (награда/ошибка).
        """
        # Создаём узел события с энергией, зависящей от исхода
        energy = 1.0
        if outcome.get('reward', 0) > 0:
            energy = outcome['reward'] * 0.5 + 0.5   # reward от 0 до 2 -> энергия от 0.5 до 1.5
        elif outcome.get('error', 0) > 0:
            energy = max(0.1, 1.0 - outcome['error'] * 0.1)
        node_id = self.graph.add_node('outcome', outcome, energy=energy)

        # Связываем с действием (создаём узел-действие, если его нет)
        action_node = f"action_{action}"
        if action_node not in self.graph.nodes:
            self.graph.add_node('action', {'action': action}, energy=0.5)
        self.graph.add_edge(action_node, node_id, 'causal', weight=1.0)

        # Если исход положительный, дополнительно усиливаем связь
        if outcome.get('reward', 0) > 0:
            # Увеличиваем вес ребра между действием и исходом
            key = self.graph._edge_key(action_node, node_id)
            if key in self.graph.edges:
                self.graph.edges[key]['weight'] += 0.1