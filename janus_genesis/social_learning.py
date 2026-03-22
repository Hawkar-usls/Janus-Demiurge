#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOCIAL LEARNING ENGINE v2.0 — культурная эволюция, социальные сети, мемы как функции,
репутация, школы с центроидами, гибридизация, предсказание через Tachyon.
"""

import random
import numpy as np
import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger("JANUS")

class SocialLearningEngine:
    """
    Движок социального обучения с продвинутой эволюцией знаний.
    """
    def __init__(self, memory_size=1000, tachyon=None, evolutionary_memory=None):
        self.role_models = deque(maxlen=memory_size)          # (agent_id, config, score)
        self.schools = defaultdict(list)                      # arch_type -> list of agent_ids
        self.observation_chance = 0.1
        self.copy_probability = 0.3
        self.bards = []                                       # агенты-барды
        self.cultural_memes = deque(maxlen=100)               # старые строковые мемы (для совместимости)
        self.meta_memes = []                                  # список правил, изменяющих параметры движка

        # Новые структуры
        self.trust = defaultdict(float)                       # trust score для агентов
        self.network = defaultdict(set)                       # граф социальных связей (agent_id -> set of agent_ids)
        self.failures = deque(maxlen=500)                     # память о плохих конфигурациях
        self.efficiency_history = defaultdict(list)           # для оценки эффективности (score / cost)

        # Внешние системы (для предсказаний)
        self.tachyon = tachyon
        self.evolutionary_memory = evolutionary_memory

        # Параметры, которые могут меняться мета-мемами
        self.params = {
            "observation_chance": 0.1,
            "copy_probability": 0.3,
            "trust_decay": 0.99,
            "network_connection_chance": 0.1,
            "pressure_strength": 0.2,
            "hybridization_chance": 0.3,
            "tachyon_filter_threshold": 0.8
        }

    # ---------- Основные методы (совместимость) ----------
    def add_success(self, agent):
        """Добавляет успешного агента в ролевые модели."""
        self.role_models.append((agent.id, agent.base_config.copy(), agent.score))
        self.update_trust(agent, agent.score * 0.01)

    def get_best_recent(self, n=5):
        """Возвращает n лучших недавних конфигураций."""
        if not self.role_models:
            return []
        sorted_models = sorted(self.role_models, key=lambda x: x[2], reverse=True)
        return [model[1] for model in sorted_models[:n]]

    # ---------- НОВЫЕ МЕТОДЫ ----------

    # --- Репутация (trust) ---
    def update_trust(self, agent, delta):
        """Обновляет trust score агента."""
        self.trust[agent.id] = self.trust.get(agent.id, 0.0) + delta
        self.trust[agent.id] = max(0.0, min(1.0, self.trust[agent.id]))
        # лёгкое затухание для всех
        for aid in list(self.trust.keys()):
            self.trust[aid] *= self.params["trust_decay"]

    def select_with_trust(self, agent, others):
        """Выбирает агента для подражания на основе trust и score."""
        if not others:
            return None
        weights = []
        for other in others:
            trust = self.trust.get(other.id, 0.1)
            # вес = trust * (score - среднее) + базовый
            weight = trust * (other.score + 0.1)
            weights.append(weight)
        # Нормализация
        total = sum(weights)
        if total == 0:
            return random.choice(others)
        probs = [w / total for w in weights]
        return np.random.choice(others, p=probs)

    # --- Школы с центроидом ---
    def assign_to_school(self, agent):
        arch_type = agent.arch_genome.arch_type if hasattr(agent, 'arch_genome') else 'unknown'
        self.schools[arch_type].append(agent.id)

    def school_center(self, arch_type):
        """Возвращает центроид конфигурации школы."""
        members = self.schools.get(arch_type, [])
        if not members:
            return None
        # собираем реальные объекты агентов из world (передаётся в методы)
        # здесь нужен доступ к world, поэтому будем передавать world при вызове
        # но для удобства сделаем заглушку – возвращаем средние значения параметров из истории
        # Лучше передавать world в метод, который использует эту функцию
        # Пока вернём словарь с None, а реальное вычисление будет в school_influence
        return None  # реальное вычисление сделаем в school_influence, где есть доступ к world

    def school_influence(self, agent, world):
        """
        Если агент в школе, применяет влияние центроида школы.
        Возвращает новую конфигурацию (частично усреднённую с центроидом).
        """
        arch_type = agent.arch_genome.arch_type if hasattr(agent, 'arch_genome') else 'unknown'
        school_ids = self.schools.get(arch_type, [])
        if len(school_ids) < 2 or agent.id not in school_ids:
            return None

        # Собираем реальных агентов из world
        members = [a for a in world.population if a.id in school_ids]
        if not members:
            return None
        # Вычисляем центроид по гиперпараметрам
        center = {}
        keys = ['gain', 'temperature', 'lr', 'n_embd', 'n_head', 'n_layer']
        for k in keys:
            vals = [getattr(a.base_config, k, None) for a in members if hasattr(a.base_config, k)]
            if vals:
                center[k] = np.mean(vals)
        if not center:
            return None

        # Усредняем текущую конфигурацию агента с центроидом
        new_config = agent.base_config.copy()
        for k, v in center.items():
            if k in new_config:
                new_config[k] = (new_config[k] + v) / 2.0
        # Ограничения
        from janus_character import PARAM_RANGES  # импорт для ограничений
        for param, ranges in PARAM_RANGES.items():
            if param in new_config:
                if isinstance(ranges, tuple):
                    low, high = ranges
                    new_config[param] = max(low, min(high, new_config[param]))
                elif isinstance(ranges, list):
                    new_config[param] = min(ranges, key=lambda x: abs(x - new_config[param]))
        return new_config

    # --- Мемы как функции ---
    def add_meme_effect(self, text: str, effect: Callable):
        """Добавляет мем с функцией, изменяющей конфигурацию."""
        self.cultural_memes.append({"text": text, "effect": effect})

    def add_meme(self, text: str):
        """Для совместимости – добавляет строковый мем."""
        self.cultural_memes.append({"text": text, "effect": None})

    def get_random_meme(self):
        """Возвращает случайный мем (может быть как строкой, так и функцией)."""
        if not self.cultural_memes:
            return None
        return random.choice(self.cultural_memes)

    def apply_meme(self, meme, config):
        """Применяет эффект мема к конфигурации."""
        if isinstance(meme, dict) and "effect" in meme and meme["effect"] is not None:
            return meme["effect"](config)
        return config  # строковый мем не влияет на параметры

    # --- Социальное давление ---
    def conformity_pressure(self, agent, world):
        """Вычисляет давление конформности (разница между score агента и средним по школе)."""
        arch_type = agent.arch_genome.arch_type if hasattr(agent, 'arch_genome') else 'unknown'
        school_ids = self.schools.get(arch_type, [])
        if len(school_ids) < 5:
            return 0.0
        members = [a for a in world.population if a.id in school_ids]
        if not members:
            return 0.0
        avg_score = np.mean([a.score for a in members])
        return avg_score - agent.score

    # --- Гибридизация конфигураций ---
    def hybrid_config(self, config1, config2):
        """Создаёт гибрид двух конфигураций (генетическое смешивание)."""
        hybrid = {}
        keys = set(config1.keys()) | set(config2.keys())
        for k in keys:
            if k not in config1:
                hybrid[k] = config2[k]
            elif k not in config2:
                hybrid[k] = config1[k]
            else:
                # Случайный выбор или усреднение
                if isinstance(config1[k], (int, float)) and isinstance(config2[k], (int, float)):
                    if random.random() < 0.5:
                        hybrid[k] = (config1[k] + config2[k]) / 2
                    else:
                        hybrid[k] = random.choice([config1[k], config2[k]])
                else:
                    hybrid[k] = random.choice([config1[k], config2[k]])
        return hybrid

    # --- Память о неудачах ---
    def add_failure(self, config):
        self.failures.append(config)

    def avoid_failures(self, config):
        """Проверяет, не является ли конфигурация заведомо плохой."""
        for fail in self.failures:
            if self._config_distance(config, fail) < 0.05:
                return True
        return False

    def _config_distance(self, c1, c2):
        """Евклидово расстояние между двумя конфигурациями."""
        keys = ['lr', 'gain', 'temperature', 'n_embd', 'n_head', 'n_layer']
        diff = 0.0
        for k in keys:
            if k in c1 and k in c2:
                v1 = c1[k]
                v2 = c2[k]
                # нормализация
                if k == 'lr':
                    v1 = np.log10(v1 + 1e-8)
                    v2 = np.log10(v2 + 1e-8)
                elif k in ['n_embd', 'n_head', 'n_layer']:
                    v1 = v1 / 100.0
                    v2 = v2 / 100.0
                diff += (v1 - v2) ** 2
        return np.sqrt(diff)

    # --- Социальная сеть ---
    def social_network_update(self, agent, target):
        """Обновляет граф связей при взаимодействии."""
        self.network[agent.id].add(target.id)
        self.network[target.id].add(agent.id)

    def get_social_neighbors(self, agent):
        """Возвращает список соседей по социальной сети."""
        neighbors_ids = self.network.get(agent.id, set())
        return [aid for aid in neighbors_ids]

    # --- Барды и пропаганда ---
    def add_bard(self, agent):
        if agent not in self.bards:
            self.bards.append(agent)

    def bard_influence(self, agent, world):
        """Возвращает строку для логирования и, возможно, изменяет параметры агента."""
        if self.bards and random.random() < 0.1:
            bard = random.choice(self.bards)
            meme = self.get_random_meme()
            if meme:
                # Если мем имеет эффект, применяем его к агенту
                if isinstance(meme, dict) and meme.get("effect"):
                    new_config = meme["effect"](agent.base_config)
                    agent.base_config = new_config
                    agent._update_current_config()
                return f"Бард {bard.id[:8]} напевает: '{meme['text'] if isinstance(meme, dict) else meme}'"
        return None

    # --- Мета-мемы (эволюция правил) ---
    def add_meta_meme(self, rule: str, effect: Callable):
        """Добавляет мета-мем, изменяющий параметры самого движка."""
        self.meta_memes.append({"rule": rule, "effect": effect})

    def apply_meta_memes(self):
        """Применяет все мета-мемы к параметрам движка."""
        for mm in self.meta_memes:
            mm["effect"](self.params)

    # --- Обновлённый метод наблюдения и обучения ---
    def observe_and_learn(self, agent, all_agents, world):
        """
        Агент учится у других с учётом репутации, социальной сети, гибридизации,
        предсказаний Tachyon и эффективности.
        Возвращает новую конфигурацию или None.
        """
        if random.random() > self.params["observation_chance"]:
            return None
        if len(all_agents) < 2:
            return None

        others = [a for a in all_agents if a.id != agent.id]
        if not others:
            return None

        # Выбор кандидата с учётом доверия и социальной сети
        neighbors = self.get_social_neighbors(agent)
        if neighbors:
            # отбираем соседей, которые есть среди others
            candidates = [a for a in others if a.id in neighbors]
            if candidates:
                target = self.select_with_trust(agent, candidates)
            else:
                target = self.select_with_trust(agent, others)
        else:
            target = self.select_with_trust(agent, others)

        if target is None:
            return None

        # Социальное давление увеличивает вероятность копирования
        pressure = self.conformity_pressure(agent, world)
        prob = self.params["copy_probability"]
        if pressure > 0:
            prob *= (1 + self.params["pressure_strength"])
        # Если в одной пати (party) – увеличиваем
        if hasattr(world, 'party_system'):
            party1 = world.party_system.find_party_by_member(agent)
            party2 = world.party_system.find_party_by_member(target)
            if party1 and party2 and party1 == party2:
                prob *= 2

        # Проверка, стоит ли копировать: предсказание Tachyon
        if self.tachyon and hasattr(self.tachyon, 'predict_outcome'):
            # Предсказываем score для текущей конфигурации агента и для конфигурации кандидата
            # (упрощённо – используем конфигурацию как фичи)
            features_agent = self._config_to_features(agent.base_config)
            pred_agent = self.tachyon.predict_outcome(features_agent)
            features_target = self._config_to_features(target.base_config)
            pred_target = self.tachyon.predict_outcome(features_target)
            if pred_agent and pred_target:
                if pred_target.get('score', 0) < pred_agent.get('score', 0) * self.params["tachyon_filter_threshold"]:
                    # копировать невыгодно
                    return None

        # Теперь решаем, копировать или гибридизировать
        if random.random() < prob:
            if random.random() < self.params["hybridization_chance"]:
                # Гибридизация
                new_config = self.hybrid_config(agent.base_config, target.base_config)
                logger.info(f"🧬 {agent} гибридизировал конфигурации (с {target})")
            else:
                # Простое копирование
                new_config = target.base_config.copy()
                logger.info(f"🧠 {agent} скопировал конфигурацию у {target}")

            # Мутация
            for param in ['lr', 'gain', 'temperature']:
                if param in new_config:
                    new_config[param] *= random.uniform(0.95, 1.05)
            # Ограничения
            new_config['lr'] = max(1e-5, min(1e-2, new_config['lr']))
            new_config['gain'] = max(0.3, min(2.0, new_config['gain']))
            new_config['temperature'] = max(0.3, min(2.0, new_config['temperature']))

            # Применение мема, если есть
            meme = self.get_random_meme()
            if meme:
                new_config = self.apply_meme(meme, new_config)

            # Проверка на неудачные конфигурации
            if self.avoid_failures(new_config):
                logger.info(f"   ⚠️ {agent} избежал неудачной конфигурации")
                return None

            # Обновляем социальную сеть
            self.social_network_update(agent, target)

            # Обновляем trust (если копирование было успешным – позже)
            # Здесь можно зафиксировать попытку, но успех будет определён позже
            return new_config

        return None

    def _config_to_features(self, config):
        """Преобразует конфигурацию в словарь фич для Tachyon."""
        return {
            "event_type": "CONFIG",
            "importance": 1.0,
            "prompt_len": 0,
            "steps": 0,
            "seed_mod": 0,
            "cpu": 0,
            "ram": 0,
            "gpu": 0,
            "style": "default"
        }

    # --- Вспомогательные методы ---
    def school_center(self, arch_type, world):
        """Возвращает центроид школы для данного arch_type (реальная реализация)."""
        school_ids = self.schools.get(arch_type, [])
        if not school_ids:
            return None
        members = [a for a in world.population if a.id in school_ids]
        if not members:
            return None
        center = {}
        keys = ['gain', 'temperature', 'lr', 'n_embd', 'n_head', 'n_layer']
        for k in keys:
            vals = [getattr(a.base_config, k, None) for a in members if hasattr(a.base_config, k)]
            if vals:
                center[k] = np.mean(vals)
        return center