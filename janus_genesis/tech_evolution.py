# janus_genesis/tech_evolution.py
import random
import uuid

class Technology:
    def __init__(self, name, category, cost, effect):
        self.id = str(uuid.uuid4())
        self.name = name
        self.category = category      # "economy", "military", "culture", "crafting"
        self.cost = cost              # сколько ресурсов нужно для открытия
        self.effect = effect          # функция, применяемая к миру
        self.discovered = False
        self.discoverer = None

class TechEvolutionEngine:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.technologies = self._init_techs()
        self.discovered_techs = []

    def _init_techs(self):
        return [
            Technology("Advanced Mining", "economy", 100,
                       lambda w: w.economy.resources.update({"compute": w.economy.resources.get("compute",0)+50})),
            Technology("Raid Tactics", "military", 150,
                       lambda w: setattr(w.raids, 'difficulty_multiplier', getattr(w.raids,'difficulty_multiplier',1.0)*0.9)),
            Technology("Cultural Exchange", "culture", 80,
                       lambda w: w.memes.spread_meme("Unity", random.sample(w.population, min(5,len(w.population))))),
            Technology("Master Crafter", "crafting", 120,
                       lambda w: [setattr(agent, 'crafting_bonus', getattr(agent,'crafting_bonus',1.0)*1.2) for agent in w.population if agent.profession in ['blacksmith','alchemist']]),
        ]

    def can_discover(self, agent, tech):
        """Может ли агент открыть технологию."""
        # например, по уровню, профессии и ресурсам
        if tech.category == "economy" and agent.gold < tech.cost:
            return False
        if tech.category == "military" and agent.level < 5:
            return False
        return True

    def attempt_discovery(self, agent):
        """Случайная попытка открыть новую технологию."""
        undiscovered = [t for t in self.technologies if not t.discovered]
        if not undiscovered:
            return None
        tech = random.choice(undiscovered)
        if self.can_discover(agent, tech):
            # списываем ресурсы
            if tech.category == "economy":
                agent.gold -= tech.cost
            tech.discovered = True
            tech.discoverer = agent
            self.discovered_techs.append(tech)
            tech.effect(self.world)
            self.event_bus.emit("tech_discovered", technology=tech, discoverer=agent)
            print(f"🔬 {agent.id[:8]} открыл технологию: {tech.name}")
            return tech
        return None

    def update(self):
        """Каждый тик с малым шансом агент пытается открыть технологию."""
        for agent in self.world.population:
            if random.random() < 0.001:   # очень редкий шанс
                self.attempt_discovery(agent)