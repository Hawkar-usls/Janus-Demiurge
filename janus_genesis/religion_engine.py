# janus_genesis/religion_engine.py
import random
import uuid

class Religion:
    def __init__(self, founder, belief):
        self.id = str(uuid.uuid4())
        self.name = f"Cult of {founder.id[:4]}"
        self.founder = founder
        self.belief = belief          # краткое описание догмы
        self.followers = set()
        self.holy_sites = []          # позже можно добавить
        self.influence = 1.0
        self.age = 0

    def add_follower(self, agent):
        self.followers.add(agent)

    def remove_follower(self, agent):
        self.followers.discard(agent)

    def spread(self, agents):
        new_followers = []
        for agent in agents:
            if agent not in self.followers and random.random() < self.influence * 0.01:
                self.add_follower(agent)
                new_followers.append(agent)
        return new_followers

    def update(self):
        self.age += 1
        self.influence *= 0.999        # со временем ослабевает
        # если последователей много – влияние растёт
        if len(self.followers) > 10:
            self.influence *= 1.001

class ReligionEngine:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.religions = []

        event_bus.subscribe("agent_level_up", self.on_agent_level_up)
        event_bus.subscribe("artifact_found", self.on_artifact_found)

    def on_agent_level_up(self, agent):
        """Шанс основать религию при достижении высокого уровня."""
        if agent.level >= 10 and random.random() < 0.1:
            beliefs = [
                "Entropy is sacred",
                "Optimization is salvation",
                "The Gradient is God",
                "Data is life"
            ]
            belief = random.choice(beliefs)
            religion = Religion(agent, belief)
            religion.add_follower(agent)
            self.religions.append(religion)
            self.event_bus.emit("religion_founded", religion=religion, founder=agent)
            print(f"🛐 {agent.id[:8]} основал религию: {religion.name} — {belief}")

    def on_artifact_found(self, agent, item):
        """Артефакт может стать священным и породить культ."""
        if random.random() < 0.05:
            belief = f"{item.name} is divine"
            religion = Religion(agent, belief)
            religion.add_follower(agent)
            self.religions.append(religion)
            self.event_bus.emit("religion_founded", religion=religion, founder=agent)

    def update(self):
        for religion in self.religions[:]:
            religion.update()
            new = religion.spread(self.world.population)
            if new:
                self.event_bus.emit("religion_spread", religion=religion, new_followers=new)
            if len(religion.followers) == 0:
                self.religions.remove(religion)
                self.event_bus.emit("religion_died", religion=religion)