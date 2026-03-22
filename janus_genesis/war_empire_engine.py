# janus_genesis/war_empire_engine.py
import random
import uuid

class Empire:
    def __init__(self, name, founder):
        self.id = str(uuid.uuid4())
        self.name = name
        self.founder = founder
        self.ruler = founder
        self.territory_size = 1
        self.military_power = 1.0
        self.wealth = 0
        self.members = [founder]

    def add_member(self, agent):
        if agent not in self.members:
            self.members.append(agent)

    def remove_member(self, agent):
        if agent in self.members and agent != self.ruler:
            self.members.remove(agent)

    def power(self):
        return len(self.members) * self.military_power

class WarEmpireEngine:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.empires = []

        event_bus.subscribe("party_formed", self.on_party_formed)
        event_bus.subscribe("raid_win", self.on_raid_win)

    def on_party_formed(self, party, leader, members):
        """Крупная партия может стать империей."""
        if len(party.members) >= 5 and random.random() < 0.2:
            empire = Empire(f"Empire of {leader.id[:4]}", leader)
            empire.members = party.members.copy()
            self.empires.append(empire)
            self.event_bus.emit("empire_founded", empire=empire, founder=leader)
            print(f"🏰 {leader.id[:8]} основал империю {empire.name}!")

    def on_raid_win(self, agents, boss_name):
        """Успешный рейд укрепляет империю."""
        for empire in self.empires:
            if any(a in empire.members for a in agents):
                empire.military_power *= 1.05
                empire.wealth += 100

    def declare_war(self, empire1, empire2):
        """Объявление войны между империями."""
        self.event_bus.emit("war_started", empire1=empire1, empire2=empire2)
        print(f"⚔️ Война между {empire1.name} и {empire2.name}!")

    def battle(self, empire1, empire2):
        """Простой исход битвы."""
        power1 = empire1.power()
        power2 = empire2.power()
        if power1 > power2:
            winner, loser = empire1, empire2
        else:
            winner, loser = empire2, empire1
        # победитель получает ресурсы
        winner.wealth += loser.wealth // 2
        loser.wealth //= 2
        # часть побеждённых переходит к победителю
        defectors = random.sample(loser.members, min(2, len(loser.members)))
        for a in defectors:
            loser.remove_member(a)
            winner.add_member(a)
        self.event_bus.emit("battle_ended", winner=winner, loser=loser)
        if len(loser.members) == 0:
            self.empires.remove(loser)
            self.event_bus.emit("empire_destroyed", empire=loser)

    def update(self):
        """Периодические конфликты между империями."""
        if len(self.empires) >= 2 and random.random() < 0.01:
            e1, e2 = random.sample(self.empires, 2)
            self.declare_war(e1, e2)
            self.battle(e1, e2)