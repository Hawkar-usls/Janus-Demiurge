# data_loader.py
import os
import json
import re
import numpy as np
import logging
import time
from collections import Counter
from config import VOCAB_SIZE, RAW_LOGS_DIR

logger = logging.getLogger("JANUS")

CONFIG = {
    'device_data_file': os.path.join(RAW_LOGS_DIR, "device_data.json"),
    'cache_size': 2000,
    'seq_len': 64,
    'num_sequences': 128
}

def repair_json(content: str) -> str:
    """Пытается восстановить повреждённый JSON."""
    # Удаляем управляющие символы
    content = re.sub(r'[\x00-\x1f\x7f]', '', content)
    if content.startswith('\ufeff'):
        content = content[1:]
    # Исправляем незакавыченные ключи
    content = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
    # Исправляем лишние запятые
    content = re.sub(r',\s*}', '}', content)
    content = re.sub(r',\s*]', ']', content)
    # Незакрытые скобки
    open_braces = content.count('{')
    close_braces = content.count('}')
    if open_braces > close_braces:
        content += '}' * (open_braces - close_braces)
    open_brackets = content.count('[')
    close_brackets = content.count(']')
    if open_brackets > close_brackets:
        content += ']' * (open_brackets - close_brackets)
    # Исправляем одинарные кавычки
    content = re.sub(r"'([^']*)'", r'"\1"', content)
    return content

def _safe_remove_file(filepath: str, max_attempts=3):
    """Безопасное удаление файла с повторными попытками."""
    for attempt in range(max_attempts):
        try:
            os.remove(filepath)
            logger.info(f"Файл {filepath} успешно удалён.")
            return True
        except PermissionError:
            logger.warning(f"Файл {filepath} занят, попытка {attempt+1}/{max_attempts}...")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Не удалось удалить {filepath}: {e}")
            return False
    logger.error(f"Не удалось удалить {filepath} после {max_attempts} попыток. Оставляем файл.")
    return False

def load_real_data(num_sequences: int = CONFIG['num_sequences'],
                   seq_len: int = CONFIG['seq_len']):
    """
    Загружает реальные данные из device_data.json и возвращает последовательности токенов.
    При ошибках генерирует фальшивые данные. При пустом файле делает повторные попытки.
    """
    if not os.path.exists(CONFIG['device_data_file']):
        logger.debug(f"Файл {CONFIG['device_data_file']} не найден, генерируем фальшивые данные.")
        return _generate_fake_data(num_sequences, seq_len), {}

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Проверяем размер файла, если пустой, ждём
            if os.path.getsize(CONFIG['device_data_file']) == 0:
                if attempt < max_attempts - 1:
                    logger.debug(f"Файл {CONFIG['device_data_file']} пуст, попытка {attempt+1}/{max_attempts}, ждём 0.1 сек")
                    time.sleep(0.1)
                    continue
                else:
                    logger.warning(f"Файл {CONFIG['device_data_file']} пуст после {max_attempts} попыток, генерируем фальшивые данные.")
                    return _generate_fake_data(num_sequences, seq_len), {}
            with open(CONFIG['device_data_file'], 'r', encoding='utf-8') as f:
                raw = f.read()
            if not raw.strip():
                if attempt < max_attempts - 1:
                    logger.debug(f"Файл {CONFIG['device_data_file']} содержит пустую строку, попытка {attempt+1}/{max_attempts}")
                    time.sleep(0.1)
                    continue
                else:
                    logger.warning(f"Файл {CONFIG['device_data_file']} пуст после {max_attempts} попыток, генерируем фальшивые данные.")
                    return _generate_fake_data(num_sequences, seq_len), {}
            repaired = repair_json(raw)
            content = json.loads(repaired)
            break  # успешно
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга {CONFIG['device_data_file']} после восстановления (попытка {attempt+1}): {e}. Удаляем файл и генерируем фальшивые данные.")
            _safe_remove_file(CONFIG['device_data_file'])
            return _generate_fake_data(num_sequences, seq_len), {}
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при чтении {CONFIG['device_data_file']} (попытка {attempt+1}): {e}. Генерируем фальшивые данные.")
            return _generate_fake_data(num_sequences, seq_len), {}
    else:
        # если не удалось прочитать после всех попыток
        logger.warning(f"Не удалось прочитать {CONFIG['device_data_file']} после {max_attempts} попыток, генерируем фальшивые данные.")
        return _generate_fake_data(num_sequences, seq_len), {}

    if isinstance(content, dict):
        all_records = [content]
    elif isinstance(content, list):
        all_records = content
    else:
        logger.warning("Неизвестный формат данных в device_data.json. Генерируем фальшивые данные.")
        return _generate_fake_data(num_sequences, seq_len), {}

    if not all_records:
        logger.warning("Нет данных в device_data.json. Генерируем фальшивые данные.")
        return _generate_fake_data(num_sequences, seq_len), {}

    recent_records = all_records[-CONFIG['cache_size']:] if len(all_records) > CONFIG['cache_size'] else all_records

    history = []
    device_counter = Counter()
    for rec in recent_records:
        device_id = rec.get('device_id', 'unknown')
        d = rec.get('data', {})
        # Проверяем, что d — словарь (игнорируем строки)
        if not isinstance(d, dict):
            logger.debug(f"Пропуск записи от {device_id}: data не словарь")
            continue
        t = d.get('temperature', 20.0)
        p = d.get('pressure', 1013.0)
        raw_accel = d.get('accel', [0, 0, 0])
        s = d.get('shock', sum([abs(x) for x in raw_accel]) if isinstance(raw_accel, list) else 0.0)
        m = d.get('micLevel', 0.0)
        e = d.get('entropy', 1.0)
        m2r = d.get('m2r', d.get('m2r_index', 0.0))

        snapshot = [t, p, s, m, e, m2r]
        history.append(snapshot)
        device_counter[device_id] += 1

    if len(history) < seq_len:
        pad_size = seq_len - len(history)
        history = (history * (pad_size // len(history) + 2))[-seq_len:]

    signals = np.array(history, dtype=np.float32)
    for i in range(signals.shape[1]):
        col = signals[:, i]
        min_val, max_val = col.min(), col.max()
        if max_val - min_val > 1e-6:
            signals[:, i] = (col - min_val) / (max_val - min_val)
        else:
            signals[:, i] = 0.5

    combined = signals.mean(axis=1)
    tokens = (combined * (VOCAB_SIZE - 1)).astype(int)

    sequences = []
    max_start = len(tokens) - seq_len
    if max_start <= 0:
        tokens = np.tile(tokens, (seq_len // len(tokens) + 1))[:seq_len]
        max_start = 0
    for _ in range(num_sequences):
        start_idx = np.random.randint(0, max_start + 1) if max_start > 0 else 0
        seq = tokens[start_idx : start_idx + seq_len].tolist()
        sequences.append(seq)

    return sequences, dict(device_counter)

def _generate_fake_data(num_sequences: int, seq_len: int):
    fake_tokens = np.random.randint(0, VOCAB_SIZE, (seq_len * 10,))
    sequences = []
    for _ in range(num_sequences):
        start = np.random.randint(0, len(fake_tokens) - seq_len)
        sequences.append(fake_tokens[start:start + seq_len].tolist())
    return sequences