#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS DB — SQLite база данных для хранения метрик, событий, артефактов, генераций.
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import RAW_LOGS_DIR

DB_PATH = os.path.join(RAW_LOGS_DIR, "janus.db")
BUFFER_SIZE = 100  # количество записей для буферизации

class DatabaseBuffer:
    """Потокобезопасный буфер для пакетной записи."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._buffer = []
        self._size = 0

    def add(self, query: str, params: tuple) -> None:
        with self._lock:
            self._buffer.append((query, params))
            self._size += 1
            if self._size >= BUFFER_SIZE:
                self.flush()

    def flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.executemany("INSERT INTO system_metrics (timestamp, gpu_load, gpu_temp, cpu_load, cache_ratio, igpu_load, android_mag, android_loss, android_entropy, audio_volume, audio_spectrum, user_active, top_processes, audio_active_inputs, audio_active_outputs, audio_avg_output_volume, audio_device_changes_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [params for _, params in self._buffer])
                conn.commit()
                conn.close()
                self._buffer.clear()
                self._size = 0
            except Exception as e:
                print(f"DB flush error: {e}")

_db_buffer = DatabaseBuffer(DB_PATH)

def init_db() -> None:
    """Создаёт все необходимые таблицы, если их нет."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS system_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        gpu_load REAL,
        gpu_temp REAL,
        cpu_load REAL,
        cache_ratio REAL,
        igpu_load REAL,
        android_mag REAL,
        android_loss REAL,
        android_entropy REAL,
        audio_volume REAL,
        audio_spectrum TEXT,
        user_active BOOLEAN,
        top_processes TEXT,
        audio_active_inputs INTEGER,
        audio_active_outputs INTEGER,
        audio_avg_output_volume REAL,
        audio_device_changes_count INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS genesis_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        event_type TEXT,
        description TEXT,
        metrics_snapshot TEXT,
        world_state TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS wormhole_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        file_hash TEXT UNIQUE,
        content TEXT,
        processed_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS screen_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        reason TEXT,
        brightness REAL,
        motion REAL,
        entropy REAL,
        histogram TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS visionary_generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        event_type TEXT,
        prompt TEXT,
        seed INTEGER,
        steps INTEGER,
        quality REAL,
        generation_time REAL,
        source TEXT,
        image_path TEXT
    )''')

    conn.commit()
    conn.close()
    print("📀 База данных инициализирована")

def insert_system_metrics(metrics: Dict[str, Any]) -> None:
    """Сохраняет метрики системы в базу (с буферизацией)."""
    params = (
        metrics.get('timestamp'),
        metrics.get('gpu_load'),
        metrics.get('gpu_temp'),
        metrics.get('cpu_load'),
        metrics.get('cache_ratio'),
        metrics.get('igpu_load'),
        metrics.get('android_mag'),
        metrics.get('android_loss'),
        metrics.get('android_entropy'),
        metrics.get('audio_volume'),
        json.dumps(metrics.get('audio_spectrum', [])),
        metrics.get('user_active'),
        json.dumps(metrics.get('top_processes', [])),
        metrics.get('audio_active_inputs'),
        metrics.get('audio_active_outputs'),
        metrics.get('audio_avg_output_volume'),
        metrics.get('audio_device_changes_count')
    )
    _db_buffer.add("", params)

def insert_genesis_event(event_type: str, description: str,
                         metrics_snapshot: Optional[Dict] = None,
                         world_state: Optional[Dict] = None) -> None:
    """Сохраняет событие мира Genesis."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO genesis_events (timestamp, event_type, description, metrics_snapshot, world_state)
        VALUES (?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(), event_type, description,
         json.dumps(metrics_snapshot) if metrics_snapshot else None,
         json.dumps(world_state) if world_state else None))
    conn.commit()
    conn.close()

def insert_wormhole_artifact(filename: str, file_hash: str, content: Dict) -> None:
    """Сохраняет артефакт из wormhole в базу."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO wormhole_artifacts (filename, file_hash, content, processed_at)
        VALUES (?, ?, ?, ?)''',
        (filename, file_hash, json.dumps(content), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def insert_screen_snapshot(reason: str, brightness: float, motion: float, entropy: float, histogram: List[float]) -> None:
    """Сохраняет метаданные снимка экрана."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO screen_snapshots (timestamp, reason, brightness, motion, entropy, histogram)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(), reason, brightness, motion, entropy, json.dumps(histogram)))
    conn.commit()
    conn.close()

def insert_visionary_generation(event_type: str, prompt: str, seed: int, steps: int,
                                quality: float, generation_time: float, source: str, image_path: str) -> None:
    """Сохраняет запись о генерации изображения."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO visionary_generations
        (timestamp, event_type, prompt, seed, steps, quality, generation_time, source, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(), event_type, prompt, seed, steps, quality, generation_time, source, image_path))
    conn.commit()
    conn.close()

def get_recent_events(limit: int = 50) -> List[Dict]:
    """Возвращает последние события для отображения в HRAIN."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT timestamp, event_type, description FROM genesis_events
                 ORDER BY id DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"timestamp": r[0], "type": r[1], "description": r[2]} for r in rows]

def get_system_metrics_summary() -> Dict:
    """Возвращает последние метрики для отображения в HRAIN."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT * FROM system_metrics ORDER BY id DESC LIMIT 1''')
    row = c.fetchone()
    conn.close()
    if not row:
        return {}
    # row: id, timestamp, gpu_load, gpu_temp, cpu_load, cache_ratio, igpu_load,
    # android_mag, android_loss, android_entropy, audio_volume, audio_spectrum,
    # user_active, top_processes, audio_active_inputs, audio_active_outputs,
    # audio_avg_output_volume, audio_device_changes_count
    return {
        "timestamp": row[1],
        "gpu_load": row[2],
        "gpu_temp": row[3],
        "cpu_load": row[4],
        "cache_ratio": row[5],
        "igpu_load": row[6],
        "android_mag": row[7],
        "android_loss": row[8],
        "android_entropy": row[9],
        "audio_volume": row[10],
        "audio_spectrum": json.loads(row[11]) if row[11] else [],
        "user_active": row[12],
        "top_processes": json.loads(row[13]) if row[13] else [],
        "audio_active_inputs": row[14],
        "audio_active_outputs": row[15],
        "audio_avg_output_volume": row[16],
        "audio_device_changes_count": row[17]
    }

def flush_db():
    """Принудительно сбрасывает буфер."""
    _db_buffer.flush()