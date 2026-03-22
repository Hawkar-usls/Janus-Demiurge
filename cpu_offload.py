#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU OFFLOAD ENGINE — распределение лёгких задач по свободным ядрам процессора.
"""

import threading
import concurrent.futures
import psutil
import time
import logging
from typing import Any, Callable, List, Optional, Iterable
from collections import deque

logger = logging.getLogger("JANUS.CPUOffload")

CONFIG = {
    'idle_core_threshold': 30,      # % загрузки, ниже которого ядро считается свободным
    'cache_ratio_threshold': 1.5,   # выше этого кэш перегружен
    'min_idle_cores': 2,
    'high_priority_threshold': 8,
    'history_size': 100
}


class CPUOffload:
    def __init__(self, max_workers: Optional[int] = None, cache_probe: Optional[Any] = None):
        self.cpu_count = psutil.cpu_count(logical=True)
        self.max_workers = max_workers or max(1, self.cpu_count - 1)
        self.cache_probe = cache_probe
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_tasks = 0
        self.lock = threading.Lock()
        self.history = deque(maxlen=CONFIG['history_size'])
        logger.info(f"⚙️ CPUOffload инициализирован: доступно {self.max_workers} ядер")

    def get_idle_cores(self) -> int:
        per_core = psutil.cpu_percent(percpu=True, interval=0.1)
        return sum(1 for p in per_core if p < CONFIG['idle_core_threshold'])

    def can_offload(self, task_priority: int = 1) -> bool:
        idle = self.get_idle_cores()
        if idle == 0:
            return False

        if self.cache_probe:
            cache_ratio = self.cache_probe.get_metrics().get('ratio', 1.0)
            if cache_ratio > CONFIG['cache_ratio_threshold']:
                logger.debug("Кэш перегружен, оффлоад отменён")
                return False

        if idle >= CONFIG['min_idle_cores'] or task_priority >= CONFIG['high_priority_threshold']:
            return True
        return False

    def submit(self, fn: Callable, *args, priority: int = 1, **kwargs) -> Optional[concurrent.futures.Future]:
        if not self.can_offload(priority):
            return None
        with self.lock:
            self.active_tasks += 1
        future = self.executor.submit(self._wrapper, fn, *args, **kwargs)
        future.add_done_callback(self._task_done)
        return future

    def _wrapper(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в offload-задаче: {e}", exc_info=True)
            return None

    def _task_done(self, future):
        with self.lock:
            self.active_tasks -= 1

    def map(self, fn: Callable, iterable: Iterable, priority: int = 1) -> Optional[List]:
        if not self.can_offload(priority):
            return None
        chunk_size = max(1, len(list(iterable)) // self.max_workers)
        chunks = [iterable[i:i+chunk_size] for i in range(0, len(list(iterable)), chunk_size)]
        futures = []
        for chunk in chunks:
            future = self.submit(lambda ch: [fn(x) for x in ch], chunk, priority=priority)
            if future:
                futures.append(future)
        results = []
        for f in concurrent.futures.as_completed(futures):
            results.extend(f.result())
        return results

    def shutdown(self):
        self.executor.shutdown(wait=True)