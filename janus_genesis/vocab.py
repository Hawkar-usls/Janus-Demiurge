# janus_genesis/vocab.py
import unicodedata
import json
import os

def get_vocab(vocab_file="vocab.json"):
    """Загружает словарь из файла или создаёт стандартный."""
    if os.path.exists(vocab_file):
        with open(vocab_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Эмодзи из твоих примеров
        EMOJI_LIST = [
            "\U0001F50D", "\U0001F6E1", "\U0001F9EC", "\u26A0\uFE0F", "\U0001F916",
            "\U0001F4BE", "\U0001F4A1", "\U0001F517", "\u274C", "\u2705",
            "🌀", "📈", "💀", "🔮", "🎭", "⚡", "🏛️", "👁️", "🗣️", "💤"
        ]
        BASIC_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?;:-"
        CYRILLIC = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        ALL_CHARS = EMOJI_LIST + list(BASIC_CHARS) + list(CYRILLIC)
        vocab = []
        seen = set()
        for ch in ALL_CHARS:
            norm = unicodedata.normalize('NFC', ch)
            if norm not in seen:
                seen.add(norm)
                vocab.append(ch)
        # Сохраняем для будущих запусков
        with open(vocab_file, 'w', encoding='utf-8') as f:
            json.dump(vocab, f, ensure_ascii=False, indent=2)
        return vocab