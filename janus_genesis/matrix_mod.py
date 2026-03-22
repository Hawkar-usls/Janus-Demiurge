#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MATRIX MODE v1.0 — СИСТЕМНОЕ ВМЕШАТЕЛЬСТВО БЕЗ ЧИТОВ
При включении Янус начинает создавать дозированную нагрузку на GPU во время игры,
вызывая равномерное замедление игрового времени (эффект «матрицы»).
Не изменяет память игры, не внедряет код — только честное использование ресурсов.
"""

import threading
import time
import logging
import torch
import numpy as np

logger = logging.getLogger("JANUS.MATRIX")

# ============================================
# ГЛАВНЫЙ ПЕРЕКЛЮЧАТЕЛЬ — МЕНЯЙ ЗДЕСЬ
# ============================================
MATRIX_MODE = False  # ← поставь True, чтобы активировать эффект

# Настройки интенсивности (можно подбирать под свою систему)
BASE_LOAD = 0.3       # базовая доля нагрузки GPU (0.0 - 1.0)
MAX_LOAD = 0.7        # максимальная нагрузка, чтобы не убить игру
INTENSITY_STEP = 0.05 # шаг изменения нагрузки при адаптации


class MatrixEngine:
    """
    Движок, создающий регулируемую нагрузку на GPU.
    Использует простые тензорные вычисления, чтобы загружать видеокарту.
    Интенсивность подстраивается под текущую загрузку игры (чем выше FPS, тем сильнее давим).
    """
    def __init__(self, game_detector, tachyon=None):
        self.game_detector = game_detector
        self.tachyon = tachyon
        self.active = False
        self.current_intensity = BASE_LOAD
        self.target_intensity = BASE_LOAD
        self.lock = threading.Lock()
        self.thread = None
        self.stop_event = threading.Event()

        # Подготовим случайные тензоры для вычислений (чтобы не создавать их каждый раз)
        self.a = torch.randn(2048, 2048, device='cuda')
        self.b = torch.randn(2048, 2048, device='cuda')
        self.c = torch.randn(2048, 2048, device='cuda')

    def _load_loop(self):
        """Основной цикл нагрузки."""
        while not self.stop_event.is_set():
            with self.lock:
                intensity = self.current_intensity
                target = self.target_intensity

            # Плавно подстраиваем текущую интенсивность к целевой
            if intensity < target:
                intensity = min(intensity + INTENSITY_STEP, target)
            elif intensity > target:
                intensity = max(intensity - INTENSITY_STEP, target)
            with self.lock:
                self.current_intensity = intensity

            # Если интенсивность почти нулевая — просто спим
            if intensity < 0.01:
                time.sleep(0.1)
                continue

            # Выполняем несколько итераций вычислений в зависимости от интенсивности
            num_iters = int(intensity * 10) + 1
            start = time.perf_counter()
            for _ in range(num_iters):
                # Простое умножение матриц
                self.c = torch.matmul(self.a, self.b)
                # Небольшая синхронизация, чтобы нагрузка была реальной
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - start

            # Спим оставшееся время, чтобы не забивать GPU на 100%
            sleep_time = max(0.01, 0.1 - elapsed)
            time.sleep(sleep_time)

    def update_intensity(self, game_fps_estimate=None):
        """
        Вызывается из основного цикла Януса (или из отдельного потока) для адаптации нагрузки.
        game_fps_estimate — оценочный FPS игры (можно получать из GameDetector).
        """
        if not MATRIX_MODE:
            self.target_intensity = 0.0
            return

        # Если игра не запущена — ничего не делаем
        # Используем атрибут gaming_mode, который есть в SystemMonitor
        if not getattr(self.game_detector, 'gaming_mode', False):
            self.target_intensity = 0.0
            return

        # Если есть Tachyon, можем использовать его предсказания
        if self.tachyon and hasattr(self.tachyon, 'predict_fps'):
            predicted_fps = self.tachyon.predict_fps()
            if predicted_fps is not None and predicted_fps > 60:
                self.target_intensity = min(MAX_LOAD, self.target_intensity + INTENSITY_STEP)
            else:
                self.target_intensity = max(BASE_LOAD, self.target_intensity - INTENSITY_STEP)
        else:
            # Простая логика: если FPS высокий — увеличиваем нагрузку
            if game_fps_estimate and game_fps_estimate > 80:
                self.target_intensity = min(MAX_LOAD, self.target_intensity + INTENSITY_STEP)
            elif game_fps_estimate and game_fps_estimate < 30:
                self.target_intensity = max(0.0, self.target_intensity - INTENSITY_STEP)
            else:
                # Держим базовую нагрузку
                self.target_intensity = BASE_LOAD

        logger.debug(f"Matrix intensity: target={self.target_intensity:.2f}, current={self.current_intensity:.2f}")

    def start(self):
        """Запускает поток нагрузки."""
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._load_loop, daemon=True)
        self.thread.start()
        logger.info("Matrix Engine запущен. Добро пожаловать в Матрицу.")

    def stop(self):
        """Останавливает поток нагрузки."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Matrix Engine остановлен.")