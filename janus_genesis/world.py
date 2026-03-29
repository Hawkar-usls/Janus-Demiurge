# janus_genesis/world.py (исправленный: восстановление arch_genome + связь артефактов + динамические шансы + вера при создании)
import os
import json
import random
import time
import numpy as np
import copy
from .agent import JanusAgent, RACES, CLASSES, PROFESSIONS
from .inventory import Inventory, Item
from .factions import FactionSystem
from .economy import Economy
from .raids import RaidSystem
from .events import EventSystem
from .needs import NeedsSystem
from .disease import DiseaseSystem
from .buffs import BuffSystem
from .crafting import CraftingSystem
from .party import PartySystem
from .event_bus import EventBus
from .institutions import InstitutionSystem
from .memes import MemeSystem
from .religion_engine import ReligionEngine
from .tech_evolution import TechEvolutionEngine
from .war_empire_engine import WarEmpireEngine
from .environment import WeatherSystem
from .cultural_evolution import CulturalEvolutionEngine
from .economic_collapse import EconomicCollapseSimulator
from .legendary_leaders import LegendaryLeaderSystem
from architect_ai import ArchitectureGenome

from world_memory import WorldMemory
from meaning_engine import MeaningEngine
from meta_consciousness import MetaConsciousness
from janus_self import JanusSelf
from divine_laws import DivineLaws

from config import RAW_LOGS_DIR

class Market:
    def __init__(self):
        self.listings = []
        self.transaction_history = []

    def add_listing(self, item, price, seller_id):
        self.listings.append({
            'item': item,
            'price': price,
            'seller_id': seller_id
        })

    def remove_listing(self, index):
        if 0 <= index < len(self.listings):
            return self.listings.pop(index)
        return None

    def clear_expired(self):
        pass


class JanusWorld:
    def __init__(self, real_economy=None, save_file=None, hrain_daemon=None):
        self.tick = 0
        self.population = []
        self.inventory = Inventory()
        self.factions = FactionSystem()
        self.economy = Economy()
        self.raids = RaidSystem()
        self.real_economy = real_economy
        self.market = Market()
        self.events = EventSystem()
        self.hrain = hrain_daemon

        self.needs = NeedsSystem()
        self.disease = DiseaseSystem()
        self.buffs = BuffSystem()
        self.crafting = CraftingSystem()
        self.party_system = PartySystem()
        self.event_bus = EventBus()
        self.institutions = InstitutionSystem(self.event_bus)
        self.memes = MemeSystem(self.event_bus)

        self.religion = ReligionEngine(self, self.event_bus)
        self.tech = TechEvolutionEngine(self, self.event_bus)
        self.war = WarEmpireEngine(self, self.event_bus)

        self.weather = WeatherSystem(self, self.event_bus)
        self.culture = CulturalEvolutionEngine(self, self.event_bus)
        self.economy_collapse = EconomicCollapseSimulator(self, self.event_bus)
        self.leaders = LegendaryLeaderSystem(self, self.event_bus)

        self.memory = WorldMemory()
        self.meaning = MeaningEngine(self)
        self.meta = MetaConsciousness(self)

        self.janus_self = JanusSelf()
        self.laws = DivineLaws(self)

        if save_file is None:
            self.save_file = os.path.join(RAW_LOGS_DIR, "janus_world_agents.json")
        else:
            self.save_file = save_file

        # Переопределяемые шансы (для Демиурга)
        self.raid_chance_override = None
        self.market_chance_override = None

        self.load()

    def spawn_agent(self, config):
        if not isinstance(config, dict):
            print(f"[ERROR] spawn_agent: config has type {type(config).__name__}, expected dict. Using empty config.")
            config = {}
        agent = JanusAgent(config)
        # Назначаем веру при создании, если ещё нет
        if agent.belief is None:
            agent.belief = random.choice(["P_EQUALS_NP", "P_NOT_EQUALS_NP", "BALANCE", "CHAOS"])
        self.factions.assign_faction(agent)
        self.needs.init_agent(agent)
        self.buffs.init_agent(agent)
        if random.random() < 0.3:
            item = self.inventory.random_item()
            agent.add_item(item)
        self.population.append(agent)
        self.event_bus.emit("agent_created", agent=agent)
        self.memory.record("agent_created", {"agent_id": agent.id, "faction": agent.faction})
        return agent

    def reward_agent(self, agent, score):
        agent.train_reward(score)
        if random.random() < 0.2:
            item = self.inventory.random_item()
            agent.add_item(item)
        self.memory.record("agent_rewarded", {"agent_id": agent.id, "score": score})

    def raid_event(self):
        if not self.population:
            return
        boss = self.raids.random_boss()
        parties = [p for p in self.party_system.parties if p.is_active()]
        if parties and random.random() < 0.5:
            party = random.choice(parties)
            participants = party.members
            group_power = party.get_power()
            agent_names = ", ".join([a.id[:4] for a in participants])
            print(f"     [👥] Группа {agent_names} атакует {boss.name}!")
        else:
            participants = [random.choice(self.population)]
            group_power = participants[0].level + participants[0].score

        win = self.raids.fight(participants, boss)
        event_data = {
            "type": "world_event",
            "subtype": "raid",
            "tick": self.tick,
            "boss_name": boss.name,
            "win": win,
            "participants": [a.id for a in participants]
        }
        self.memory.record("raid", {"boss": boss.name, "win": win, "participants": [a.id for a in participants]})

        if win:
            reward = self.economy.reward()
            self.economy.apply_reward(reward)
            for agent in participants:
                agent.add_exp(50)
            for agent in participants:
                if random.random() < 0.3:
                    artifact = self.inventory.random_item(rarity="rare", with_knowledge=True)
                    agent.add_item(artifact)
            print(f"     [⚔️] Группа победила {boss.name}! +50 XP каждому, ресурсы +{reward}, артефакты выпали.")
            event_data["reward"] = reward
            self.event_bus.emit("raid_win", agents=participants, boss_name=boss.name)
        else:
            print(f"     [💀] Группа проиграла {boss.name}...")
        if self.hrain:
            self.hrain.send_event(event_data)

    def market_event(self):
        if len(self.population) < 2:
            return
        seller = random.choice(self.population)
        buyer = random.choice([a for a in self.population if a.id != seller.id])
        if not seller.inventory.items:
            return
        item = random.choice(seller.inventory.items)
        price = item.value if hasattr(item, 'value') else 10
        self.market.add_listing(item, price, seller.id)
        print(f"     [🏪] {seller} выставил {item.name} за {price} золота")
        if self.hrain:
            self.hrain.send_event({
                "type": "world_event",
                "subtype": "market_listing",
                "tick": self.tick,
                "seller_id": seller.id,
                "item_name": item.name,
                "price": price
            })

        if buyer.gold >= price and random.random() < 0.3:
            buyer.spend(price)
            seller.gold += price
            seller.remove_item(item)
            buyer.add_item(item)
            print(f"     [🛒] {buyer} купил предмет")
            self.market.remove_listing(-1)
            self.event_bus.emit("market_transaction", seller=seller, buyer=buyer, item=item, price=price)
            if self.hrain:
                self.hrain.send_event({
                    "type": "world_event",
                    "subtype": "market_purchase",
                    "tick": self.tick,
                    "seller_id": seller.id,
                    "buyer_id": buyer.id,
                    "item_name": item.name,
                    "price": price
                })

    def adapt_content(self):
        if not self.population:
            return
        avg_level = np.mean([a.level for a in self.population])
        avg_score = np.mean([a.score for a in self.population])
        self.raids.adapt_all(avg_level, avg_score)
        self.events.event_chance = 0.1 + 0.05 * avg_level

    def update(self, pc_metrics=None, cardputer_metrics=None):
        self.tick += 1

        self.meaning.update()

        for agent in self.population:
            self.needs.update(agent)
            self.disease.update(agent)
            self.buffs.update(agent)
            self.disease.infect(agent)

        if pc_metrics:
            self.weather.update_from_real_metrics(pc_metrics, cardputer_metrics or {})
        self.weather.apply_effects()

        self.economy_collapse.update()
        self.culture.evolve()
        self.leaders.influence_world()

        # Рейдовое событие (шанс может быть переопределён Демиургом)
        raid_chance = self.raid_chance_override if self.raid_chance_override is not None else 0.05
        if random.random() < raid_chance:
            self.raid_event()

        # Рыночное событие (шанс может быть переопределён Демиургом)
        market_chance = self.market_chance_override if self.market_chance_override is not None else 0.05
        if random.random() < market_chance:
            self.market_event()

        self.events.update(self)

        if self.tick % 10 == 0:
            self.adapt_content()

        self.party_system.update(self)
        self.institutions.update(self)
        self.memes.update(self)
        self.religion.update()
        self.tech.update()
        self.war.update()

        for agent in self.population:
            if agent.level > getattr(agent, '_last_level', 0):
                self.event_bus.emit("agent_level_up", agent=agent)
                agent._last_level = agent.level

    def craft(self, agent, ingredients):
        success, msg, item = self.crafting.craft(agent, ingredients)
        if success and self.hrain:
            self.hrain.send_event({
                "type": "world_event",
                "subtype": "craft",
                "agent_id": agent.id,
                "ingredients": ingredients,
                "result": item.name if item else None
            })
            self.event_bus.emit("craft", agent=agent, item=item)
        return success, msg, item

    def form_party(self, leader, invitees):
        party = self.party_system.create_party(leader)
        for agent in invitees:
            if agent != leader:
                party.add_member(agent)
        self.event_bus.emit("party_formed", party=party, leader=leader, members=invitees)
        return party

    def altar_transform(self, items_json):
        try:
            items = json.loads(items_json) if isinstance(items_json, str) else items_json
            if not items:
                return None
            combined_effect = {}
            total_weight = 0
            for item in items:
                for k, v in item.get('effect', {}).items():
                    combined_effect[k] = combined_effect.get(k, 0) + v
                total_weight += item.get('weight', 1)
            new_name = f"Altar Fusion ({len(items)} items)"
            new_item = Item(new_name, combined_effect, weight=total_weight)
            return new_item
        except Exception as e:
            print(f"Altar error: {e}")
            return None

    def save(self):
        data = {
            'tick': self.tick,
            'population': []
        }
        for agent in self.population:
            agent_data = {
                'id': agent.id,
                'base_config': agent.base_config,
                'level': agent.level,
                'exp': agent.exp,
                'score': agent.score,
                'faction': agent.faction,
                'faction_bonus': agent.faction_bonus,
                'gold': agent.gold,
                'mutation_bonus': agent.mutation_bonus,
                'race': agent.race,
                'agent_class': agent.agent_class,
                'profession': agent.profession,
                'clan': agent.clan,
                'skills': agent.skills,
                'creation_time': agent.creation_time,
                'last_train_time': agent.last_train_time,
                'needs': getattr(agent, 'needs', {}),
                'disease': getattr(agent, 'disease', None),
                'buffs': [{'name': b.name, 'duration': b.duration, 'effects': b.effects} for b in getattr(agent, 'buffs', [])],
                'inventory': agent.inventory.to_dict()
            }
            if agent.arch_genome is not None:
                agent_data['arch_genome'] = agent.arch_genome.to_dict()
            data['population'].append(agent_data)
        data['weather'] = self.weather.get_state()
        data['crisis'] = {
            'active': self.economy_collapse.crisis_active,
            'severity': self.economy_collapse.crisis_severity,
            'region': self.economy_collapse.crisis_region
        }
        data['memory'] = self.memory.events[-100:]
        try:
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения мира: {e}")

    def load(self):
        if not os.path.exists(self.save_file):
            return
        try:
            with open(self.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                print(f"⚠️ Файл {self.save_file} имеет устаревший формат (список). Создаётся новый мир.")
                self.tick = 0
                self.population = []
                return
            self.tick = data.get('tick', 0)
            self.population.clear()
            if 'memory' in data:
                self.memory.events = data['memory']
            for agent_data in data.get('population', []):
                agent = JanusAgent.from_dict(agent_data, item_class=Item, genome_class=ArchitectureGenome)
                agent._update_current_config()
                self.needs.init_agent(agent)
                if hasattr(self.buffs, 'init_agent'):
                    self.buffs.init_agent(agent)
                if hasattr(self.disease, 'init_agent'):
                    self.disease.init_agent(agent)
                self.population.append(agent)
            print(f"🌍 Мир загружен: {len(self.population)} агентов, тик {self.tick}")
        except Exception as e:
            print(f"Ошибка загрузки мира: {e}")

    def clone_for_simulation(self):
        sim_world = JanusWorld(real_economy=None, save_file=None, hrain_daemon=None)
        sim_world.tick = self.tick
        sim_world.population = copy.deepcopy(self.population)
        sim_world.inventory = copy.deepcopy(self.inventory)
        sim_world.factions = copy.deepcopy(self.factions)
        sim_world.economy = copy.deepcopy(self.economy)
        sim_world.raids = copy.deepcopy(self.raids)
        sim_world.market = Market()
        sim_world.events = copy.deepcopy(self.events)
        sim_world.needs = copy.deepcopy(self.needs)
        sim_world.disease = copy.deepcopy(self.disease)
        sim_world.buffs = copy.deepcopy(self.buffs)
        sim_world.crafting = copy.deepcopy(self.crafting)
        sim_world.party_system = copy.deepcopy(self.party_system)
        sim_world.event_bus = EventBus()
        sim_world.institutions = InstitutionSystem(sim_world.event_bus)
        sim_world.memes = MemeSystem(sim_world.event_bus)
        sim_world.religion = ReligionEngine(sim_world, sim_world.event_bus)
        sim_world.tech = TechEvolutionEngine(sim_world, sim_world.event_bus)
        sim_world.war = WarEmpireEngine(sim_world, sim_world.event_bus)
        sim_world.weather = WeatherSystem(sim_world, sim_world.event_bus)
        sim_world.culture = CulturalEvolutionEngine(sim_world, sim_world.event_bus)
        sim_world.economy_collapse = EconomicCollapseSimulator(sim_world, sim_world.event_bus)
        sim_world.leaders = LegendaryLeaderSystem(sim_world, sim_world.event_bus)
        sim_world.memory = WorldMemory()
        sim_world.meaning = MeaningEngine(sim_world)
        sim_world.meta = MetaConsciousness(sim_world)
        sim_world.janus_self = JanusSelf()
        sim_world.laws = DivineLaws(sim_world)
        return sim_world