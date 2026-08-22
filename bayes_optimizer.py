#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bayesian Optimizer with preserved attempt lineage.

Historical "tachyonic" acquisition remains project vocabulary/heuristics; it
is not a claim of physical future prediction. Valid points still feed skopt,
while rejected/invalid candidates are preserved as lessons instead of silently
vanishing.
"""

import json
import logging
import os
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from spiral_evolution import SpiralLedger

logger = logging.getLogger("JANUS.BAYES")

CONFIG = {
    'gain_range': (0.3, 2.0),
    'temp_range': (0.3, 2.0),
    'lr_range': (1e-5, 1e-2),
    'n_embd_options': [128, 256, 384, 512, 768],
    'n_head_options': [4, 8, 12, 16],
    'n_layer_options': [4, 6, 8, 10, 12],
    'n_initial_points': 5,
    'acq_func': 'EI',
    'log_file': 'bayes_log.json',
    'tachyonic_penalty': 0.1,
    'filter_37_enabled': True,
    'resonance_boost': 1.2
}

try:
    from config import digital_root, is_resonant
except ImportError:
    def digital_root(n: int) -> int:
        if n == 0:
            return 0
        return 1 + (n - 1) % 9

    def is_resonant(value: int) -> bool:
        return (value % 37 == 0) or (digital_root(value) == 3)

try:
    from skopt import Optimizer as SkoptOptimizer
    from skopt.space import Real, Categorical
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False
    logger.warning("⚠️ scikit-optimize не установлен, байесовская оптимизация недоступна")


class BayesianOptimizer:
    def __init__(self,
                 gain_range: Tuple[float, float] = CONFIG['gain_range'],
                 temp_range: Tuple[float, float] = CONFIG['temp_range'],
                 lr_range: Tuple[float, float] = CONFIG['lr_range'],
                 n_embd_options: List[int] = CONFIG['n_embd_options'],
                 n_head_options: List[int] = CONFIG['n_head_options'],
                 n_layer_options: List[int] = CONFIG['n_layer_options'],
                 n_initial_points: int = CONFIG['n_initial_points'],
                 acq_func: str = CONFIG['acq_func'],
                 log_file: str = CONFIG['log_file'],
                 tachyonic_penalty: float = CONFIG['tachyonic_penalty'],
                 filter_37_enabled: bool = CONFIG['filter_37_enabled']):
        self.gain_range = gain_range
        self.temp_range = temp_range
        self.lr_range = lr_range
        self.n_embd_options = n_embd_options
        self.n_head_options = n_head_options
        self.n_layer_options = n_layer_options
        self.acq_func = acq_func
        self.log_file = log_file
        stem, ext = os.path.splitext(log_file)
        self.attempt_log_file = f"{stem}_attempts{ext or '.json'}"
        self.tachyonic_penalty = tachyonic_penalty
        self.filter_37_enabled = filter_37_enabled

        self.history = self.load_history()
        self.attempt_history = self.load_attempt_history()
        self.spiral = SpiralLedger("JANUS_BAYES_OPTIMIZER")
        self.skopt = None
        if SKOPT_AVAILABLE:
            self.space = [
                Real(*gain_range, name='gain'),
                Real(*temp_range, name='temperature'),
                Real(*lr_range, name='lr'),
                Categorical(n_embd_options, name='n_embd'),
                Categorical(n_head_options, name='n_head'),
                Categorical(n_layer_options, name='n_layer')
            ]
            self.skopt = SkoptOptimizer(
                dimensions=self.space,
                base_estimator='GP',
                n_initial_points=n_initial_points,
                acq_func='EI'
            )
            if self.history:
                valid_history = [h for h in self.history if isinstance(h.get('score'), (int, float))]
                X = [[h['gain'], h['temperature'], h['lr'], h['n_embd'], h['n_head'], h['n_layer']]
                     for h in valid_history]
                y = [-h['score'] for h in valid_history]
                valid_X, valid_y = [], []
                for xi, yi in zip(X, y):
                    if (xi[3] in n_embd_options and xi[4] in n_head_options and xi[5] in n_layer_options):
                        valid_X.append(xi)
                        valid_y.append(yi)
                if valid_X:
                    try:
                        self.skopt.tell(valid_X, valid_y)
                    except Exception as exc:
                        logger.warning("Ошибка при инициализации байесовского оптимизатора: %s", exc)

    @staticmethod
    def _load_json_list(path: str) -> List[Dict[str, Any]]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    value = json.load(handle)
                return value if isinstance(value, list) else []
            except Exception as exc:
                logger.error("Ошибка загрузки истории %s: %s", path, exc)
        return []

    @staticmethod
    def _atomic_save(path: str, value: Any) -> None:
        tmp = path + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(value, handle, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as exc:
            logger.error("Ошибка сохранения истории %s: %s", path, exc)

    def load_history(self) -> List[Dict]:
        return self._load_json_list(self.log_file)

    def load_attempt_history(self) -> List[Dict]:
        return self._load_json_list(self.attempt_log_file)

    def save_history(self) -> None:
        self._atomic_save(self.log_file, self.history)

    def save_attempt_history(self) -> None:
        self._atomic_save(self.attempt_log_file, self.attempt_history)

    def ask(self, mood_acq: Optional[str] = None) -> Dict[str, Any]:
        if self.skopt is None:
            return self._random_config()
        x_next = self.skopt.ask()
        return {
            'gain': round(x_next[0], 3),
            'temperature': round(x_next[1], 3),
            'lr': round(x_next[2], 5),
            'n_embd': int(x_next[3]),
            'n_head': int(x_next[4]),
            'n_layer': int(x_next[5])
        }

    def ask_tachyonic(self, mood_acq: Optional[str] = None, resonance_penalty: float = None) -> Dict[str, Any]:
        """Historical heuristic acquisition; no physical future-prediction claim."""
        if self.skopt is None:
            return self._random_config()
        penalty = resonance_penalty if resonance_penalty is not None else self.tachyonic_penalty
        x_next = self.skopt.ask()
        dr_sum = sum(digital_root(abs(p)) for p in x_next if isinstance(p, (int, float)))
        if self.filter_37_enabled and (dr_sum % 9 != 3):
            for i, val in enumerate(x_next):
                if isinstance(val, (int, float)):
                    if i in (3, 4, 5):
                        categories = list(self.space[i].categories) if hasattr(self.space[i], 'categories') else []
                        resonant_options = [opt for opt in categories if is_resonant(opt)]
                        if resonant_options:
                            x_next[i] = min(resonant_options, key=lambda x: abs(x - val))
                    else:
                        low, high = self.space[i].low, self.space[i].high
                        shift = 0.01 * (high - low) * penalty
                        x_next[i] = max(low, min(high, x_next[i] + random.uniform(-shift, shift)))
        return {
            'gain': round(x_next[0], 3),
            'temperature': round(x_next[1], 3),
            'lr': round(x_next[2], 5),
            'n_embd': int(x_next[3]),
            'n_head': int(x_next[4]),
            'n_layer': int(x_next[5])
        }

    def _is_valid(self, config: Dict[str, Any]) -> bool:
        return (
            config.get('n_embd') in self.n_embd_options
            and config.get('n_head') in self.n_head_options
            and config.get('n_layer') in self.n_layer_options
        )

    def _record_attempt(self, config: Dict[str, Any], score: Optional[float], status: str, lesson: str) -> None:
        attempt = {
            "turn": self.spiral.next_turn,
            "timestamp": datetime.now().isoformat(),
            "config": dict(config),
            "score": score,
            "status": status,
            "lesson": lesson,
        }
        turn = self.spiral.ascend(
            state_before={"evaluated_points": len(self.history), "attempts": len(self.attempt_history)},
            candidate_state=attempt,
            active_state_after={"evaluated_points": len(self.history), "attempts": len(self.attempt_history) + 1},
            lessons=[lesson],
            constraints=[] if status == "ADMITTED_VALID_POINT" else [status],
            score_candidate=score,
            promoted=status == "ADMITTED_VALID_POINT",
            outcome="ASCENDED" if status == "ADMITTED_VALID_POINT" else "INTEGRATED_LESSON",
        )
        attempt["fingerprint"] = turn.fingerprint
        self.attempt_history.append(attempt)
        self.save_attempt_history()

    def tell(self, config: Dict[str, Any], score: float) -> None:
        if not self._is_valid(config):
            logger.debug("Байес: конфигурация %s вне допустимых диапазонов; сохраняем как урок", config)
            self._record_attempt(
                config,
                score,
                "REJECTED_INVALID_CONFIG",
                "Invalid optimizer candidate preserved; do not feed it to skopt without repair."
            )
            return

        entry = config.copy()
        entry['score'] = score
        entry['timestamp'] = datetime.now().isoformat()
        self.history.append(entry)
        self.save_history()
        self._record_attempt(
            config,
            score,
            "ADMITTED_VALID_POINT",
            "Valid evaluated candidate admitted while preserving optimizer ancestry."
        )
        if self.skopt is not None:
            X = [[config['gain'], config['temperature'], config['lr'],
                  config['n_embd'], config['n_head'], config['n_layer']]]
            try:
                self.skopt.tell(X, [-score])
            except Exception as exc:
                logger.warning("Ошибка при добавлении точки: %s", exc)
                self._record_attempt(
                    config,
                    score,
                    "SKOPT_TELL_FAILED",
                    f"skopt rejected/failed to ingest an otherwise valid point: {type(exc).__name__}."
                )

    def _random_config(self) -> Dict[str, Any]:
        return {
            'gain': round(random.uniform(*self.gain_range), 3),
            'temperature': round(random.uniform(*self.temp_range), 3),
            'lr': round(random.uniform(*self.lr_range), 5),
            'n_embd': random.choice(self.n_embd_options),
            'n_head': random.choice(self.n_head_options),
            'n_layer': random.choice(self.n_layer_options)
        }

    def get_best_config(self) -> Optional[Dict[str, Any]]:
        valid = [h for h in self.history if isinstance(h.get('score'), (int, float))]
        if not valid:
            return None
        best = max(valid, key=lambda x: x['score'])
        return {k: best[k] for k in ['gain', 'temperature', 'lr', 'n_embd', 'n_head', 'n_layer']}
