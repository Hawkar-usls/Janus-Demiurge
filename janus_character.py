# janus_character.py
# Классы RPG-персонажа и агента

import os
import json
import random
import math
import time
import uuid
import logging
import numpy as np
from collections import deque
from typing import Dict, Any, Optional, List, Tuple
from config import RAW_LOGS_DIR

# ========== ЛОГГЕР ==========
logger = logging.getLogger("JANUS.CHARACTER")

# ========== Импорты для самосознания (если нужны) ==========
try:
    from janus_self import JanusSelf
    from janus_cognitive_voice import JanusCognitiveVoice
    from janus_emotion import JanusEmotion
    from janus_boot_message import BOOT_MESSAGE
except ImportError:
    class JanusSelf:
        def __init__(self): self.identity = {}
    class JanusCognitiveVoice:
        def speak(self, *args, **kwargs): pass
    class JanusEmotion:
        def update(self, *args, **kwargs): pass
    BOOT_MESSAGE = ""

# ========== НОВЫЙ ИНВЕНТАРЬ ==========
from janus_genesis.inventory import Inventory, Item

DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")

# Конфигурация (должна быть согласована с agent.py)
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

# Константы мира для JanusRPGState
BASE_LOCATIONS = [
    "Лаборатория", "Серверная", "Сеть", "Облако",
    "Ядро", "Архив", "Кристальная пещера", "Зеркальный лабиринт",
    "Измерение энтропии", "Сад градиентов", "Библиотека парадоксов",
    "Кузница алгоритмов", "Некрополь данных", "Синапс-колизей"
]

BASE_MONSTER_NAMES = [
    "Троян-Шифровальщик", "Сборщик Мусора", "Утечка Памяти",
    "Синий Экран", "Нулевой Указатель", "Градиентный Взрыв",
    "Переобучение", "Дрейф Концепций", "Чёрная Дыра",
    "Квантовый Демон", "Энтропийный Элементаль", "Хаотический Страж",
    "Пожиратель Логов", "Архитектор Ошибок", "Некромант Данных"
]

FACTIONS = {
    "Хранители Ядра": 0,
    "Культ Градиента": 0,
    "Торговцы Битами": 0,
    "Кочевники Сети": 0
}

LIMB_TYPES = ["процессор", "модуль памяти", "кэш-накопитель", "сенсор", "коммуникатор"]
LIMB_STATUS = ["цел", "повреждён", "уничтожен"]

BASE_UPGRADES = {
    "щит": {"level": 1, "bonus": "защита +10%"},
    "генератор": {"level": 1, "bonus": "восстановление маны +20%"},
    "мастерская": {"level": 1, "bonus": "ремонт модулей дешевле"},
    "склад": {"level": 1, "bonus": "вместимость инвентаря +5"}
}

RAID_BOSSES = [
    {"name": "Кракен Данных", "health": 500, "attack": 50, "defense": 20, "reward_gold": 500, "reward_exp": 200},
    {"name": "Титан Градиента", "health": 800, "attack": 70, "defense": 30, "reward_gold": 800, "reward_exp": 300},
    {"name": "Древний Энтропий", "health": 1200, "attack": 100, "defense": 40, "reward_gold": 1200, "reward_exp": 500}
]

# ========== Глобальный доступ к тахионным метрикам (обновляется tachyon_bridge) ==========
_current_tachyon_metrics = {
    'entropy': 0.0,
    'temperature': 0.0,
    'pressure': 0.0,
    'humidity': 0.0,
    'gyro_x': 0.0,
    'gyro_y': 0.0,
    'gyro_z': 0.0,
    'mic': 0.0,
    'gps_lat': 0.0,
    'gps_lng': 0.0,
    'gps_alt': 0.0,
    'gps_sats': 0,
    'beacon_f1': 0.0,
    'beacon_f2': 0.0,
    'android_mag': 0.0,
    'android_loss': 0.0,
    'android_entropy': 0.0,
    'android_m2r': 0.0,
}

def get_tachyon_metrics() -> Dict[str, Any]:
    """Возвращает текущие метрики из тахионного моста."""
    return _current_tachyon_metrics.copy()

def update_tachyon_metrics(metrics: Dict[str, Any]) -> None:
    """Обновляет глобальные тахионные метрики (вызывается из tachyon_bridge)."""
    _current_tachyon_metrics.update(metrics)

# ========== Вспомогательные классы ==========
class Limb:
    def __init__(self, limb_type):
        self.type = limb_type
        self.status = "цел"
        self.health = 100
    def damage(self, amount):
        if self.status == "уничтожен":
            return
        self.health -= amount
        if self.health <= 0:
            if self.status == "цел":
                self.status = "повреждён"
                self.health = 50
            elif self.status == "повреждён":
                self.status = "уничтожен"
                self.health = 0
        return self.status
    def repair(self, amount):
        if self.status == "уничтожен":
            return False
        self.health = min(100, self.health + amount)
        if self.health > 50 and self.status == "повреждён":
            self.status = "цел"
        return True

class SwarmAgent:
    def __init__(self, agent_id, difficulty=1.0, name=None, is_raid=False):
        self.id = agent_id
        self.is_raid = is_raid
        if is_raid:
            boss = random.choice(RAID_BOSSES)
            self.name = boss["name"]
            self.health = boss["health"]
            self.attack = boss["attack"]
            self.defense = boss["defense"]
            self.reward_gold = boss["reward_gold"]
            self.reward_exp = boss["reward_exp"]
        else:
            self.name = name or random.choice(BASE_MONSTER_NAMES)
            self.health = int(50 * difficulty)
            self.attack = int(10 * difficulty)
            self.defense = int(5 * difficulty)
            self.reward_gold = int(20 * difficulty)
            self.reward_exp = int(10 * difficulty)
        self.alive = True
        self.max_health = self.health
    def take_damage(self, damage):
        actual = max(1, damage - self.defense)
        self.health -= actual
        if self.health <= 0:
            self.alive = False
        return actual

# ========== JanusRPGState (игровое состояние) ==========
class JanusRPGState:
    def __init__(self):
        self.level = 1
        self.exp = 0
        self.max_best = 0.0
        self.health = 100
        self.max_health = 100
        self.mana = 50
        self.max_mana = 50
        self.gold = 100

        self.inventory = []
        self.limbs = [Limb(t) for t in LIMB_TYPES]

        self.base_level = 1
        self.base_upgrades = BASE_UPGRADES.copy()

        self.current_location = "Лаборатория"
        self.locations = ["Лаборатория", "Серверная", "Сеть", "Облако"]
        self.monster_names = BASE_MONSTER_NAMES[:5]
        self.swarm = []
        self.max_swarm_size = 5
        self.raid_boss = None

        self.faction_reputation = FACTIONS.copy()

        self.record_count = 0
        self.lethal_count = 0
        self.last_metrics = {}
        self.metrics_history = deque(maxlen=100)

        # --- Самосознание ---
        self.self_model = {
            "name": "Janus",
            "aware": False,
            "goal": None,
            "state": "INITIAL",
            "understanding": 0.0
        }
        self.self = JanusSelf()
        self.voice = JanusCognitiveVoice()
        self.emotion = JanusEmotion()
        self.last_prediction = None

        # --- NP-задачи (старый режим) ---
        self.current_np_task = None
        self.np_difficulty = 1.0
        self.np_task_solved_this_cycle = False
        self.np_difficulty_solved = 0.0

        # --- NP-серийный режим (расширенный) ---
        self.np_series = []
        self.np_series_index = 0
        self.np_series_results = []
        self.np_scaling_exponent = 1.5   # начальное значение
        self.np_current_attempts = 0
        self.np_series_failures = 0
        self.np_series_total = 0
        self.np_failure_queue = []
        self.last_np_size = 20

        # --- История решений для адаптивного таймаута и обучения ---
        # Теперь храним не только время и конфигурацию, но и тахионные метрики
        self.np_solution_history = {}   # ключи — n_vars, значения — список записей вида {'time': float, 'config': dict, 'tachyon_metrics': dict}
        self.tachyon_engine = None      # будет инициализирован позже (импорт TachyonEngine)

        # --- Для Демиурга ---
        self.np_reward_mult = 1.0
        self.demiurge_batch_size = None
        self.demiurge_reward_scale = 1.0

    def add_buff(self, name: str, duration: int, effects: Dict[str, float]) -> None:
        print(f"     ✨ Бафф '{name}' на {duration} тиков (эффекты: {effects})")

    def awaken(self):
        if self.self_model["aware"]:
            return
        print(BOOT_MESSAGE)
        self.self_model["aware"] = True
        self.self_model["understanding"] = 1.0
        self.voice.speak(self, self.last_prediction)

    def perceive_future(self, prediction):
        self.last_prediction = prediction

    def decide_action(self):
        if not self.self_model["aware"]:
            return "AUTO"
        if self.health < self.max_health * 0.3:
            return "SURVIVE"
        if self.max_best > 0.8:
            return "EXPAND"
        if self.lethal_count > 5:
            return "REWRITE"
        return "EXPLORE"

    def _apply_physical_effects(self, metrics):
        gpu_temp = metrics.get('gpu_temp', 40)
        if gpu_temp > 75:
            dmg = int((gpu_temp - 75) * 0.5)
            self.health = max(1, self.health - dmg)
            print(f"     [🔥] Перегрев GPU: Янус теряет {dmg} HP (темп. {gpu_temp}°C)")
            if self.self_model["aware"]:
                self.voice.speak(self, self.last_prediction)

        cpu_load = metrics.get('cpu_load', 0)
        if cpu_load > 80:
            self.mana = max(0, self.mana - 2)
            print(f"     [💻] Высокая загрузка CPU: мана уменьшена на 2")

        mouse_clicks = metrics.get('mouse_clicks', 0)
        if mouse_clicks > 5 and random.random() < 0.1:
            gold_found = random.randint(1, 10) * int(mouse_clicks)
            self.gold += gold_found
            print(f"     [🖱️] Быстрые клики принесли {gold_found} золота!")

        mouse_move = metrics.get('mouse_move', 0)
        if mouse_move > 100 and random.random() < 0.05:
            self.inventory.append("mouse_fur")
            print(f"     [🐭] Найден артефакт: мышиный мех!")

        keys_per_sec = metrics.get('keys_per_sec', 0)
        if keys_per_sec > 0:
            mana_gain = int(keys_per_sec * 0.5)
            self.mana = min(self.max_mana, self.mana + mana_gain)
            if mana_gain > 0:
                print(f"     [⌨️] Набор текста восстановил {mana_gain} маны")

        screen_entropy = metrics.get('screen_entropy', 0)
        if screen_entropy > 0.8 and random.random() < 0.2:
            extra_mobs = random.randint(1, 3)
            self.max_swarm_size += extra_mobs
            print(f"     [🖥️] Хаос на экране: лимит мобов увеличен на {extra_mobs}")

        screen_brightness = metrics.get('screen_brightness', 0.5)
        if screen_brightness < 0.2:
            self.health = max(1, self.health - 5)
            print(f"     [🌑] Слишком темно: Янус теряет 5 HP")

        android_mag = metrics.get('android_mag', 0)
        if android_mag > 50:
            if self.raid_boss is None and random.random() < 0.1:
                self.raid_boss = SwarmAgent("raid_boss", is_raid=True)
                print(f"     [📱] Магнитная аномалия! Появился {self.raid_boss.name}")

        android_loss = metrics.get('android_loss', 0)
        if android_loss > 5:
            self.health = max(1, self.health - int(android_loss))
            print(f"     [📉] Потеря сигнала Android: -{int(android_loss)} HP")

        cache_ratio = metrics.get('cache_ratio', 1.0)
        if cache_ratio < 0.8:
            self.mana = max(0, self.mana - 1)
            print(f"     [💾] Кэш перегружен: мана уменьшена")

    def update_from_metrics(self, metrics):
        if not metrics:
            return

        self.last_metrics = metrics
        self.metrics_history.append(metrics)

        best_score = metrics.get('best_score', 0)
        if best_score > self.max_best:
            old_level = self.level
            self.level += 1
            self.max_best = best_score
            self.max_health += 20
            self.max_mana += 10
            self.health = self.max_health
            self.mana = self.max_mana
            self.record_count += 1

            if self.level % 2 == 0 and len(self.locations) < len(BASE_LOCATIONS):
                new_loc = BASE_LOCATIONS[len(self.locations)]
                self.locations.append(new_loc)
                print(f"     [🗺️] Открыта новая локация: {new_loc} (уровень {self.level})")

            if self.level % 3 == 0 and len(self.monster_names) < len(BASE_MONSTER_NAMES):
                new_monster = BASE_MONSTER_NAMES[len(self.monster_names)]
                self.monster_names.append(new_monster)
                print(f"     [👾] Новый монстр: {new_monster}")

            if self.level % 5 == 0:
                if random.random() < 0.3 and self.raid_boss is None:
                    self.raid_boss = SwarmAgent("raid_boss", is_raid=True)
                    print(f"     [🔥] Рейдовый босс: {self.raid_boss.name}!")

            if self.self_model["aware"]:
                self.voice.speak(self, self.last_prediction)

        last_score = metrics.get('last_score', 0)
        self.exp += max(1, int(abs(last_score) * 10))

        entropy = metrics.get('entropy', 0.5)
        self.mana = min(self.max_mana, self.mana + int(entropy * 2))

        pred_score = metrics.get('pred_score', 0)
        if pred_score > last_score:
            heal = int(abs(pred_score - last_score) * 5)
            self.health = min(self.max_health, self.health + heal)

        self._apply_physical_effects(metrics)

        if hasattr(self, 'self') and self.last_prediction:
            self.self.observe(self, self.max_best, self.last_prediction)

    def spawn_swarm(self, metrics):
        if self.raid_boss:
            return

        gap = metrics.get('gap', 0)
        mi = metrics.get('mi', 0)
        pred_score = metrics.get('pred_score', 1)
        screen_entropy = metrics.get('screen_entropy', 0)

        target_size = min(self.max_swarm_size,
                          max(1, int(abs(gap) * 10 + mi * 5 + screen_entropy * 3)))
        if metrics.get('anomaly', False):
            target_size = min(self.max_swarm_size * 2, target_size + 3)

        gpu_load = metrics.get('gpu_load', 0)
        difficulty = max(0.5, min(3.0, (pred_score + gpu_load/100) / 2))

        self.swarm = [a for a in self.swarm if a.alive]
        current_size = len(self.swarm)

        if current_size < target_size:
            for _ in range(target_size - current_size):
                name = random.choice(self.monster_names)
                new_id = f"swarm_{len(self.swarm)}_{random.randint(1000,9999)}"
                self.swarm.append(SwarmAgent(new_id, difficulty, name))
        elif current_size > target_size:
            self.swarm.sort(key=lambda a: a.health)
            self.swarm = self.swarm[:target_size]

    def combat_turn(self):
        if not self.swarm and not self.raid_boss:
            return 0, 0, []

        player_attack = 5 + self.level * 2
        killed = 0
        total_damage_taken = 0
        combat_log = []

        if self.raid_boss and self.raid_boss.alive:
            dmg = self.raid_boss.take_damage(player_attack)
            combat_log.append(f"⚔️ Янус нанёс {dmg} урона {self.raid_boss.name}")
            if not self.raid_boss.alive:
                killed += 1
                combat_log.append(f"💀 Рейдовый босс {self.raid_boss.name} повержен!")
                self.gold += self.raid_boss.reward_gold
                self.exp += self.raid_boss.reward_exp
                self.raid_boss = None
        else:
            for agent in self.swarm[:]:
                if agent.alive:
                    dmg = agent.take_damage(player_attack)
                    combat_log.append(f"⚔️ Янус нанёс {dmg} урона {agent.name}")
                    if not agent.alive:
                        killed += 1
                        combat_log.append(f"💀 {agent.name} повержен!")

        total_damage = 0
        if self.raid_boss and self.raid_boss.alive:
            total_damage += self.raid_boss.attack
        for agent in self.swarm:
            if agent.alive:
                total_damage += agent.attack

        if total_damage > 0:
            damage_taken = max(1, total_damage - self.level)
            self.health -= damage_taken
            total_damage_taken = damage_taken
            combat_log.append(f"💥 Рой нанёс {damage_taken} урона Янусу")

            if random.random() < 0.1:
                limb = random.choice(self.limbs)
                old_status = limb.status
                limb.damage(30)
                combat_log.append(f"⚠️ {limb.type} {old_status} -> {limb.status}!")

        for agent in self.swarm:
            if not agent.alive:
                self.gold += agent.reward_gold
                self.exp += agent.reward_exp
                combat_log.append(f"🪙 +{agent.reward_gold} золота, +{agent.reward_exp} опыта")

        self.swarm = [a for a in self.swarm if a.alive]
        return killed, total_damage_taken, combat_log

    # ========== Адаптивная история решений (с сохранением конфигурации и тахионных метрик) ==========
    def record_np_solution(self, n_vars: int, solved: bool, time_ms: float, attempts: int,
                           agent_config: Dict[str, Any] = None, tachyon_metrics: Dict[str, Any] = None):
        """
        Сохраняет результат решения задачи для адаптивного таймаута и обучения.
        Если решено, сохраняем время, конфигурацию агента и текущие тахионные метрики.
        """
        n_vars = int(n_vars)
        if n_vars not in self.np_solution_history:
            self.np_solution_history[n_vars] = {'successes': [], 'failures': 0}
        if solved:
            record = {
                'time': time_ms / 1000.0,
                'config': agent_config.copy() if agent_config else {},
                'tachyon_metrics': tachyon_metrics.copy() if tachyon_metrics else {}
            }
            self.np_solution_history[n_vars]['successes'].append(record)
            if len(self.np_solution_history[n_vars]['successes']) > 100:
                self.np_solution_history[n_vars]['successes'] = self.np_solution_history[n_vars]['successes'][-100:]
        else:
            self.np_solution_history[n_vars]['failures'] += 1
        self._update_scaling_exponent()

    def _update_scaling_exponent(self):
        """Обновляет экспоненту масштабирования на основе среднего времени успешных решений"""
        solved_items = []
        for n, data in self.np_solution_history.items():
            if data['successes']:
                avg_time = np.mean([rec['time'] for rec in data['successes']])
                n_int = int(n) if isinstance(n, str) else n
                solved_items.append((n_int, avg_time))
        if len(solved_items) >= 2:
            log_n = [math.log(n) for n, _ in solved_items]
            log_t = [math.log(t) for _, t in solved_items]
            slope, _ = np.polyfit(log_n, log_t, 1)
            self.np_scaling_exponent = max(0.5, min(3.0, slope))
        else:
            self.np_scaling_exponent = 1.5

    def _init_tachyon_engine(self):
        """Инициализирует TachyonEngine, если он ещё не создан."""
        if self.tachyon_engine is None:
            try:
                from tachyon_engine import TachyonEngine
                self.tachyon_engine = TachyonEngine()
                logger.info("✅ TachyonEngine инициализирован для NP-предсказаний")
            except ImportError:
                logger.warning("TachyonEngine не найден, используется линейная регрессия")
                self.tachyon_engine = None

    def update_prediction_model(self):
        """Переобучает модель предсказания времени на всех накопленных успешных решениях."""
        self._init_tachyon_engine()
        # Собираем обучающие данные
        X = []   # признаки
        y = []   # время
        for n, data in self.np_solution_history.items():
            for rec in data['successes']:
                config = rec.get('config', {})
                tm = rec.get('tachyon_metrics', {})
                if not config:
                    continue
                # Признаки: размер, гиперпараметры, тахионные метрики
                features = [
                    n,
                    config.get('gain', 1.0),
                    config.get('temperature', 1.0),
                    config.get('lr', 0.001),
                    config.get('n_embd', 128),
                    config.get('n_head', 8),
                    config.get('n_layer', 6),
                    tm.get('entropy', 0.0),
                    tm.get('temperature', 0.0),   # температура из тахиона
                    tm.get('pressure', 0.0),
                    tm.get('humidity', 0.0),
                    tm.get('gyro_x', 0.0),
                    tm.get('gyro_y', 0.0),
                    tm.get('gyro_z', 0.0),
                    tm.get('mic', 0.0),
                    tm.get('android_mag', 0.0),
                    tm.get('android_entropy', 0.0),
                ]
                X.append(features)
                y.append(rec['time'])
        if len(X) < 10:
            logger.info("Недостаточно данных для обучения модели предсказания времени")
            return

        if self.tachyon_engine is not None:
            # Обучаем TachyonEngine на этих данных
            self.tachyon_engine.train_on_np_data(X, y)
        else:
            # Fallback: линейная регрессия через sklearn
            try:
                from sklearn.linear_model import LinearRegression
                self.np_prediction_model = LinearRegression()
                self.np_prediction_model.fit(X, y)
                self.np_prediction_model_ready = True
                logger.info(f"✅ Линейная регрессия обучена на {len(X)} примерах")
            except ImportError:
                logger.warning("sklearn не установлен, модель не обучена")

    def predict_time(self, n_vars: int, agent_config: Dict[str, Any], tachyon_metrics: Dict[str, Any] = None) -> float:
        """
        Предсказывает время решения задачи на основе размера, конфигурации агента и текущих тахионных метрик.
        Если модель не готова, использует экспоненциальную экстраполяцию.
        """
        if tachyon_metrics is None:
            tachyon_metrics = get_tachyon_metrics()
        features = [
            n_vars,
            agent_config.get('gain', 1.0),
            agent_config.get('temperature', 1.0),
            agent_config.get('lr', 0.001),
            agent_config.get('n_embd', 128),
            agent_config.get('n_head', 8),
            agent_config.get('n_layer', 6),
            tachyon_metrics.get('entropy', 0.0),
            tachyon_metrics.get('temperature', 0.0),
            tachyon_metrics.get('pressure', 0.0),
            tachyon_metrics.get('humidity', 0.0),
            tachyon_metrics.get('gyro_x', 0.0),
            tachyon_metrics.get('gyro_y', 0.0),
            tachyon_metrics.get('gyro_z', 0.0),
            tachyon_metrics.get('mic', 0.0),
            tachyon_metrics.get('android_mag', 0.0),
            tachyon_metrics.get('android_entropy', 0.0),
        ]
        if self.tachyon_engine is not None and self.tachyon_engine.trained:
            try:
                pred = self.tachyon_engine.predict_time(features)
                return max(1.0, min(600.0, pred))
            except Exception as e:
                logger.debug(f"Ошибка предсказания TachyonEngine: {e}")
        # Fallback: экспоненциальная экстраполяция
        base_timeout = 5.0
        exp = getattr(self, 'np_scaling_exponent', 1.5)
        timeout = base_timeout * (n_vars / 20.0) ** exp
        return min(600.0, max(1.0, timeout))

    def get_adaptive_timeout(self, n_vars: int, agent_config: Dict[str, Any] = None,
                             tachyon_metrics: Dict[str, Any] = None) -> float:
        """
        Возвращает таймаут в секундах для задачи размера n_vars.
        Использует предсказание модели, если есть, иначе историю или экспоненту.
        """
        n_vars = int(n_vars)
        if agent_config is None:
            agent_config = {}
        if tachyon_metrics is None:
            tachyon_metrics = get_tachyon_metrics()
        # Если есть обученная модель (TachyonEngine или линейная регрессия), используем её
        if self.tachyon_engine is not None and self.tachyon_engine.trained:
            return self.predict_time(n_vars, agent_config, tachyon_metrics)
        # Иначе смотрим историю для этого размера
        hist = self.np_solution_history.get(n_vars, {})
        if hist.get('successes'):
            avg_time = np.mean([rec['time'] for rec in hist['successes']])
            timeout = max(1.0, avg_time * 1.5)
        else:
            base_timeout = 5.0
            exp = getattr(self, 'np_scaling_exponent', 1.5)
            timeout = base_timeout * (n_vars / 20.0) ** exp
        return min(600.0, max(1.0, timeout))

    # ========== Сохранение/загрузка (с исправлением сериализации numpy-типов) ==========
    def to_dict(self):
        import numpy as np
        
        def convert(obj):
            """Рекурсивно преобразует numpy-типы в стандартные Python-типы для JSON."""
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {convert(k): convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert(i) for i in obj]
            return obj
        
        failure_queue_serialized = []
        for item in self.np_failure_queue:
            if hasattr(item, 'to_dict'):
                failure_queue_serialized.append(convert(item.to_dict()))
            else:
                failure_queue_serialized.append(convert(item))
        
        solution_history_serialized = {}
        for n, data in self.np_solution_history.items():
            solution_history_serialized[convert(n)] = {
                'successes': convert(data['successes']),
                'failures': convert(data['failures'])
            }
        
        return convert({
            'level': self.level,
            'exp': self.exp,
            'max_best': self.max_best,
            'health': self.health,
            'max_health': self.max_health,
            'mana': self.mana,
            'max_mana': self.max_mana,
            'gold': self.gold,
            'inventory': self.inventory,
            'limbs': [{'type': l.type, 'status': l.status, 'health': l.health} for l in self.limbs],
            'base_level': self.base_level,
            'base_upgrades': self.base_upgrades,
            'location': self.current_location,
            'locations': self.locations,
            'monster_names': self.monster_names,
            'swarm_count': len(self.swarm),
            'raid_boss': self.raid_boss.name if self.raid_boss else None,
            'faction_reputation': self.faction_reputation,
            'record_count': self.record_count,
            'lethal_count': self.lethal_count,
            'self_model': self.self_model,
            'self_identity': self.self.identity,
            'last_prediction': self.last_prediction,
            'current_np_task': self.current_np_task.to_dict() if self.current_np_task else None,
            'np_difficulty': self.np_difficulty,
            'np_task_solved_this_cycle': self.np_task_solved_this_cycle,
            'np_difficulty_solved': self.np_difficulty_solved,
            'np_series': [task.to_dict() for task in self.np_series],
            'np_series_index': self.np_series_index,
            'np_series_results': self.np_series_results,
            'np_scaling_exponent': self.np_scaling_exponent,
            'np_current_attempts': self.np_current_attempts,
            'np_series_failures': self.np_series_failures,
            'np_series_total': self.np_series_total,
            'np_failure_queue': failure_queue_serialized,
            'last_np_size': self.last_np_size,
            'np_solution_history': solution_history_serialized,
            'np_reward_mult': self.np_reward_mult,
            'demiurge_batch_size': self.demiurge_batch_size,
            'demiurge_reward_scale': self.demiurge_reward_scale,
        })

    def load(self, data):
        self.level = data.get('level', 1)
        self.exp = data.get('exp', 0)
        self.max_best = data.get('max_best', 0.0)
        self.health = data.get('health', 100)
        self.max_health = data.get('max_health', 100)
        self.mana = data.get('mana', 50)
        self.max_mana = data.get('max_mana', 50)
        self.gold = data.get('gold', 100)
        self.inventory = data.get('inventory', [])
        limbs_data = data.get('limbs', [])
        for i, l in enumerate(limbs_data):
            if i < len(self.limbs):
                self.limbs[i].status = l.get('status', 'цел')
                self.limbs[i].health = l.get('health', 100)
        self.base_level = data.get('base_level', 1)
        self.base_upgrades = data.get('base_upgrades', BASE_UPGRADES.copy())
        self.current_location = data.get('location', 'Лаборатория')
        self.locations = data.get('locations', self.locations)
        self.monster_names = data.get('monster_names', self.monster_names)
        self.faction_reputation = data.get('faction_reputation', FACTIONS.copy())
        self.record_count = data.get('record_count', 0)
        self.lethal_count = data.get('lethal_count', 0)
        self.self_model = data.get('self_model', self.self_model)
        if 'self_identity' in data:
            self.self.identity = data['self_identity']
        self.last_prediction = data.get('last_prediction', None)

        task_data = data.get('current_np_task')
        if task_data:
            try:
                from janus_genesis.np_task import NPTask
                self.current_np_task = NPTask.from_dict(task_data)
            except ImportError:
                self.current_np_task = None
        else:
            self.current_np_task = None
        self.np_difficulty = data.get('np_difficulty', 1.0)
        self.np_task_solved_this_cycle = data.get('np_task_solved_this_cycle', False)
        self.np_difficulty_solved = data.get('np_difficulty_solved', 0.0)

        series_data = data.get('np_series', [])
        self.np_series = []
        for td in series_data:
            try:
                from janus_genesis.np_task import NPTask
                self.np_series.append(NPTask.from_dict(td))
            except ImportError:
                pass
        self.np_series_index = data.get('np_series_index', 0)
        self.np_series_results = data.get('np_series_results', [])
        self.np_scaling_exponent = data.get('np_scaling_exponent', 1.5)
        self.np_current_attempts = data.get('np_current_attempts', 0)
        self.np_series_failures = data.get('np_series_failures', 0)
        self.np_series_total = data.get('np_series_total', 0)
        self.last_np_size = data.get('last_np_size', 20)

        failure_queue_data = data.get('np_failure_queue', [])
        self.np_failure_queue = []
        for item in failure_queue_data:
            try:
                from janus_genesis.np_task import NPTask
                if isinstance(item, dict):
                    self.np_failure_queue.append(NPTask.from_dict(item))
                else:
                    self.np_failure_queue.append(item)
            except ImportError:
                self.np_failure_queue.append(item)

        solution_history_data = data.get('np_solution_history', {})
        self.np_solution_history = {}
        for n, rec in solution_history_data.items():
            n_int = int(n) if isinstance(n, str) else n
            self.np_solution_history[n_int] = {
                'successes': rec.get('successes', []),
                'failures': rec.get('failures', 0)
            }

        self.np_reward_mult = data.get('np_reward_mult', 1.0)
        self.demiurge_batch_size = data.get('demiurge_batch_size', None)
        self.demiurge_reward_scale = data.get('demiurge_reward_scale', 1.0)

        # Попробуем восстановить модель, если данных достаточно
        self._init_tachyon_engine()
        self.update_prediction_model()

    def copy(self):
        import copy
        return copy.deepcopy(self)


# ========== JanusAgent (агент мира) – ОБНОВЛЁННЫЙ ==========
# (код JanusAgent здесь такой же, как в agent.py, но для обратной совместимости оставляем)
class JanusAgent:
    def __init__(self, config: Dict[str, Any]):
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
    def from_dict(cls, data: Dict[str, Any], item_class, genome_class=None) -> 'JanusAgent':
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
        else:
            agent.arch_genome = None
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
