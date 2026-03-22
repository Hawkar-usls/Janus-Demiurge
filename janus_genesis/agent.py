# janus_genesis/agent.py (исправленный)
import uuid
import random
import time
from typing import Dict, List, Optional, Any, Tuple

from .inventory import Inventory, Item

RACES = ["human", "synthetic", "mutant", "ancient"]
CLASSES = ["warrior", "mage", "rogue", "engineer"]
PROFESSIONS = ["miner", "blacksmith", "alchemist", "scribe", "trader"]

PARAM_RANGES = {
    'gain': (0.3, 2.0),
    'temperature': (0.3, 2.0),
    'lr': (1e-5, 1e-2),
    'n_embd': [128, 256, 384, 512, 768],
    'n_head': [4, 8, 12, 16],
    'n_layer': [4, 6, 8, 10, 12]
}


class JanusAgent:
    def __init__(self, config: Dict[str, Any]):
        # === ЗАЩИТА ОТ НЕПРАВИЛЬНОГО ТИПА ===
        if not isinstance(config, dict):
            print(f"[ERROR] JanusAgent.__init__: config is {type(config).__name__}, expected dict. Creating empty config.")
            config = {}
        # ====================================
        self.id = str(uuid.uuid4())
        self.base_config = config.copy()
        self.current_config = config.copy()
        self.level = 1
        self.exp = 0
        self.score = 0
        self.faction = None
        self.faction_bonus = {}
        self.inventory = Inventory(max_weight=100)   # новый инвентарь
        self.gold = 100
        self.mutation_bonus = 1.0

        self.race = random.choice(RACES)
        self.agent_class = random.choice(CLASSES)
        self.profession = random.choice(PROFESSIONS)
        self.clan = None
        self.reputation = {}
        self.skills = {self.profession: 1}

        self.belief = None
        self.risk_tolerance = 1.0
        self.aggression = 1.0
        self.greedy = 1.0
        self.learning_rate = 1.0

        self.arch_genome = None

        self.creation_time = time.time()
        self.last_train_time = self.creation_time

        self.config_memory: List[Dict[str, Any]] = []
        self.hypotheses: List[Dict[str, Any]] = []
        self.meta_goal: str = "SEARCH_P_VS_NP"

    @property
    def config(self):
        return self.current_config

    def add_exp(self, value: int) -> None:
        self.exp += value
        required = self._exp_for_level(self.level)
        while self.exp >= required and self.level < 100:
            self.level += 1
            self.exp -= required
            required = self._exp_for_level(self.level)
        if self.level >= 100:
            self.exp = 0

    @staticmethod
    def _exp_for_level(level: int) -> int:
        return 100 * (level ** 2)

    def add_item(self, item: Item) -> bool:
        return self.inventory.add_item(item)

    def remove_item(self, item: Item) -> bool:
        return self.inventory.remove_item(item)

    def equip_item(self, item: Item) -> Tuple[bool, str]:
        return self.inventory.equip(item)

    def unequip_item(self, slot: str) -> Tuple[bool, str]:
        return self.inventory.unequip(slot)

    def _apply_item_effects(self, item: Item):
        if "mutation_bonus" in item.effect:
            self.mutation_bonus *= (1 + item.effect["mutation_bonus"])

    def set_faction(self, faction_name: str, faction_bonus: Dict[str, float]) -> None:
        self.faction = faction_name
        self.faction_bonus = faction_bonus.copy()
        self._update_current_config()

    def _update_current_config(self) -> None:
        config = self.base_config.copy()
        # Бонусы фракции
        for param, delta in self.faction_bonus.items():
            if param in config and isinstance(config[param], (int, float)):
                config[param] += delta
        # Эффекты экипировки и сетов
        effects = self.inventory.all_effects()
        for param, delta in effects.items():
            if param in config and isinstance(config[param], (int, float)):
                config[param] += delta
        # Ограничения
        for param, value in config.items():
            if param in PARAM_RANGES:
                range_val = PARAM_RANGES[param]
                if isinstance(range_val, tuple):
                    low, high = range_val
                    config[param] = max(low, min(high, value))
                elif isinstance(range_val, list):
                    config[param] = min(range_val, key=lambda x: abs(x - value))
        if config['n_embd'] % config['n_head'] != 0:
            possible_heads = [h for h in PARAM_RANGES['n_head'] if config['n_embd'] % h == 0]
            if possible_heads:
                config['n_head'] = min(possible_heads, key=lambda x: abs(x - config['n_head']))
            else:
                config['n_head'] = 8
        self.current_config = config

    def apply_items(self) -> Dict[str, Any]:
        return self.current_config

    def train_reward(self, score: float) -> None:
        self.score = score
        record = {"config": self.current_config.copy(), "score": score}
        self.config_memory.append(record)
        xp = max(1, int(abs(score) * 10))
        self.add_exp(xp)
        self.last_train_time = time.time()
        self.gold += max(1, int(score * 5))
        self.generate_hypothesis()

    def generate_hypothesis(self) -> Optional[Dict[str, Any]]:
        if len(self.config_memory) < 5:
            return None
        best = max(self.config_memory, key=lambda x: x["score"])
        worst = min(self.config_memory, key=lambda x: x["score"])
        for param in ['lr', 'gain', 'temperature']:
            if best["config"][param] > worst["config"][param]:
                idea = f"increase_{param}"
            else:
                idea = f"decrease_{param}"
            break
        hypothesis = {"idea": idea, "confidence": random.random()}
        self.hypotheses.append(hypothesis)
        return hypothesis

    def mutate_config(self) -> Dict[str, Any]:
        new_config = self.current_config.copy()
        for param, ranges in PARAM_RANGES.items():
            if random.random() < 0.3:
                if isinstance(ranges, tuple):
                    low, high = ranges
                    delta = random.uniform(-0.1, 0.1) * (high - low)
                    new_config[param] += delta
                    new_config[param] = max(low, min(high, new_config[param]))
                elif isinstance(ranges, list):
                    idx = ranges.index(new_config[param]) if new_config[param] in ranges else 0
                    new_idx = max(0, min(len(ranges)-1, idx + random.choice([-1, 0, 1])))
                    new_config[param] = ranges[new_idx]
        for p in ['n_embd', 'n_head', 'n_layer']:
            new_config[p] = int(round(new_config[p]))
        if new_config['n_embd'] % new_config['n_head'] != 0:
            possible_heads = [h for h in PARAM_RANGES['n_head'] if new_config['n_embd'] % h == 0]
            if possible_heads:
                new_config['n_head'] = min(possible_heads, key=lambda x: abs(x - new_config['n_head']))
            else:
                new_config['n_head'] = 8
        return new_config

    def apply_belief(self) -> None:
        if self.belief == "P_EQUALS_NP":
            self.current_config["lr"] *= 1.1
            self.current_config["temperature"] *= 0.9
        elif self.belief == "P_NOT_EQUALS_NP":
            self.current_config["temperature"] *= 1.2
        elif self.belief == "CHAOS":
            low, high = PARAM_RANGES['lr']
            self.current_config["lr"] = random.uniform(low, high)
        elif self.belief == "BALANCE":
            self.current_config["lr"] = min(1e-2, max(1e-5, self.current_config["lr"]))
        for param, ranges in PARAM_RANGES.items():
            if isinstance(ranges, tuple):
                low, high = ranges
                self.current_config[param] = max(low, min(high, self.current_config[param]))
            elif isinstance(ranges, list):
                self.current_config[param] = min(ranges, key=lambda x: abs(x - self.current_config[param]))
        self._update_current_config()

    def decide_action(self) -> str:
        if len(self.config_memory) < 10:
            return "EXPLORE"
        avg_score = sum(x["score"] for x in self.config_memory[-10:]) / 10
        if avg_score > 0.8:
            return "EXPLOIT"
        if self.belief == "P_EQUALS_NP":
            return "OPTIMIZE"
        if self.belief == "P_NOT_EQUALS_NP":
            return "SEARCH_PROOF"
        if self.belief == "CHAOS":
            return "RANDOMIZE"
        if self.belief == "BALANCE":
            return "EXPLORE"
        return "EXPLORE"

    def choose_with_tachyon(self, tachyon, state) -> str:
        actions = ["EXPLORE", "EXPLOIT", "MUTATE", "SEARCH_PROOF", "OPTIMIZE"]
        scores = tachyon.evaluate_actions(state, actions)
        return max(scores, key=scores.get)

    def observe(self, other_agent: 'JanusAgent') -> bool:
        if other_agent.score > self.score:
            self.current_config = other_agent.current_config.copy()
            self._update_current_config()
            return True
        return False

    def pursue_meta_goal(self) -> Dict[str, Any]:
        if self.meta_goal == "SEARCH_P_VS_NP":
            return {"action": "generate_counterexample", "target": "complexity_boundary"}
        return {"action": "idle"}

    def can_afford(self, price: int) -> bool:
        return self.gold >= price

    def spend(self, amount: int) -> bool:
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'base_config': self.base_config,
            'level': self.level,
            'exp': self.exp,
            'score': self.score,
            'faction': self.faction,
            'faction_bonus': self.faction_bonus,
            'gold': self.gold,
            'mutation_bonus': self.mutation_bonus,
            'race': self.race,
            'agent_class': self.agent_class,
            'profession': self.profession,
            'clan': self.clan,
            'skills': self.skills,
            'belief': self.belief,
            'risk_tolerance': self.risk_tolerance,
            'aggression': self.aggression,
            'greedy': self.greedy,
            'learning_rate': self.learning_rate,
            'arch_genome': self.arch_genome.to_dict() if self.arch_genome else None,
            'creation_time': self.creation_time,
            'last_train_time': self.last_train_time,
            'config_memory': self.config_memory,
            'hypotheses': self.hypotheses,
            'meta_goal': self.meta_goal,
            'inventory': self.inventory.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], item_class=None, genome_class=None) -> 'JanusAgent':
        agent = cls(data['base_config'])
        agent.id = data['id']
        agent.level = data['level']
        agent.exp = data['exp']
        agent.score = data['score']
        agent.faction = data['faction']
        agent.faction_bonus = data.get('faction_bonus', {})
        agent.gold = data.get('gold', 100)
        agent.mutation_bonus = data.get('mutation_bonus', 1.0)
        agent.race = data.get('race', random.choice(RACES))
        agent.agent_class = data.get('agent_class', random.choice(CLASSES))
        agent.profession = data.get('profession', random.choice(PROFESSIONS))
        agent.clan = data.get('clan', None)
        agent.skills = data.get('skills', {agent.profession: 1})
        agent.belief = data.get('belief', None)
        agent.risk_tolerance = data.get('risk_tolerance', 1.0)
        agent.aggression = data.get('aggression', 1.0)
        agent.greedy = data.get('greedy', 1.0)
        agent.learning_rate = data.get('learning_rate', 1.0)
        if genome_class and data.get('arch_genome'):
            agent.arch_genome = genome_class.from_dict(data['arch_genome'])
        agent.creation_time = data.get('creation_time', time.time())
        agent.last_train_time = data.get('last_train_time', agent.creation_time)
        agent.config_memory = data.get('config_memory', [])
        agent.hypotheses = data.get('hypotheses', [])
        agent.meta_goal = data.get('meta_goal', "SEARCH_P_VS_NP")
        if 'inventory' in data:
            agent.inventory = Inventory.from_dict(data['inventory'])
        agent._update_current_config()
        return agent

    def __repr__(self):
        return f"<JanusAgent {self.race} {self.agent_class} lvl={self.level} score={self.score:.2f} gold={self.gold}>"