# janus_genesis/meta_civilization_engine.py
"""
Мета-интеллект Януса: собирает состояние мира, выбирает стратегическое действие,
получает награду и обучается (пока rule-based, но позже можно заменить на RL).
"""

import random
from .state_encoder import WorldStateEncoder
from .strategic_actions import StrategicExecutor

class MetaCivilizationEngine:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.encoder = WorldStateEncoder()
        self.executor = StrategicExecutor()
        self.last_state = None
        self.last_action = None
        self.total_reward = 0

        # Подписываемся на события, которые дают награду
        event_bus.subscribe("raid_win", self.on_raid_win)
        event_bus.subscribe("institution_founded", self.on_institution_founded)

    def on_raid_win(self, agents, boss_name):
        """Награда за победу в рейде."""
        reward = len(agents) * 10
        self.total_reward += reward
        # Здесь можно обучить модель

    def on_institution_founded(self, institution, founder):
        """Награда за основание института."""
        self.total_reward += 50

    def choose_action(self):
        """Выбирает действие на основе состояния мира (пока рандомно)."""
        state = self.encoder.encode(self.world)
        # Здесь можно вызвать политику (нейросеть), пока случайный выбор
        action = random.choice(StrategicExecutor.ACTIONS)
        self.last_state = state
        self.last_action = action
        return action

    def apply_action(self, action):
        """Применяет действие и возвращает сообщение."""
        msg = self.executor.execute(action, self.world)
        self.event_bus.emit("strategic_action", action=action, result=msg)
        return msg

    def update(self):
        """Главный цикл мета-интеллекта (вызывается раз в N тиков)."""
        action = self.choose_action()
        result = self.apply_action(action)
        # Здесь можно добавить обучение на основе self.total_reward
        # Пока просто сбросим награду после шага
        self.total_reward = 0
        return action, result