#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wormhole_reader.py — читает JSON из wormhole, сохраняет в БД, удаляет файлы.
"""

import os
import json
import hashlib
import asyncio
import random
import logging
from typing import Any, Dict, Optional

import janus_db

logger = logging.getLogger("JANUS.WORMHOLE")

CONFIG = {
    'wormhole_dir': None,  # будет установлен из внешнего конфига
    'visionary_chance': 0.3
}


class WormholeReader:
    def __init__(self, wormhole_dir: str, storyteller: Any, social_engine: Any, visionary: Optional[Any] = None):
        self.wormhole_dir = wormhole_dir
        self.storyteller = storyteller
        self.social = social_engine
        self.visionary = visionary

    def scan_and_process(self) -> None:
        """
        Сканирует wormhole, обрабатывает новые JSON-файлы, удаляет их после обработки.
        """
        if not os.path.exists(self.wormhole_dir):
            return
        for filename in os.listdir(self.wormhole_dir):
            if not filename.endswith('.json'):
                continue
            path = os.path.join(self.wormhole_dir, filename)

            try:
                with open(path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                janus_db.insert_wormhole_artifact(filename, file_hash, data)
                self._process_one(data, filename)
                os.remove(path)
                logger.info(f"🗑️ Файл {filename} обработан и удалён")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Ошибка обработки {filename}: {e}", exc_info=True)

    def _process_one(self, data: Dict[str, Any], filename: str) -> None:
        logger.info(f"📦 Обработка {filename}...")

        text = None
        if isinstance(data, dict):
            for key in ['label', 'text', 'description', 'insight', 'dream', 'message']:
                if key in data and isinstance(data[key], str):
                    text = data[key]
                    break
            if text is None and 'data' in data and isinstance(data['data'], dict):
                for key in ['label', 'text', 'description']:
                    if key in data['data'] and isinstance(data['data'][key], str):
                        text = data['data'][key]
                        break
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                for key in ['label', 'text', 'description']:
                    if key in first and isinstance(first[key], str):
                        text = first[key]
                        break

        if text:
            try:
                self.storyteller.lang.train_step(text, lr=0.01)
                logger.info(f"   📖 Языковая модель обучена на тексте: {text[:50]}...")
                self.social.add_meme(text)
            except Exception as e:
                logger.error(f"Ошибка при обучении языковой модели: {e}")

            if self.visionary and random.random() < CONFIG['visionary_chance']:
                context = {
                    'event_type': 'WORMHOLE',
                    'data': data,
                    'filename': filename,
                    'text': text
                }
                try:
                    prompt = self.storyteller.generate_story(context, max_len=50)
                    asyncio.create_task(self.visionary.on_event("WORMHOLE", {"prompt": prompt}, None))
                except Exception as e:
                    logger.error(f"Ошибка генерации истории: {e}")
        else:
            logger.warning(f"   ⚠️ Не удалось извлечь текст из {filename}")