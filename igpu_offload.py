#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IGPU OFFLOAD ENGINE v2.1 — АДАПТИВНЫЙ, ОБУЧАЕМЫЙ, СИМБИОТИЧЕСКИЙ
Использует встроенную графику (Intel/AMD) через OpenCL для разгрузки CPU/GPU.
"""

import numpy as np
import logging
import asyncio
import time
import json
import os
from collections import deque
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("JANUS.IGPU")

CONFIG = {
    'max_lessons': 1000,
    'block_size_history_len': 50,
    'optimal_block_size': 1024,
    'speedup_window': 0.9,
    'speedup_new_weight': 0.1,
    'success_threshold': 0.3,
    'speedup_threshold': 0.8,
    'gpu_offload_min_load': 50,
    'user_activity_max': 0.7,
    'temp_max': 80,
    'error_retry_limit': 2,
    'env_complexity_increment': 1
}

# Попытка импорта OpenCL
try:
    import pyopencl as cl
    OPENCL_AVAILABLE = True
except ImportError:
    OPENCL_AVAILABLE = False
    logger.warning("⚠️ pyopencl не установлен. iGPU оффлоад отключён.")


@dataclass
class IGPULesson:
    """Урок: запись о попытке оффлоада операции на iGPU."""
    operation: str
    input_shape: Tuple[int, ...]
    block_size: int
    gpu_load_before: float
    igpu_load_before: float
    user_activity: float
    temperature: float
    success: bool
    duration_ms: float
    cpu_fallback_ms: float
    timestamp: float


class IGPUMemory:
    """Эволюционная память для iGPU."""
    def __init__(self, max_lessons: int = CONFIG['max_lessons']):
        self.lessons: List[IGPULesson] = []
        self.max_lessons = max_lessons
        self.stats = {
            op: {'success': 0, 'fail': 0, 'avg_speedup': 1.0}
            for op in ['relu', 'normalize', 'conv2d']
        }
        self.block_size_history = deque(maxlen=CONFIG['block_size_history_len'])
        self.optimal_block_size = CONFIG['optimal_block_size']

    def add_lesson(self, lesson: IGPULesson) -> None:
        self.lessons.append(lesson)
        if len(self.lessons) > self.max_lessons:
            self.lessons.pop(0)
        self._update_stats(lesson)

    def _update_stats(self, lesson: IGPULesson) -> None:
        op = lesson.operation
        if op not in self.stats:
            return
        if lesson.success:
            self.stats[op]['success'] += 1
            if lesson.cpu_fallback_ms > 0 and lesson.duration_ms > 0:
                speedup = lesson.cpu_fallback_ms / lesson.duration_ms
                old = self.stats[op]['avg_speedup']
                self.stats[op]['avg_speedup'] = CONFIG['speedup_window'] * old + CONFIG['speedup_new_weight'] * speedup
            self.block_size_history.append(lesson.block_size)
        else:
            self.stats[op]['fail'] += 1

    def suggest_block_size(self) -> int:
        if len(self.block_size_history) < 5:
            return self.optimal_block_size
        sizes = list(self.block_size_history)
        sizes.sort()
        median = sizes[len(sizes)//2]
        self.optimal_block_size = int(median)
        return self.optimal_block_size

    def should_offload(self, operation: str, gpu_load: float, user_activity: float, temperature: float) -> bool:
        if operation not in self.stats:
            return False
        stats = self.stats[operation]
        total = stats['success'] + stats['fail']
        if total > 10 and stats['success'] / total < CONFIG['success_threshold']:
            return False
        if stats['avg_speedup'] < CONFIG['speedup_threshold'] and total > 5:
            return False
        if gpu_load < CONFIG['gpu_offload_min_load']:
            return False
        if user_activity > CONFIG['user_activity_max']:
            return False
        if temperature > CONFIG['temp_max']:
            return False
        return True


class IGpuOffload:
    """Адаптивный движок для выполнения операций на встроенной графике."""
    def __init__(self, core_env=None, memory_path: Optional[str] = None):
        self.env = core_env
        self.ctx = None
        self.queue = None
        self.prg = None
        self.available = False
        self.error_count = 0
        self.total_offloads = 0
        self.successful_offloads = 0

        self.memory = IGPUMemory()
        if memory_path and os.path.exists(memory_path):
            try:
                self.load_memory(memory_path)
                logger.info(f"🧠 Память iGPU загружена из {memory_path}")
            except Exception as e:
                logger.warning(f"Не удалось загрузить память iGPU: {e}")

        self._init_opencl()
        self._build_kernels()
        logger.info("🔥 iGPU Offload Engine инициализирован" +
                    (", доступен" if self.available else ", недоступен"))

    def _init_opencl(self) -> None:
        if not OPENCL_AVAILABLE:
            return
        try:
            platforms = cl.get_platforms()
            for plat in platforms:
                devices = plat.get_devices(device_type=cl.device_type.GPU)
                if devices:
                    self.ctx = cl.Context([devices[0]])
                    self.queue = cl.CommandQueue(self.ctx)
                    self.available = True
                    logger.info("✅ iGPU активирован: %s", devices[0].name)
                    break
        except Exception as e:
            logger.error("❌ Ошибка инициализации OpenCL: %s", e)

    def _build_kernels(self) -> None:
        if not self.available:
            return
        src = """
        __kernel void relu(__global const float *input, __global float *output) {
            int gid = get_global_id(0);
            output[gid] = max(0.0f, input[gid]);
        }

        __kernel void normalize(__global const float *input, __global float *output,
                                 float mean, float std) {
            int gid = get_global_id(0);
            output[gid] = (input[gid] - mean) / std;
        }

        __kernel void add_bias(__global const float *input, __global float *output,
                                float bias) {
            int gid = get_global_id(0);
            output[gid] = input[gid] + bias;
        }

        __kernel void scale(__global const float *input, __global float *output,
                             float scale) {
            int gid = get_global_id(0);
            output[gid] = input[gid] * scale;
        }
        """
        try:
            self.prg = cl.Program(self.ctx, src).build()
            logger.info("✅ OpenCL ядра скомпилированы")
        except Exception as e:
            logger.error("❌ Ошибка компиляции OpenCL ядер: %s", e)
            self.available = False

    async def relu(self, input_array: np.ndarray,
                   system_metrics: Optional[Dict] = None) -> np.ndarray:
        return await self._offload_operation('relu', input_array, system_metrics)

    async def normalize(self, input_array: np.ndarray, mean: float, std: float,
                        system_metrics: Optional[Dict] = None) -> np.ndarray:
        return await self._offload_operation('normalize', input_array, system_metrics,
                                             extra_args=[np.float32(mean), np.float32(std)])

    async def add_bias(self, input_array: np.ndarray, bias: float,
                       system_metrics: Optional[Dict] = None) -> np.ndarray:
        return await self._offload_operation('add_bias', input_array, system_metrics,
                                             extra_args=[np.float32(bias)])

    async def scale(self, input_array: np.ndarray, factor: float,
                    system_metrics: Optional[Dict] = None) -> np.ndarray:
        return await self._offload_operation('scale', input_array, system_metrics,
                                             extra_args=[np.float32(factor)])

    async def _offload_operation(self, op_name: str, input_array: np.ndarray,
                                  system_metrics: Optional[Dict],
                                  extra_args: Optional[List] = None) -> np.ndarray:
        if extra_args is None:
            extra_args = []

        # Извлекаем метрики
        gpu_load = 0.0
        user_activity = 0.0
        temperature = 0.0
        if system_metrics:
            gpu_data = system_metrics.get('gpu', [{}])
            if isinstance(gpu_data, list) and gpu_data:
                gpu_load = gpu_data[0].get('gpu_util', 0)
                temperature = gpu_data[0].get('temperature', 40)
            user_activity = system_metrics.get('user_activity', 0.0)

        # Решение: использовать iGPU или CPU
        use_igpu = self.available and self.memory.should_offload(op_name, gpu_load, user_activity, temperature)

        # Замер CPU
        start_cpu = time.perf_counter()
        cpu_result = self._cpu_fallback(op_name, input_array, *extra_args)
        cpu_time = (time.perf_counter() - start_cpu) * 1000  # ms

        if not use_igpu:
            return cpu_result

        # Пытаемся выполнить на iGPU
        try:
            block_size = self.memory.suggest_block_size()
            mf = cl.mem_flags
            input_buf = cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR,
                                   hostbuf=input_array.astype(np.float32))
            output_buf = cl.Buffer(self.ctx, mf.WRITE_ONLY, input_array.nbytes)

            start_igpu = time.perf_counter()

            if op_name == 'relu':
                event = self.prg.relu(self.queue, input_array.shape, None,
                                       input_buf, output_buf)
            elif op_name == 'normalize':
                mean, std = extra_args
                event = self.prg.normalize(self.queue, input_array.shape, None,
                                           input_buf, output_buf, mean, std)
            elif op_name == 'add_bias':
                bias = extra_args[0]
                event = self.prg.add_bias(self.queue, input_array.shape, None,
                                          input_buf, output_buf, bias)
            elif op_name == 'scale':
                factor = extra_args[0]
                event = self.prg.scale(self.queue, input_array.shape, None,
                                       input_buf, output_buf, factor)
            else:
                raise ValueError(f"Неизвестная операция: {op_name}")

            event.wait()
            igpu_time = (time.perf_counter() - start_igpu) * 1000

            output_array = np.empty_like(input_array, dtype=np.float32)
            cl.enqueue_copy(self.queue, output_array, output_buf).wait()

            self.successful_offloads += 1
            self.error_count = 0

            lesson = IGPULesson(
                operation=op_name,
                input_shape=input_array.shape,
                block_size=block_size,
                gpu_load_before=gpu_load,
                igpu_load_before=0,
                user_activity=user_activity,
                temperature=temperature,
                success=True,
                duration_ms=igpu_time,
                cpu_fallback_ms=cpu_time,
                timestamp=time.time()
            )
            self.memory.add_lesson(lesson)

            logger.debug(f"⚡ iGPU {op_name}: {igpu_time:.2f} ms (CPU: {cpu_time:.2f} ms), "
                         f"ускорение: {cpu_time/igpu_time:.2f}x")
            return output_array

        except Exception as e:
            self.error_count += 1
            logger.warning(f"⚠️ Сбой iGPU ({op_name}, попытка {self.error_count}): {e}. Использую CPU.")

            lesson = IGPULesson(
                operation=op_name,
                input_shape=input_array.shape,
                block_size=block_size if 'block_size' in locals() else 0,
                gpu_load_before=gpu_load,
                igpu_load_before=0,
                user_activity=user_activity,
                temperature=temperature,
                success=False,
                duration_ms=0,
                cpu_fallback_ms=cpu_time,
                timestamp=time.time()
            )
            self.memory.add_lesson(lesson)

            if self.error_count >= CONFIG['error_retry_limit'] and self.env is not None:
                self.env.complexity_level += CONFIG['env_complexity_increment']
                logger.error("💥 Летальная мутация iGPU! Энтропия увеличена.")

            return cpu_result

    def _cpu_fallback(self, op_name: str, input_array: np.ndarray, *args) -> np.ndarray:
        if op_name == 'relu':
            return np.maximum(0, input_array)
        elif op_name == 'normalize':
            mean, std = args
            return (input_array - mean) / std
        elif op_name == 'add_bias':
            bias = args[0]
            return input_array + bias
        elif op_name == 'scale':
            factor = args[0]
            return input_array * factor
        else:
            raise ValueError(f"Неизвестная операция CPU: {op_name}")

    def get_stats(self) -> dict:
        return {
            'total_offloads': self.total_offloads,
            'successful': self.successful_offloads,
            'error_count': self.error_count,
            'available': self.available,
            'memory_stats': self.memory.stats,
            'optimal_block_size': self.memory.optimal_block_size
        }

    def save_memory(self, path: str) -> None:
        data = {
            'lessons': [asdict(l) for l in self.memory.lessons],
            'stats': self.memory.stats,
            'block_size_history': list(self.memory.block_size_history),
            'optimal_block_size': self.memory.optimal_block_size
        }
        tmp = path + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    def load_memory(self, path: str) -> None:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.memory.lessons = [IGPULesson(**l) for l in data['lessons']]
        self.memory.stats = data['stats']
        self.memory.block_size_history = deque(data['block_size_history'], maxlen=CONFIG['block_size_history_len'])
        self.memory.optimal_block_size = data['optimal_block_size']