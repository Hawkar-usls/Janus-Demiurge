import random
import uuid


class Culture:

    def __init__(self):

        self.id = str(uuid.uuid4())

        self.values = {
            "cooperation": random.uniform(0, 1),
            "aggression": random.uniform(0, 1),
            "tradition": random.uniform(0, 1),
            "innovation": random.uniform(0, 1)
        }

        self.members = []


class CulturalEvolutionEngine:

    def __init__(self, world, event_bus):

        self.world = world
        self.event_bus = event_bus
        self.cultures = []

        event_bus.subscribe("agent_created", self.on_agent_created)

    def create_culture(self):

        culture = Culture()
        self.cultures.append(culture)

        return culture

    def assign_agent(self, agent):

        if not self.cultures:
            culture = self.create_culture()
        else:
            culture = random.choice(self.cultures)

        culture.members.append(agent)

        agent.culture = culture

    def on_agent_created(self, agent):

        self.assign_agent(agent)

    def evolve(self):

        for culture in self.cultures:

            for k in culture.values:

                culture.values[k] += random.uniform(-0.02, 0.02)

                culture.values[k] = max(0, min(1, culture.values[k]))