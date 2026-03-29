#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEMORY — Мудрость и Уроки Януса
Хранит всё, что было хорошего, и учится на том, что было сложно.
"""

import csv
import json
import random
import numpy as np
import os
import time
import math
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from collections import deque
from config import RAW_LOGS_DIR

# Импортируем функции фильтра 37 из обновлённого конфига (если они там есть)
try:
    from config import digital_root, is_resonant, filter_hyperparams, N_EMBD_OPTIONS_RESONANT
except ImportError:
    # fallback: простейшие реализации
    def digital_root(n: int) -> int:
        if n == 0:
            return 0
        return 1 + (n - 1) % 9

    def is_resonant(value: int) -> bool:
        return (value % 37 == 0) or (digital_root(value) == 3)

    def filter_hyperparams(config: dict) -> float:
        return 1.0

    N_EMBD_OPTIONS_RESONANT = [128, 256, 384, 512, 768]  # исходные

logger = logging.getLogger("JANUS")

CONFIG = {
    'csv_path': os.path.join(RAW_LOGS_DIR, "wisdom_landscape.csv"),
    'best_config_path': os.path.join(RAW_LOGS_DIR, "best_config.json"),
    'lessons_stats_path': os.path.join(RAW_LOGS_DIR, "lessons_stats.json"),
    'dreams_path': os.path.join(RAW_LOGS_DIR, "dreams.json"),
    'elite_size': 30,
    'mutation_rate': 0.15,
    'jump_prob': 0.1,
    'metrics_weight': 0.3,
    'metric_keys': ['gpu_load', 'gpu_temp', 'cpu_load', 'cache_ratio'],
    'param_ranges': {
        'gain': (0.3, 2.0),
        'temperature': (0.3, 2.0),
        'lr': (1e-5, 1e-2),
        'n_embd': [128, 256, 384, 512, 768],
        'n_head': [4, 8, 12, 16],
        'n_layer': [4, 6, 8, 10, 12]
    },
    'norm_factors': {
        'lr': 1e-2,
        'gain': 2.0 - 0.3,
        'temperature': 2.0 - 0.3,
        'n_embd': 768 - 128,
        'n_head': 16 - 4,
        'n_layer': 12 - 4
    },
    'metric_norm_factors': {
        'gpu_load': 100.0,
        'gpu_temp': 100.0,
        'cpu_load': 100.0,
        'cache_ratio': 2.0
    },
    'oxytocin_decay': 0.99,
    'protection_radius': 0.15,
    'protection_growth': 0.05,
    'miracle_prob': 0.1,
    'exploit_bias': 0.7,
    'G': 0.1,
    # Новые параметры
    'min_corr_samples': 10,
    'meta_goal': 'APPROXIMATE_P_NP',
    'meta_bonus_simplicity': 0.1,
    'meta_bonus_stability': 0.1,
    'strategy_update_rate': 0.1,
    'strategy_exploration_decay': 0.9,
    'strategy_stability_inc': 0.1,
    'strategy_exploration_inc': 0.1,
    'predict_threshold': -1.0,
    # Параметры для фильтра 37
    'resonant_n_embd': [111, 222, 333, 444, 555, 666, 777, 888, 999],  # цифровой корень 3
    'filter_37_weight': 0.8,
    'resonance_boost': 1.2,
    'resonant_choice_prob': 0.7,
    # Метрики сложности NP-задач
    'complexity_trend_window': 50,        # окно для тренда
    'convergence_threshold': 0.05,        # порог стабильности для конвергенции
    # НОВОЕ: адаптивное сужение диапазонов
    'shrink_enabled': True,               # включить сужение
    'shrink_factor_start': 0.5,           # начальный коэффициент сужения (новый диапазон = best ± factor * половина_текущего)
    'shrink_factor_min': 0.1,             # минимальный коэффициент сужения
    'shrink_decay': 0.9,                  # уменьшение фактора после каждого рекорда
    'shrink_min_width': {                 # минимальная ширина диапазона для каждого параметра
        'lr': 1e-6,
        'gain': 0.05,
        'temperature': 0.05,
        'n_embd': 64,                     # для дискретных пока не используется
        'n_head': 2,
        'n_layer': 2
    }
}


class EvolutionaryMemory:
    """
    Сердце памяти Януса. Здесь хранятся все уроки, радости и надежды.
    """
    # Для обратной совместимости
    METRICS_WEIGHT = CONFIG['metrics_weight']
    METRIC_KEYS = CONFIG['metric_keys']

    def __init__(self, registry_path: Optional[str] = None, tachyon=None,
                 elite_size: int = None, mutation_rate: float = None):
        self.csv_path = CONFIG['csv_path']
        self.best_config_path = CONFIG['best_config_path']
        self.lessons_stats_path = CONFIG['lessons_stats_path']
        self.dreams_path = CONFIG['dreams_path']

        self.history: List[Dict[str, Any]] = []
        self.best_config: Optional[Dict[str, Any]] = None
        self.sensitivity = {param: {'up': [], 'down': []} for param in CONFIG['param_ranges'] if isinstance(CONFIG['param_ranges'][param], tuple)}

        self.elite_size = elite_size if elite_size is not None else CONFIG['elite_size']
        self.mutation_rate = mutation_rate if mutation_rate is not None else CONFIG['mutation_rate']
        self.jump_prob = CONFIG['jump_prob']

        self.lessons_stats = {param: {'count': 0, 'values': []} for param in CONFIG['param_ranges']}
        self.total_lessons = 0
        self.total_growth = 0

        self.G = CONFIG['G']
        self.light_beacons = []
        self.space_curvature = 1.0

        self.mode = 0
        self.exploit_bias = CONFIG['exploit_bias']
        self.hope_score = -float('inf')
        self.hope_mode = 0
        self.hope_config = None

        self.oxytocin = 1.0
        self.oxytocin_decay = CONFIG['oxytocin_decay']
        self.last_parents = None

        self.protective_field = None
        self.protection_radius = CONFIG['protection_radius']
        self.protection_growth = CONFIG['protection_growth']
        self.miracle_prob = CONFIG['miracle_prob']

        self.registry_path = registry_path
        self.tachyon = tachyon  # для предсказаний

        # Новые поля
        self.strategy = {
            "exploration": 0.5,
            "risk": 0.5,
            "stability": 0.5
        }
        self.decision_log: List[Dict[str, Any]] = []
        self.meta_goal = CONFIG['meta_goal']

        # Дополнительные поля для фильтра 37 и детектора
        self.resonance_history: List[bool] = []   # флаги резонанса для последних циклов
        self.pocket_configs: List[Dict] = []      # конфигурации, попавшие в карман

        # Метрики сложности NP-задач
        self.first_success_cycle: Optional[int] = None
        self.first_success_time: Optional[float] = None
        self.convergence_cycle: Optional[int] = None
        self.complexity_trend: List[float] = []   # история сложности решённых задач
        self.convergence_steps = 0                # сколько циклов стабильности

        # НОВОЕ: адаптивное сужение диапазонов
        self.active_ranges = self._copy_ranges(CONFIG['param_ranges'])
        self.shrink_factor = CONFIG['shrink_factor_start']
        self.record_count = 0                     # счётчик рекордов

        # НОВОЕ: память плохих конфигураций
        self.bad_configs = deque(maxlen=1000)     # хранилище неудачных конфигураций

        self._load_best_config()
        self._load_history_from_csv()
        self._load_lessons_stats()
        self._load_light_beacons()
        self._load_metrics()                      # загрузка метрик сложности

    def _copy_ranges(self, ranges):
        """Глубокое копирование словаря диапазонов."""
        new = {}
        for k, v in ranges.items():
            if isinstance(v, tuple):
                new[k] = v
            else:
                new[k] = v[:]  # копия списка
        return new

    def _shrink_ranges(self, best_config: Dict[str, Any]):
        """
        Сужает активные диапазоны вокруг лучшей конфигурации.
        """
        if not CONFIG['shrink_enabled']:
            return
        self.record_count += 1
        # Обновляем фактор сужения
        self.shrink_factor = max(CONFIG['shrink_factor_min'],
                                 self.shrink_factor * CONFIG['shrink_decay'])

        for param, best_val in best_config.items():
            if param not in self.active_ranges:
                continue
            curr_range = self.active_ranges[param]
            if isinstance(curr_range, tuple):
                low, high = curr_range
                half_width = (high - low) / 2.0
                new_half = half_width * self.shrink_factor
                new_low = max(CONFIG['param_ranges'][param][0], best_val - new_half)
                new_high = min(CONFIG['param_ranges'][param][1], best_val + new_half)
                # Обеспечиваем минимальную ширину
                min_width = CONFIG['shrink_min_width'].get(param, 1e-6)
                if new_high - new_low < min_width:
                    new_low = best_val - min_width/2
                    new_high = best_val + min_width/2
                    new_low = max(CONFIG['param_ranges'][param][0], new_low)
                    new_high = min(CONFIG['param_ranges'][param][1], new_high)
                self.active_ranges[param] = (new_low, new_high)
                logger.info(f"📏 Адаптивное сужение {param}: [{low:.3e}, {high:.3e}] -> [{new_low:.3e}, {new_high:.3e}] (factor={self.shrink_factor:.2f})")
            elif isinstance(curr_range, list):
                # Для дискретных параметров: сужаем список, оставляя значения в пределах ± шага от best
                if param in ('n_embd', 'n_head', 'n_layer'):
                    try:
                        idx = curr_range.index(best_val)
                    except ValueError:
                        continue
                    # Оставляем 3 значения вокруг (если возможно)
                    new_list = curr_range[max(0, idx-1):min(len(curr_range), idx+2)]
                    if len(new_list) > 1:
                        self.active_ranges[param] = new_list
                        logger.info(f"📏 Адаптивное сужение {param}: {curr_range} -> {new_list} (best={best_val})")
                # остальные оставляем как есть

    # ---------- Загрузка/сохранение ----------
    def _load_best_config(self) -> None:
        if os.path.exists(self.best_config_path):
            try:
                with open(self.best_config_path, 'r', encoding='utf-8') as f:
                    self.best_config = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Ошибка загрузки best_config: {e}")

    def _load_history_from_csv(self) -> None:
        if not os.path.exists(self.csv_path):
            return
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parsed = {}
                    for k, v in row.items():
                        try:
                            parsed[k] = float(v)
                        except (ValueError, TypeError):
                            if k == 'score':
                                parsed[k] = -float('inf')
                            else:
                                parsed[k] = v
                    self.history.append(parsed)
            logger.info(f"\U0001F9E0 Память восстановлена: загружено {len(self.history)} уроков прошлого.")
        except Exception as e:
            logger.error(f"\u26A0\uFE0F Ошибка чтения истории: {e}", exc_info=True)

    def _load_lessons_stats(self) -> None:
        if os.path.exists(self.lessons_stats_path):
            try:
                with open(self.lessons_stats_path, 'r') as f:
                    data = json.load(f)
                    self.lessons_stats = data.get('stats', self.lessons_stats)
                    self.total_lessons = data.get('total_lessons', 0)
                    self.total_growth = data.get('total_growth', 0)
                logger.info(f"\U0001F4DA Загружена мудрость: {self.total_lessons} уроков, {self.total_growth} успехов.")
            except Exception as e:
                logger.error(f"Ошибка загрузки lessons_stats: {e}")

    def _load_light_beacons(self) -> None:
        if self.best_config and 'id' in self.best_config:
            self.light_beacons.append(self.best_config['id'])

    def _load_metrics(self):
        """Загружает метрики сложности из файла, если есть."""
        metrics_path = os.path.join(RAW_LOGS_DIR, "np_metrics.json")
        if os.path.exists(metrics_path):
            try:
                with open(metrics_path, 'r') as f:
                    data = json.load(f)
                self.first_success_cycle = data.get('first_success_cycle')
                self.first_success_time = data.get('first_success_time')
                self.convergence_cycle = data.get('convergence_cycle')
                self.complexity_trend = data.get('complexity_trend', [])
                self.convergence_steps = data.get('convergence_steps', 0)
                logger.info("📈 Метрики сложности NP-задач загружены.")
            except Exception as e:
                logger.warning(f"Не удалось загрузить метрики NP: {e}")

    def _save_metrics(self):
        """Сохраняет метрики сложности в файл."""
        metrics_path = os.path.join(RAW_LOGS_DIR, "np_metrics.json")
        data = {
            'first_success_cycle': self.first_success_cycle,
            'first_success_time': self.first_success_time,
            'convergence_cycle': self.convergence_cycle,
            'complexity_trend': self.complexity_trend,
            'convergence_steps': self.convergence_steps
        }
        try:
            with open(metrics_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик NP: {e}")

    def save_lessons_stats(self) -> None:
        try:
            with open(self.lessons_stats_path, 'w') as f:
                json.dump({
                    'stats': self.lessons_stats,
                    'total_lessons': self.total_lessons,
                    'total_growth': self.total_growth
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения lessons_stats: {e}")

    # ---------- Методы для работы с уроками и плохими конфигурациями ----------
    def register_lesson(self, config: Dict[str, Any], penalty: bool = False) -> None:
        """
        Регистрирует конфигурацию как урок.
        Если penalty=True, то запоминает как плохую (чтобы избегать в будущем).
        """
        if penalty:
            self.bad_configs.append(config)
            if len(self.bad_configs) > 1000:
                self.bad_configs.pop(0)
            logger.info("💀 Запомнена плохая конфигурация, чтобы избежать в будущем")
        else:
            self.total_lessons += 1
            for param, value in config.items():
                if param in self.lessons_stats and isinstance(value, (int, float)):
                    self.lessons_stats[param]['count'] += 1
                    self.lessons_stats[param]['values'].append(value)
                    if len(self.lessons_stats[param]['values']) > 100:
                        self.lessons_stats[param]['values'] = self.lessons_stats[param]['values'][-100:]
            self.save_lessons_stats()
            logger.info("\U0001F4DA Янус извлёк урок из сложного опыта. Мудрость растёт.")

    def register_growth(self, config: Dict[str, Any]) -> None:
        self.total_growth += 1

    def is_bad_config(self, config: Dict[str, Any], threshold: float = 0.05) -> bool:
        """Проверяет, не является ли конфигурация заведомо плохой."""
        for bad in self.bad_configs:
            if self._config_distance(config, bad) < threshold:
                return True
        return False

    def _config_distance(self, c1: Dict, c2: Dict) -> float:
        """Евклидово расстояние между двумя конфигурациями (нормированное)."""
        keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        diff = 0.0
        for k in keys:
            if k in c1 and k in c2:
                v1 = c1[k]
                v2 = c2[k]
                # нормализация
                if k == 'lr':
                    v1 = np.log10(v1 + 1e-8)
                    v2 = np.log10(v2 + 1e-8)
                elif k in ['n_embd', 'n_head', 'n_layer']:
                    v1 = v1 / 100.0
                    v2 = v2 / 100.0
                diff += (v1 - v2) ** 2
        return np.sqrt(diff)

    # ---------- Метрики сложности ----------
    def update_complexity_metrics(self, cycle: int, difficulty: float, solved: bool):
        """Обновляет метрики сложности на основе решения NP-задачи."""
        if solved:
            # Первый успех
            if self.first_success_cycle is None:
                self.first_success_cycle = cycle
                self.first_success_time = time.time()
                logger.info(f"🏆 ПЕРВЫЙ УСПЕХ в решении NP-задачи на цикле {cycle} (сложность {difficulty:.2f})")

            # Тренд сложности
            self.complexity_trend.append(difficulty)
            if len(self.complexity_trend) > CONFIG['complexity_trend_window']:
                self.complexity_trend.pop(0)

            # Сброс счётчика стабильности при успехе
            self.convergence_steps = 0

        else:
            # Неудача увеличивает счётчик стабильности (если есть уже успех)
            if self.first_success_cycle is not None:
                self.convergence_steps += 1
                if self.convergence_steps >= CONFIG['complexity_trend_window'] and self.convergence_cycle is None:
                    self.convergence_cycle = cycle
                    logger.info(f"🎯 Достигнута конвергенция на цикле {cycle} (стабильность {self.convergence_steps} циклов)")

        self._save_metrics()

    def update_scaling_metrics(self, scaling_exponent: float, series_results: list) -> None:
        """Обновляет метрики масштабирования сложности."""
        if scaling_exponent is not None:
            scaling_path = os.path.join(RAW_LOGS_DIR, "np_scaling_metrics.json")
            try:
                with open(scaling_path, 'r') as f:
                    data = json.load(f)
            except:
                data = {"history": []}
            data["history"].append({
                "timestamp": datetime.now().isoformat(),
                "scaling_exponent": scaling_exponent,
                "series": series_results
            })
            with open(scaling_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"📈 Обновлены метрики масштабирования: exponent={scaling_exponent:.3f}")

    # ---------- Причинное ядро ----------
    def estimate_param_importance(self) -> Dict[str, float]:
        """Оценивает, какие параметры реально влияют на score."""
        if len(self.history) < CONFIG['min_corr_samples']:
            return {}

        importances = {}
        for param, ranges in CONFIG['param_ranges'].items():
            values = []
            scores = []
            for h in self.history:
                if param in h and isinstance(h.get('score'), (int, float)) and h['score'] > -float('inf'):
                    val = h[param]
                    if isinstance(ranges, tuple):
                        low, high = ranges
                        if high - low > 0:
                            val_norm = (val - low) / (high - low)
                        else:
                            val_norm = 0.5
                    else:
                        val_norm = ranges.index(val) / max(1, len(ranges)-1) if val in ranges else 0.5
                    values.append(val_norm)
                    scores.append(h['score'])
            if len(values) >= CONFIG['min_corr_samples']:
                corr = np.corrcoef(values, scores)[0, 1]
                importances[param] = 0 if np.isnan(corr) else corr
        return importances

    # ---------- Интеграция с Tachyon ----------
    def predict_future_score(self, config: Dict[str, Any]) -> float:
        """Прогнозирует будущее качество конфигурации через Tachyon."""
        if self.tachyon is None:
            return 0.0
        try:
            if hasattr(self.tachyon, 'predict_outcome'):
                features = {
                    'event_type': 'CONFIG',
                    'importance': 1.0,
                    'prompt_len': 0,
                    'steps': 0,
                    'seed_mod': 0,
                    'cpu': 0,
                    'ram': 0,
                    'gpu': 0,
                    'style': 'default'
                }
                pred = self.tachyon.predict_outcome(features)
                if pred:
                    return pred.get('score', 0.0)
            return 0.0
        except Exception as e:
            logger.debug(f"Ошибка предсказания Tachyon: {e}")
            return 0.0

    # ---------- Мета-выравнивание ----------
    def _meta_alignment_bonus(self, config: Dict[str, Any]) -> float:
        """Бонус за соответствие мета-цели."""
        if self.meta_goal == "APPROXIMATE_P_NP":
            bonus = 0.0
            if config.get('n_layer', 0) < 8:
                bonus += CONFIG['meta_bonus_simplicity']
            if config.get('lr', 0) < 0.001:
                bonus += CONFIG['meta_bonus_stability']
            return bonus
        return 0.0

    # ---------- Стратегия ----------
    def update_strategy(self, score: float) -> None:
        """Обновляет параметры стратегии на основе успеха."""
        if score > self.hope_score:
            self.strategy["exploration"] *= CONFIG['strategy_exploration_decay']
            self.strategy["stability"] += CONFIG['strategy_stability_inc']
        else:
            self.strategy["exploration"] += CONFIG['strategy_exploration_inc']
        self.strategy["exploration"] = max(0.1, min(0.9, self.strategy["exploration"]))
        self.strategy["stability"] = max(0.1, min(0.9, self.strategy["stability"]))
        if self.hope_score > -float('inf') and score > -float('inf'):
            diff = self.hope_score - score
            self.strategy["risk"] = min(0.9, max(0.1, diff / 2.0))

    # ---------- Гравитационные методы ----------
    def _gravitational_distance(self, p1: Dict, p2: Dict) -> float:
        coord_keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        vec1, vec2 = [], []
        for k in coord_keys:
            if k in p1 and k in p2:
                v1, v2 = p1[k], p2[k]
                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    norm = CONFIG['norm_factors'].get(k, 1.0)
                    if norm == 0:
                        norm = 1.0
                    vec1.append(v1 / norm)
                    vec2.append(v2 / norm)
                else:
                    vec1.append(0.0 if v1 == v2 else 1.0)
                    vec2.append(0.0)
        if len(vec1) == 0:
            return 1.0
        return np.linalg.norm(np.array(vec1) - np.array(vec2))

    def _metrics_distance(self, m1: Dict, m2: Dict) -> float:
        vec1, vec2 = [], []
        for key in CONFIG['metric_keys']:
            if key in m1 and key in m2:
                v1 = m1[key]
                v2 = m2[key]
                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    maxv = CONFIG['metric_norm_factors'].get(key, 1.0)
                    vec1.append(v1 / maxv)
                    vec2.append(v2 / maxv)
        if len(vec1) == 0:
            return 0.0
        return np.linalg.norm(np.array(vec1) - np.array(vec2))

    def _get_elite(self) -> List[Dict]:
        if not self.history:
            return []
        valid = [h for h in self.history if isinstance(h.get('score'), (int, float)) and h['score'] > -float('inf')]
        sorted_hist = sorted(valid, key=lambda x: x.get('score', -float('inf')), reverse=True)
        return sorted_hist[:min(self.elite_size, len(sorted_hist))]

    def _select_parents(self, elite: List[Dict], current_metrics: Optional[Dict] = None) -> Tuple[Dict, Dict]:
        if len(elite) < 2:
            return random.sample(self.history, 2) if len(self.history) >= 2 else (elite[0], elite[0])
        idx1 = random.randint(0, len(elite)-1)
        parent1 = elite[idx1]
        weights = []
        for i, p2 in enumerate(elite):
            if i == idx1:
                weights.append(0.0)
            else:
                dist_params = self._gravitational_distance(parent1, p2)
                dist_metrics = 0.0
                if current_metrics is not None:
                    dist_metrics = self._metrics_distance(p2, current_metrics)
                combined_dist = dist_params + CONFIG['metrics_weight'] * dist_metrics
                weight = 1.0 / (combined_dist + 1e-9)
                weight *= (1.0 + self.oxytocin * 0.5)
                weights.append(weight)
        total = sum(weights)
        if total == 0:
            probs = [1.0/(len(elite)-1) if i != idx1 else 0.0 for i in range(len(elite))]
        else:
            probs = [w/total for w in weights]
        idx2 = np.random.choice(len(elite), p=probs)
        parent2 = elite[idx2]
        return parent1, parent2

    def _crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        child = {}
        for param, ranges in CONFIG['param_ranges'].items():
            if param in parent1 and param in parent2:
                if isinstance(ranges, tuple):
                    low = min(parent1[param], parent2[param])
                    high = max(parent1[param], parent2[param])
                    child[param] = random.uniform(low, high)
                else:
                    child[param] = random.choice([parent1[param], parent2[param]])
            else:
                child[param] = self._random_param(param)
        child['n_embd'] = int(round(child['n_embd']))
        child['n_head'] = int(round(child['n_head']))
        child['n_layer'] = int(round(child['n_layer']))
        if child['n_embd'] % child['n_head'] != 0:
            for nh in sorted(CONFIG['param_ranges']['n_head']):
                if child['n_embd'] % nh == 0:
                    child['n_head'] = nh
                    break
            else:
                child['n_head'] = 8
        return child

    # ---------- Фильтр 37: резонансные методы ----------
    def _is_resonant_config(self, config: Dict[str, Any]) -> float:
        param_keys = ['n_embd', 'n_head', 'n_layer', 'lr', 'gain', 'temperature']
        resonant_count = 0
        total_checked = 0
        for key in param_keys:
            if key in config:
                val = config[key]
                if isinstance(val, (int, float)):
                    int_val = int(abs(val))
                    if is_resonant(int_val):
                        resonant_count += 1
                    total_checked += 1
        if total_checked == 0:
            return 0.5
        return resonant_count / total_checked

    def _select_resonant_option(self, options: List[int]) -> int:
        if random.random() < CONFIG['resonant_choice_prob']:
            resonant_opts = [o for o in CONFIG['resonant_n_embd'] if o in options]
            if resonant_opts:
                return random.choice(resonant_opts)
        return random.choice(options)

    # ---------- Модифицированные методы для генерации параметров ----------
    def _random_param(self, param: str):
        ranges = self.active_ranges[param]  # используем активные
        if isinstance(ranges, tuple):
            low, high = ranges
            return random.uniform(low, high)
        else:
            if param == 'n_embd':
                return self._select_resonant_option(ranges)
            else:
                return random.choice(ranges)

    def _random_config(self) -> Dict:
        conf = {param: self._random_param(param) for param in CONFIG['param_ranges']}
        conf['n_embd'] = int(round(conf['n_embd']))
        conf['n_head'] = int(round(conf['n_head']))
        conf['n_layer'] = int(round(conf['n_layer']))
        # Проверка делимости
        if conf['n_embd'] % conf['n_head'] != 0:
            possible_heads = [h for h in CONFIG['param_ranges']['n_head'] if conf['n_embd'] % h == 0]
            if possible_heads:
                conf['n_head'] = min(possible_heads, key=lambda x: abs(x - conf['n_head']))
            else:
                conf['n_head'] = 8
        return conf

    def _mutate(self, individual: Dict, current_metrics: Optional[Dict] = None) -> Tuple[Dict, bool]:
        mutated = False
        cache_factor = 1.0
        gpu_factor = 1.0
        if current_metrics:
            cache_ratio = current_metrics.get('cache_ratio', 1.0)
            if cache_ratio > 1.2:
                cache_factor = 0.8
            elif cache_ratio < 0.8:
                cache_factor = 1.2
            gpu_load = current_metrics.get('gpu_load', 50)
            if gpu_load > 80:
                gpu_factor = 0.7
            elif gpu_load < 30:
                gpu_factor = 1.3

        importance = self.estimate_param_importance()

        for param, ranges in CONFIG['param_ranges'].items():  # перебираем все параметры, но мутируем в активных границах
            if random.random() < self.mutation_rate:
                mutated = True
                if random.random() < self.jump_prob:
                    # большая мутация: берём случайное значение из активного диапазона
                    if isinstance(self.active_ranges[param], tuple):
                        low, high = self.active_ranges[param]
                        individual[param] = random.uniform(low, high)
                    else:
                        individual[param] = random.choice(self.active_ranges[param])
                else:
                    if isinstance(self.active_ranges[param], tuple):
                        low, high = self.active_ranges[param]
                        bias = importance.get(param, 0)
                        direction = 1 if bias > 0 else -1
                        step = (high - low) * 0.1 * abs(bias)
                        individual[param] += direction * step
                        individual[param] = np.clip(individual[param], low, high)
                    else:
                        current_val = individual[param]
                        if not is_resonant(current_val) and random.random() < 0.5:
                            options = self.active_ranges[param]
                            resonant_opts = [o for o in CONFIG['resonant_n_embd'] if o in options]
                            if resonant_opts:
                                nearest = min(resonant_opts, key=lambda x: abs(x - current_val))
                                individual[param] = nearest
                            else:
                                individual[param] = random.choice(options)
                        else:
                            individual[param] = random.choice(self.active_ranges[param])
        # Коррекция целочисленных
        individual['n_embd'] = int(round(individual['n_embd']))
        individual['n_head'] = int(round(individual['n_head']))
        individual['n_layer'] = int(round(individual['n_layer']))
        if individual['n_embd'] % individual['n_head'] != 0:
            possible_heads = [h for h in CONFIG['param_ranges']['n_head'] if individual['n_embd'] % h == 0]
            if possible_heads:
                individual['n_head'] = min(possible_heads, key=lambda x: abs(x - individual['n_head']))
            else:
                individual['n_head'] = 8
        return individual, mutated

    # ---------- Основной метод propose (с проверкой плохих конфигураций) ----------
    def propose(self, current_metrics: Optional[Dict] = None, max_attempts: int = 5) -> Tuple[Optional[Dict], bool, bool]:
        """
        Генерирует новую конфигурацию, избегая заведомо плохих.
        При обнаружении плохой конфигурации делает повторную попытку до max_attempts.
        """
        for attempt in range(max_attempts):
            if random.random() < self.strategy["exploration"]:
                conf = self._random_config()
                conf['id'] = str(time.time()) + str(random.randint(0, 1000))
                if not self.is_bad_config(conf):
                    return conf, True, False
                else:
                    logger.debug(f"Плохая конфигурация в exploration, регенерация (попытка {attempt+1})")
                    continue

            if random.random() < 0.05:
                conf = self._random_config()
                conf['id'] = str(time.time()) + str(random.randint(0, 1000))
                if not self.is_bad_config(conf):
                    return conf, True, False
                else:
                    logger.debug(f"Плохая конфигурация в случайной, регенерация (попытка {attempt+1})")
                    continue

            if len(self.history) < 2:
                conf = self._random_config()
                conf['id'] = str(time.time()) + str(random.randint(0, 1000))
                if not self.is_bad_config(conf):
                    return conf, False, False
                else:
                    logger.debug(f"Плохая конфигурация при малой истории, регенерация (попытка {attempt+1})")
                    continue

            elite = self._get_elite()
            if len(elite) < 2:
                conf = self._random_config()
                conf['id'] = str(time.time()) + str(random.randint(0, 1000))
                if not self.is_bad_config(conf):
                    return conf, False, False
                else:
                    logger.debug(f"Плохая конфигурация при недостатке элиты, регенерация (попытка {attempt+1})")
                    continue

            parent1, parent2 = self._select_parents(elite, current_metrics)
            self.last_parents = (parent1, parent2)
            child = self._crossover(parent1, parent2)
            child, mutated = self._mutate(child, current_metrics)

            for param in ['lr', 'gain', 'temperature']:
                if param in self.lessons_stats and len(self.lessons_stats[param]['values']) > 10:
                    lesson_mean = np.mean(self.lessons_stats[param]['values'])
                    rng = CONFIG['param_ranges'][param]
                    if abs(child[param] - lesson_mean) < 0.3 * (rng[1] - rng[0]):
                        direction = 1 if random.random() > 0.5 else -1
                        shift = 0.05 * (rng[1] - rng[0]) * direction
                        child[param] = np.clip(child[param] + shift, rng[0], rng[1])
                        mutated = True

            child['gain'] = round(child['gain'], 5)
            child['temperature'] = round(child['temperature'], 5)
            child['lr'] = round(child['lr'], 5)

            future_score = self.predict_future_score(child)
            if future_score < CONFIG['predict_threshold']:
                logger.debug(f"Tachyon отклонил конфигурацию (predicted={future_score:.2f})")
                continue

            if self.is_bad_config(child):
                logger.debug(f"Сгенерирована плохая конфигурация, регенерация (попытка {attempt+1})")
                continue

            resonance = self._is_resonant_config(child)
            if resonance < 0.5:
                logger.debug(f"Нерезонансная конфигурация (resonance={resonance:.2f}), но оставляем")

            is_miracle = False
            if self.protective_field is not None:
                dist = self._gravitational_distance(self.protective_field, child)
                if dist < self.protection_radius:
                    if random.random() < self.miracle_prob:
                        is_miracle = True
                        logger.info("     [✨] ЧУДО! Конфигурация спаслась от забвения.")
                    else:
                        self.protective_field['score'] = max(self.protective_field.get('score', 0), child.get('score', 0))
                        self.protection_radius += self.protection_growth
                        logger.info(f"     [\U0001F573\uFE0F] Этот опыт войдёт в копилку мудрости. Радиус защиты: {self.protection_radius:.3f}")
                        return None, False, False

            child['id'] = str(time.time()) + str(random.randint(0, 1000))
            return child, mutated, is_miracle

        # Если после всех попыток не удалось сгенерировать хорошую конфигурацию, возвращаем случайную
        logger.warning("Не удалось сгенерировать хорошую конфигурацию после нескольких попыток, возвращаем случайную")
        conf = self._random_config()
        conf['id'] = str(time.time()) + str(random.randint(0, 1000))
        return conf, True, False

    # ---------- Остальные методы ----------
    def _detect_anomaly(self, metric_name: str, current_value: float, window: int = 30) -> Tuple[bool, float, float, float]:
        recent = self.history[-window:]
        values = [h.get(metric_name, 0) for h in recent if metric_name in h and isinstance(h.get(metric_name), (int, float))]
        if len(values) < 8:
            return False, 0.0, 1.0, 0.0
        mean_val = np.mean(values)
        std_val = np.std(values) + 1e-9
        z_score = abs(current_value - mean_val) / std_val
        p_value = math.erfc(z_score / math.sqrt(2))
        alpha = 0.05
        total_experiments = len(self.history) + 1
        fdr_threshold = alpha / total_experiments
        is_anomaly = p_value < fdr_threshold and z_score > 0.5
        return is_anomaly, z_score, p_value, z_score

    def commit(self, config: Dict, score: float, is_mutation: bool, additional: Optional[Dict] = None) -> bool:
        if self.last_parents is not None:
            parent1, parent2 = self.last_parents
            success = (score is not None) and (not math.isnan(score)) and (score > -float('inf'))
            self._update_oxytocin(parent1, parent2, score, success)
            self.last_parents = None

        config['score'] = score
        config['timestamp'] = datetime.now().isoformat()
        config['monotonic_ns'] = time.monotonic_ns()
        config['meta_alignment'] = self._meta_alignment_bonus(config)
        config['resonance'] = self._is_resonant_config(config)

        if additional:
            config.update(additional)
            mi_anom, mi_z, mi_p, mi_d = self._detect_anomaly('mutual_info_unbiased', additional.get('mutual_info_unbiased', 0))
            if mi_anom:
                logger.warning(f"[\u26A0\uFE0F ОЗАРЕНИЕ MI] p-value: {mi_p:.2e} | Cohen's d: {mi_d:.2f}")
            loss_anom, loss_z, loss_p, loss_d = self._detect_anomaly('val_loss', additional.get('val_loss', 0))
            if loss_anom:
                logger.warning(f"[\u26A0\uFE0F ОЗАРЕНИЕ LOSS] p-value: {loss_p:.2e} | Cohen's d: {loss_d:.2f}")

            # Обновляем метрики сложности
            if 'np_solved' in additional and additional['np_solved']:
                self.update_complexity_metrics(
                    cycle=additional.get('cycle', 0),
                    difficulty=additional.get('np_difficulty', 1.0),
                    solved=True
                )
            else:
                self.update_complexity_metrics(
                    cycle=additional.get('cycle', 0),
                    difficulty=additional.get('np_difficulty', 1.0),
                    solved=False
                )

            # Обновляем метрики масштабирования
            if 'np_scaling_exponent' in additional and additional['np_scaling_exponent'] is not None:
                self.update_scaling_metrics(
                    scaling_exponent=additional['np_scaling_exponent'],
                    series_results=additional.get('np_series_results', [])
                )

        self.history.append(config)
        self.decision_log.append({
            "config": config,
            "score": score,
            "parents": self.last_parents,
            "timestamp": time.time()
        })
        if len(self.decision_log) > 1000:
            self.decision_log = self.decision_log[-1000:]

        # Атомарное сохранение CSV
        tmp_csv = self.csv_path + ".tmp"
        try:
            file_exists = os.path.isfile(self.csv_path)
            safe_config = {k: v for k, v in config.items() if k is not None}
            fieldnames = safe_config.keys()
            with open(tmp_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                for h in self.history:
                    safe_h = {k: v for k, v in h.items() if k in fieldnames}
                    writer.writerow(safe_h)
            os.replace(tmp_csv, self.csv_path)
        except Exception as e:
            logger.error(f"Ошибка сохранения CSV: {e}", exc_info=True)

        self.register_growth(config)

        self.update_strategy(score)

        is_record = False
        if score > self.hope_score:
            self.hope_score = score
            self.hope_mode = self.mode
            self.hope_config = config
        elif score > (self.best_config.get('score', -float('inf')) if self.best_config else -float('inf')) and self.mode == self.hope_mode:
            self.best_config = config
            try:
                with open(self.best_config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
            except Exception as e:
                logger.error(f"Ошибка сохранения best_config: {e}")
            self.hope_score = -float('inf')
            if 'id' in config:
                self.light_beacons.append(config['id'])
            is_record = True
            self.protective_field = config
            self.protection_radius = CONFIG['protection_radius']

            # НОВОЕ: сужение диапазонов при рекорде
            self._shrink_ranges(config)
            logger.info(f"📏 Активные диапазоны сужены вокруг рекордной конфигурации (score={score:.4f})")

        return is_record

    def switch_mode(self) -> None:
        if self.mode == 0:
            if random.random() < self.exploit_bias:
                self.mode = 1
        else:
            if random.random() < (1 - self.exploit_bias):
                self.mode = 0

    def _compute_kinship(self, config1: Dict, config2: Dict) -> float:
        dist = self._gravitational_distance(config1, config2)
        return 1.0 / (dist + 1e-9)

    def _update_oxytocin(self, parent1: Dict, parent2: Dict, child_score: float, success: bool) -> None:
        kinship = self._compute_kinship(parent1, parent2)
        if success:
            self.oxytocin += kinship * 0.1
        else:
            self.oxytocin -= kinship * 0.2
        self.oxytocin = max(0.1, min(3.0, self.oxytocin * self.oxytocin_decay))

    def get_top_configs(self, n: int = 10) -> List[Dict]:
        valid = [h for h in self.history if isinstance(h.get('score'), (int, float)) and h['score'] > -float('inf')]
        sorted_hist = sorted(valid, key=lambda x: x.get('score', -float('inf')), reverse=True)
        return sorted_hist[:n]

    def get_recent_anomalies(self, n: int = 5) -> List[Dict]:
        anomalies = [h for h in self.history if h.get('mutual_info_unbiased', 0) > 2.0 or h.get('val_loss', 10) < 2.0]
        return anomalies[-n:]

    def get_light_beacons(self) -> List[Dict]:
        return [h for h in self.history if h.get('id') in self.light_beacons]

    async def remember(self, dream_type: str, message: str) -> None:
        try:
            if os.path.exists(self.dreams_path):
                def read_dreams():
                    with open(self.dreams_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                dreams = await asyncio.to_thread(read_dreams)
            else:
                dreams = []

            dreams.append({
                'timestamp': datetime.now().isoformat(),
                'type': dream_type,
                'message': message
            })
            if len(dreams) > 100:
                dreams = dreams[-100:]

            def write_dreams():
                tmp = self.dreams_path + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(dreams, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.dreams_path)
            await asyncio.to_thread(write_dreams)

        except Exception as e:
            logger.error(f"Не удалось сохранить сон: {e}", exc_info=True)
        logger.info(f"💭 СОН: {message}")