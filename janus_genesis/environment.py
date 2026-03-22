# janus_genesis/environment.py
"""
Модуль погоды и времени. Использует реальные метрики с ПК и Cardputer.
Влияет на потребности, здоровье, экономику и возникновение кризисов.
"""

import random
import math
import time

class WeatherSystem:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.season = "spring"          # весна, лето, осень, зима
        self.weather = "clear"           # ясно, дождь, жара, буря
        self.temperature = 20.0           # в градусах Цельсия (игровая)
        self.humidity = 50.0              # влажность, %
        self.disaster = None               # текущее бедствие (засуха, наводнение и т.д.)
        self.disaster_duration = 0

        # Подписываемся на события, которые могут влиять на погоду
        event_bus.subscribe("tech_discovered", self.on_tech_discovered)
        event_bus.subscribe("war_started", self.on_war_started)

    def on_tech_discovered(self, technology, discoverer):
        """Некоторые технологии могут менять климат (например, индустриализация)."""
        if technology.name == "Advanced Mining":
            self.temperature += 0.5  # глобальное потепление

    def on_war_started(self, empire1, empire2):
        """Войны могут вызывать загрязнение (ядерная зима?)."""
        self.temperature -= 1.0
        self.humidity += 5

    def update_from_real_metrics(self, pc_metrics, cardputer_metrics):
        """
        Обновляет игровую погоду на основе реальных данных.
        pc_metrics: словарь с gpu_temp, gpu_load, cpu_load.
        cardputer_metrics: словарь с temperature, humidity (если есть).
        """
        # Базовое смещение
        self.temperature = 20.0
        self.humidity = 50.0

        # Влияние GPU: чем горячее GPU, тем теплее в игре
        gpu_temp = pc_metrics.get('gpu_temp', 40)
        self.temperature += (gpu_temp - 40) * 0.2

        # Нагрузка на GPU/CPU создаёт "энтропийный шум" – может вызывать бури
        gpu_load = pc_metrics.get('gpu_load', 0)
        cpu_load = pc_metrics.get('cpu_load', 0)
        entropy = (gpu_load + cpu_load) / 200.0  # от 0 до 1
        if entropy > 0.8 and random.random() < 0.01:
            self.weather = "entropy_storm"
            self.event_bus.emit("weather_disaster", disaster="entropy_storm")
        elif entropy > 0.5 and random.random() < 0.005:
            self.weather = "thunderstorm"
        else:
            # Нормальная погода по сезону
            self._update_seasonal_weather()

        # Данные с Cardputer
        if cardputer_metrics:
            real_temp = cardputer_metrics.get('temperature')
            real_hum = cardputer_metrics.get('humidity')
            if real_temp is not None:
                self.temperature += (real_temp - 20) * 0.5  # влияние реальной температуры
            if real_hum is not None:
                self.humidity += (real_hum - 50) * 0.3

        # Ограничения
        self.temperature = max(-10, min(50, self.temperature))
        self.humidity = max(0, min(100, self.humidity))

        # Обновляем сезон в зависимости от времени года (упрощённо)
        month = (self.world.tick // 30) % 12
        if month < 3:
            self.season = "winter"
        elif month < 6:
            self.season = "spring"
        elif month < 9:
            self.season = "summer"
        else:
            self.season = "autumn"

    def _update_seasonal_weather(self):
        """Определяет погоду по сезону и текущим условиям."""
        if self.season == "summer":
            if self.humidity > 70:
                self.weather = "rain"
            elif self.temperature > 30:
                self.weather = "heatwave"
            else:
                self.weather = "clear"
        elif self.season == "winter":
            if self.temperature < 0:
                self.weather = "snow"
            else:
                self.weather = "cold"
        else:
            self.weather = "clear"

    def apply_effects(self):
        """Применяет эффекты погоды к агентам и миру."""
        for agent in self.world.population:
            # Влияние на потребности
            if self.weather == "heatwave":
                agent.needs["thirst"] -= 0.05  # жажда быстрее
            elif self.weather == "snow":
                agent.needs["energy"] -= 0.03  # холод消耗 энергию
            elif self.weather == "entropy_storm":
                agent.needs["energy"] -= 0.1
                agent.needs["hygiene"] -= 0.1
                # Шанс болезни
                if random.random() < 0.1:
                    self.world.disease.infect(agent)

            # Влияние на здоровье
            if self.temperature > 35 and random.random() < 0.05:
                agent.needs["health"] = getattr(agent, 'health', 100) - 5

        # Экономические эффекты
        if self.weather == "entropy_storm":
            # Торговля затруднена
            self.world.market.listings.clear()
            self.event_bus.emit("market_crash", reason="entropy_storm")
        elif self.weather == "heatwave":
            # Урожай (если есть) гибнет – влияет на цены
            for item in self.world.market.listings:
                if "food" in item['item'].name.lower():
                    item['price'] *= 2  # дефицит

    def get_state(self):
        """Возвращает состояние погоды для логирования."""
        return {
            'season': self.season,
            'weather': self.weather,
            'temperature': round(self.temperature, 1),
            'humidity': round(self.humidity, 1),
            'disaster': self.disaster
        }