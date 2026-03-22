import os
import json
import glob
import random
from datetime import datetime

# Пути
BASE_DIR = r"E:\Janus_BFaiN"
MODEL_ZOO_DIR = os.path.join(BASE_DIR, "Model_Zoo")
RAW_LOGS_DIR = os.path.join(BASE_DIR, "raw_logs")
OUTPUT_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")

# Собираем все JSON-файлы из Model_Zoo
json_files = glob.glob(os.path.join(MODEL_ZOO_DIR, "*.json"))
print(f"Найдено {len(json_files)} файлов")

data = []
for file_path in json_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        # Извлекаем нужные поля
        cycle = content.get("cycle", 0)
        loss = content.get("loss", 5.5)
        weights = content.get("weights", {})
        extra = content.get("extra", {})
        
        # Генерируем метрики (можно использовать реальные из extra, если есть)
        # В твоих файлах extra содержит loss, entropy, m2r
        entropy = extra.get("entropy", random.uniform(0.5, 1.5))
        m2r = extra.get("m2r", random.uniform(0, 20))
        
        # Создаём запись в формате device_data.json
        record = {
            "device_id": "android_01",
            "timestamp": datetime.now().isoformat(),  # можно не заморачиваться
            "data": {
                "temperature": random.uniform(20, 30),
                "pressure": random.uniform(1000, 1020),
                "mag_x": random.uniform(-50, 50),
                "mag_y": random.uniform(-50, 50),
                "mag_z": random.uniform(-50, 50),
                "loss": loss,
                "entropy": entropy,
                "m2r": m2r
            }
        }
        data.append(record)
        
    except Exception as e:
        print(f"Ошибка обработки {file_path}: {e}")

# Ограничим последними 1000 (как в data_loader.py)
if len(data) > 1000:
    data = data[-1000:]

# Сохраняем
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print(f"Сохранено {len(data)} записей в {OUTPUT_FILE}")