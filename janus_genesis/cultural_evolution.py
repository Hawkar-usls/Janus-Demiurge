import random
import uuid

from spiral_evolution import SpiralLedger, fingerprint_payload


class Culture:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.values = {
            "cooperation": random.uniform(0, 1),
            "aggression": random.uniform(0, 1),
            "tradition": random.uniform(0, 1),
            "innovation": random.uniform(0, 1),
        }
        self.members = []
        self.member_history = []
        self.spiral = SpiralLedger(f"CULTURE:{self.id}")

    def add_member(self, agent):
        if agent not in self.members:
            self.members.append(agent)
        self.member_history.append({
            "turn": self.spiral.next_turn,
            "event": "MEMBER_JOINED",
            "agent_id": getattr(agent, "id", repr(agent)),
        })

    def evolve_values(self):
        before = dict(self.values)
        candidate = dict(before)
        for key in candidate:
            candidate[key] = max(0, min(1, candidate[key] + random.uniform(-0.02, 0.02)))
        self.values = candidate
        changed = before != candidate
        self.spiral.ascend(
            state_before=before,
            candidate_state=candidate,
            active_state_after=dict(self.values),
            lessons=["Cultural drift integrated as a new turn; parent values remain in lineage."],
            promoted=changed,
            outcome="ASCENDED" if changed else "NO_ASCENT",
        )

    def lineage_fingerprint(self):
        return fingerprint_payload({
            "culture_id": self.id,
            "turns": [turn.to_dict() for turn in self.spiral.turns],
            "member_history": self.member_history,
        })


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
        culture.add_member(agent)
        agent.culture = culture

    def on_agent_created(self, agent):
        self.assign_agent(agent)

    def evolve(self):
        for culture in self.cultures:
            culture.evolve_values()
