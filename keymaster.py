#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KEYMASTER BRIDGE — связь между ArtMoney и M5-устройством.
Принимает данные по Serial, управляет параметрами ArtMoney через Magic-память.
"""

import asyncio
import ctypes
import json
import logging
import os
import subprocess
import serial
import sys
import signal
from typing import Dict, Any

# ========== КОНФИГУРАЦИЯ ==========
CONFIG = {
    'am_path': os.environ.get('AM_PATH', r"C:\ArtMoney\am818.exe"),
    'log_dir': os.environ.get('LOG_DIR', r"E:\Janus_BFaiN\raw_logs"),
    'serial_port': os.environ.get('SERIAL_PORT', 'COM3'),
    'baudrate': int(os.environ.get('BAUDRATE', 115200)),
    'timeout': float(os.environ.get('SERIAL_TIMEOUT', 0.1)),
    'device_id': os.environ.get('DEVICE_ID', 'm5_node_04'),
    'magic': 1488,
    'default_f1': 432.0,
    'default_f2': 439.83,
    'default_gain': 1.0,
    'overload_threshold': 80.0,
    'resonance_threshold': 0.5,
    'overload_f1': 7.83,
    'overload_gain': 0.5,
    'resonance_f1': 432.0,
    'resonance_gain': 1.2,
    'sleep_interval': 0.02
}

# Настройка логирования
logger = logging.getLogger("JANUS.KEYMASTER")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

# Пути
LOG_PATH = os.path.join(CONFIG['log_dir'], "device_data.json")
TEMP_PATH = LOG_PATH + ".tmp"
os.makedirs(CONFIG['log_dir'], exist_ok=True)

# Структура для ArtMoney (Magic 1488)
class JanusMemory(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_int),
        ("f1", ctypes.c_float),
        ("f2", ctypes.c_float),
        ("gain_control", ctypes.c_float)
    ]

mem = JanusMemory(CONFIG['magic'], CONFIG['default_f1'], CONFIG['default_f2'], CONFIG['default_gain'])
mem_lock = asyncio.Lock()  # для потокобезопасного доступа

async def keymaster_logic(ser: serial.Serial, e_val: float, m2r_val: float) -> None:
    """
    Интеллект Ключника: управление параметрами ArtMoney.
    """
    async with mem_lock:
        if m2r_val > CONFIG['overload_threshold']:
            mem.f1 = CONFIG['overload_f1']
            mem.gain_control = CONFIG['overload_gain']
            logger.debug(f"Защита: m2r={m2r_val:.2f} -> f1={mem.f1}, gain={mem.gain_control}")
        elif e_val < CONFIG['resonance_threshold']:
            mem.f1 = CONFIG['resonance_f1']
            mem.gain_control = CONFIG['resonance_gain']
            logger.debug(f"Резонанс: e={e_val:.2f} -> f1={mem.f1}, gain={mem.gain_control}")
        # else оставляем предыдущие значения

        cmd = f"SET:{mem.f1:.2f}:{mem.f2:.2f}:{mem.gain_control:.2f}\n"
        # Запись в COM-порт выполняется в executor, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ser.write, cmd.encode('utf-8'))

async def run_bridge() -> None:
    # Запускаем ArtMoney, если он есть
    if os.path.exists(CONFIG['am_path']):
        try:
            subprocess.Popen([CONFIG['am_path']], shell=True)
            logger.info("ArtMoney запущен")
        except Exception as e:
            logger.error(f"Не удалось запустить ArtMoney: {e}")
    else:
        logger.warning(f"ArtMoney не найден по пути {CONFIG['am_path']}")

    # Открываем Serial
    try:
        ser = serial.Serial(CONFIG['serial_port'], CONFIG['baudrate'], timeout=CONFIG['timeout'])
        logger.info(f"Serial порт {CONFIG['serial_port']} открыт")
    except Exception as e:
        logger.error(f"Не удалось открыть {CONFIG['serial_port']}: {e}")
        return

    loop = asyncio.get_event_loop()
    logger.info("КЛЮЧНИК ЗАПУЩЕН. Ожидание данных...")

    # Флаг для graceful shutdown
    shutdown = False

    def signal_handler():
        nonlocal shutdown
        shutdown = True
        logger.info("Получен сигнал остановки")

    # Регистрируем обработчики сигналов (только в основном потоке)
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        while not shutdown:
            if ser.in_waiting:
                try:
                    line = await loop.run_in_executor(None, ser.readline)
                    line = line.decode(errors='ignore').strip()
                    if line.startswith("ID:1488"):
                        # Парсим строку: ID:1488|E:0.123|M2R:45.6
                        parts = {}
                        for part in line.split('|'):
                            if ':' in part:
                                k, v = part.split(':', 1)
                                parts[k] = v
                        e_val = float(parts.get('E', 0))
                        m2r_val = float(parts.get('M2R', 0))

                        # Формируем JSON для сохранения
                        data_to_save = [{
                            "device_id": CONFIG['device_id'],
                            "data": {
                                "entropy": e_val,
                                "shock": m2r_val,
                                "f1": mem.f1,
                                "micLevel": e_val * 0.5
                            }
                        }]

                        # Атомарная запись
                        try:
                            with open(TEMP_PATH, 'w', encoding='utf-8') as f:
                                json.dump(data_to_save, f)
                            os.replace(TEMP_PATH, LOG_PATH)
                        except Exception as e:
                            logger.error(f"Ошибка записи JSON: {e}")

                        # Управление через ArtMoney
                        await keymaster_logic(ser, e_val, m2r_val)
                except (ValueError, KeyError, json.JSONDecodeError) as e:
                    logger.debug(f"Ошибка обработки строки: {line} - {e}")
                except Exception as e:
                    logger.error(f"Неожиданная ошибка: {e}", exc_info=True)

            await asyncio.sleep(CONFIG['sleep_interval'])

    except asyncio.CancelledError:
        pass
    finally:
        ser.close()
        logger.info("Serial порт закрыт")

def main():
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")

if __name__ == "__main__":
    main()