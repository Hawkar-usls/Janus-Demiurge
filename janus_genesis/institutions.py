# janus_genesis/institutions.py
"""
Самопоявляющиеся институты: гильдии, культы, торговые компании.
"""

import random
import uuid

class Institution:
    def __init__(self, founder, inst_type):
        self.id = str(uuid.uuid4())
        self.type = inst_type          # "guild", "cult", "trading_company", "military_order"
        self.founder = founder
        self.members = [founder]
        self.rules = {}                # например {"share_loot": True, "tax": 0.1}
        self.funds = 0
        self.created_tick = 0

    def add_member(self, agent):
        if agent not in self.members:
            self.members.append(agent)

    def remove_member(self, agent):
        if agent in self.members and agent != self.founder:
            self.members.remove(agent)

    def is_active(self):
        return len(self.members) >= 2

    def collect_tax(self, amount):
        self.funds += amount

    def distribute(self, amount):
        if self.funds >= amount:
            for agent in self.members:
                agent.gold += amount // len(self.members)
            self.funds -= amount


class InstitutionSystem:
    def __init__(self, event_bus):
        self.institutions = []
        self.event_bus = event_bus
        # Подписываемся на события
        event_bus.subscribe("agent_level_up", self.on_agent_level_up)
        event_bus.subscribe("raid_win", self.on_raid_win)

    def on_agent_level_up(self, agent):
        """При повышении уровня агент может основать институт."""
        if agent.level >= 5 and random.random() < 0.1:
            inst_type = random.choice(["guild", "cult", "trading_company"])
            inst = Institution(agent, inst_type)
            self.institutions.append(inst)
            self.event_bus.emit("institution_founded", institution=inst, founder=agent)

    def on_raid_win(self, agents, boss_name):
        """После победы над боссом институт может получить ресурсы."""
        if agents and random.random() < 0.2:
            for inst in self.institutions:
                if any(a in inst.members for a in agents):
                    inst.funds += 100
                    break

    def update(self, world):
        """Обновление институтов: сбор налогов, распад и т.д."""
        for inst in self.institutions[:]:
            if not inst.is_active():
                self.institutions.remove(inst)
            else:
                # Случайный сбор налогов
                if random.random() < 0.05:
                    total_tax = 0
                    for member in inst.members:
                        tax = int(member.gold * 0.05)
                        member.gold -= tax
                        total_tax += tax
                    inst.funds += total_tax