# janus_genesis/storyteller.py
"""
STORYTELLER — автономный генератор историй на основе микро-модели.
"""

import os
import json
import random
import logging
from typing import Dict, Any, Optional, Tuple

from .language_model import LanguageEngine
from .social_learning import SocialLearningEngine
from .vocab import get_vocab

logger = logging.getLogger("JANUS")

CONFIG = {
    'stories_file': 'stories.json',
    'model_path': 'storyteller_model.pkl',
    'vocab_file': 'vocab.json',
    'max_len': 50,
    'temperature': 0.9,
    'train_lr': 0.01,
    'save_every': 10,
    'max_retries': 3,
    'reward_threshold': 0.6,
    'failures_to_remember': 100
}


class Storyteller:
    def __init__(self, stories_file=CONFIG['stories_file'], model_path=CONFIG['model_path'],
                 social_engine=None, vocab_file=CONFIG['vocab_file']):
        self.stories_file = stories_file
        self.model_path = model_path
        self.social = social_engine
        self.stories = self.load_stories()
        self.failure_stories = []  # истории, которые не прошли порог
        self.lang = LanguageEngine(
            vocab_file=vocab_file,
            model_path=None,  # временно отключаем загрузку, чтобы избежать несоответствия словаря
            n_layer=1, n_embd=32, block_size=32, n_head=4,
            mode='char'
        )
        # Дообучаем на последних историях
        if self.stories:
            for story in self.stories[-10:]:
                self.lang.train_step(story, lr=CONFIG['train_lr'])

    def load_stories(self):
        """Загружает истории из файла."""
        if os.path.exists(self.stories_file):
            try:
                with open(self.stories_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки историй: {e}")
        return []

    def save_stories(self):
        """Атомарно сохраняет истории."""
        try:
            os.makedirs(os.path.dirname(self.stories_file), exist_ok=True)
            tmp = self.stories_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.stories, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.stories_file)
        except Exception as e:
            logger.error(f"Ошибка сохранения историй: {e}")

    def _get_meme_text(self) -> Optional[str]:
        """Извлекает текст мема (если есть) из social_engine."""
        if not self.social:
            return None
        meme = self.social.get_random_meme()
        if meme is None:
            return None
        if isinstance(meme, dict):
            return meme.get('text', None)
        return meme

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Формирует промпт на основе контекста."""
        event_type = context.get('event_type')
        extra = context.get('extra', {})
        data = context.get('data', {})
        cycle = context.get('cycle', 0)
        meme_text = self._get_meme_text()

        # Определяем базовый промпт
        if event_type == "EXTINCTION":
            species = extra.get('species_names', 'несколько видов')
            base_prompt = f"Цикл {cycle}: {species} исчезли из мира."
        elif event_type == "RECORD":
            agent_name = extra.get('agent_name', 'неизвестный агент')
            score = extra.get('score', data.get('score', 0))
            base_prompt = f"Агент {agent_name} установил новый рекорд с score {score:.2f}!"
        elif event_type == "NEW_SPECIES":
            name = extra.get('new_species_name', 'новый вид')
            arch = extra.get('arch_type', 'неизвестный')
            base_prompt = f"В мире зародился новый вид: {name}, тип {arch}."
        elif event_type == "RAID":
            boss = extra.get('boss_name', 'босс')
            win = extra.get('win', False)
            if win:
                base_prompt = f"Герои победили {boss} в эпической битве!"
            else:
                base_prompt = f"Бой с {boss} закончился поражением..."
        elif event_type == "INSTITUTION_FOUNDED":
            inst = extra.get('institution_name', 'институт')
            founder = extra.get('founder', 'неизвестный')
            base_prompt = f"Основан новый институт: {inst}, основатель {founder}."
        elif event_type == "WORMHOLE":
            text = extra.get('text', 'Что-то странное')
            base_prompt = f"Из червоточины пришло: {text}"
        else:
            prompt_parts = []
            if context.get('best_score') and context['best_score'] > context.get('last_score', 0):
                prompt_parts.append("Сияет новый рекорд.")
            if context.get('velocity', 0) > 0.1:
                prompt_parts.append("Эволюция ускоряется.")
            if context.get('population', 0) > 10:
                prompt_parts.append("Мир полнится агентами.")
            base_prompt = " ".join(prompt_parts) if prompt_parts else "В мире тишина."

        if meme_text:
            base_prompt += f" {meme_text}"
        return base_prompt

    def generate_story(self, context: Dict[str, Any], max_len=CONFIG['max_len']) -> str:
        """Генерирует историю на основе контекста с повторными попытками при ошибке."""
        prompt = self._build_prompt(context)
        for attempt in range(CONFIG['max_retries']):
            try:
                story, reward = self.lang.generate(prompt, max_len=max_len,
                                                   temperature=CONFIG['temperature'],
                                                   clean=True)
                # Если история слишком короткая, возможно ошибка – пробуем снова
                if len(story.split()) < 3:
                    logger.debug(f"Слишком короткая история (попытка {attempt+1})")
                    continue
                # Если есть награда и она низкая, можно тоже регенерировать
                if reward is not None and reward < 0.3 and attempt < CONFIG['max_retries']-1:
                    logger.debug(f"Низкая награда {reward:.2f}, регенерация")
                    continue
                return story
            except Exception as e:
                logger.error(f"Ошибка генерации истории (попытка {attempt+1}): {e}")
        return "Тишина в мире."

    def generate_story_with_reward(self, context: Dict[str, Any], max_len=CONFIG['max_len']) -> Tuple[str, float]:
        """Генерирует историю и возвращает (текст, награда)."""
        prompt = self._build_prompt(context)
        story, reward = self.lang.generate(prompt, max_len=max_len,
                                           temperature=CONFIG['temperature'],
                                           clean=True)
        return story, reward if reward is not None else 0.0

    def learn_from_cycle(self, world, memory, cycle):
        """Генерирует историю, обучает модель и сохраняет."""
        # Собираем контекст
        context = {
            'cycle': cycle,
            'population': len(world.population) if world.population else 0,
            'avg_level': sum(a.level for a in world.population) / len(world.population) if world.population else 0,
            'best_score': max((a.score for a in world.population), default=0),
            'last_score': memory.hope_score if memory.hope_score > -float('inf') else 0,
            'velocity': getattr(memory, 'velocity', 0),
        }
        story, reward = self.generate_story_with_reward(context)
        if reward > CONFIG['reward_threshold']:
            # Хорошая история – сохраняем и обучаем
            self.stories.append(story)
            if len(self.stories) > 1000:
                self.stories.pop(0)
            self.save_stories()
            self.lang.train_step(story, lr=CONFIG['train_lr'])
        else:
            # Плохая – запоминаем как неудачу (для CulturalDecadenceEngine)
            self.failure_stories.append(story)
            if len(self.failure_stories) > CONFIG['failures_to_remember']:
                self.failure_stories.pop(0)
            logger.debug(f"История не прошла порог (reward={reward:.2f})")

        if cycle % CONFIG['save_every'] == 0:
            self.lang.save(self.model_path)
        return story

    def learn_from_failure(self, story: str):
        """Обучается на неудачной истории (для CulturalDecadenceEngine)."""
        self.failure_stories.append(story)
        if len(self.failure_stories) > CONFIG['failures_to_remember']:
            self.failure_stories.pop(0)
        # Можно также слабо обучить модель
        self.lang.train_step(story, lr=CONFIG['train_lr'] * 0.5)

    def get_failure_stories(self, n=5):
        """Возвращает последние неудачные истории."""
        return self.failure_stories[-n:]

    def save_model(self):
        """Сохраняет модель."""
        self.lang.save(self.model_path)

    def load_model(self):
        """Загружает модель."""
        if os.path.exists(self.model_path):
            self.lang.load(self.model_path)