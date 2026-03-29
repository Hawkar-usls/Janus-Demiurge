# janus_genesis/religion_engine.py
import random
import uuid
import os
import json
import logging
from config import RAW_LOGS_DIR

logger = logging.getLogger("JANUS.RELIGION")

class Religion:
    def __init__(self, founder, belief, religion_id=None, followers=None, influence=1.0, age=0):
        self.id = religion_id or str(uuid.uuid4())
        self.name = f"Cult of {founder.id[:4]}"
        self.founder = founder
        self.belief = belief
        self.followers = set(followers) if followers else set()
        self.holy_sites = []
        self.influence = influence
        self.age = age

    def add_follower(self, agent):
        self.followers.add(agent)

    def remove_follower(self, agent):
        self.followers.discard(agent)

    def spread(self, agents):
        new_followers = []
        for agent in agents:
            if agent not in self.followers and random.random() < self.influence * 0.01:
                self.add_follower(agent)
                new_followers.append(agent)
        return new_followers

    def update(self):
        self.age += 1
        self.influence *= 0.999
        if len(self.followers) > 10:
            self.influence *= 1.001

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'founder_id': self.founder.id,
            'belief': self.belief,
            'followers': [a.id for a in self.followers],
            'holy_sites': self.holy_sites,
            'influence': self.influence,
            'age': self.age
        }

    @classmethod
    def from_dict(cls, data, agents_by_id):
        founder = agents_by_id.get(data['founder_id'])
        if not founder:
            logger.warning(f"Основатель религии {data['name']} не найден, пропускаем")
            return None
        followers = set()
        for aid in data['followers']:
            if aid in agents_by_id:
                followers.add(agents_by_id[aid])
        religion = cls(founder, data['belief'], religion_id=data['id'], followers=followers,
                       influence=data['influence'], age=data['age'])
        religion.name = data['name']
        religion.holy_sites = data['holy_sites']
        return religion


class ReligionEngine:
    def __init__(self, world, event_bus, save_file=None):
        self.world = world
        self.event_bus = event_bus
        self.save_file = save_file or os.path.join(RAW_LOGS_DIR, "religions.json")
        self.religions = []
        self.load_state()

        event_bus.subscribe("agent_level_up", self.on_agent_level_up)
        event_bus.subscribe("artifact_found", self.on_artifact_found)

    def on_agent_level_up(self, agent):
        if agent.level >= 10 and random.random() < 0.1:
            beliefs = [
                "Entropy is sacred",
                "Optimization is salvation",
                "The Gradient is God",
                "Data is life"
            ]
            belief = random.choice(beliefs)
            religion = Religion(agent, belief)
            religion.add_follower(agent)
            self.religions.append(religion)
            self.event_bus.emit("religion_founded", religion=religion, founder=agent)
            logger.info(f"🛐 {agent.id[:8]} основал религию: {religion.name} — {belief}")
            self.save_state()

    def on_artifact_found(self, agent, item):
        if random.random() < 0.05:
            belief = f"{item.name} is divine"
            religion = Religion(agent, belief)
            religion.add_follower(agent)
            self.religions.append(religion)
            self.event_bus.emit("religion_founded", religion=religion, founder=agent)
            logger.info(f"🛐 {agent.id[:8]} основал религию вокруг артефакта {item.name}")
            self.save_state()

    def update(self):
        for religion in self.religions[:]:
            religion.update()
            new = religion.spread(self.world.population)
            if new:
                self.event_bus.emit("religion_spread", religion=religion, new_followers=new)
            if len(religion.followers) == 0:
                self.religions.remove(religion)
                self.event_bus.emit("religion_died", religion=religion)
        # периодическое сохранение (можно раз в 100 циклов, но пока сохраняем при изменении)
        self.save_state()

    def save_state(self):
        try:
            data = [religion.to_dict() for religion in self.religions]
            tmp = self.save_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.save_file)
            logger.debug("💾 Религии сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения религий: {e}")

    def load_state(self):
        if not os.path.exists(self.save_file):
            return
        try:
            with open(self.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Строим словарь агентов по id (нужен для восстановления)
            agents_by_id = {agent.id: agent for agent in self.world.population}
            self.religions = []
            for rel_data in data:
                religion = Religion.from_dict(rel_data, agents_by_id)
                if religion:
                    self.religions.append(religion)
            logger.info(f"📖 Загружено {len(self.religions)} религий")
        except Exception as e:
            logger.error(f"Ошибка загрузки религий: {e}")