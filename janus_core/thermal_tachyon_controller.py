#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THERMAL TACHYON CONTROLLER — единый модуль управления нагрузкой по температуре и стабильности.
Реализует:
- Термо‑адаптивную логику (EXPLORE, FREEZE, CONTRACT)
- Холодную память лучших состояний
- Реверсивный поиск (tachyon rewind)
- M2R‑эффективность (score / ресурсы)
- Учёт скорости охлаждения (rate of cooling)
- Адаптацию к свободным ядрам (idle_cores) для увеличения нагрузки при простое системы
"""

import time
import logging
from collections import deque
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("JANUS.THERMAL")

class ThermalTachyonController:
    def __init__(self, config: Dict[str, Any]):
        """
        config: словарь с настройками
        """
        # Температурные пороги
        self.target_temp = config.get('target_temp', 55.0)        # золотая зона
        self.max_temp = config.get('max_temp', 80.0)              # аварийный порог
        self.explore_threshold = config.get('explore_threshold', 65.0)
        self.freeze_threshold = config.get('freeze_threshold', 50.0)
        self.contract_threshold = config.get('contract_threshold', 40.0)

        # Пороги стабильности
        self.stability_high = config.get('stability_high', 0.85)   # очень стабильно
        self.stability_low = config.get('stability_low', 0.6)      # нестабильно

        # Параметры памяти и отката
        self.cold_memory_size = config.get('cold_memory_size', 20)
        self.revert_threshold = config.get('revert_threshold', 0.9)  # если текущий score < best_score * порог, откат
        self.cold_states = deque(maxlen=self.cold_memory_size)

        # M2R
        self.m2r_window = config.get('m2r_window', 20)
        self.m2r_history = deque(maxlen=self.m2r_window)

        # Коэффициенты для регулировки нагрузки (по умолчанию)
        self.batch_factor = 1.0
        self.parallel_factor = 1.0
        self.pause_factor = 1.0

        # Состояния
        self.current_mode = "EXPLORE"
        self.best_score = -float('inf')
        self.best_config = None
        self.best_metrics = None

        # Для расчёта скорости охлаждения
        self.prev_temp = None

    # ---------- Вспомогательные расчёты ----------
    def _compute_resources(self, metrics: Dict[str, Any]) -> float:
        """
        Оценивает затраченные ресурсы: можно взять среднюю загрузку CPU/GPU, температуру, энтропию.
        Возвращает число (чем больше, тем ресурсоёмко).
        """
        cpu_load = metrics.get('cpu', {}).get('percent_total', 50.0) / 100.0
        gpu_load = 0.0
        gpu_data = metrics.get('gpu', [{}])
        if isinstance(gpu_data, list) and gpu_data:
            gpu_load = gpu_data[0].get('gpu_util', 0) / 100.0
        temp = metrics.get('cpu_temperature', 50.0) / 100.0
        entropy = metrics.get('hardware_entropy', {}).get('execution_variance', 0.0) * 100
        resources = 0.4 * cpu_load + 0.3 * gpu_load + 0.2 * temp + 0.1 * entropy
        return resources

    def _compute_thermal_eff(self, metrics: Dict[str, Any]) -> float:
        """
        Основная метрика: эффективность = стабильность / (1 + температура + джиттер)
        """
        cpu_temp = metrics.get('cpu_temperature', 60.0) or 60.0
        entropy = metrics.get('hardware_entropy', {})
        stability = entropy.get('stability_score', 0.5)
        jitter = entropy.get('timing_jitter', 0.0)

        # Штраф за джиттер (чем выше джиттер, тем больше наказание)
        efficiency = stability / (1.0 + cpu_temp * 0.02 + jitter * 50.0)
        return efficiency

    def _compute_rate_of_cooling(self, metrics: Dict[str, Any]) -> Optional[float]:
        """
        Вычисляет скорость охлаждения (разница с предыдущим замером).
        Если температура падает быстро, это может быть сигналом к ускорению.
        """
        current_temp = metrics.get('cpu_temperature')
        if current_temp is None or self.prev_temp is None:
            self.prev_temp = current_temp
            return None
        delta = self.prev_temp - current_temp
        self.prev_temp = current_temp
        return delta

    # ---------- Основные методы ----------
    def update_mode(self, metrics: Dict[str, Any]) -> str:
        """
        Определяет режим работы на основе температуры и стабильности.
        """
        cpu_temp = metrics.get('cpu_temperature', 60.0) or 60.0
        stability = metrics.get('hardware_entropy', {}).get('stability_score', 0.5)

        if cpu_temp > self.explore_threshold or stability < self.stability_low:
            mode = "EXPLORE"
        elif cpu_temp < self.contract_threshold and stability > self.stability_high:
            mode = "CONTRACT"
        elif cpu_temp < self.freeze_threshold:
            mode = "FREEZE"
        else:
            mode = "EXPLORE"
        self.current_mode = mode
        return mode

    def update_m2r(self, score: float, metrics: Dict[str, Any]) -> float:
        """
        Добавляет точку в M2R‑историю и возвращает текущий M2R (score / resources).
        """
        resources = self._compute_resources(metrics)
        if resources > 0:
            m2r = score / resources
        else:
            m2r = score
        self.m2r_history.append((score, resources))
        return m2r

    def update_cold_memory(self, score: float, config: Dict[str, Any], metrics: Dict[str, Any]):
        """
        Сохраняет состояние в холодную память, если оно достаточно хорошее.
        """
        thermal_eff = self._compute_thermal_eff(metrics)
        if thermal_eff > 0.8:  # порог для "хорошего" состояния
            self.cold_states.append({
                "score": score,
                "config": config.copy(),
                "metrics": metrics.copy(),
                "thermal_eff": thermal_eff,
                "timestamp": time.time()
            })
            logger.debug(f"❄️ Сохранено в холодную память: score {score:.4f}, eff {thermal_eff:.3f}")

    def check_revert(self, current_score: float, current_metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Проверяет, нужно ли откатиться к лучшему холодному состоянию.
        """
        if not self.cold_states:
            return None

        # Находим лучшее состояние в холодной памяти
        best_cold = max(self.cold_states, key=lambda x: x["score"])
        if current_score < best_cold["score"] * self.revert_threshold:
            cpu_temp = current_metrics.get('cpu_temperature', 60.0)
            stability = current_metrics.get('hardware_entropy', {}).get('stability_score', 0.5)
            if cpu_temp > self.explore_threshold or stability < self.stability_low:
                logger.info(f"🔄 Откат к холодному состоянию (score {best_cold['score']:.4f}, eff {best_cold['thermal_eff']:.3f})")
                return best_cold["config"]
        return None

    def update_best_state(self, score: float, config: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """
        Обновляет лучшее состояние (глобальный максимум).
        """
        if score > self.best_score:
            self.best_score = score
            self.best_config = config.copy()
            self.best_metrics = metrics.copy()
            logger.info(f"🏆 Новый рекорд: score {score:.4f}")
            return True
        return False

    # ---------- Основные факторы для регулировки нагрузки ----------
    def get_factors(self, metrics: Dict[str, Any], current_score: float = None) -> Tuple[float, float, float]:
        """
        Возвращает (batch_factor, parallel_factor, pause_factor) на основе текущих метрик.
        """
        cpu_temp = metrics.get('cpu_temperature', 60.0) or 60.0
        stability = metrics.get('hardware_entropy', {}).get('stability_score', 0.5)
        thermal_eff = self._compute_thermal_eff(metrics)
        rate_of_cooling = self._compute_rate_of_cooling(metrics)

        # Получаем данные о свободных ядрах и игровом режиме
        idle_cores = metrics.get('idle_cores', 0)
        total_cores = metrics.get('total_cores', 1)
        gaming_mode = metrics.get('gaming_mode', False)

        # Режимы
        mode = self.update_mode(metrics)

        # Базовые факторы в зависимости от режима
        if mode == "EXPLORE":
            batch_factor = 1.0
            parallel_factor = 1.0
            pause_factor = 0.8
        elif mode == "FREEZE":
            batch_factor = 0.85
            parallel_factor = 0.7
            pause_factor = 1.2
        else:  # CONTRACT
            batch_factor = 0.6
            parallel_factor = 0.4
            pause_factor = 1.5

        # Коррекция на основе эффективности
        if thermal_eff > 0.9:
            batch_factor = min(1.0, batch_factor * 1.1)   # можно чуть ускорить
            pause_factor = max(0.5, pause_factor * 0.9)
        elif thermal_eff < 0.5:
            batch_factor = max(0.3, batch_factor * 0.8)
            pause_factor = min(3.0, pause_factor * 1.2)

        # Коррекция на основе скорости охлаждения
        if rate_of_cooling is not None and rate_of_cooling > 2.0 and stability > self.stability_high:
            # Быстрое охлаждение при высокой стабильности — можно ускорить
            batch_factor = min(1.0, batch_factor * 1.2)
            pause_factor = max(0.5, pause_factor * 0.8)
            logger.debug(f"❄️ Быстрое охлаждение ({rate_of_cooling:.1f}°C) – ускоряем")

        # *** НОВАЯ ЛОГИКА: учёт свободных ядер ***
        if not gaming_mode:   # если не в игре, можно увеличить нагрузку
            free_ratio = idle_cores / total_cores if total_cores > 0 else 0
            if free_ratio > 0.5:   # более 50% ядер свободны
                # Увеличиваем batch и parallel факторы, но не выше 1.5
                batch_factor = min(1.5, batch_factor * (1 + free_ratio * 0.3))
                parallel_factor = min(1.5, parallel_factor * (1 + free_ratio * 0.3))
                # Паузу можно уменьшить
                pause_factor = max(0.5, pause_factor * (1 - free_ratio * 0.2))
                logger.debug(f"💨 Много свободных ядер ({free_ratio:.1%}) – ускоряем обучение")
        else:
            # Во время игры не увеличиваем нагрузку, даже если ядра свободны
            logger.debug("🎮 Игровой режим – приоритет отдан игре, ускорение отключено")

        # Аварийное замедление
        if cpu_temp > self.max_temp:
            batch_factor = 0.3
            parallel_factor = 0.2
            pause_factor = 3.0

        # Ограничиваем
        batch_factor = max(0.2, min(1.5, batch_factor))
        parallel_factor = max(0.1, min(1.5, parallel_factor))
        pause_factor = max(0.5, min(5.0, pause_factor))

        self.batch_factor = batch_factor
        self.parallel_factor = parallel_factor
        self.pause_factor = pause_factor

        logger.debug(f"🌡️ Factors: batch={batch_factor:.2f}, par={parallel_factor:.2f}, pause={pause_factor:.2f} | mode={mode} | eff={thermal_eff:.3f} | temp={cpu_temp:.1f}°C | idle_cores={idle_cores}/{total_cores}")
        return batch_factor, parallel_factor, pause_factor

    # ---------- Доступ к режиму и состоянию ----------
    def get_current_mode(self) -> str:
        return self.current_mode

    def get_best_config(self) -> Optional[Dict[str, Any]]:
        return self.best_config

    def get_thermal_eff(self, metrics: Dict[str, Any]) -> float:
        return self._compute_thermal_eff(metrics)