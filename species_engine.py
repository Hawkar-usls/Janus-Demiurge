#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPECIES ENGINE — управляет эволюцией видов моделей.
Каждый вид имеет свой архитектурный тип и популяцию.
"""

import json
import os
import random
import numpy as np
from config import RAW_LOGS_DIR

class Species:
    def __init__(self, name, arch_type, population=None):
        self.name = name
        self.arch_type = arch_type
        self.population = population if population else []  # список ID агентов
        self.fitness_history = []
        self.birth_time = None  # будет установлено при создании
        self.extinct = False

    def add_agent(self, agent_id):
        if agent_id not in self.population:
            self.population.append(agent_id)

    def remove_agent(self, agent_id):
        if agent_id in self.population:
            self.population.remove(agent_id)

    def update_fitness(self, agents_dict):
        """Вычисляет среднюю fitness по живым агентам вида."""
        if not self.population:
            return 0.0
        scores = []
        for aid in self.population:
            if aid in agents_dict:
                scores.append(agents_dict[aid].score)
        if scores:
            avg = np.mean(scores)
            self.fitness_history.append(avg)
            return avg
        return 0.0

    def to_dict(self):
        return {
            'name': self.name,
            'arch_type': self.arch_type,
            'population': self.population,
            'fitness_history': self.fitness_history,
            'birth_time': self.birth_time,
            'extinct': self.extinct
        }

    @classmethod
    def from_dict(cls, data):
        sp = cls(data['name'], data['arch_type'], data['population'])
        sp.fitness_history = data['fitness_history']
        sp.birth_time = data['birth_time']
        sp.extinct = data['extinct']
        return sp


class SpeciesEngine:
    def __init__(self, registry_path=None):
        if registry_path is None:
            self.registry_path = os.path.join(RAW_LOGS_DIR, "species_registry.json")
        else:
            self.registry_path = registry_path
        self.species_list = []
        self.load()

    def create_species(self, name, arch_type):
        """Создаёт новый вид."""
        sp = Species(name, arch_type)
        sp.birth_time = len(self.species_list)  # простой идентификатор
        self.species_list.append(sp)
        return sp

    def assign_agent_to_species(self, agent, species_name):
        """Назначает агента виду (если вид существует, иначе создаёт)."""
        # +++ ИСПРАВЛЕНО: проверяем наличие arch_genome у агента +++
        if hasattr(agent, 'arch_genome') and agent.arch_genome:
            arch_type = agent.arch_genome.arch_type
        else:
            arch_type = "unknown"
            # можно также создать дефолтный геном, но пока просто unknown

        species = self.get_species_by_name(species_name)
        if not species:
            species = self.create_species(species_name, arch_type)
        species.add_agent(agent.id)
        agent.species = species_name

    def get_species_by_name(self, name):
        for sp in self.species_list:
            if sp.name == name and not sp.extinct:
                return sp
        return None

    def update_all_fitness(self, agents_dict):
        """Обновляет fitness всех видов."""
        for sp in self.species_list:
            if sp.extinct:
                continue
            sp.update_fitness(agents_dict)

    def cull_weak_species(self, threshold=0.5):
        """
        Удаляет виды со средней fitness ниже порога (от текущей максимальной).
        Возвращает список вымерших видов.
        """
        if not self.species_list:
            return []

        # Вычисляем максимальную среднюю fitness среди живых видов
        alive_species = [sp for sp in self.species_list if not sp.extinct]
        if not alive_species:
            return []

        max_fitness = max(sp.fitness_history[-1] if sp.fitness_history else -float('inf') for sp in alive_species)
        if max_fitness <= -float('inf'):
            return []

        extinct = []
        for sp in alive_species:
            current = sp.fitness_history[-1] if sp.fitness_history else -float('inf')
            if current < max_fitness * threshold:
                sp.extinct = True
                extinct.append(sp.name)

        return extinct

    def spawn_new_species(self, base_arch_types=None):
        """
        Создаёт новый вид на основе существующих (комбинация).
        """
        if not base_arch_types:
            base_arch_types = ['transformer', 'wide_transformer', 'deep_transformer']
        new_arch = random.choice(base_arch_types) + "_variant"
        name = f"Species_{len(self.species_list)}_{new_arch}"
        return self.create_species(name, new_arch)

    def save(self):
        data = [sp.to_dict() for sp in self.species_list]
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.species_list = [Species.from_dict(d) for d in data]
            except Exception as e:
                print(f"Ошибка загрузки видов: {e}")