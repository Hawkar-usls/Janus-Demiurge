# janus_genesis/agent.py (гибридный SAT-решатель с защитой от несовместимых решений в памяти)
import uuid
import random
import time
import logging
from typing import Dict, List, Optional, Any, Tuple

from .inventory import Inventory, Item

logger = logging.getLogger("JANUS_AGENT")

RACES = ["human", "synthetic", "mutant", "ancient"]
CLASSES = ["warrior", "mage", "rogue", "engineer"]
PROFESSIONS = ["miner", "blacksmith", "alchemist", "scribe", "trader"]

PARAM_RANGES = {
    'gain': (0.5, 1.5),
    'temperature': (0.5, 1.5),
    'lr': (1e-5, 5e-3),
    'n_embd': [128, 256, 384, 512, 768],
    'n_head': [4, 8, 12, 16],
    'n_layer': [4, 6, 8, 10, 12]
}


class Buff:
    def __init__(self, name: str, duration: int, effects: Dict[str, float]):
        self.name = name
        self.duration = duration
        self.effects = effects


class JanusAgent:
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            config = {}
        self.id = str(uuid.uuid4())
        self.base_config = config.copy()
        self.current_config = config.copy()
        self.level = 1
        self.exp = 0
        self.score = 0
        self.faction = None
        self.faction_bonus = {}
        self.inventory = Inventory(max_weight=100)
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

        self.buffs: List[Buff] = []
        self.disease: Optional[str] = None
        self.relationships: Dict[str, float] = {}
        self.needs: Dict[str, float] = {}

        # Память хороших решений для meta-learning
        self.sat_memory: List[List[bool]] = []

        self.np_context = "DEFAULT"

    @property
    def config(self):
        return self.current_config

    # ---------- Вспомогательные методы (болезни, баффы, отношения) ----------
    def add_buff(self, name: str, duration: int, effects: Dict[str, float]) -> None:
        self.buffs.append(Buff(name, duration, effects))

    def remove_buff(self, name: str) -> None:
        self.buffs = [b for b in self.buffs if b.name != name]

    def update_buffs(self) -> None:
        for buff in self.buffs[:]:
            for attr, delta in buff.effects.items():
                if hasattr(self, attr):
                    setattr(self, attr, getattr(self, attr) * delta)
            buff.duration -= 1
            if buff.duration <= 0:
                self.buffs.remove(buff)

    def set_disease(self, disease_name: str) -> None:
        self.disease = disease_name

    def cure_disease(self) -> None:
        self.disease = None

    def update_disease(self, disease_config: Dict) -> None:
        if not self.disease:
            return
        effect = disease_config.get(self.disease, {})
        if "score_penalty" in effect:
            self.score -= effect["score_penalty"]
        if "learning_rate_penalty" in effect:
            self.learning_rate *= (1 - effect["learning_rate_penalty"])

    def update_relationship(self, other_id: str, delta: float) -> None:
        current = self.relationships.get(other_id, 0.0)
        self.relationships[other_id] = max(-1.0, min(1.0, current + delta))

    def get_relationship(self, other_id: str) -> float:
        return self.relationships.get(other_id, 0.0)

    def apply_hyper_effect(self, knowledge: Dict[str, Any]) -> None:
        for param, value in knowledge.items():
            self.base_config[param] = value
        self._update_current_config()

    # ---------- Уровни, опыт, инвентарь ----------
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

    # ---------- Конфигурация и обучение ----------
    def set_faction(self, faction_name: str, faction_bonus: Dict[str, float]) -> None:
        self.faction = faction_name
        self.faction_bonus = faction_bonus.copy()
        self._update_current_config()

    def _update_current_config(self) -> None:
        config = self.base_config.copy()
        for param, delta in self.faction_bonus.items():
            if param in config and isinstance(config[param], (int, float)):
                config[param] += delta
        effects = self.inventory.all_effects()
        for param, delta in effects.items():
            if param in config and isinstance(config[param], (int, float)):
                config[param] += delta
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
            self.current_config["lr"] = min(5e-3, max(1e-5, self.current_config["lr"]))
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

    # ========== ГИБРИДНЫЙ РЕШАТЕЛЬ 3-SAT (Clause Weighting + Meta-learning) ==========

    def _clause_satisfied(self, clause, assignment):
        for var, neg in clause:
            idx = var - 1
            if idx < 0 or idx >= len(assignment):
                continue
            val = assignment[idx]
            if neg:
                val = not val
            if val:
                return True
        return False

    def _init_clause_weights(self, clauses):
        return [1.0 for _ in clauses]

    def _update_clause_weights(self, weights, assignment, clauses):
        new_weights = weights.copy()
        for i, clause in enumerate(clauses):
            if not self._clause_satisfied(clause, assignment):
                new_weights[i] += 0.2
            else:
                new_weights[i] *= 0.98
        return [min(w, 10.0) for w in new_weights]

    def _fitness_weighted(self, assignment, clauses, weights):
        score = 0.0
        for w, clause in zip(weights, clauses):
            if self._clause_satisfied(clause, assignment):
                score += w
        return score

    def _batch_fitness(self, population, clauses, weights):
        scores = []
        for sol in population:
            scores.append(self._fitness_weighted(sol, clauses, weights))
        return scores

    def _walksat(self, solution, clauses, steps=60):
        n_vars = len(solution)
        for _ in range(steps):
            unsat = []
            for clause in clauses:
                if not self._clause_satisfied(clause, solution):
                    unsat.append(clause)
            if not unsat:
                return solution
            clause = random.choice(unsat)
            if random.random() < 0.5:
                var = abs(random.choice(clause)[0]) - 1
            else:
                best_var = None
                best_score = -1
                for lit in clause:
                    var_idx = abs(lit[0]) - 1
                    if var_idx < 0 or var_idx >= n_vars:
                        continue
                    solution[var_idx] = not solution[var_idx]
                    score = self._fitness_weighted(solution, clauses, [1.0]*len(clauses))
                    solution[var_idx] = not solution[var_idx]
                    if score > best_score:
                        best_score = score
                        best_var = var_idx
                var = best_var
            if var is not None and 0 <= var < n_vars:
                solution[var] = not solution[var]
        return solution

    def _hill_climb(self, solution, clauses, steps=60):
        n_vars = len(solution)
        for _ in range(steps):
            improved = False
            base_score = self._fitness_weighted(solution, clauses, [1.0]*len(clauses))
            for i in range(n_vars):
                solution[i] = not solution[i]
                score = self._fitness_weighted(solution, clauses, [1.0]*len(clauses))
                if score > base_score:
                    improved = True
                    base_score = score
                else:
                    solution[i] = not solution[i]
            if not improved:
                break
        return solution

    def _inject_memory(self, population, n_vars):
        """Внедряет в начало популяции мутированные копии из памяти хороших решений"""
        if not self.sat_memory:
            return population
        memory_copy = []
        # Берём до 5 случайных решений из памяти, но только совместимые по размеру
        candidates = [sol for sol in self.sat_memory if len(sol) == n_vars]
        if not candidates:
            return population
        for _ in range(min(5, len(candidates))):
            base = random.choice(candidates)
            mutated = base.copy()
            for j in range(n_vars):
                if random.random() < 0.1:
                    mutated[j] = not mutated[j]
            memory_copy.append(mutated)
        for i, sol in enumerate(memory_copy):
            if i < len(population):
                population[i] = sol
        return population

    def solve_np_task(self, task, timeout=2.0):
        n_vars = task.n_vars
        clauses = task.clauses
        n_clauses = len(clauses)

        # Проверка корректности задачи
        if clauses:
            max_var = max(abs(lit[0]) for clause in clauses for lit in clause)
            if max_var > n_vars:
                logger.warning(f"Некорректная задача: максимальная переменная {max_var} > {n_vars}. Решение невозможно.")
                return False, [], 0.0

        # Защита от слишком низких параметров из мета-режима
        base_gain = max(0.8, self.current_config.get('gain', 1.0))
        base_temp = max(0.8, self.current_config.get('temperature', 1.0))
        learning_rate = self.learning_rate

        if n_vars > 30:
            base_gain *= 1.5
            base_temp *= 1.5

        pop_size = max(32, int(64 * base_temp * learning_rate))
        mutation_rate = 0.15 * base_gain

        weights = self._init_clause_weights(clauses)

        def random_solution():
            return [random.choice([True, False]) for _ in range(n_vars)]

        population = [random_solution() for _ in range(pop_size)]
        population = self._inject_memory(population, n_vars)

        best_solution = None
        best_fitness = 0
        total_weight = sum(weights)

        start_time = time.time()
        while time.time() - start_time < timeout:
            scores = self._batch_fitness(population, clauses, weights)
            ranked = sorted(zip(population, scores), key=lambda x: x[1], reverse=True)
            population = [x[0] for x in ranked]

            current_fitness = ranked[0][1]
            if current_fitness > best_fitness:
                best_fitness = current_fitness
                best_solution = population[0].copy()

            if best_fitness >= total_weight:
                if best_solution and len(best_solution) == n_vars:
                    self.sat_memory.append(best_solution)
                    if len(self.sat_memory) > 50:
                        self.sat_memory.pop(0)
                reward_mult = 1.0 + task.difficulty() * 0.1
                return True, best_solution, reward_mult

            weights = self._update_clause_weights(weights, population[0], clauses)
            total_weight = sum(weights)

            new_pop = population[:8]
            while len(new_pop) < pop_size:
                parent = random.choice(population[:16])
                child = parent.copy()
                for i in range(n_vars):
                    if random.random() < mutation_rate:
                        child[i] = not child[i]
                child = self._walksat(child, clauses, steps=40)
                child = self._hill_climb(child, clauses, steps=40)
                new_pop.append(child)
            population = new_pop

        if best_solution and best_fitness > 0.8 * n_clauses:
            if len(best_solution) == n_vars:
                self.sat_memory.append(best_solution)
                if len(self.sat_memory) > 50:
                    self.sat_memory.pop(0)

        solved = best_fitness == n_clauses
        reward_mult = (best_fitness / n_clauses) * (1 + task.difficulty() * 0.1) if not solved else 1.0 + task.difficulty() * 0.1
        return solved, best_solution, reward_mult

    # ---------- Сериализация ----------
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
            'inventory': self.inventory.to_dict(),
            'buffs': [{'name': b.name, 'duration': b.duration, 'effects': b.effects} for b in self.buffs],
            'disease': self.disease,
            'relationships': self.relationships,
            'sat_memory': self.sat_memory,
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
        if 'buffs' in data:
            for bd in data['buffs']:
                agent.buffs.append(Buff(bd['name'], bd['duration'], bd['effects']))
        agent.disease = data.get('disease', None)
        agent.relationships = data.get('relationships', {})
        agent.sat_memory = data.get('sat_memory', [])
        agent._update_current_config()
        return agent

    def __repr__(self):
        return f"<JanusAgent {self.race} {self.agent_class} lvl={self.level} score={self.score:.2f} gold={self.gold}>"