#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BELIEF SYSTEM — система вер, влияющих на поведение агентов.
Каждая вера имеет количество последователей и доктрину.
Вера влияет на параметры агентов (например, risk_tolerance).
"""

import os
import json
import random
import logging
from typing import Dict, List, Any

from config import RAW_LOGS_DIR

logger = logging.getLogger("JANUS.BELIEF")

CONFIG = {
    'beliefs': ["P_EQUALS_NP", "P_NOT_EQUALS_NP", "BALANCE", "CHAOS"],
    'effects': {
        'P_EQUALS_NP': {'risk_tolerance': 0.8, 'learning_rate': 1.2, 'aggression': 0.9},
        'P_NOT_EQUALS_NP': {'risk_tolerance': 1.2, 'learning_rate': 0.9, 'aggression': 1.1},
        'BALANCE': {'risk_tolerance': 1.0, 'learning_rate': 1.0, 'aggression': 1.0},
        'CHAOS': {'risk_tolerance': 1.5, 'learning_rate': 1.5, 'aggression': 1.3}
    },
    'spread_chance': 0.1,  # увеличено с 0.01
    'max_followers': 1000
}

class Belief:
    def __init__(self, name: str, doctrine: str):
        self.name = name
        self.doctrine = doctrine
        self.followers = 0
        self.effects = CONFIG['effects'].get(name, {})

    def spread(self):
        self.followers += 1

    def lose_follower(self):
        if self.followers > 0:
            self.followers -= 1

    def to_dict(self):
        return {
            'name': self.name,
            'doctrine': self.doctrine,
            'followers': self.followers,
            'effects': self.effects
        }

    @classmethod
    def from_dict(cls, data):
        belief = cls(data['name'], data['doctrine'])
        belief.followers = data['followers']
        belief.effects = data['effects']
        return belief


class BeliefSystem:
    def __init__(self, save_file: str = None):
        self.save_file = save_file or os.path.join(RAW_LOGS_DIR, "beliefs.json")
        self.beliefs: Dict[str, Belief] = {}
        self._init_beliefs()
        self.load_state()

    def _init_beliefs(self):
        for name in CONFIG['beliefs']:
            doctrine = f"Учение веры {name}"
            self.beliefs[name] = Belief(name, doctrine)

    def update(self, agents: List[Any], meta_goal: Any = None) -> None:
        """
        Обновляет веры на основе агентов и мета-цели.
        """
        if not agents:
            return

        # Подсчёт текущих вер
        belief_counts = {name: 0 for name in self.beliefs}
        for agent in agents:
            if agent.belief and agent.belief in belief_counts:
                belief_counts[agent.belief] += 1

        # Применяем к Belief объектам
        for name, count in belief_counts.items():
            self.beliefs[name].followers = count

        # Случайное распространение веры (новые агенты получают веру)
        for agent in agents:
            if random.random() < CONFIG['spread_chance']:
                # Выбираем веру с вероятностью, пропорциональной числу последователей
                total = sum(b.followers for b in self.beliefs.values())
                if total > 0:
                    names = list(self.beliefs.keys())
                    weights = [self.beliefs[n].followers for n in names]
                    chosen = random.choices(names, weights=weights, k=1)[0]
                    agent.belief = chosen
                    logger.debug(f"Агент {agent.id[:8]} принял веру {chosen}")

        # Если у некоторых агентов всё ещё нет веры, назначаем случайную
        for agent in agents:
            if not agent.belief:
                agent.belief = random.choice(CONFIG['beliefs'])
                logger.debug(f"Агенту {agent.id[:8]} назначена случайная вера {agent.belief}")

        # Влияние веры на параметры агентов
        for agent in agents:
            if agent.belief and agent.belief in self.beliefs:
                belief = self.beliefs[agent.belief]
                for param, factor in belief.effects.items():
                    if hasattr(agent, param):
                        current = getattr(agent, param)
                        # Плавно подстраиваем параметр
                        new_val = current * (0.9 + factor * 0.2)
                        setattr(agent, param, new_val)

        # Сохраняем состояние
        self.save_state()

    def get_dominant_belief(self) -> tuple:
        """Возвращает (имя_веры, количество_последователей)."""
        if not self.beliefs:
            return (None, 0)
        dominant = max(self.beliefs.items(), key=lambda x: x[1].followers)
        return (dominant[0], dominant[1].followers)

    def narrate(self) -> List[str]:
        """Возвращает строки для лога."""
        lines = []
        for name, belief in self.beliefs.items():
            lines.append(f"    {name}: {belief.followers}")
        return lines

    def save_state(self):
        """Сохраняет состояние вер в файл."""
        state = {
            name: belief.to_dict() for name, belief in self.beliefs.items()
        }
        try:
            tmp = self.save_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.save_file)
            logger.debug("💾 Belief system сохранён")
        except Exception as e:
            logger.error(f"Ошибка сохранения belief system: {e}")

    def load_state(self):
        """Загружает состояние вер из файла."""
        if not os.path.exists(self.save_file):
            return
        try:
            with open(self.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for name, belief_data in data.items():
                if name in self.beliefs:
                    self.beliefs[name].followers = belief_data['followers']
                    self.beliefs[name].effects = belief_data['effects']
            logger.info(f"📖 Belief system загружен: {self.get_dominant_belief()}")
        except Exception as e:
            logger.error(f"Ошибка загрузки belief system: {e}")

    def reset(self):
        """Сбрасывает все веры (для отладки)."""
        self._init_beliefs()
        self.save_state()