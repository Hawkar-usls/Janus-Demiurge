# nas_client.py
import json
import os
import sqlite3
from config import DB_PATH, RAW_LOGS_DIR

class NASClient:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.nas_results_file = os.path.join(RAW_LOGS_DIR, "nas_results.json")
        self.ensure_table()

    def ensure_table(self):
        """Создаёт таблицу nas_results, если её нет."""
        if os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('''
                    CREATE TABLE IF NOT EXISTS nas_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config TEXT NOT NULL,
                        score REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[NAS] Ошибка создания таблицы: {e}")

    def get_best_configs(self, limit=3):
        """Получает лучшие конфигурации из NAS (сначала из БД, потом из JSON)."""
        configs = []
        # Пытаемся из SQLite
        if os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('''
                    SELECT config, score FROM nas_results 
                    ORDER BY score DESC LIMIT ?
                ''', (limit,))
                rows = c.fetchall()
                for config_json, score in rows:
                    conf = json.loads(config_json)
                    conf['score'] = score
                    configs.append(conf)
                conn.close()
            except Exception as e:
                print(f"[NAS] Ошибка чтения БД: {e}")

        # Если нет в БД, читаем из JSON (например, лучший конфиг из NAS)
        if not configs and os.path.exists(self.nas_results_file):
            try:
                with open(self.nas_results_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        configs = data[:limit]
                    else:
                        configs = [data]
            except Exception as e:
                print(f"[NAS] Ошибка чтения JSON: {e}")
        return configs