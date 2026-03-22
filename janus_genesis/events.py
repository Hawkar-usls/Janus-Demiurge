import random
import time

class Event:
    """Базовое событие в мире."""
    def __init__(self, name, description, duration=1):
        self.name = name
        self.description = description
        self.duration = duration  # сколько тиков активно
        self.start_time = time.time()

    def is_active(self):
        return (time.time() - self.start_time) < self.duration * 60  # условно минуты

    def apply_effect(self, world):
        """Может изменять параметры мира."""
        pass

    def get_reward(self, participant):
        """Награда участнику."""
        return {}


class RaidEvent(Event):
    """Событие "нашествие монстров" – появляется сильный босс."""
    def __init__(self, difficulty):
        super().__init__("Нашествие", "Орды монстров атакуют!", duration=10)
        self.difficulty = difficulty
        self.boss_spawned = False

    def apply_effect(self, world):
        if not self.boss_spawned:
            # спавним дополнительного босса
            boss = world.raids.random_boss()
            boss.current_difficulty = self.difficulty
            world.raid_boss = boss  # допустим, в world есть поле raid_boss
            self.boss_spawned = True


class TradeCaravan(Event):
    """Торговая караван – можно купить редкие предметы."""
    def __init__(self):
        super().__init__("Караван", "Торговцы привезли редкие товары!", duration=5)
        self.inventory = []  # список предметов с ценами

    def apply_effect(self, world):
        if not self.inventory:
            # генерируем несколько предметов
            from .inventory import Inventory
            inv = Inventory()
            for _ in range(3):
                item = inv.random_item()
                price = world.economy.market.suggest_price(item) * 2
                self.inventory.append((item, price))


class ExplorationQuest(Event):
    """Квест на исследование новой локации."""
    def __init__(self, location):
        super().__init__("Экспедиция", f"Исследуйте {location}!", duration=20)
        self.location = location
        self.reward_exp = 100
        self.reward_gold = 200


class EventSystem:
    """Генератор и обработчик событий."""
    def __init__(self):
        self.active_events = []
        self.event_chance = 0.1  # шанс нового события за тик

    def update(self, world):
        # Генерируем новое событие
        if random.random() < self.event_chance and len(self.active_events) < 3:
            event_type = random.choice(['raid', 'caravan', 'quest'])
            if event_type == 'raid':
                diff = random.randint(5, 15)
                self.active_events.append(RaidEvent(diff))
            elif event_type == 'caravan':
                self.active_events.append(TradeCaravan())
            else:
                loc = random.choice(world.locations) if hasattr(world, 'locations') else "Неизвестная земля"
                self.active_events.append(ExplorationQuest(loc))

        # Обрабатываем активные события
        for event in self.active_events[:]:
            event.apply_effect(world)
            if not event.is_active():
                self.active_events.remove(event)

    def get_active_events(self):
        return self.active_events