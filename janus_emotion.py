#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS EMOTION — эмоциональный слой Януса.
"""

CONFIG = {
    'trust_inc_on_small_error': 0.01,
    'trust_dec_factor_on_large_error': 0.99,
    'curiosity_recovery': 1.001,
    'max_curiosity': 2.0,
    'error_threshold': 0.1
}


class JanusEmotion:
    def __init__(self):
        self.trust = 1.0      # доверие к своим прогнозам
        self.curiosity = 1.0   # любопытство
        self.regret = 0.0      # сожаление

    def update(self, prediction: float, outcome: float) -> None:
        """Обновляет эмоции на основе ошибки предсказания."""
        error = abs(prediction - outcome)
        self.regret = error
        if error < CONFIG['error_threshold']:
            self.trust += CONFIG['trust_inc_on_small_error']
        else:
            self.trust *= CONFIG['trust_dec_factor_on_large_error']
        self.curiosity = min(CONFIG['max_curiosity'], self.curiosity * CONFIG['curiosity_recovery'])