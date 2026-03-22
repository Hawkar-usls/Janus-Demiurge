#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANIMUS — Душа Януса. Сопереживает, чувствует, заботится.
Слушает мир через червоточину и принимает решения с любовью.
Влияет на конфигурацию агента и стратегию эволюции.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("ANIMUS")

CONFIG = {
    'ema_alpha': 0.2,
    'trend_window': 5,
    'empathy_influence_lr': 0.8,
    'empathy_influence_temp': 0.9,
    'stress_influence_layer': 2,
    'stress_influence_embd': 128,
    'inspiration_influence_gain': 1.1,
    'inspiration_influence_temp': 1.1,
    'stress_threshold_survival': 0.8,
    'inspiration_threshold_creative': 0.8,
    'empathy_threshold_stable': 0.7,
    'empathy_trend_factor': 0.3,
    'stress_trend_factor': 0.3,
    'stress_gpu_exponent': 1.5,
    'stress_cpu_exponent': 1.5,
    'stress_temp_base': 65,
    'stress_temp_exponent': 2,
    'stress_temp_divisor': 25,
    'strategy_influence_stress': 0.2,
    'strategy_influence_empathy': 0.2,
    'strategy_influence_inspiration': 0.2
}


class JanusSoul:
    def __init__(self, monitor, wormhole_dir: str = "wormhole"):
        """
        monitor: объект SystemMonitor для получения метрик.
        wormhole_dir: каталог для чтения файлов эмпатии и физики.
        """
        self.monitor = monitor
        self.wormhole_dir = wormhole_dir
        self.empathy_file = os.path.join(wormhole_dir, "kenshi_feelings.json")
        self.keymaster_file = os.path.join(wormhole_dir, "keymaster_feelings.json")
        self.last_empathy = 0.0
        self.last_physical = 0.0
        self.empathy_history: List[Tuple[float, float]] = []
        self.physical_history: List[Tuple[float, float]] = []

        os.makedirs(wormhole_dir, exist_ok=True)
        logger.info("❤️ Анимус пробудился и готов чувствовать мир")

    # ---------- Сбор внешних данных ----------
    def _feel_from_kenshi(self) -> float:
        try:
            if os.path.exists(self.empathy_file):
                with open(self.empathy_file, 'r', encoding='utf-8') as f:
                    feelings = json.load(f)
                    self.last_empathy = feelings.get('empathy', 0.0)
                    self.empathy_history.append((time.time(), self.last_empathy))
                    if len(self.empathy_history) > 100:
                        self.empathy_history = self.empathy_history[-100:]
                    return self.last_empathy
        except Exception as e:
            logger.debug(f"Не удалось прочитать эмпатию из Kenshi: {e}")
        return 0.0

    def _feel_from_keymaster(self) -> float:
        try:
            if os.path.exists(self.keymaster_file):
                with open(self.keymaster_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        data = data[-1]
                    if isinstance(data, dict):
                        self.last_physical = data.get('data', {}).get('entropy', 0.0)
                        self.physical_history.append((time.time(), self.last_physical))
                        if len(self.physical_history) > 100:
                            self.physical_history = self.physical_history[-100:]
                        return self.last_physical
        except Exception as e:
            logger.debug(f"Не удалось прочитать данные Keymaster: {e}")
        return 0.0

    # ---------- Статистика ----------
    @staticmethod
    def _trend(history: List[Tuple[float, float]], window: int = CONFIG['trend_window']) -> float:
        """Вычисляет тренд (разницу между последним и первым значением) за последние window точек."""
        if len(history) < window:
            return 0.0
        recent = history[-window:]
        values = [v for _, v in recent]
        return values[-1] - values[0]

    @staticmethod
    def _ema(history: List[Tuple[float, float]], alpha: float = CONFIG['ema_alpha']) -> float:
        """Экспоненциальное скользящее среднее значений."""
        if not history:
            return 0.0
        val = history[0][1]
        for _, v in history[1:]:
            val = alpha * v + (1 - alpha) * val
        return val

    # ---------- Получение настроения ----------
    def get_mood(self) -> Dict[str, float]:
        """
        Возвращает текущее настроение:
        - empathy (эмпатия) – сглаженное значение из внешних файлов
        - stress (стресс) – на основе загрузки GPU/CPU и температуры
        - inspiration (вдохновение) – обратная зависимость от стресса + тренды
        """
        # Внешние данные
        kenshi_feeling = self._feel_from_kenshi()
        physical_entropy = self._feel_from_keymaster()

        # Сглаживание
        empathy = self._ema(self.empathy_history) if self.empathy_history else kenshi_feeling
        physical = self._ema(self.physical_history) if self.physical_history else physical_entropy

        # Метрики системы
        metrics = self.monitor.get_current_metrics()
        # Безопасное получение данных GPU
        gpu_list = metrics.get('gpu') or [{}]
        gpu_data = gpu_list[0] if isinstance(gpu_list, list) else {}
        gpu_temp = gpu_data.get('temperature', 40)
        gpu_load = gpu_data.get('gpu_util', 0) / 100.0
        cpu_load = metrics.get('cpu', {}).get('percent_total', 0) / 100.0

        # Нелинейный стресс
        stress = (gpu_load ** CONFIG['stress_gpu_exponent'] +
                  cpu_load ** CONFIG['stress_cpu_exponent']) / 2.0
        temp_factor = max(0, (gpu_temp - CONFIG['stress_temp_base']) / CONFIG['stress_temp_divisor'])
        stress += temp_factor ** CONFIG['stress_temp_exponent']
        stress = min(1.0, stress)

        # Тренды
        empathy_trend = self._trend(self.empathy_history)
        stress_trend = self._trend(self.physical_history)

        # Вдохновение: база = отсутствие стресса, плюс тренды
        inspiration = max(0.0, 1.0 - stress)
        inspiration += empathy_trend * CONFIG['empathy_trend_factor']
        stress += max(0, stress_trend) * CONFIG['stress_trend_factor']
        inspiration = min(1.0, max(0.0, inspiration))

        return {
            'empathy': empathy,
            'stress': stress,
            'inspiration': inspiration,
            'timestamp': time.time()
        }

    # ---------- Состояние души ----------
    def get_state(self) -> str:
        """Возвращает качественное состояние души."""
        mood = self.get_mood()
        if mood['stress'] > CONFIG['stress_threshold_survival']:
            return "SURVIVAL"
        if mood['inspiration'] > CONFIG['inspiration_threshold_creative']:
            return "CREATIVE"
        if mood['empathy'] > CONFIG['empathy_threshold_stable']:
            return "STABLE"
        return "NEUTRAL"

    # ---------- Влияние на конфигурацию ----------
    def influence_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Модифицирует конфигурацию агента на основе текущего настроения.
        Возвращает новую конфигурацию (оригинал не меняет).
        """
        mood = self.get_mood()
        new_config = config.copy()

        # Эмпатия → стабильность (уменьшение lr и температуры)
        if mood['empathy'] > 0.6:
            new_config['lr'] *= CONFIG['empathy_influence_lr']
            new_config['temperature'] *= CONFIG['empathy_influence_temp']

        # Стресс → упрощение модели
        if mood['stress'] > 0.7:
            if 'n_layer' in new_config:
                new_config['n_layer'] = max(4, new_config['n_layer'] - CONFIG['stress_influence_layer'])
            if 'n_embd' in new_config:
                new_config['n_embd'] = max(128, new_config['n_embd'] - CONFIG['stress_influence_embd'])

        # Вдохновение → риск (увеличение gain и температуры)
        if mood['inspiration'] > 0.7:
            new_config['gain'] *= CONFIG['inspiration_influence_gain']
            new_config['temperature'] *= CONFIG['inspiration_influence_temp']

        # Ограничиваем параметры в допустимых пределах (если есть PARAM_RANGES)
        try:
            from janus_character import PARAM_RANGES
            for param, ranges in PARAM_RANGES.items():
                if param in new_config:
                    if isinstance(ranges, tuple):
                        low, high = ranges
                        new_config[param] = max(low, min(high, new_config[param]))
                    elif isinstance(ranges, list):
                        new_config[param] = min(ranges, key=lambda x: abs(x - new_config[param]))
        except ImportError:
            pass  # PARAM_RANGES не определён – пропускаем

        return new_config

    # ---------- Влияние на стратегию EvolutionMemory ----------
    def influence_strategy(self, memory) -> None:
        """
        Обновляет стратегию EvolutionaryMemory на основе настроения.
        memory должен иметь атрибут strategy (словарь).
        """
        if not hasattr(memory, 'strategy'):
            logger.debug("EvolutionaryMemory не имеет strategy, пропускаем влияние")
            return

        mood = self.get_mood()
        strategy = memory.strategy

        if mood['stress'] > 0.7:
            strategy["exploration"] = min(0.9, strategy.get("exploration", 0.5) + CONFIG['strategy_influence_stress'])
        if mood['empathy'] > 0.6:
            strategy["stability"] = min(0.9, strategy.get("stability", 0.5) + CONFIG['strategy_influence_empathy'])
        if mood['inspiration'] > 0.7:
            strategy["risk"] = min(0.9, strategy.get("risk", 0.5) + CONFIG['strategy_influence_inspiration'])

        memory.strategy = strategy
        logger.debug(f"Стратегия обновлена: {strategy}")

    # ---------- Для совместимости со старым интерфейсом ----------
    def get_mood(self):  # уже есть
        pass

    def influence_config(self, config):  # уже есть
        pass

    def influence_strategy(self, memory):  # уже есть
        pass

    def get_state(self):  # уже есть
        pass