import random
from collections import defaultdict

class Faction:
    """Фракция со своим бонусом и репутацией у агентов."""

    def __init__(self, name, bonus):
        self.name = name
        self.bonus = bonus
        self.members = []


class RelationshipSystem:
    """
    Система отношений между агентами.
    Хранит пары (agent1, agent2) -> значение отношения (-1..1).
    """
    def __init__(self):
        self.relations = defaultdict(float)  # ключ (id1, id2) в любом порядке

    def update(self, agent1, agent2, delta):
        """Изменяет отношение между двумя агентами на delta."""
        if agent1.id == agent2.id:
            return
        key = tuple(sorted((agent1.id, agent2.id)))
        self.relations[key] += delta
        self.relations[key] = max(-1.0, min(1.0, self.relations[key]))

    def get(self, agent1, agent2):
        """Возвращает текущее отношение (по умолчанию 0)."""
        if agent1.id == agent2.id:
            return 1.0
        key = tuple(sorted((agent1.id, agent2.id)))
        return self.relations.get(key, 0.0)

    def ally_probability(self, agent1, agent2):
        """Вероятность, что агенты объединятся против общего врага (зависит от отношения)."""
        rel = self.get(agent1, agent2)
        return (rel + 1) / 2  # от 0 до 1


class FactionSystem:
    """Система распределения по фракциям и управления отношениями."""

    def __init__(self):
        self.factions = [
            Faction("Transformers", {"n_head": 2}),
            Faction("Efficient", {"lr": -0.00005}),
            Faction("Chaos", {"temperature": 0.2}),
            Faction("Deep", {"n_layer": 1}),
        ]
        self.relationship_system = RelationshipSystem()

    def assign_faction(self, agent):
        """Случайно назначает агента во фракцию и применяет бонус через set_faction."""
        faction = random.choice(self.factions)
        agent.set_faction(faction.name, faction.bonus)
        faction.members.append(agent)

    def get_faction_by_name(self, name):
        for f in self.factions:
            if f.name == name:
                return f
        return None

    def handle_interaction(self, agent1, agent2, event_type):
        """
        Обновляет отношения на основе взаимодействия.
        event_type: 'trade', 'raid_together', 'fight', etc.
        """
        delta_map = {
            'trade': 0.1,
            'raid_together': 0.2,
            'fight': -0.3,
            'help': 0.3,
            'betray': -0.5
        }
        delta = delta_map.get(event_type, 0)
        self.relationship_system.update(agent1, agent2, delta)