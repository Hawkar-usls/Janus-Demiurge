import random

class RaidBoss:
    """Рейдовый босс — сложная задача, сложность адаптируется к популяции."""

    def __init__(self, name, base_difficulty, loot_table=None):
        self.name = name
        self.base_difficulty = base_difficulty
        self.current_difficulty = base_difficulty
        self.loot_table = loot_table if loot_table else []

    def adapt_to_population(self, avg_level, avg_score):
        """Подстраивает сложность под средний уровень популяции."""
        # Сложность растёт с уровнем и падает с силой популяции (чтобы боссы не были слишком лёгкими)
        target_difficulty = self.base_difficulty * (1 + 0.1 * avg_level) * (1 + 0.05 * avg_score)
        self.current_difficulty = max(1, int(target_difficulty))
        return self.current_difficulty

    @property
    def hp(self):
        return self.current_difficulty * 1000

    def get_loot(self):
        loot = []
        for item, chance in self.loot_table:
            if random.random() < chance:
                loot.append(item)
        return loot


class RaidSystem:
    """Система рейдов с адаптивной сложностью."""

    def __init__(self):
        self.bosses = [
            RaidBoss("Language Hydra", 5, loot_table=[
                ("Attention Crystal", 0.8),
                ("Gradient Shard", 0.5),
            ]),
            RaidBoss("Entropy Titan", 8, loot_table=[
                ("Entropy Stone", 0.9),
                ("Optimizer Core", 0.4),
                ("Artifact of Evolution", 0.1),
            ]),
            RaidBoss("Compression Leviathan", 10, loot_table=[
                ("Embedding Relic", 0.7),
                ("Layer Fragment", 0.6),
                ("Artifact of Evolution", 0.2),
            ]),
            RaidBoss("Gradient Dragon", 12, loot_table=[
                ("Gradient Shard", 0.9),
                ("Attention Crystal", 0.8),
                ("Artifact of Evolution", 0.3),
            ]),
        ]

    def random_boss(self):
        return random.choice(self.bosses)

    def adapt_all(self, avg_level, avg_score):
        for boss in self.bosses:
            boss.adapt_to_population(avg_level, avg_score)

    def fight(self, party, boss):
        """
        Бой группы агентов с боссом.
        party: список агентов.
        Возвращает (win, loot), где win - bool, loot - список предметов.
        """
        total_power = sum(agent.level + agent.score * 2 for agent in party)
        damage = total_power * random.random()
        win = damage > boss.current_difficulty * 5
        loot = boss.get_loot() if win else []
        return win, loot