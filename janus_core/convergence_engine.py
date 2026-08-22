# janus_core/convergence_engine.py

import random
import zlib
from typing import Any, Dict, List

import numpy as np

from spiral_evolution import PreservingWindow, fingerprint_payload


class ConvergenceEngine:
    """Measures the active frontier while preserving every older entropy sample."""

    def __init__(self, window: int = 100):
        self.history = PreservingWindow(window)
        self.initial_entropy = None
        self.spiral_turn = 0

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
        progress = float(np.clip(1.0 - (entropy / self.initial_entropy), 0.0, 1.0))
        self.history.append(entropy)
        stability = 0.0
        if len(self.history) > 10:
            stability = 1.0 - min(1.0, float(np.std(list(self.history))))
        turn = self.spiral_turn
        self.spiral_turn += 1
        return {
            "progress": progress,
            "entropy": entropy,
            "stability": stability,
            "spiral_turn": turn,
            "archived_entropy_samples": len(self.history.archive),
        }


class PartialSolutionMemory:
    """Active recombination window plus a lossless archive of older fragments."""

    def __init__(self, max_size=200):
        self.fragments = PreservingWindow(max_size)
        self.spiral_turn = 0

    def store(self, fragment: Any, score: float):
        record = {
            "turn": self.spiral_turn,
            "fragment": fragment,
            "score": score,
            "fingerprint": fingerprint_payload(fragment),
        }
        self.spiral_turn += 1
        self.fragments.append(record)

    def recombine(self):
        active = list(self.fragments)
        if len(active) < 2:
            return None
        a, b = random.sample(active, 2)
        return self._merge(a["fragment"], b["fragment"])

    def _merge(self, f1, f2):
        if isinstance(f1, dict) and isinstance(f2, dict):
            merged = {}
            for k in f1.keys():
                merged[k] = (f1[k] + f2[k]) / 2 if k in f2 else f1[k]
            for k in f2.keys():
                if k not in merged:
                    merged[k] = f2[k]
            return merged
        return random.choice([f1, f2])


class Verifier:
    """Reality-gradient fallback verifier. A score is not world truth by itself."""

    def verify(self, solution: Any) -> float:
        if solution is None:
            return 0.0
        if isinstance(solution, dict):
            score = 0.0
            if "lr" in solution:
                score += max(0.0, 1.0 - abs(solution["lr"] - 0.001) / 0.001)
            if "temperature" in solution:
                score += max(0.0, 1.0 - abs(solution["temperature"] - 1.0) / 1.0)
            if "gain" in solution:
                score += max(0.0, 1.0 - abs(solution["gain"] - 1.0) / 1.0)
            return 0.5 if score == 0.0 else max(0.0, min(1.0, score / 3.0))
        return 0.5


def compression_score(solution: Any) -> float:
    s = str(solution).encode()
    comp = zlib.compress(s)
    ratio = len(comp) / (len(s) + 1)
    return max(0.0, min(1.0, 1.0 - ratio))


class SolutionField:
    """Lossless solution lineage plus a bounded active frontier."""

    def __init__(self, frontier_size: int = 100):
        self.frontier_size = frontier_size
        self.lineage = []
        self.pool = []  # backwards-compatible active frontier
        self.spiral_turn = 0

    def add(self, solution, verify_score, compression, progress):
        total = 0.5 * verify_score + 0.3 * compression + 0.2 * progress
        record = {
            "turn": self.spiral_turn,
            "solution": solution,
            "score": total,
            "verify_score": verify_score,
            "compression": compression,
            "progress": progress,
            "fingerprint": fingerprint_payload(solution),
        }
        self.spiral_turn += 1
        self.lineage.append(record)
        self.pool.append((solution, total))
        self.pool = sorted(self.pool, key=lambda x: x[1], reverse=True)[:self.frontier_size]
        return record

    def best(self):
        return self.pool[0][0] if self.pool else None

    def lessons_below_frontier(self):
        active_fingerprints = {fingerprint_payload(solution) for solution, _ in self.pool}
        return [x for x in self.lineage if x["fingerprint"] not in active_fingerprints]
