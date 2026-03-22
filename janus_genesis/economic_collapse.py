# janus_genesis/economic_collapse.py
"""
Экономические кризисы больше не случайны – они возникают из-за накопления факторов:
- Инфляция (слишком много золота у агентов)
- Истощение ресурсов (слишком много крафта, мало добычи)
- Войны (империи) разрушают торговлю
- Погодные катаклизмы
- Болезни снижают работоспособность
"""

import random
import numpy as np

class EconomicCollapseSimulator:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.inflation = 1.0
        self.crisis_active = False
        self.crisis_region = None  # может быть фракция или регион
        self.crisis_severity = 0.0

        # Подписываемся на события
        event_bus.subscribe("weather_disaster", self.on_weather_disaster)
        event_bus.subscribe("war_started", self.on_war_started)
        event_bus.subscribe("empire_destroyed", self.on_empire_destroyed)

    def on_weather_disaster(self, disaster):
        """Природное бедствие может спровоцировать локальный кризис."""
        if disaster in ["entropy_storm", "heatwave"]:
            self.crisis_severity += 0.3
            self.crisis_region = "global"  # пока глобально
            print(f"💥 Погодное бедствие усиливает экономическую нестабильность!")

    def on_war_started(self, empire1, empire2):
        """Война нарушает торговлю между фракциями."""
        self.inflation *= 1.05
        # война может привести к локальному кризису в зоне конфликта
        self.crisis_severity += 0.1

    def on_empire_destroyed(self, empire):
        """Разрушение империи вызывает экономический шок."""
        self.crisis_severity += 0.2

    def update(self):
        """Ежедневное обновление экономических показателей."""
        if self.crisis_active:
            # Кризис уже идёт
            self._apply_crisis_effects()
            self.crisis_severity *= 0.95  # постепенное затухание
            if self.crisis_severity < 0.1:
                self.crisis_active = False
                self.crisis_region = None
                self.event_bus.emit("crisis_ended")
                print("✅ Экономический кризис завершён.")
            return

        # Расчёт факторов риска
        risk = self._calculate_risk()

        # Порог для начала кризиса
        if risk > 2.0 and random.random() < 0.01:
            self.crisis_active = True
            self.crisis_severity = min(risk, 5.0)
            self.crisis_region = self._select_region()
            self.event_bus.emit("crisis_started", severity=self.crisis_severity, region=self.crisis_region)
            print(f"💥 ЭКОНОМИЧЕСКИЙ КРИЗИС начался! Регион: {self.crisis_region}, тяжесть: {self.crisis_severity:.2f}")

    def _calculate_risk(self):
        """Возвращает число – риск кризиса."""
        risk = 0.0

        # Инфляция (если у агентов слишком много золота)
        avg_gold = np.mean([a.gold for a in self.world.population]) if self.world.population else 0
        if avg_gold > 500:
            risk += 0.5
        elif avg_gold > 1000:
            risk += 1.0

        # Истощение ресурсов (исправлено: используем .items)
        total_items = sum(len(a.inventory.items) for a in self.world.population)
        if total_items > len(self.world.population) * 5:
            risk += 0.3  # много предметов – перепроизводство

        # Войны
        risk += len(self.world.war.empires) * 0.2

        # Погода
        if hasattr(self.world, 'weather'):
            if self.world.weather.weather == "entropy_storm":
                risk += 1.0
            elif self.world.weather.weather == "heatwave":
                risk += 0.5

        # Болезни
        sick_count = sum(1 for a in self.world.population if hasattr(a, 'disease') and a.disease)
        risk += sick_count * 0.1

        return risk

    def _select_region(self):
        """Выбирает регион кризиса (пока просто случайная фракция)."""
        if self.world.factions.factions:
            return random.choice(self.world.factions.factions).name
        return "global"

    def _apply_crisis_effects(self):
        """Применяет эффекты кризиса к миру."""
        severity = self.crisis_severity

        # Обесценивание золота
        for agent in self.world.population:
            if self.crisis_region == "global" or agent.faction == self.crisis_region:
                agent.gold = int(agent.gold * (1 - severity * 0.1))

        # Торговля замирает (удаляем часть листингов)
        self.world.market.listings = [l for l in self.world.market.listings if random.random() > severity * 0.2]

        # Цены скачут
        for listing in self.world.market.listings:
            listing['price'] = int(listing['price'] * (1 + random.uniform(-severity*0.2, severity*0.2)))

        # Бедность снижает score
        for agent in self.world.population:
            if agent.gold < 10:
                agent.score -= 0.1