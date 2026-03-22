#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Model — предсказывает успех конфигурации на основе истории.
Использует RandomForestRegressor. Учитывает гиперпараметры и системные метрики.
"""

import numpy as np
import logging
from sklearn.ensemble import RandomForestRegressor
from typing import List, Dict, Any, Optional

logger = logging.getLogger("JANUS.META")

CONFIG = {
    'max_samples': 200,
    'n_estimators': 20,
    'random_state': 42,
    'feature_keys': [
        'gain', 'temperature', 'lr_log',  # гиперпараметры (lr в лог-масштабе)
        'n_embd_norm', 'n_head_norm', 'n_layer_norm',
        'gpu_load', 'gpu_temp', 'cpu_load', 'cache_ratio'  # метрики
    ],
    'norm_factors': {
        'n_embd': 768.0,
        'n_head': 16.0,
        'n_layer': 12.0,
        'gpu_load': 100.0,
        'gpu_temp': 100.0,
        'cpu_load': 100.0,
        'cache_ratio': 2.0
    }
}


class MetaModel:
    def __init__(self, max_samples: int = CONFIG['max_samples']):
        self.model: Optional[RandomForestRegressor] = None
        self.max_samples = max_samples
        self.X: List[List[float]] = []
        self.y: List[float] = []
        self.is_trained = False

    def add_sample(self, full_data: Dict[str, Any], score: float) -> None:
        """
        Добавляет точку в обучающую выборку.
        full_data: словарь, содержащий как гиперпараметры, так и метрики.
        """
        vec = self._to_vector(full_data)
        self.X.append(vec)
        self.y.append(score)
        if len(self.X) > self.max_samples:
            self.X = self.X[-self.max_samples:]
            self.y = self.y[-self.max_samples:]

    def train(self) -> None:
        """Обучает модель на текущей выборке."""
        if len(self.X) < 10:
            self.is_trained = False
            return
        X = np.array(self.X)
        y = np.array(self.y)
        self.model = RandomForestRegressor(
            n_estimators=CONFIG['n_estimators'],
            random_state=CONFIG['random_state']
        )
        self.model.fit(X, y)
        self.is_trained = True
        logger.info(f"Мета-модель обучена на {len(self.X)} примерах")

    def predict(self, data_list: List[Dict[str, Any]]) -> List[float]:
        """
        Возвращает список предсказанных score для списка словарей.
        """
        if not self.is_trained or self.model is None:
            return [0.0] * len(data_list)
        X = np.array([self._to_vector(d) for d in data_list])
        return self.model.predict(X).tolist()

    def _to_vector(self, data: Dict[str, Any]) -> List[float]:
        """
        Преобразует словарь в вектор признаков.
        """
        # Гиперпараметры с безопасными значениями по умолчанию
        gain = data.get('gain', 1.0)
        temp = data.get('temperature', 1.0)
        lr = data.get('lr', 1e-4)
        n_embd = data.get('n_embd', 256)
        n_head = data.get('n_head', 8)
        n_layer = data.get('n_layer', 6)

        # Нормализация гиперпараметров
        n_embd_norm = n_embd / CONFIG['norm_factors']['n_embd']
        n_head_norm = n_head / CONFIG['norm_factors']['n_head']
        n_layer_norm = n_layer / CONFIG['norm_factors']['n_layer']

        # Метрики (если нет, нейтральные значения)
        gpu_load = data.get('gpu_load', 50.0) / CONFIG['norm_factors']['gpu_load']
        gpu_temp = data.get('gpu_temp', 50.0) / CONFIG['norm_factors']['gpu_temp']
        cpu_load = data.get('cpu_load', 50.0) / CONFIG['norm_factors']['cpu_load']
        cache_ratio = min(data.get('cache_ratio', 1.0), CONFIG['norm_factors']['cache_ratio']) / CONFIG['norm_factors']['cache_ratio']

        return [
            gain,
            temp,
            np.log10(max(lr, 1e-8)),  # логарифм learning rate
            n_embd_norm,
            n_head_norm,
            n_layer_norm,
            gpu_load,
            gpu_temp,
            cpu_load,
            cache_ratio
        ]