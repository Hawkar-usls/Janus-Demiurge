# janus_genesis/strategic_actions.py
"""
Высокоуровневые действия, которые может выполнять Янус.
"""

import random

class StrategicExecutor:
    ACTIONS = [
        "boost_economy",
        "spawn_resource",
        "encourage_raids",
        "promote_trade",
        "support_faction",
        "spread_idea",
        "stabilize_market"
    ]

    def execute(self, action, world):
        """Применяет действие к миру."""
        if action == "boost_economy":
            for res in world.economy.resources:
                world.economy.resources[res] += 20
            return "Экономика усилена."

        elif action == "spawn_resource":
            item = world.inventory.random_item()
            if world.population:
                agent = random.choice(world.population)
                agent.add_item(item)
                return f"Ресурс {item.name} передан агенту {agent.id[:8]}."

        elif action == "encourage_raids":
            # безопасное увеличение множителя
            mult = getattr(world.raids, 'difficulty_multiplier', 1.0)
            world.raids.difficulty_multiplier = mult * 1.1
            return "Частота рейдов увеличена."

        elif action == "promote_trade":
            world.market_event()
            return "Торговля стимулирована."

        elif action == "support_faction":
            if world.factions.factions:
                faction = random.choice(world.factions.factions)
                for agent in world.population:
                    if agent.faction == faction.name:
                        agent.gold += 50
                return f"Фракция {faction.name} получила поддержку."

        elif action == "spread_idea":
            if hasattr(world, 'memes'):
                idea = random.choice(["trust", "fear", "greed"])
                world.memes.spread_meme(idea, random.sample(world.population, min(3, len(world.population))))
                return f"Идея {idea} распространена."

        elif action == "stabilize_market":
            world.market.listings.clear()
            return "Рынок стабилизирован."

        return "Неизвестное действие"