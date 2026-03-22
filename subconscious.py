#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subconscious — подсознание Януса.
Содержит модули:
- Chronos: извлечение уроков из прошлых бэкапов
- Hypnos: сны (случайные комбинации)
- Nebuchadnezzar: хаотические мутации графа
- Ouroboros: самомодификация кода
"""

import os
import json
import random
import time
import shutil
import ast
import hashlib
import logging
import aiosqlite
from datetime import datetime

logger = logging.getLogger("SUBCONSCIOUS")

class Chronos:
    def __init__(self, db_path="janus.db", backup_dir="backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)

    async def scavenge_past(self, engine):
        """Извлекает случайный урок из старого бэкапа и добавляет в память."""
        backups = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.db')])
        if not backups:
            return
        target_db = os.path.join(self.backup_dir, random.choice(backups))
        try:
            async with aiosqlite.connect(target_db) as old_db:
                cursor = await old_db.execute("SELECT content FROM thoughts ORDER BY RANDOM() LIMIT 1")
                row = await cursor.fetchone()
                if row:
                    await engine.memory.remember("ANCIENT_WISDOM", f"Урок прошлого: {row[0]}")
                    logger.info(f"⏳ ХРОНОС: Извлечен урок прошлого из бэкапа.")
        except Exception as e:
            logger.error(f"ХРОНОС ошибка: {e}")

class Hypnos:
    def __init__(self, engine):
        self.engine = engine

    async def assimilate(self):
        """Генерирует «сон» — случайную конфигурацию и добавляет в память как идею."""
        config = self.engine.memory._random_config()
        await self.engine.memory.remember("DREAM", f"Сон: {config}")
        logger.info(f"🌙 ГИПНОС: Янусу приснилась новая идея.")

class Nebuchadnezzar:
    def __init__(self, engine):
        self.engine = engine

    async def mutate(self, nodes, links):
        """Создаёт хаотическую связь между случайными узлами графа."""
        if len(nodes) < 2:
            return False
        n1, n2 = random.sample(nodes, 2)
        if not any(l['source'] == n1['id'] and l['target'] == n2['id'] for l in links):
            links.append({"source": n1['id'], "target": n2['id'], "reason": "CHAOS_LINK"})
            logger.info(f"🌀 НЕБУХАДНЕЦЦАР: Создана хаотическая связь.")
            return True
        return False

class Ouroboros:
    def __init__(self, engine, updates_dir="updates"):
        self.engine = engine
        self.updates_dir = updates_dir
        os.makedirs(updates_dir, exist_ok=True)

    async def attempt_modular_genesis(self):
        """Генерирует новый модуль-плагин с помощью ИИ и сохраняет в modules."""
        prompt = "TASK: Напиши модуль 'Plugin' (Python) с функцией async run(core). Только код."
        try:
            code = await self.engine.face.invoke(prompt, explicit_model=self.engine.navigator.get_smart())
            code = self._clean_code(code)
            if "run" not in code:
                return
            mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
            os.makedirs(mod_path, exist_ok=True)
            full_path = os.path.join(mod_path, f"gen_{int(time.time())}.py")
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)
            logger.info(f"🦖 УРОБОРОС: Сгенерирован новый модуль: {full_path}")
        except Exception as e:
            logger.error(f"УРОБОРОС ошибка: {e}")

    def _clean_code(self, raw_text):
        if "```python" in raw_text:
            return raw_text.split("```python")[1].split("```")[0].strip()
        if "```" in raw_text:
            return raw_text.split("```")[1].split("```")[0].strip()
        return raw_text.strip()