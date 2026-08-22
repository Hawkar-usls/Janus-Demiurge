# janus_genesis/tech_evolution.py
import random
import uuid

from spiral_evolution import SpiralLedger


class Technology:
    def __init__(self, name, category, cost, effect):
        self.id = str(uuid.uuid4())
        self.name = name
        self.category = category
        self.cost = cost
        self.effect = effect
        self.discovered = False
        self.discoverer = None
        self.discovery_history = []


class TechEvolutionEngine:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.technologies = self._init_techs()
        self.discovered_techs = []
        self.spiral = SpiralLedger("JANUS_TECH_EVOLUTION")
        self.attempt_history = []

    def _init_techs(self):
        return [
            Technology("Advanced Mining", "economy", 100,
                       lambda w: w.economy.resources.update({"compute": w.economy.resources.get("compute", 0) + 50})),
            Technology("Raid Tactics", "military", 150,
                       lambda w: setattr(w.raids, 'difficulty_multiplier', getattr(w.raids, 'difficulty_multiplier', 1.0) * 0.9)),
            Technology("Cultural Exchange", "culture", 80,
                       lambda w: w.memes.spread_meme("Unity", random.sample(w.population, min(5, len(w.population))))),
            Technology("Master Crafter", "crafting", 120,
                       lambda w: [setattr(agent, 'crafting_bonus', getattr(agent, 'crafting_bonus', 1.0) * 1.2)
                                  for agent in w.population if agent.profession in ['blacksmith', 'alchemist']]),
        ]

    def can_discover(self, agent, tech):
        if tech.category == "economy" and agent.gold < tech.cost:
            return False
        if tech.category == "military" and agent.level < 5:
            return False
        return True

    @staticmethod
    def _agent_state(agent):
        return {
            "agent_id": getattr(agent, "id", repr(agent)),
            "gold": getattr(agent, "gold", None),
            "level": getattr(agent, "level", None),
        }

    def _record_attempt(self, agent, tech, before, promoted, reason):
        after = self._agent_state(agent)
        record = {
            "turn": self.spiral.next_turn,
            "agent": after["agent_id"],
            "technology_id": tech.id if tech else None,
            "technology": tech.name if tech else None,
            "reason": reason,
            "promoted": bool(promoted),
        }
        turn = self.spiral.ascend(
            state_before={"agent": before, "technology_discovered": bool(tech.discovered) if tech else None},
            candidate_state={"technology": tech.name if tech else None, "attempt_reason": reason},
            active_state_after={"agent": after, "technology_discovered": bool(tech.discovered) if tech else None},
            lessons=[
                "Discovery admitted and ancestry retained."
                if promoted
                else f"Discovery not admitted: {reason}; preserve constraint for a later turn."
            ],
            constraints=[] if promoted else [reason],
            promoted=promoted,
            outcome="ASCENDED" if promoted else "INTEGRATED_LESSON",
        )
        record["fingerprint"] = turn.fingerprint
        self.attempt_history.append(record)
        if tech is not None:
            tech.discovery_history.append(record)

    def attempt_discovery(self, agent):
        """Attempt a technology turn. Failure is retained as learning, not erased."""
        before = self._agent_state(agent)
        undiscovered = [t for t in self.technologies if not t.discovered]
        if not undiscovered:
            self._record_attempt(agent, None, before, False, "NO_UNDISCOVERED_TECHNOLOGY_AVAILABLE")
            return None

        tech = random.choice(undiscovered)
        if not self.can_discover(agent, tech):
            reason = "INSUFFICIENT_REQUIREMENTS"
            if tech.category == "economy" and getattr(agent, "gold", 0) < tech.cost:
                reason = "INSUFFICIENT_GOLD"
            elif tech.category == "military" and getattr(agent, "level", 0) < 5:
                reason = "INSUFFICIENT_LEVEL"
            self._record_attempt(agent, tech, before, False, reason)
            return None

        if tech.category == "economy":
            agent.gold -= tech.cost
        tech.discovered = True
        tech.discoverer = agent
        self.discovered_techs.append(tech)
        tech.effect(self.world)
        self.event_bus.emit("tech_discovered", technology=tech, discoverer=agent)
        self._record_attempt(agent, tech, before, True, "DISCOVERY_ADMITTED")
        print(f"🔬 {agent.id[:8]} открыл технологию: {tech.name}")
        return tech

    def update(self):
        for agent in self.world.population:
            if random.random() < 0.001:
                self.attempt_discovery(agent)
