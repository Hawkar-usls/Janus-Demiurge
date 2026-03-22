"""
Детектор карманов (abuser pockets) — выявляет зацикливание метрик.
"""

import numpy as np
from collections import deque

class AbuserPocketDetector:
    def __init__(self, window: int = 20, std_threshold: float = 0.01):
        self.window = window
        self.std_threshold = std_threshold
        self.scores = deque(maxlen=window)
        self.losses = deque(maxlen=window)
        self.pockets = []  # список запомненных карманов

    def update(self, score: float, loss: float) -> bool:
        """
        Добавляет новые значения метрик.
        Возвращает True, если обнаружено зацикливание (карман).
        """
        self.scores.append(score)
        self.losses.append(loss)
        if len(self.scores) < self.window:
            return False
        score_std = np.std(self.scores)
        loss_std = np.std(self.losses)
        if score_std < self.std_threshold and loss_std < self.std_threshold:
            pocket = (tuple(self.scores), tuple(self.losses))
            if pocket not in self.pockets:
                self.pockets.append(pocket)
                return True
        return False