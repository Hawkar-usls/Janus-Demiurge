# janus_genesis/buffs.py
class Buff:
    """Класс бафа (временного эффекта)."""
    def __init__(self, name, duration, effects):
        self.name = name
        self.duration = duration  # в тиках
        self.effects = effects    # словарь {атрибут: изменение}

class BuffSystem:
    """Система управления бафами агентов."""

    def init_agent(self, agent):
        """Добавляет агенту список бафов."""
        agent.buffs = []

    def apply_buff(self, agent, buff):
        """Применяет баф к агенту."""
        agent.buffs.append(buff)

    def update(self, agent):
        """Обновляет длительность бафов и применяет эффекты."""
        for buff in agent.buffs[:]:
            for attr, val in buff.effects.items():
                if hasattr(agent, attr):
                    setattr(agent, attr, getattr(agent, attr) + val)
            buff.duration -= 1
            if buff.duration <= 0:
                agent.buffs.remove(buff)