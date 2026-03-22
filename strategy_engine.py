#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRATEGY ENGINE — меняет поведение Януса в зависимости от состояния.
"""

import logging

logger = logging.getLogger("JANUS.STRATEGY")

class StrategyEngine:
    def adjust(self, self_model, regret):
        """
        На основе SelfModel и сожаления выбирает новый режим.
        """
        mode = self_model.identity["mode"]
        confidence = self_model.identity["confidence"]

        if regret > 0.2:
            mode = "explorer"
        elif confidence > 0.85:
            mode = "efficient"
        elif regret < 0.05:
            mode = "balanced"

        self_model.identity["mode"] = mode
        return mode