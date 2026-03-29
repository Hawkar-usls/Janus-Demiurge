# janus_genesis/device_manager.py
"""
Универсальный менеджер внешних устройств (Android, M5Stack, Cardputer, камера и т.д.)
Поддерживает:
- Чтение из COM-портов (Windows) по последовательному протоколу (JSON-строки)
- Чтение из файлов (например, device_data.json от Android)
- Чтение из HTTP/WebSocket (для Wi-Fi устройств)
- Автоматическое обнаружение и переподключение
"""

import os
import json
import time
import threading
import serial
import serial.tools.list_ports
import requests
import logging
from typing import Dict, Any, List

logger = logging.getLogger("JANUS.DEVICE")

# Конфигурация
COM_BAUDRATES = [115200, 9600, 57600, 38400]
DEVICE_DATA_FILE = "E:/Janus_BFaiN/raw_logs/device_data.json"  # путь к файлу от Android
HTTP_ENDPOINTS = [
    "http://192.168.4.1:80/data",   # пример для M5Stack AtomS3R-M12
]

# Порты, которые не нужно пытаться открывать (например, COM1 обычно занят системой)
IGNORED_COM_PORTS = ["COM1"]  # можно добавить "COM3", если он не используется

class DeviceDriver:
    """Базовый класс для драйвера устройства."""
    def __init__(self, name: str):
        self.name = name
        self.last_data: Dict[str, Any] = {}
        self.last_update = 0.0
        self.running = True

    def update(self) -> Dict[str, Any]:
        """Обновить данные с устройства. Возвращает словарь."""
        raise NotImplementedError

    def stop(self):
        self.running = False


class SerialDeviceDriver(DeviceDriver):
    """Драйвер для устройств, подключённых по COM-порту (JSON-строки)."""
    def __init__(self, port: str, baudrate: int = 115200, name: str = None):
        super().__init__(name or f"COM_{port}")
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self._last_attempt = 0
        self._attempt_interval = 30.0  # секунд между попытками
        self._error_reported = False
        self._connect()

    def _connect(self):
        now = time.time()
        if now - self._last_attempt < self._attempt_interval:
            return
        self._last_attempt = now
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info(f"✅ Подключён COM-порт {self.port} ({self.baudrate} бод)")
            self._error_reported = False
        except Exception as e:
            if not self._error_reported:
                logger.warning(f"⚠️ Не удалось подключиться к {self.port}: {e}")
                self._error_reported = True
            self.ser = None

    def update(self) -> Dict[str, Any]:
        if not self.ser or not self.ser.is_open:
            self._connect()
            return self.last_data

        try:
            # Читаем строки до \n
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    data = json.loads(line)
                    self.last_data = data
                    self.last_update = time.time()
                    return data
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Ошибка чтения {self.port}: {e}")
            self.ser = None
        return self.last_data

    def stop(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


class FileDeviceDriver(DeviceDriver):
    """Драйвер для чтения данных из файла (как Android)."""
    def __init__(self, file_path: str, name: str = "AndroidFile"):
        super().__init__(name)
        self.file_path = file_path
        self.last_mtime = 0

    def update(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            return self.last_data
        mtime = os.path.getmtime(self.file_path)
        if mtime == self.last_mtime:
            return self.last_data
        self.last_mtime = mtime
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Если файл содержит список, берём последнюю запись
            if isinstance(data, list):
                data = data[-1] if data else {}
            self.last_data = data
            self.last_update = time.time()
        except Exception as e:
            logger.error(f"Ошибка чтения {self.file_path}: {e}")
        return self.last_data


class HttpDeviceDriver(DeviceDriver):
    """Драйвер для устройств, работающих по HTTP."""
    def __init__(self, url: str, interval: float = 2.0, name: str = None):
        super().__init__(name or f"HTTP_{url}")
        self.url = url
        self.interval = interval
        self._last_poll = 0

    def update(self) -> Dict[str, Any]:
        now = time.time()
        if now - self._last_poll < self.interval:
            return self.last_data
        self._last_poll = now
        try:
            resp = requests.get(self.url, timeout=2)
            if resp.status_code == 200:
                self.last_data = resp.json()
                self.last_update = now
        except Exception as e:
            logger.debug(f"Ошибка HTTP запроса к {self.url}: {e}")
        return self.last_data


class DeviceManager:
    """Управляет всеми драйверами устройств."""
    def __init__(self):
        self.drivers: List[DeviceDriver] = []
        self._init_drivers()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logger.info("🔄 DeviceManager запущен")

    def _init_drivers(self):
        # 1. COM-порты
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.device in IGNORED_COM_PORTS:
                logger.debug(f"Порт {port.device} игнорируется (в списке IGNORED_COM_PORTS)")
                continue
            # Для каждого порта создаём драйверы для разных скоростей, но без немедленной проверки
            for baud in COM_BAUDRATES:
                self.drivers.append(SerialDeviceDriver(port.device, baudrate=baud, name=f"{port.device}_{baud}"))

        # 2. Файл от Android
        if os.path.exists(DEVICE_DATA_FILE):
            self.drivers.append(FileDeviceDriver(DEVICE_DATA_FILE, name="AndroidFile"))

        # 3. HTTP-эндпоинты (M5Stack и т.д.)
        for url in HTTP_ENDPOINTS:
            self.drivers.append(HttpDeviceDriver(url, interval=1.0))

        logger.info(f"📡 Зарегистрировано {len(self.drivers)} драйверов устройств")

    def _update_loop(self):
        while True:
            for driver in self.drivers:
                try:
                    driver.update()
                except Exception as e:
                    logger.debug(f"Ошибка в драйвере {driver.name}: {e}")
            time.sleep(0.5)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Возвращает словарь с данными всех устройств."""
        result = {}
        for driver in self.drivers:
            if driver.last_data:
                result[driver.name] = driver.last_data
        return result

    def stop(self):
        for driver in self.drivers:
            driver.stop()

# Глобальный экземпляр
device_manager = DeviceManager()