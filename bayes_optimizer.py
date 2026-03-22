#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bayesian Optimizer — байесовская оптимизация гиперпараметров.
Добавлена тахионная acquisition с учётом фильтра 37.
"""

import os
import json
import random
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("JANUS.BAYES")

CONFIG = {
    'gain_range': (0.3, 2.0),
    'temp_range': (0.3, 2.0),
    'lr_range': (1e-5, 1e-2),
    'n_embd_options': [128, 256, 384, 512, 768],
    'n_head_options': [4, 8, 12, 16],
    'n_layer_options': [4, 6, 8, 10, 12],
    'n_initial_points': 5,
    'acq_func': 'EI',                     # стандартная acquisition для SkoptOptimizer
    'log_file': 'bayes_log.json',
    'tachyonic_penalty': 0.1,            # штраф за нерезонансную конфигурацию
    'filter_37_enabled': True,
    'resonance_boost': 1.2
}

# Пытаемся импортировать функции фильтра 37 из конфига (если они там есть)
try:
    from config import digital_root, is_resonant
except ImportError:
    # fallback: простейшие реализации
    def digital_root(n: int) -> int:
        if n == 0:
            return 0
        return 1 + (n - 1) % 9

    def is_resonant(value: int) -> bool:
        return (value % 37 == 0) or (digital_root(value) == 3)

try:
    from skopt import Optimizer as SkoptOptimizer
    from skopt.space import Real, Integer, Categorical
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
                 acq_func: str = CONFIG['acq_func'],        # стандартная acquisition
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
        self.tachyonic_penalty = tachyonic_penalty
        self.filter_37_enabled = filter_37_enabled

        self.history = self.load_history()
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
            # Всегда используем стандартную acquisition для базового оптимизатора
            self.skopt = SkoptOptimizer(
                dimensions=self.space,
                base_estimator='GP',
                n_initial_points=n_initial_points,
                acq_func='EI'   # принудительно ставим 'EI'
            )
            if self.history:
                X = [[h['gain'], h['temperature'], h['lr'],
                      h['n_embd'], h['n_head'], h['n_layer']] for h in self.history]
                y = [-h['score'] for h in self.history]
                # Фильтруем только корректные точки
                valid_X, valid_y = [], []
                for xi, yi in zip(X, y):
                    if (xi[3] in n_embd_options and
                        xi[4] in n_head_options and
                        xi[5] in n_layer_options):
                        valid_X.append(xi)
                        valid_y.append(yi)
                if valid_X:
                    try:
                        self.skopt.tell(valid_X, valid_y)
                    except Exception as e:
                        logger.warning(f"Ошибка при инициализации байесовского оптимизатора: {e}")

    def load_history(self) -> List[Dict]:
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки истории: {e}")
        return []

    def save_history(self) -> None:
        tmp = self.log_file + ".tmp"
        try:
            with open(tmp, 'w') as f:
                json.dump(self.history, f, indent=2)
            os.replace(tmp, self.log_file)
        except Exception as e:
            logger.error(f"Ошибка сохранения истории: {e}")

    def ask(self, mood_acq: Optional[str] = None) -> Dict[str, Any]:
        """Стандартный метод ask без тахионной коррекции."""
        if self.skopt is None:
            return self._random_config()
        x_next = self.skopt.ask()
        config = {
            'gain': round(x_next[0], 3),
            'temperature': round(x_next[1], 3),
            'lr': round(x_next[2], 5),
            'n_embd': int(x_next[3]),
            'n_head': int(x_next[4]),
            'n_layer': int(x_next[5])
        }
        return config

    def ask_tachyonic(self, mood_acq: Optional[str] = None, resonance_penalty: float = None) -> Dict[str, Any]:
        """
        Возвращает конфигурацию с учётом тахионной коррекции.
        resonance_penalty – если не указано, используется self.tachyonic_penalty.
        """
        if self.skopt is None:
            return self._random_config()

        penalty = resonance_penalty if resonance_penalty is not None else self.tachyonic_penalty

        # Получаем следующую точку от стандартного оптимизатора
        x_next = self.skopt.ask()
        # Применяем штраф на основе резонанса гиперпараметров
        dr_sum = sum(digital_root(abs(p)) for p in x_next if isinstance(p, (int, float)))
        # Если суммарный цифровой корень не кратен 3, применяем штраф (сдвигаем точку)
        if self.filter_37_enabled and (dr_sum % 9 != 3):
            # Смещаем каждый параметр в сторону ближайшего резонансного значения
            for i, val in enumerate(x_next):
                if isinstance(val, (int, float)):
                    # Для категориальных параметров (n_embd, n_head, n_layer) пытаемся найти ближайший резонансный
                    if i in (3, 4, 5):  # индексы категориальных
                        options = [self.space[i].categories] if hasattr(self.space[i], 'categories') else None
                        if options:
                            # Находим ближайшее резонансное значение из списка допустимых
                            resonant_options = [opt for opt in options if is_resonant(opt)]
                            if resonant_options:
                                closest = min(resonant_options, key=lambda x: abs(x - val))
                                x_next[i] = closest
                    else:
                        # Для непрерывных параметров: небольшой сдвиг
                        low, high = self.space[i].low, self.space[i].high
                        shift = 0.01 * (high - low) * penalty
                        x_next[i] += random.uniform(-shift, shift)
                        x_next[i] = max(low, min(high, x_next[i]))

        config = {
            'gain': round(x_next[0], 3),
            'temperature': round(x_next[1], 3),
            'lr': round(x_next[2], 5),
            'n_embd': int(x_next[3]),
            'n_head': int(x_next[4]),
            'n_layer': int(x_next[5])
        }
        return config

    def tell(self, config: Dict[str, Any], score: float) -> None:
        # Проверка допустимости
        if (config['n_embd'] not in self.n_embd_options or
            config['n_head'] not in self.n_head_options or
            config['n_layer'] not in self.n_layer_options):
            logger.debug(f"Байес: конфигурация {config} вне допустимых диапазонов, пропускаем")
            return

        entry = config.copy()
        entry['score'] = score
        entry['timestamp'] = datetime.now().isoformat()
        self.history.append(entry)
        self.save_history()
        if self.skopt is not None:
            X = [[config['gain'], config['temperature'], config['lr'],
                  config['n_embd'], config['n_head'], config['n_layer']]]
            try:
                self.skopt.tell(X, [-score])
            except Exception as e:
                logger.warning(f"Ошибка при добавлении точки: {e}")

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
        if not self.history:
            return None
        best = max(self.history, key=lambda x: x.get('score', -float('inf')))
        return {k: best[k] for k in ['gain', 'temperature', 'lr', 'n_embd', 'n_head', 'n_layer']}