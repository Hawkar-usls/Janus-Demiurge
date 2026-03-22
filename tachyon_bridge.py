# -*- coding: utf-8 -*-
"""
JANUS TACHYON BRIDGE v2.0 — CSV EDITION
- Чтение CSV-логов маяка из Model_Zoo (E:\Janus_BFaiN\Model_Zoo)
- Парсинг метрик: температура, давление, энтропия, магнитометр, GPS и др.
- Интеграция данных в систему (обновление предсказаний, обучение моделей)
- Сохранение обработанных CSV в архив
- Сохранена оригинальная функциональность COM-моста и GPU-квотирования
"""

import asyncio
import ctypes
import csv
import json
import logging
import os
import shutil
import serial
import psutil
import math
import time
from datetime import datetime
from typing import Dict, List, Optional

# Импорт константы квотирования
try:
    from config import GPU_TICKET_PATH
except ImportError:
    BASE_DIR = r"E:\Janus_BFaiN"
    GPU_TICKET_PATH = os.path.join(BASE_DIR, "raw_logs", "gpu_ticket.json")

logger = logging.getLogger("JANUS_TACHYON")

# ------------------------------------------------------------
# НАСТРОЙКИ ПУТЕЙ
# ------------------------------------------------------------
BASE_DIR = r"E:\Janus_BFaiN"
RAW_LOGS_DIR = os.path.join(BASE_DIR, "raw_logs")
MODEL_ZOO_DIR = os.path.join(BASE_DIR, "Model_Zoo")
CSV_ARCHIVE_DIR = os.path.join(MODEL_ZOO_DIR, "csv_archive")  # папка для обработанных файлов

CORE_STATE_PATH = os.path.join(BASE_DIR, "core_state.json")
DEVICE_LOG_PATH = os.path.join(RAW_LOGS_DIR, "device_data.json")
TEMP_PATH = DEVICE_LOG_PATH + ".tmp"
AM_PATH = r"C:\ArtMoney\am818.exe"

os.makedirs(RAW_LOGS_DIR, exist_ok=True)
os.makedirs(CSV_ARCHIVE_DIR, exist_ok=True)

# ------------------------------------------------------------
# СТРУКТУРА ПАМЯТИ ДЛЯ ARTMONEY
# ------------------------------------------------------------
class JanusMemory(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_int),
        ("f1", ctypes.c_float),
        ("f2", ctypes.c_float),
        ("gain_control", ctypes.c_float)
    ]

# ------------------------------------------------------------
# GPU TICKET MONITOR (СИСТЕМА КВОТ)
# ------------------------------------------------------------
def check_gpu_ticket():
    """
    Проверяет наличие валидной квоты на использование GPU.
    Возвращает (bool: можно_ли_использовать, float: осталось_времени_в_сек).
    """
    if not os.path.exists(GPU_TICKET_PATH):
        return False, 0.0

    try:
        with open(GPU_TICKET_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if data.get("janus_can_use_gpu") and data.get("duration", 0) > 0:
            remaining = data["duration"] - (time.time() - data["timestamp"])
            if remaining > 0.05:  # запас 50 мс
                return True, remaining
    except (json.JSONDecodeError, IOError):
        pass
    except Exception as e:
        logger.error(f"[!] Ошибка чтения квоты: {e}")
        
    return False, 0.0

# ------------------------------------------------------------
# УТИЛИТЫ
# ------------------------------------------------------------
def atomic_write(filepath, data):
    tmp = filepath + ".tmp"
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, filepath)
    except Exception as e:
        logger.error(f"Atomic write error: {e}")

def parse_beacon_csv(filepath: str) -> List[Dict]:
    """
    Парсит CSV-файл маяка, возвращает список словарей с метриками.
    Ожидаемый формат строк:
    timestamp,f1,f2,temperature,humidity,pressure,shock,gyro_x,gyro_y,gyro_z,mic,entropy,m2r,android_mag,android_loss,android_entropy,android_m2r,gps_lat,gps_lng,gps_alt,gps_sats
    """
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = None
            for row in reader:
                if not row:
                    continue
                if headers is None:
                    # Пропускаем заголовок, если он есть
                    if row[0].strip().lower() == 'timestamp':
                        headers = row
                        continue
                    else:
                        # Если заголовка нет, создаём стандартные имена
                        headers = [
                            'timestamp', 'f1', 'f2', 'temperature', 'humidity', 'pressure',
                            'shock', 'gyro_x', 'gyro_y', 'gyro_z', 'mic', 'entropy', 'm2r',
                            'android_mag', 'android_loss', 'android_entropy', 'android_m2r',
                            'gps_lat', 'gps_lng', 'gps_alt', 'gps_sats'
                        ]
                if len(row) < len(headers):
                    logger.warning(f"Неполная строка в {filepath}, пропускаем")
                    continue
                record = {}
                for i, key in enumerate(headers):
                    val = row[i].strip()
                    if val == '':
                        val = '0'
                    try:
                        # Пытаемся преобразовать в число, если возможно
                        if '.' in val or 'e' in val:
                            record[key] = float(val)
                        else:
                            record[key] = int(val)
                    except ValueError:
                        record[key] = val
                records.append(record)
    except Exception as e:
        logger.error(f"Ошибка парсинга CSV {filepath}: {e}")
    return records

def process_csv_file(filepath: str):
    """
    Обрабатывает один CSV-файл: извлекает метрики, обновляет данные для обучения,
    сохраняет обработанный файл в архив.
    """
    logger.info(f"Обработка CSV: {filepath}")
    records = parse_beacon_csv(filepath)
    if not records:
        logger.warning(f"Файл {filepath} не содержит данных")
        return

    # Сохраняем последнюю запись как самую актуальную (можно взять средние)
    latest = records[-1]
    
    # Обновляем структуру device_data.json (для совместимости с core)
    # Читаем текущие данные, если есть
    current = {}
    if os.path.exists(DEVICE_LOG_PATH):
        try:
            with open(DEVICE_LOG_PATH, 'r', encoding='utf-8') as f:
                current = json.load(f)
        except:
            pass
    
    # Добавляем новые поля
    current.update({
        "beacon_timestamp": latest.get('timestamp', 0),
        "beacon_f1": latest.get('f1', 0),
        "beacon_f2": latest.get('f2', 0),
        "temperature": latest.get('temperature', 0),
        "humidity": latest.get('humidity', 0),
        "pressure": latest.get('pressure', 0),
        "shock": latest.get('shock', 0),
        "gyro_x": latest.get('gyro_x', 0),
        "gyro_y": latest.get('gyro_y', 0),
        "gyro_z": latest.get('gyro_z', 0),
        "mic": latest.get('mic', 0),
        "entropy": latest.get('entropy', 0),
        "m2r": latest.get('m2r', 0),
        "android_mag": latest.get('android_mag', 0),
        "android_loss": latest.get('android_loss', 0),
        "android_entropy": latest.get('android_entropy', 0),
        "android_m2r": latest.get('android_m2r', 0),
        "gps_lat": latest.get('gps_lat', 0),
        "gps_lng": latest.get('gps_lng', 0),
        "gps_alt": latest.get('gps_alt', 0),
        "gps_sats": latest.get('gps_sats', 0),
        "csv_processed": datetime.now().isoformat(),
        "source": "beacon_csv"
    })
    
    atomic_write(DEVICE_LOG_PATH, current)
    
    # Дополнительно можно сохранить все записи в отдельный файл для глубокого обучения
    all_records_path = os.path.join(RAW_LOGS_DIR, "beacon_all_records.json")
    try:
        existing = []
        if os.path.exists(all_records_path):
            with open(all_records_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.extend(records)
        # Ограничиваем размер (например, последние 10000 записей)
        if len(existing) > 10000:
            existing = existing[-10000:]
        atomic_write(all_records_path, existing)
    except Exception as e:
        logger.error(f"Ошибка сохранения всех записей: {e}")
    
    # Перемещаем обработанный файл в архив
    base = os.path.basename(filepath)
    archive_path = os.path.join(CSV_ARCHIVE_DIR, base)
    try:
        shutil.move(filepath, archive_path)
        logger.info(f"CSV перемещён в архив: {archive_path}")
    except Exception as e:
        logger.error(f"Ошибка перемещения файла: {e}")

def scan_csv_files():
    """Сканирует MODEL_ZOO_DIR на наличие файлов janus_beacon_log.csv и обрабатывает их."""
    for filename in os.listdir(MODEL_ZOO_DIR):
        if filename == "janus_beacon_log.csv" or (filename.endswith(".csv") and "beacon" in filename.lower()):
            filepath = os.path.join(MODEL_ZOO_DIR, filename)
            if os.path.isfile(filepath):
                process_csv_file(filepath)

# ------------------------------------------------------------
# КЛАСС TACHYON FIELD (модернизированный для обучения на CSV)
# ------------------------------------------------------------
class TachyonField:
    def __init__(self, lead_factor=1.8):
        self.prev_val = None
        self.prev_prev_val = None
        self.lead = lead_factor
        self.history = []  # история для обучения

    def step(self, current_val):
        if self.prev_val is None:
            self.prev_val = current_val
            self.prev_prev_val = current_val
            return current_val, 0.0, 0.0

        velocity = current_val - self.prev_val
        acceleration = current_val - 2 * self.prev_val + self.prev_prev_val
        predicted = current_val + velocity * self.lead + 0.5 * acceleration

        self.prev_prev_val = self.prev_val
        self.prev_val = current_val

        return predicted, velocity, acceleration

    def update_from_history(self, records: List[Dict]):
        """
        Обучает поле Тахиона на исторических данных (энтропия, f1, f2, и т.д.)
        Простая линейная регрессия для корректировки lead_factor.
        """
        if len(records) < 10:
            return
        # Берём энтропию как основную метрику
        entropies = [r.get('entropy', 0) for r in records if 'entropy' in r]
        if len(entropies) < 5:
            return
        # Ищем периоды ускорения
        diffs = [entropies[i] - entropies[i-1] for i in range(1, len(entropies))]
        if not diffs:
            return
        avg_acc = sum(diffs[-5:]) / min(5, len(diffs))
        # Корректируем lead_factor
        if avg_acc > 0.02:
            self.lead = min(3.0, self.lead + 0.02)
        elif avg_acc < -0.02:
            self.lead = max(1.0, self.lead - 0.01)

# ------------------------------------------------------------
# ОСНОВНОЙ ЦИКЛ МОСТА
# ------------------------------------------------------------
async def bridge_loop():
    mem = JanusMemory(1488, 432.0, 439.83, 1.0)
    field = TachyonField(lead_factor=1.8)
    
    # Пытаемся открыть COM-порт (если не удаётся, работаем только с CSV)
    ser = None
    try:
        ser = serial.Serial('COM3', 115200, timeout=0.1)
        logger.info("[*] COM3 открыт. Ожидание данных...")
    except Exception as e:
        logger.warning(f"COM-порт недоступен: {e}. Работаем только с CSV-файлами.")
    
    logger.info("[*] TACHYON BRIDGE v2.0 запущен. Обработка CSV и COM...")
    loop = asyncio.get_event_loop()
    
    # Таймер для периодического сканирования CSV
    last_csv_scan = 0
    CSV_SCAN_INTERVAL = 10  # секунд

    while True:
        now = time.time()
        if now - last_csv_scan > CSV_SCAN_INTERVAL:
            scan_csv_files()
            last_csv_scan = now

        # 1. Читаем квоту GPU
        gpu_allowed, time_left = check_gpu_ticket()
        
        # 2. Выбираем вычислительный вектор
        if gpu_allowed:
            compute_device = "CUDA"
            logger.debug(f"[⚡] GPU свободен. Окно: {time_left:.2f}с")
            # TODO: Здесь можно вызвать тяжёлую нейросеть / семантический поиск
        else:
            compute_device = "CPU"

        # 3. Работа с COM-портом (если доступен)
        if ser and ser.in_waiting:
            line = await loop.run_in_executor(None, ser.readline)
            line = line.decode(errors='ignore').strip()
            
            if line.startswith("ID:1488"):
                try:
                    parts = {p.split(':')[0]: p.split(':')[1] for p in line.split('|')}
                    entropy = float(parts.get('E', 0))
                except Exception:
                    continue

                # Читаем состояние ядра
                core_score, core_velocity, core_acceleration = 0, 0, 0
                if os.path.exists(CORE_STATE_PATH):
                    try:
                        with open(CORE_STATE_PATH, 'r') as f:
                            c_data = json.load(f)
                            core_score = c_data.get('score', 0)
                            core_velocity = c_data.get('velocity', 0)
                            core_acceleration = c_data.get('acceleration', 0)
                    except:
                        pass

                # Расчет поля Тахиона
                predicted, velocity, acceleration = field.step(entropy)

                # Обратная связь с Маяком
                if acceleration < -0.1 and core_acceleration < 0:
                    mem.gain_control = max(0.1, mem.gain_control - 0.05)
                elif velocity > 0.05 and core_velocity > 0:
                    mem.gain_control = min(5.0, mem.gain_control + 0.1)

                if predicted < entropy:
                    field.lead = min(3.0, field.lead + 0.05)
                else:
                    field.lead = max(1.0, field.lead - 0.02)

                # Отправка команды
                cmd = f"SET:{mem.f1:.2f}:{mem.f2:.2f}:{mem.gain_control:.2f}\n"
                await loop.run_in_executor(None, ser.write, cmd.encode("utf-8"))

                # Логирование
                log_data = {
                    "entropy": entropy,
                    "predicted_entropy": predicted,
                    "velocity": velocity,
                    "acceleration": acceleration,
                    "core_velocity": core_velocity,
                    "core_acceleration": core_acceleration,
                    "core_score": core_score,
                    "f1": mem.f1,
                    "gain": mem.gain_control,
                    "lead": field.lead,
                    "active_device": compute_device,
                    "timestamp": time.time()
                }
                atomic_write(DEVICE_LOG_PATH, log_data)

        # 4. Если CSV-файлов нет, ждём немного
        await asyncio.sleep(0.02)

# ------------------------------------------------------------
# ТОЧКА ВХОДА
# ------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(RAW_LOGS_DIR, "bridge.log")),
            logging.StreamHandler()
        ]
    )
    
    try:
        asyncio.run(bridge_loop())
    except KeyboardInterrupt:
        logger.info("[!] Работа моста завершена пользователем.")
    except Exception as e:
        logger.critical(f"FATAL BRIDGE ERROR: {e}", exc_info=True)