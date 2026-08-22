#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECIES ENGINE — спиральное развитие видов без вымирания данных/идентичности."""

import json
import os
import random
import statistics

from config import RAW_LOGS_DIR
from spiral_evolution import fingerprint_payload


class Species:
    def __init__(self, name, arch_type, population=None):
        self.name = name
        self.arch_type = arch_type
        self.population = list(population or [])
        self.fitness_history = []
        self.birth_time = None
        self.status = "ACTIVE"
        self.spiral_turn = 0
        self.lineage = []
        self.member_history = []
        self.development_plan = []
        # Backwards compatibility only. Canonical engine never sets True.
        self.extinct = False

    def add_agent(self, agent_id):
        if agent_id not in self.population:
            self.population.append(agent_id)
            self.member_history.append({"turn": self.spiral_turn, "agent_id": agent_id, "event": "JOIN"})

    def transition_agent(self, agent_id, destination=None, reason="ROLE_TRANSITION"):
        """Move an agent out of the active membership without erasing lineage."""
        if agent_id in self.population:
            self.population.remove(agent_id)
        self.member_history.append({
            "turn": self.spiral_turn,
            "agent_id": agent_id,
            "event": "TRANSITION",
            "destination": destination,
            "reason": reason,
        })

    def remove_agent(self, agent_id):
        """Legacy API: removal is translated into a traceable transition."""
        self.transition_agent(agent_id, reason="LEGACY_REMOVE_REQUEST_PRESERVED")

    def update_fitness(self, agents_dict):
        if not self.population:
            return 0.0
        scores = [agents_dict[aid].score for aid in self.population if aid in agents_dict]
        if scores:
            avg = statistics.fmean(scores)
            self.fitness_history.append(avg)
            return avg
        return 0.0

    def integrate_growth_lesson(self, lesson, target_fitness=None):
        before = {
            "status": self.status,
            "fitness": self.fitness_history[-1] if self.fitness_history else None,
            "turn": self.spiral_turn,
        }
        self.spiral_turn += 1
        self.status = "ASCENDING"
        entry = {
            "turn": self.spiral_turn,
            "parent_fingerprint": fingerprint_payload(before),
            "lesson": str(lesson),
            "target_fitness": target_fitness,
        }
        self.lineage.append(entry)
        self.development_plan.append(str(lesson))
        return entry

    def to_dict(self):
        return {
            'name': self.name,
            'arch_type': self.arch_type,
            'population': self.population,
            'fitness_history': self.fitness_history,
            'birth_time': self.birth_time,
            'status': self.status,
            'spiral_turn': self.spiral_turn,
            'lineage': self.lineage,
            'member_history': self.member_history,
            'development_plan': self.development_plan,
            # Keep legacy key readable, but extinction is no longer an active state.
            'extinct': False,
        }

    @classmethod
    def from_dict(cls, data):
        sp = cls(data['name'], data['arch_type'], data.get('population', []))
        sp.fitness_history = data.get('fitness_history', [])
        sp.birth_time = data.get('birth_time')
        sp.status = data.get('status', 'ACTIVE')
        sp.spiral_turn = data.get('spiral_turn', 0)
        sp.lineage = data.get('lineage', [])
        sp.member_history = data.get('member_history', [])
        sp.development_plan = data.get('development_plan', [])
        if data.get('extinct'):
            sp.status = "RECOVERED_FROM_LEGACY_EXTINCTION"
            sp.spiral_turn += 1
            sp.lineage.append({
                "turn": sp.spiral_turn,
                "event": "LEGACY_EXTINCTION_MIGRATED_TO_RECOVERY",
            })
        sp.extinct = False
        return sp


class SpeciesEngine:
    def __init__(self, registry_path=None):
        self.registry_path = registry_path or os.path.join(RAW_LOGS_DIR, "species_registry.json")
        self.species_list = []
        self.load()

    def create_species(self, name, arch_type):
        sp = Species(name, arch_type)
        sp.birth_time = len(self.species_list)
        self.species_list.append(sp)
        return sp

    def assign_agent_to_species(self, agent, species_name):
        arch_type = agent.arch_genome.arch_type if getattr(agent, 'arch_genome', None) else "unknown"
        species = self.get_species_by_name(species_name)
        if not species:
            species = self.create_species(species_name, arch_type)
        species.add_agent(agent.id)
        agent.species = species_name

    def get_species_by_name(self, name):
        for sp in self.species_list:
            if sp.name == name:
                return sp
        return None

    def update_all_fitness(self, agents_dict):
        for sp in self.species_list:
            sp.update_fitness(agents_dict)

    def ascend_weak_species(self, threshold=0.5):
        """Diagnose weaker species and give them a next-turn development plan."""
        if not self.species_list:
            return []
        measured = [sp for sp in self.species_list if sp.fitness_history]
        if not measured:
            return []
        max_fitness = max(sp.fitness_history[-1] for sp in measured)
        if max_fitness <= 0:
            return []
        ascending = []
        for sp in measured:
            current = sp.fitness_history[-1]
            if current < max_fitness * threshold:
                sp.integrate_growth_lesson(
                    "Fitness below current frontier: preserve identity, increase exploration and learn from stronger peer evidence.",
                    target_fitness=max_fitness * threshold,
                )
                ascending.append(sp.name)
            elif sp.status != "ACTIVE":
                sp.status = "ACTIVE"
        return ascending

    def cull_weak_species(self, threshold=0.5):
        """Deprecated compatibility alias: culling now means coached ascent, never extinction."""
        return self.ascend_weak_species(threshold=threshold)

    def spawn_new_species(self, base_arch_types=None):
        if not base_arch_types:
            base_arch_types = ['transformer', 'wide_transformer', 'deep_transformer']
        new_arch = random.choice(base_arch_types) + "_variant"
        name = f"Species_{len(self.species_list)}_{new_arch}"
        sp = self.create_species(name, new_arch)
        sp.lineage.append({"turn": 0, "event": "CREATED_AS_NEW_SPIRAL_BRANCH"})
        return sp

    def save(self):
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump([sp.to_dict() for sp in self.species_list], f, indent=2, ensure_ascii=False)

    def load(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.species_list = [Species.from_dict(d) for d in data]
            except Exception as e:
                print(f"Ошибка загрузки видов: {e}")
