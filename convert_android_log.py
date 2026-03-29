# convert_android_log.py
import os
import json
import glob
import random
import time
import csv
from datetime import datetime

BASE_DIR = r"E:\Janus_BFaiN"
MODEL_ZOO_DIR = os.path.join(BASE_DIR, "Model_Zoo")
RAW_LOGS_DIR = os.path.join(BASE_DIR, "raw_logs")
OUTPUT_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
LOCK_FILE = OUTPUT_FILE + ".lock"
BEACON_CSV = os.path.join(RAW_LOGS_DIR, "janus_beacon_log.csv")

def acquire_lock(timeout=5):
    start = time.time()
    while os.path.exists(LOCK_FILE):
        if time.time() - start > timeout:
            print("Таймаут ожидания блокировки, продолжаем...")
            break
        time.sleep(0.1)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def parse_beacon_csv(csv_path):
    """Парсит CSV от маяка (Cardputer) и возвращает список записей."""
    records = []
    if not os.path.exists(csv_path):
        return records
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            # Определяем разделитель (запятая или точка с запятой)
            sample = f.read(1024)
            f.seek(0)
            delimiter = ',' if ',' in sample else ';'
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                # Пытаемся привести значения к float/int
                def safe_float(x):
                    try:
                        return float(x.replace(',', '.')) if x else 0.0
                    except:
                        return 0.0
                data = {}
                # Магнитные поля
                for m in ['mag_x', 'magX', 'x']:
                    if m in row:
                        data['mag_x'] = safe_float(row[m])
                        break
                for m in ['mag_y', 'magY', 'y']:
                    if m in row:
                        data['mag_y'] = safe_float(row[m])
                        break
                for m in ['mag_z', 'magZ', 'z']:
                    if m in row:
                        data['mag_z'] = safe_float(row[m])
                        break
                # Другие поля
                for key in ['loss', 'entropy', 'm2r', 'purity', 'temperature', 'pressure']:
                    if key in row:
                        data[key] = safe_float(row[key])
                # Если есть timestamp
                ts = row.get('timestamp', row.get('time', ''))
                if not ts:
                    ts = datetime.now().isoformat()
                record = {
                    "device_id": "cardputer_beacon",
                    "timestamp": ts,
                    "data": data
                }
                records.append(record)
    except Exception as e:
        print(f"Ошибка парсинга CSV {csv_path}: {e}")
    return records

def main():
    if not acquire_lock():
        print("Не удалось получить блокировку, выход.")
        return

    try:
        # 1. Собираем данные из model_zoo
        json_files = glob.glob(os.path.join(MODEL_ZOO_DIR, "*.json"))
        print(f"Найдено {len(json_files)} JSON файлов")

        data = []
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)

                cycle = content.get("cycle", 0)
                loss = content.get("loss", 5.5)
                extra = content.get("extra", {})
                entropy = extra.get("entropy", random.uniform(0.5, 1.5))
                m2r = extra.get("m2r", random.uniform(0, 20))
                temperature = extra.get("temperature", random.uniform(20, 40))
                purity = extra.get("purity_score", random.uniform(0, 100))

                mag_x = m2r * random.uniform(-5, 5)
                mag_y = m2r * random.uniform(-5, 5)
                mag_z = m2r * random.uniform(-5, 5)

                record = {
                    "device_id": "android_01",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "temperature": temperature,
                        "pressure": random.uniform(1000, 1020),
                        "mag_x": mag_x,
                        "mag_y": mag_y,
                        "mag_z": mag_z,
                        "loss": loss,
                        "entropy": entropy,
                        "m2r": m2r,
                        "purity": purity,
                        "cycle": cycle
                    }
                }
                data.append(record)
            except Exception as e:
                print(f"Ошибка обработки {file_path}: {e}")

        # 2. Добавляем данные из маяка (Cardputer)
        beacon_records = parse_beacon_csv(BEACON_CSV)
        print(f"Найдено {len(beacon_records)} записей из маяка")
        data.extend(beacon_records)

        # 3. Ограничиваем размер (последние 2000 записей)
        if len(data) > 2000:
            data = data[-2000:]

        # 4. Атомарная запись с проверкой
        tmp_file = OUTPUT_FILE + ".tmp"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Проверка записанного файла
            with open(tmp_file, 'r', encoding='utf-8') as f:
                json.load(f)
            os.replace(tmp_file, OUTPUT_FILE)
            print(f"Сохранено {len(data)} записей в {OUTPUT_FILE}")
        except Exception as e:
            print(f"Ошибка записи: {e}")
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    finally:
        release_lock()

if __name__ == "__main__":
    main()