# janus_genesis/state_encoder.py
"""
Преобразует состояние мира в компактный вектор для обучения Януса.
"""

class WorldStateEncoder:
    def encode(self, world):
        """Возвращает список чисел – состояние мира."""
        return [
            len(world.population),                          # 0
            sum(a.level for a in world.population) / max(len(world.population), 1),  # 1
            world.economy.resources.get("compute", 0),      # 2
            world.economy.resources.get("data", 0),         # 3
            world.economy.resources.get("entropy", 0),      # 4
            len(world.market.listings),                     # 5
            len(world.party_system.parties),                # 6
            len(world.institutions.institutions) if hasattr(world, 'institutions') else 0,  # 7
            world.tick                                       # 8
        ]