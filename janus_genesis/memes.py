# janus_genesis/memes.py
"""
Экология информации: мемы, слухи, идеи.
"""

import random

class Meme:
    def __init__(self, text, spread_rate=None):
        self.text = text
        self.strength = 1.0
        self.spread_rate = spread_rate if spread_rate is not None else random.uniform(0.1, 0.5)
        self.holders = set()

    def spread(self, agents):
        """Распространить мем среди агентов."""
        new_holders = []
        for agent in agents:
            if agent not in self.holders and random.random() < self.spread_rate:
                self.holders.add(agent)
                if hasattr(agent, 'memory'):
                    agent.memory.append(self.text)
                new_holders.append(agent)
        return new_holders

    def influence(self, agent):
        """Влияние мема на поведение агента (заглушка)."""
        # Можно реализовать позже, например изменение score, решений и т.д.
        pass


class MemeSystem:
    def __init__(self, event_bus):
        self.memes = []
        self.event_bus = event_bus
        event_bus.subscribe("agent_created", self.on_agent_created)
        event_bus.subscribe("institution_founded", self.on_institution_founded)

    def on_agent_created(self, agent):
        """Новый агент может случайно подхватить мем."""
        if self.memes and random.random() < 0.1:
            meme = random.choice(self.memes)
            meme.holders.add(agent)

    def on_institution_founded(self, institution, founder):
        """Основание института может породить мем."""
        meme_text = f"{institution.type} of {founder.id[:4]} is powerful!"
        meme = Meme(meme_text, spread_rate=0.3)
        self.memes.append(meme)
        meme.holders.add(founder)

    def spread_meme(self, text, agents):
        """Создать новый мем и распространить среди указанных агентов."""
        meme = Meme(text)
        self.memes.append(meme)
        for agent in agents:
            meme.holders.add(agent)
        return meme

    def update(self, world):
        """Ежедневное распространение мемов."""
        for meme in self.memes:
            meme.spread(world.population)
            # Старые мемы теряют силу
            meme.strength *= 0.999
        # Удаляем очень слабые мемы
        self.memes = [m for m in self.memes if m.strength > 0.1]