#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерирует device_data.json из нескольких источников:
- wisdom_landscape.csv (история циклов Януса)
- janus_beacon_log.csv (если есть)
- PLATINUM.LOG (специальный формат логов)
Запускай перед core.py, чтобы Янус учился на реальных данных.
"""

import os
import csv
import json
import random
import re
from datetime import datetime
from config import RAW_LOGS_DIR

WISDOM_CSV = os.path.join(RAW_LOGS_DIR, "wisdom_landscape.csv")
BEACON_CSV = os.path.join(RAW_LOGS_DIR, "janus_beacon_log.csv")
PLATINUM_LOG = os.path.join(RAW_LOGS_DIR, "PLATINUM.LOG")
OUTPUT_PATH = os.path.join(RAW_LOGS_DIR, "device_data.json")

def safe_float(val, default=0.0):
    """Безопасное преобразование в float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_wisdom_csv():
    """Читает wisdom_landscape.csv и возвращает список записей."""
    records = []
    if not os.path.exists(WISDOM_CSV):
        print(f"[⚠️] {WISDOM_CSV} не найден.")
        return records
    with open(WISDOM_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Пропускаем строки, где не удаётся получить ключевые поля
                loss = safe_float(row.get('val_loss'), None)
                if loss is None:
                    continue
                rec = {
                    'timestamp': row.get('timestamp', datetime.now().isoformat()),
                    'loss': loss,
                    'entropy': safe_float(row.get('entropy'), 0.5),
                    'mi': safe_float(row.get('mutual_info_unbiased'), 0.0),
                    'gap': safe_float(row.get('gap'), 0.0),
                    'gpu_load': safe_float(row.get('gpu_load'), 50.0),
                    'gpu_temp': safe_float(row.get('gpu_temp'), 40.0),
                    'cpu_load': safe_float(row.get('cpu_load'), 30.0),
                    'cache_ratio': safe_float(row.get('cache_ratio'), 1.0),
                }
                # Добавляем случайные Android-метрики
                rec['mag_x'] = random.uniform(-50, 50)
                rec['mag_y'] = random.uniform(-50, 50)
                rec['mag_z'] = random.uniform(-50, 50)
                rec['temperature'] = random.uniform(20, 30)
                records.append(rec)
            except Exception as e:
                print(f"Ошибка обработки строки wisdom: {e}")
    print(f"✅ Загружено {len(records)} записей из wisdom_landscape.csv")
    return records

def parse_beacon_csv():
    """Читает janus_beacon_log.csv и возвращает список записей."""
    records = []
    if not os.path.exists(BEACON_CSV):
        return records
    try:
        with open(BEACON_CSV, 'r', encoding='utf-8') as f:
            # Пробуем определить разделитель
            sample = f.read(1024)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                try:
                    rec = {
                        'timestamp': row.get('timestamp', datetime.now().isoformat()),
                        'loss': safe_float(row.get('loss'), 5.5),
                        'entropy': safe_float(row.get('entropy'), 0.5),
                        'mi': safe_float(row.get('mi'), 0.0),
                        'gap': safe_float(row.get('gap'), 0.0),
                        'gpu_load': safe_float(row.get('gpu_load'), 50.0),
                        'gpu_temp': safe_float(row.get('gpu_temp'), 40.0),
                        'cpu_load': safe_float(row.get('cpu_load'), 30.0),
                        'cache_ratio': safe_float(row.get('cache_ratio'), 1.0),
                    }
                    rec['mag_x'] = random.uniform(-50, 50)
                    rec['mag_y'] = random.uniform(-50, 50)
                    rec['mag_z'] = random.uniform(-50, 50)
                    rec['temperature'] = random.uniform(20, 30)
                    records.append(rec)
                except Exception as e:
                    print(f"Ошибка обработки строки beacon: {e}")
    except Exception as e:
        print(f"Не удалось прочитать {BEACON_CSV}: {e}")
    print(f"✅ Загружено {len(records)} записей из janus_beacon_log.csv")
    return records

def parse_platinum_log():
    """Парсит PLATINUM.LOG. Формат строки: [число] E:знач Q:знач T:знач H:знач P:знач S:знач"""
    records = []
    if not os.path.exists(PLATINUM_LOG):
        return records
    pattern = re.compile(r'\[(\d+)\]\s+E:([\d.]+)\s+Q:([\d.]+)\s+T:([\d.]+)\s+H:([\d.]+)\s+P:([\d.]+)\s+S:([\d.]+)')
    with open(PLATINUM_LOG, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if match:
                groups = match.groups()
                try:
                    timestamp = f"PLATINUM_{groups[0]}"
                    rec = {
                        'timestamp': timestamp,
                        'loss': float(groups[1]),
                        'entropy': float(groups[2]),
                        'mi': 0.0,
                        'gap': float(groups[3]) - float(groups[1]),  # T - E
                        'gpu_load': float(groups[4]),
                        'gpu_temp': float(groups[5]),
                        'cpu_load': float(groups[6]),
                        'cache_ratio': 1.0,
                    }
                    rec['mag_x'] = random.uniform(-50, 50)
                    rec['mag_y'] = random.uniform(-50, 50)
                    rec['mag_z'] = random.uniform(-50, 50)
                    rec['temperature'] = rec['gpu_temp']
                    records.append(rec)
                except Exception as e:
                    print(f"Ошибка парсинга строки PLATINUM: {line} -> {e}")
            else:
                print(f"Пропущена строка PLATINUM (не соответствует формату): {line}")
    print(f"✅ Загружено {len(records)} записей из PLATINUM.LOG")
    return records

def main():
    all_records = []
    all_records.extend(parse_wisdom_csv())
    all_records.extend(parse_beacon_csv())
    all_records.extend(parse_platinum_log())

    if not all_records:
        print("[⚠️] Нет записей для сохранения.")
        return

    # Сортируем по времени (если есть timestamp) и оставляем последние 1000
    all_records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    if len(all_records) > 1000:
        all_records = all_records[:1000]

    # Преобразуем в формат device_data.json
    output = []
    for rec in all_records:
        output.append({
            "device_id": "android_01",
            "timestamp": rec['timestamp'],
            "data": {
                "temperature": rec['temperature'],
                "pressure": random.uniform(1000, 1020),
                "mag_x": rec['mag_x'],
                "mag_y": rec['mag_y'],
                "mag_z": rec['mag_z'],
                "loss": rec['loss'],
                "entropy": rec['entropy'],
                "m2r": rec.get('gap', 0) * 10,
                "gpu_load": rec['gpu_load'],
                "gpu_temp": rec['gpu_temp'],
                "cpu_load": rec['cpu_load'],
                "cache_ratio": rec['cache_ratio']
            }
        })

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    print(f"[✅] Сгенерировано {len(output)} записей в {OUTPUT_PATH}")

if __name__ == "__main__":
    main()