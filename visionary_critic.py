#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VISIONARY CRITIC — анализирует результаты генерации и даёт рекомендации.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("JANUS.CRITIC")

CONFIG = {
    'quality_threshold_low': 0.6,
    'quality_threshold_moderate': 0.75,
    'gen_time_threshold_slow': 6.0,
    'gen_time_threshold_overkill': 4.0,
    'perfect_quality': 0.85,
    'perfect_time': 4.0
}


class VisionaryCritic:
    def __init__(self):
        pass

    def analyze(self, prompt: str, quality: float, steps: int, gen_time: float) -> Dict[str, Any]:
        """
        Анализирует результат генерации.
        Возвращает словарь с полями 'status' и опционально 'issues', 'suggestions'.
        """
        issues = []
        suggestions = []

        if quality < CONFIG['quality_threshold_low']:
            issues.append("low_quality")
            suggestions.append("increase detail, sharper, more defined")
        elif quality < CONFIG['quality_threshold_moderate']:
            issues.append("moderate_quality")
            suggestions.append("add more contrast, improve composition")

        if gen_time > CONFIG['gen_time_threshold_slow']:
            issues.append("too_slow")
            suggestions.append("reduce steps, simplify composition")

        if quality > CONFIG['perfect_quality'] and gen_time > CONFIG['gen_time_threshold_overkill']:
            issues.append("overkill")
            suggestions.append("same scene but simpler, fewer details")

        if quality > CONFIG['perfect_quality'] and gen_time < CONFIG['perfect_time']:
            return {"status": "perfect", "suggestions": []}

        return {"status": "improvable", "issues": issues, "suggestions": suggestions}