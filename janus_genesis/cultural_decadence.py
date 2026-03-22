# janus_genesis/cultural_decadence.py
"""
Cultural Decadence & Survivorship Corrector.
Превращает неудачные конфигурации в культурное наследие,
борется с ошибкой выжившего, эстетизируя "упадок".
"""

import random
import logging
import numpy as np
from .inventory import Item
from .memes import Meme

logger = logging.getLogger("JANUS.DECADENCE")

class CulturalDecadenceEngine:
    def __init__(self, world, memory, social_engine, language_engine):
        self.world = world
        self.memory = memory          # EvolutionaryMemory
        self.social = social_engine   # SocialLearningEngine
        self.lang = language_engine   # LanguageEngine
        self.decadence_level = 0.5    # уровень декаданса (влияет на частоту артефактов)

    def update(self):
        """Обновление: анализ неудач, создание артефактов, мемов."""
        # Анализируем последние неудачные конфигурации
        recent_failures = [entry for entry in self.memory.decision_log[-100:] if entry['score'] < self.memory.hope_score * 0.7]
        if not recent_failures:
            return

        # Вероятность создания артефакта
        if random.random() < 0.05 * self.decadence_level:
            self._create_artifact_from_failure(random.choice(recent_failures))

        # Вероятность создания мема
        if random.random() < 0.1 * self.decadence_level:
            self._create_meme_from_failure(random.choice(recent_failures))

        # Коррекция стратегии: если много неудач, увеличиваем exploration (борьба с survivorship bias)
        if len(recent_failures) > 20:
            self.memory.strategy["exploration"] = min(0.9, self.memory.strategy.get("exploration", 0.5) + 0.05)
            logger.info("📉 Много неудач – увеличиваем exploration (борьба с survivorship bias).")

        # Постепенное затухание декаданса
        self.decadence_level = max(0.1, self.decadence_level * 0.99)

    def _create_artifact_from_failure(self, failure_entry):
        """Создаёт предмет-артефакт на основе неудачной конфигурации."""
        config = failure_entry['config']
        score = failure_entry['score']
        # Эффекты – усреднение параметров, но с отрицательным знаком? Нет, сделаем полезным.
        effect = {}
        # Превращаем неудачу в полезный бонус: если параметр был слишком большим/маленьким,
        # артефакт даёт противоположный эффект.
        for param, val in config.items():
            if param in ['lr', 'gain', 'temperature']:
                # Обратный эффект: если lr был слишком низкий, артефакт даёт +lr
                # Здесь упрощённо: всегда даём положительный эффект, но с учётом того, что неудача могла быть из-за этого
                # Можно поставить случайно
                effect[param] = random.uniform(0.05, 0.2) if random.random() < 0.5 else -random.uniform(0.05, 0.1)
        name = f"Remnant of Failure (score {score:.2f})"
        item = Item(name, effect, weight=1, value=10, item_type="artifact", unique=True, knowledge=config.copy())
        # Помещаем в инвентарь случайного агента
        if self.world.population:
            agent = random.choice(self.world.population)
            agent.add_item(item)
            logger.info(f"📜 Создан артефакт из неудачи: {name} (эффект: {effect}) передан агенту {agent.id[:4]}")
        return item

    def _create_meme_from_failure(self, failure_entry):
        """Создаёт мем на основе неудачной конфигурации."""
        config = failure_entry['config']
        # Генерируем текст мема через языковую модель
        prompt = f"Create a meme about a failed configuration with lr={config['lr']:.5f}, gain={config['gain']:.2f}, temp={config['temperature']:.2f}"
        meme_text, _ = self.lang.generate(prompt, max_len=20, temperature=0.8, clean=True)
        if meme_text:
            # Добавляем мем в систему мемов
            meme = Meme(meme_text, spread_rate=0.3)
            self.world.memes.memes.append(meme)
            logger.info(f"😈 Создан мем из неудачи: '{meme_text}'")
        return meme_text