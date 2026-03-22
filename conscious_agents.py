#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONSCIOUS AGENTS — агенты с внутренним голосом, мышлением и объяснениями.
"""

import random
import logging
from typing import List, Any, Dict

logger = logging.getLogger("JANUS.AGENTS")

CONFIG = {
    'curiosity_range': (0.5, 1.5),
    'fear_range': (0.5, 1.5),
    'ambition_range': (0.5, 1.5),
    'max_memory': 20,
    'ambition_growth_on_success': 1.05,
    'fear_growth_on_failure': 1.05,
    'curiosity_recovery_rate': 1.01,
    'max_curiosity': 2.0
}


class Thought:
    def __init__(self, text: str, importance: float = 1.0):
        self.text = text
        self.importance = importance


class ConsciousAgent:
    def __init__(self, base_agent: Any):
        self.base = base_agent          # оригинальный агент из JanusWorld
        self.thoughts: List[Thought] = []
        self.memory: List[str] = []

        # когнитивные параметры (уникальны для каждого агента)
        self.curiosity = random.uniform(*CONFIG['curiosity_range'])
        self.fear = random.uniform(*CONFIG['fear_range'])
        self.ambition = random.uniform(*CONFIG['ambition_range'])

    def think(self, world: Any) -> None:
        """Генерирует мысли на основе состояния мира и своего положения."""
        thoughts = []

        # Глобальная цель
        meaning_goal = getattr(world, 'meaning', None)
        if meaning_goal and hasattr(meaning_goal, 'current_goal'):
            goal = meaning_goal.current_goal
            if goal == "survival":
                thoughts.append(Thought("I must survive", 1.5))
            elif goal == "expansion":
                thoughts.append(Thought("I want to expand", 1.3))
            elif goal == "wealth":
                thoughts.append(Thought("I seek wealth", 1.4))
            elif goal == "knowledge":
                thoughts.append(Thought("I desire knowledge", 1.4))

        # Кризис
        if hasattr(world, 'economic_collapse') and world.economic_collapse.crisis:
            thoughts.append(Thought("Resources are scarce, I fear", 1.5))

        # Богатство агента
        if hasattr(self.base, 'gold') and self.base.gold > 100:
            thoughts.append(Thought("I am wealthy", 1.2))

        # Любопытство
        if random.random() < self.curiosity:
            thoughts.append(Thought("I want to explore", 1.0))

        self.thoughts = thoughts

    def decide(self) -> str:
        """Принимает решение на основе самых важных мыслей."""
        if not self.thoughts:
            return "idle"
        main = max(self.thoughts, key=lambda t: t.importance)
        text = main.text.lower()

        if "survive" in text or "fear" in text:
            return "defend"
        if "explore" in text:
            return "explore"
        if "wealth" in text or "gold" in text:
            return "trade"
        if "expand" in text:
            return "attack"
        if "knowledge" in text:
            return "research"
        return "idle"

    def explain(self) -> str:
        """Возвращает текстовое объяснение текущего действия."""
        if not self.thoughts:
            return "No thoughts"
        main = max(self.thoughts, key=lambda t: t.importance)
        return f"I act because: {main.text}"

    def learn(self, result: str) -> None:
        """Обучается на результате действия (success/failure)."""
        self.memory.append(result)
        if len(self.memory) > CONFIG['max_memory']:
            self.memory.pop(0)

        # Адаптация характера
        if result == "success":
            self.ambition *= CONFIG['ambition_growth_on_success']
        else:
            self.fear *= CONFIG['fear_growth_on_failure']

        # Любопытство со временем восстанавливается
        self.curiosity = min(CONFIG['max_curiosity'], self.curiosity * CONFIG['curiosity_recovery_rate'])