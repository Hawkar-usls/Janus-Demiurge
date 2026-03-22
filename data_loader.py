import os
import json
import numpy as np
import logging
from collections import Counter
from config import VOCAB_SIZE, RAW_LOGS_DIR

logger = logging.getLogger("JANUS")

CONFIG = {
    'device_data_file': os.path.join(RAW_LOGS_DIR, "device_data.json"),
    'cache_size': 2000,
    'seq_len': 64,
    'num_sequences': 128
}


def load_real_data(num_sequences: int = CONFIG['num_sequences'],
                   seq_len: int = CONFIG['seq_len']):
    """
    Загружает реальные данные из device_data.json и возвращает последовательности токенов.
    """
    if not os.path.exists(CONFIG['device_data_file']):
        raise FileNotFoundError(f"Файл {CONFIG['device_data_file']} не найден.")

    try:
        with open(CONFIG['device_data_file'], 'r', encoding='utf-8') as f:
            content = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Файл данных пуст или повреждён")

    if isinstance(content, dict):
        all_records = [content]
    elif isinstance(content, list):
        all_records = content
    else:
        raise ValueError("Неизвестный формат данных")

    if not all_records:
        raise ValueError("Нет данных в device_data.json")

    recent_records = all_records[-CONFIG['cache_size']:] if len(all_records) > CONFIG['cache_size'] else all_records

    history = []
    device_counter = Counter()
    for rec in recent_records:
        device_id = rec.get('device_id', 'unknown')
        d = rec.get('data', {})
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
    for _ in range(num_sequences):
        start_idx = np.random.randint(0, max_start + 1) if max_start > 0 else 0
        seq = tokens[start_idx : start_idx + seq_len].tolist()
        sequences.append(seq)

    return sequences, dict(device_counter)