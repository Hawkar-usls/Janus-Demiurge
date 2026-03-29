# janus_core/convergence_engine.py

import numpy as np
import random
import zlib
from collections import deque
from typing import Dict, List, Any, Optional


# ================================
# 📊 CONVERGENCE ENGINE
# ================================
class ConvergenceEngine:
    """
    Измеряет схлопывание пространства поиска.
    Даёт РЕАЛЬНЫЙ % прогресса.
    """

    def __init__(self, window: int = 100):
        self.history = deque(maxlen=window)
        self.initial_entropy = None

    def compute_entropy(self, values: List[float]) -> float:
        values = np.array(values)
        if len(values) == 0:
            return 0.0

        probs = values / (values.sum() + 1e-8)
        probs = probs[probs > 0]

        return float(-np.sum(probs * np.log(probs + 1e-8)))

    def update(self, scores: Dict[str, float]) -> Dict[str, float]:
        entropy = self.compute_entropy(list(scores.values()))

        if self.initial_entropy is None:
            self.initial_entropy = entropy if entropy > 0 else 1.0

        progress = 1.0 - (entropy / self.initial_entropy)
        progress = float(np.clip(progress, 0.0, 1.0))

        self.history.append(entropy)

        stability = 0.0
        if len(self.history) > 10:
            stability = 1.0 - min(1.0, np.std(self.history))

        return {
            "progress": progress,
            "entropy": entropy,
            "stability": stability
        }


# ================================
# 🧠 PARTIAL MEMORY
# ================================
class PartialSolutionMemory:
    """
    Хранит куски решений и умеет их склеивать
    """

    def __init__(self, max_size=200):
        self.fragments = deque(maxlen=max_size)

    def store(self, fragment: Any, score: float):
        self.fragments.append((fragment, score))

    def recombine(self):
        if len(self.fragments) < 2:
            return None

        a, b = random.sample(self.fragments, 2)

        return self._merge(a[0], b[0])

    def _merge(self, f1, f2):
        if isinstance(f1, dict) and isinstance(f2, dict):
            merged = {}
            for k in f1.keys():
                if k in f2:
                    merged[k] = (f1[k] + f2[k]) / 2
                else:
                    merged[k] = f1[k]
            for k in f2.keys():
                if k not in merged:
                    merged[k] = f2[k]
            return merged

        return random.choice([f1, f2])


# ================================
# ✅ VERIFIER (P-часть)
# ================================
class Verifier:
    """
    КЛЮЧЕВОЙ компонент — градиент реальности
    """

    def verify(self, solution: Any) -> float:
        """
        ДОЛЖЕН БЫТЬ РЕАЛЬНЫМ
        Сейчас — универсальный fallback
        """

        if solution is None:
            return 0.0

        # Пример: если это конфиг модели
        if isinstance(solution, dict):
            score = 0.0

            # lr в разумных пределах
            if "lr" in solution:
                lr = solution["lr"]
                score += max(0.0, 1.0 - abs(lr - 0.001) / 0.001)

            # temperature в разумных пределах
            if "temperature" in solution:
                temp = solution["temperature"]
                score += max(0.0, 1.0 - abs(temp - 1.0) / 1.0)

            # gain в разумных пределах
            if "gain" in solution:
                gain = solution["gain"]
                score += max(0.0, 1.0 - abs(gain - 1.0) / 1.0)

            # если ни одного параметра, даём 0.5
            if score == 0.0:
                return 0.5

            return max(0.0, min(1.0, score / 3.0))

        return 0.5


# ================================
# 📦 COMPRESSION (исправлена)
# ================================
def compression_score(solution: Any) -> float:
    s = str(solution).encode()
    comp = zlib.compress(s)

    ratio = len(comp) / (len(s) + 1)
    # Ограничиваем диапазон [0, 1]
    return max(0.0, min(1.0, 1.0 - ratio))


# ================================
# 🌌 SOLUTION FIELD
# ================================
class SolutionField:
    """
    Глобальная память лучших решений
    """

    def __init__(self):
        self.pool = []  # (solution, score)

    def add(self, solution, verify_score, compression, progress):
        total = (
            0.5 * verify_score +
            0.3 * compression +
            0.2 * progress
        )

        self.pool.append((solution, total))

        # ограничиваем размер
        self.pool = sorted(self.pool, key=lambda x: x[1], reverse=True)[:100]

    def best(self):
        return self.pool[0][0] if self.pool else None