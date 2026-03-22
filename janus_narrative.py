#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS NARRATIVE — голос Демиурга, отражающий состояние мира.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("JANUS.NARRATIVE")

CONFIG = {
    'reflections': {
        "crisis": "Я чувствую кризис. Всё идёт не так.",
        "growth": "Я расту. Мои возможности расширяются.",
        "stability": "Всё стабильно. Но не застойно."
    }
}


class JanusNarrative:
    def generate(self, janus: Any, world_memory: Any) -> str:
        """Генерирует стандартное повествование о состоянии Януса."""
        return f"Янус: здоровье {janus.health}, очки {janus.max_best}, летальность {janus.lethal_count}"

    def reflect(self, state_analysis: str) -> str:
        """Возвращает размышление Януса о состоянии системы."""
        return CONFIG['reflections'].get(state_analysis, f"Янус анализирует: {state_analysis}")

    def speak(self, message: str) -> None:
        """Выводит голос Януса."""
        logger.info(f"🗣️ Янус говорит: {message}")

def narrate_beliefs(belief_system: Any) -> None:
    """Выводит информацию о доминирующей вере в мире."""
    if not belief_system or not hasattr(belief_system, 'beliefs') or not belief_system.beliefs:
        return
    dominant = max(belief_system.beliefs.values(), key=lambda b: b.followers)
    logger.info(f"""
🜏 НАРРАТИВ ВЕРЫ:
Доминирующая вера: {dominant.name}
Учение: {dominant.doctrine}
Последователей: {dominant.followers}
""")