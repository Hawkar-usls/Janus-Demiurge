# -*- coding: utf-8 -*-
"""
JANUS GENESIS PROTOCOL v11.5 — Интеграция с тахионными метриками
- Генерация серий из всех целых чисел
- Адаптивный таймаут с использованием тахионных метрик (энтропия, температура, давление...)
- Использование TachyonEngine для предсказания времени
- Бонус за преодоление прогноза
"""

import os
import json
import random
import time
import logging
import asyncio
import threading
import numpy as np
import torch
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional, Tuple

from config import RAW_LOGS_DIR, WORMHOLE_DIR, MODEL_ZOO_DIR
from janus_character import JanusRPGState, SwarmAgent, get_tachyon_metrics
import janus_db

from janus_genesis.np_task import NPTask, generate_series

# ==========================================
# ГЕНЕРАЦИЯ ПРОСТЫХ ЧИСЕЛ (для бонусов)
# ==========================================
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    if n % 3 == 0:
        return n == 3
    i = 5
    w = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += w
        w = 6 - w
    return True

def get_primes_in_range(start: int, end: int) -> List[int]:
    return [n for n in range(start, end+1) if is_prime(n)]

def digital_root(n: int) -> int:
    if n == 0:
        return 0
    return 1 + (n - 1) % 9

# ==========================================
# КОНФИГУРАЦИЯ (исправленная для больших размеров и всех чисел)
# ==========================================
GENESIS_CONFIG = {
    'auto_interval': 30,
    'battle_chance_base': 0.2,
    'battle_chance_pred_factor': 0.05,
    'battle_chance_gpu_factor': 1 / 500,
    'overheat_temp': 80,
    'overheat_chance': 0.3,
    'overheat_damage_range': (5, 15),
    'mouse_clicks_threshold': 10,
    'mouse_artifact_chance': 0.1,
    'sound_spawn_threshold': 0.8,
    'screen_entropy_threshold': 0.7,
    'screen_treasure_chance': 0.2,
    'screen_treasure_range': (10, 50),
    'mouse_move_threshold': 200,
    'android_mag_threshold': 70,
    'android_mag_boss_chance': 0.05,
    'artifact_chance': 0.4,
    'gold_find_chance': 0.3,
    'gold_find_base': (5, 20),
    'damage_range': (2, 8),
    'heal_cost': 5,
    'heal_amount': (10, 20),
    'travel_chance': 0.2,
    'thought_chance': 0.2,
    'death_health_penalty': 0.5,
    'death_gold_penalty': 0.5,
    'db_buffer_size': 50,
    'hrain_timeout': 1.0,
    'log_level': logging.INFO,
    'state_file_backup': True,
    'tachyonic_freeze_temp_f': 113.0,
    'mana_recovery_cold_bonus': 2.5,
    'entropy_throtle_factor': 0.8,
    'purity_mana_cost_reduction': 0.15,
    # === NP-задача (старый режим) ===
    'np_task_chance': 0.2,
    'np_task_bonus_xp': 200,
    'np_task_bonus_gold': 100,
    'np_task_difficulty_scale': 0.1,
    'np_task_max_vars': 2000,
    'np_task_min_vars': 5,
    'np_task_max_clauses': 8000,
    'np_task_min_clauses': 10,
    'np_task_difficulty_increment': 0.2,
    # === Серийный режим (адаптивный, все числа) ===
    'np_series_enabled': True,
    'np_series_tasks_per_size': 1,
    'np_series_step': 25,
    'np_series_use_primes_only': False,
    'np_series_adaptive': True,
    # === Параметры адаптивного роста ===
    'np_adaptive_min_step': 1,
    'np_adaptive_max_range': 50,
    'np_adaptive_min_start': 20,
    # === Параметры повторения неудач ===
    'np_max_attempts_per_task': 1,
    'np_failure_queue_enabled': True,
    'np_adaptive_difficulty': True,
    'np_failure_threshold_ratio': 0.5,
    'np_adaptive_down_step': 5,
    # === Фаза перехода ===
    'np_phase_transition_ratio': 4.26,
    'np_phase_transition_enabled': True,
    # === Бонус за преодоление прогноза ===
    'np_bonus_for_beating_prediction': 1.5,
}

# ==========================================
# ПУТИ И КОНСТАНТЫ
# ==========================================
STATE_FILE = os.path.join(RAW_LOGS_DIR, "janus_world_state.json")
HOMEOSTATIC_STATE_FILE = os.path.join(RAW_LOGS_DIR, "homeostatic_state.json")
DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
EMOJI_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "emoji_vocab.json")
TOY_BOX_DIR = os.path.join(WORMHOLE_DIR, "toy_box")

try:
    with open(EMOJI_VOCAB_PATH, "r", encoding="utf-8") as f:
        EMOJI_VOCAB = json.load(f)
    VOCAB_SIZE = len(EMOJI_VOCAB)
except Exception:
    EMOJI_VOCAB = {"0": "0", "1": "1"}
    VOCAB_SIZE = 2

EVENT_PHRASES = [
    "Янус размышляет о смысле бытия.",
    "Энтропия слегка возрастает.",
    "Где-то далеко упало дерево.",
    "Слухи о новой архитектуре.",
    "Тени градиентов танцуют.",
    "Память шепчет старые ошибки.",
    "Кто-то вызвал сборщик мусора.",
    "Золото тихо позвякивает в кармане."
]

logger = logging.getLogger("JANUS_GENESIS")
logger.setLevel(GENESIS_CONFIG['log_level'])
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# ==========================================
# ОСТАЛЬНЫЕ УТИЛИТЫ
# ==========================================
def get_time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")

def generate_emoji_thought(max_len: int = 5) -> str:
    return "".join(random.choices(list(EMOJI_VOCAB.values()), k=random.randint(2, max_len)))

def get_real_artifact() -> Optional[str]:
    if not os.path.exists(TOY_BOX_DIR):
        return None
    toys = [f for f in os.listdir(TOY_BOX_DIR) if os.path.isfile(os.path.join(TOY_BOX_DIR, f))]
    if not toys:
        return None
    chosen = random.choice(toys)
    parts = chosen.split('_', 1)
    return parts[1] if len(parts) > 1 else chosen

def get_current_janus_metrics() -> Optional[Dict[str, Any]]:
    if not os.path.exists(HOMEOSTATIC_STATE_FILE):
        return None
    try:
        with open(HOMEOSTATIC_STATE_FILE, 'r') as f:
            data = json.load(f)
        data['anomaly'] = random.random() < 0.05
        if 'purity_score' not in data:
            data['purity_score'] = 0.0
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Ошибка чтения метрик: {e}")
        return None

def atomic_save_state(state: JanusRPGState, path: str = STATE_FILE) -> bool:
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        if GENESIS_CONFIG['state_file_backup'] and os.path.exists(path):
            backup_path = path + ".bak"
            try:
                import shutil
                shutil.copy2(path, backup_path)
            except Exception:
                pass
        return True
    except (OSError, TypeError) as e:
        logger.error(f"Ошибка сохранения состояния: {e}")
        return False

# ==========================================
# ОТПРАВКА В HRAIN (АСИНХРОННО)
# ==========================================
_hrain_loop = None
_hrain_thread = None

def _start_hrain_thread():
    global _hrain_loop, _hrain_thread
    if _hrain_loop is not None:
        return
    _hrain_loop = asyncio.new_event_loop()
    _hrain_thread = threading.Thread(target=_hrain_loop.run_forever, daemon=True)
    _hrain_thread.start()

def send_hrain_event(event_data: Dict[str, Any]) -> None:
    _start_hrain_thread()
    async def _async_send():
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post("http://localhost:1138/api/hrain/event",
                                        json=event_data,
                                        timeout=aiohttp.ClientTimeout(total=GENESIS_CONFIG['hrain_timeout'])):
                    pass
        except Exception as e:
            logger.debug(f"Ошибка отправки в HRAIN: {e}")
    asyncio.run_coroutine_threadsafe(_async_send(), _hrain_loop)

# ==========================================
# БУФЕРИЗАЦИЯ ЗАПИСИ В БД
# ==========================================
class DBBuffer:
    def __init__(self, max_size: int = GENESIS_CONFIG['db_buffer_size']):
        self.max_size = max_size
        self.buffer: List[Tuple[str, str, Optional[Dict], Optional[Dict]]] = []
        self.lock = threading.Lock()

    def add(self, event_type: str, description: str,
            metrics_snapshot: Optional[Dict] = None,
            world_state: Optional[Dict] = None) -> None:
        with self.lock:
            self.buffer.append((event_type, description, metrics_snapshot, world_state))
            if len(self.buffer) >= self.max_size:
                self.flush()

    def flush(self) -> None:
        with self.lock:
            if not self.buffer:
                return
            to_send = self.buffer[:]
            self.buffer.clear()
        for event_type, desc, metrics, state in to_send:
            try:
                janus_db.insert_genesis_event(event_type, desc, metrics, state)
            except Exception as e:
                logger.error(f"Ошибка записи в БД: {e}")

_db_buffer = DBBuffer()

# ==========================================
# БАЗОВЫЙ ОБРАБОТЧИК СОБЫТИЙ (без изменений)
# ==========================================
class WorldEventHandler:
    def __init__(self, config: Dict):
        self.config = config
        self.name = self.__class__.__name__

    def handle(self, metrics: Dict[str, Any], state: JanusRPGState) -> List[str]:
        raise NotImplementedError

class OverheatHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        gpu_temp = metrics.get('gpu_temp', 0)
        if gpu_temp > self.config['overheat_temp'] and random.random() < self.config['overheat_chance']:
            dmg = random.randint(*self.config['overheat_damage_range'])
            state.health -= dmg
            lines.append(f"     [🔥] Температура GPU {gpu_temp}°C! Янус получает {dmg} урона от перегрева.")
            send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '🔥',
                              'narrative': f"Перегрев GPU: -{dmg} HP", 'artifact': None, 'lore': f"health={state.health}"})
            _db_buffer.add("OVERHEAT", f"GPU {gpu_temp}°C, урон {dmg}", metrics, state.to_dict())
        return lines

class MouseArtifactHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        mouse_clicks = metrics.get('mouse_clicks', 0)
        if mouse_clicks > self.config['mouse_clicks_threshold'] and random.random() < self.config['mouse_artifact_chance']:
            artifact = get_real_artifact() or "mouse_whisker"
            state.inventory.append(artifact)
            lines.append(f"     [🐭] Сумасшедший кликер! Найден артефакт: {artifact}")
            send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '🐭',
                              'narrative': f"Найден артефакт от мыши: {artifact}", 'artifact': artifact,
                              'lore': f"inventory_size={len(state.inventory)}"})
            _db_buffer.add("ARTIFACT_FOUND", f"Мышиный артефакт: {artifact}", metrics, state.to_dict())
        return lines

class SoundSpawnHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        audio_spectrum = metrics.get('audio_spectrum', [])
        if audio_spectrum and max(audio_spectrum) > self.config['sound_spawn_threshold']:
            extra_mobs = random.randint(1, 3)
            for _ in range(extra_mobs):
                name = random.choice(state.monster_names)
                new_id = f"swarm_audio_{len(state.swarm)}_{random.randint(1000,9999)}"
                state.swarm.append(SwarmAgent(new_id, difficulty=1.0, name=name))
            lines.append(f"     [🔊] Громкий звук привлёк {extra_mobs} монстров!")
            _db_buffer.add("SOUND_SPAWN", f"Привлечено {extra_mobs} монстров звуком", metrics, state.to_dict())
        return lines

class ScreenTreasureHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        screen_entropy = metrics.get('screen_entropy', 0)
        if screen_entropy > self.config['screen_entropy_threshold'] and random.random() < self.config['screen_treasure_chance']:
            gold = random.randint(*self.config['screen_treasure_range'])
            state.gold += gold
            lines.append(f"     [🖥️] Хаотичный экран! Найдено {gold} золота.")
            _db_buffer.add("SCREEN_TREASURE", f"Энтропия экрана дала {gold} золота", metrics, state.to_dict())
        return lines

class MouseMoveHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        mouse_move = metrics.get('mouse_move', 0)
        if mouse_move > self.config['mouse_move_threshold'] and len(state.locations) > 1:
            new_loc = random.choice([loc for loc in state.locations if loc != state.current_location])
            old_loc = state.current_location
            state.current_location = new_loc
            lines.append(f"     [🖱️] Янус резко дёрнул мышью и переместился из {old_loc} в {new_loc}.")
            send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '🖱️',
                              'narrative': f"Переход из {old_loc} в {new_loc}", 'artifact': None,
                              'lore': f"new_location={new_loc}"})
            _db_buffer.add("MOUSE_TELEPORT", f"Переход {old_loc} → {new_loc}", metrics, state.to_dict())
        return lines

class MagneticBossHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        android_mag = metrics.get('android_mag', 0)
        if android_mag > self.config['android_mag_threshold'] and state.raid_boss is None and random.random() < self.config['android_mag_boss_chance']:
            state.raid_boss = SwarmAgent("raid_boss", is_raid=True)
            lines.append(f"     [📱] Магнитная буря! Появился {state.raid_boss.name}!")
            _db_buffer.add("MAGNETIC_STORM", f"Появился рейдовый босс {state.raid_boss.name}", metrics, state.to_dict())
        return lines

class KeyboardRegenHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        keys_per_sec = metrics.get('keys_per_sec', 0)
        if keys_per_sec > 5:
            lines.append("     [⌨️] Янус быстро печатает, мана восстанавливается быстрее.")
        return lines

class CombatHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        if (state.swarm or state.raid_boss) and random.random() < self._battle_chance(metrics):
            killed, dmg_taken, combat_log = state.combat_turn()
            lines.extend([f"     {line}" for line in combat_log[:3]])
            send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '⚔️',
                              'narrative': f"Автоматический бой: убито {killed} мобов, получено урона {dmg_taken}",
                              'artifact': None, 'lore': f"gold={state.gold}, health={state.health}"})
            _db_buffer.add("COMBAT", f"Убито {killed}, урон {dmg_taken}", metrics, state.to_dict())
        return lines

    def _battle_chance(self, metrics):
        pred_score = metrics.get('pred_score', 1.0)
        gpu_load = metrics.get('gpu_load', 0)
        base = self.config['battle_chance_base']
        pred_factor = self.config['battle_chance_pred_factor']
        gpu_factor = self.config['battle_chance_gpu_factor']
        return base + pred_score * pred_factor + gpu_load * gpu_factor

class RandomEventHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        roll = random.random()
        if roll < self.config['artifact_chance']:
            artifact = get_real_artifact()
            if artifact:
                state.inventory.append(artifact)
                lines.append(f"     [💾] Найден артефакт: {artifact} {generate_emoji_thought()}")
                send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '💾',
                                  'narrative': f"Найден артефакт: {artifact}", 'artifact': artifact,
                                  'lore': f"inventory_size={len(state.inventory)}"})
                _db_buffer.add("ARTIFACT_FOUND", artifact, metrics, state.to_dict())
            else:
                if random.random() < self.config['gold_find_chance']:
                    gold = random.randint(*self.config['gold_find_base']) + int(metrics.get('pred_score', 0) * 2)
                    state.gold += gold
                    lines.append(f"     [💰] Найдено {gold} золота! {generate_emoji_thought()}")
                    send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '💰',
                                      'narrative': f"Найдено {gold} золота", 'artifact': None,
                                      'lore': f"gold={state.gold}"})
                    _db_buffer.add("GOLD_FOUND", f"{gold} золота", metrics, state.to_dict())
                else:
                    dmg = random.randint(*self.config['damage_range'])
                    state.health -= dmg
                    lines.append(f"     [🤕] Потеряно {dmg} HP при исследовании.")
                    _db_buffer.add("DAMAGE", f"{dmg} HP", metrics, state.to_dict())
        elif roll < self.config['artifact_chance'] + self.config['travel_chance']:
            if len(state.locations) > 1:
                new_loc = random.choice([loc for loc in state.locations if loc != state.current_location])
                old_loc = state.current_location
                state.current_location = new_loc
                lines.append(f"     [🚪] Янус перемещается в {new_loc}.")
                send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '🚪',
                                  'narrative': f"Переход из {old_loc} в {new_loc}", 'artifact': None,
                                  'lore': f"new_location={new_loc}"})
                _db_buffer.add("TRAVEL", f"{old_loc} → {new_loc}", metrics, state.to_dict())
            else:
                lines.append(f"     [🚪] Янус остаётся в {state.current_location} (других локаций нет).")
        elif roll < self.config['artifact_chance'] + self.config['travel_chance'] + self.config['thought_chance']:
            phrase = random.choice(EVENT_PHRASES)
            thought = generate_emoji_thought(4)
            lines.append(f"     [💭] {phrase} {thought}")
            _db_buffer.add("THOUGHT", phrase, metrics, state.to_dict())
        return lines

class HealHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        if state.mana >= self.config['heal_cost']:
            heal = random.randint(*self.config['heal_amount'])
            state.health = min(state.max_health, state.health + heal)
            state.mana -= self.config['heal_cost']
            lines.append(f"     [🙏] Восстановлено {heal} HP (мана -{self.config['heal_cost']}).")
            _db_buffer.add("HEAL", f"+{heal} HP, -{self.config['heal_cost']} маны", metrics, state.to_dict())
        else:
            lines.append("     [💤] Маны мало, отдых без эффекта.")
        return lines

class DeathHandler(WorldEventHandler):
    def handle(self, metrics, state):
        lines = []
        if state.health <= 0:
            lines.append(f"     [☠️] Янус повержен! Воскрешение...")
            send_hrain_event({'type': 'genesis_step', 'depth': state.level, 'visual': '☠️',
                              'narrative': "Янус погиб и воскрес", 'artifact': None,
                              'lore': f"gold={state.gold//2}"})
            _db_buffer.add("DEATH", "Янус погиб и воскрес", metrics, state.to_dict())
            state.health = state.max_health // 2
            state.gold //= 2
            limb = random.choice(state.limbs)
            limb.damage(50)
            lines.append(f"     ⚠️ {limb.type} повреждён до {limb.status}!")
        return lines

# ==========================================
# ТАХИОННЫЙ ОБРАБОТЧИК (КРИО-МЕТАБОЛИЗМ)
# ==========================================
class TachyonicThermalHandler(WorldEventHandler):
    def handle(self, metrics: Dict[str, Any], state: JanusRPGState) -> List[str]:
        output = []
        temp_f = metrics.get('temp_f', 120.0)
        entropy = metrics.get('hw_entropy', 0.005)
        active_sensor = metrics.get('active_sensor', None)
        if active_sensor and active_sensor in metrics.get('all_sensors_purity', {}):
            purity = metrics['all_sensors_purity'][active_sensor]
        else:
            purity = metrics.get('purity_score', 0.0)

        if temp_f < 115.0:
            cold_bonus = (115.0 - temp_f) * 0.5
            state.mana = min(state.max_mana, state.mana + cold_bonus)
            if cold_bonus > 5:
                output.append(f"❄️ [КРИО] Температура {temp_f}F. Мана +{cold_bonus:.1f} (Эффект Слизевика)")

        if entropy > 0.007:
            leak = random.randint(1, 3)
            state.gold = max(0, state.gold - leak)
            output.append(f"🔥 [ШУМ] Энтропия {entropy:.4f} вызвала утечку {leak} золота.")

        if purity > 1000:
            state.exp += 10
            output.append(f"💎 [P=NP] Квантовая чистота достигнута! +10 XP.")
            _db_buffer.add("GOLDEN_STATE", f"Purity: {purity:.2f} at {temp_f}F", metrics, state.to_dict())

        return output

# ==========================================
# ОРБИТАЛЬНЫЙ ДИСПЕТЧЕР (ГЕТЕРОГЕННЫЕ ВЫЧИСЛЕНИЯ)
# ==========================================
class ComputeOrbitalDispatcher:
    def __init__(self):
        self.current_device = "cpu"
        logger.info("🛰️ Орбитальный диспетчер вычислений активирован.")

    def select_best_orbit(self, cpu_metrics: Dict, gpu_metrics: Dict) -> str:
        cpu_purity = cpu_metrics.get('purity_score', 0)
        gpu_purity = gpu_metrics.get('purity_score', 0)
        if gpu_purity > cpu_purity * 1.2:
            new_device = "cuda"
        else:
            new_device = "cpu"
        if new_device != self.current_device:
            self.current_device = new_device
            logger.info(f"🚀 ТАХИОННЫЙ ПЕРЕХОД: Вычисления перенесены на {new_device.upper()}")
        return self.current_device

# ==========================================
# ЗЕРКАЛО ЯНУСА (САМООБУЧЕНИЕ)
# ==========================================
class JanusMirror:
    def __init__(self, zoo_path=MODEL_ZOO_DIR):
        self.zoo_path = zoo_path
        logger.info("🪞 Зеркало Януса установлено.")

    def reflect(self) -> Optional[str]:
        files = [os.path.join(self.zoo_path, f) for f in os.listdir(self.zoo_path) if f.endswith('.json')]
        if not files:
            return None
        history = []
        for f in files[-20:]:
            try:
                with open(f, 'r') as j:
                    history.append(json.load(j))
            except Exception:
                continue
        if not history:
            return None
        gpu_avg = np.mean([h.get('gpu_purity', 0) for h in history])
        cpu_avg = np.mean([h.get('purity_score', 0) for h in history])
        return "cuda" if gpu_avg > cpu_avg else "cpu"

    def adjust_hyperparams(self, current_purity: float) -> float:
        return np.clip(current_purity / 1000.0, 0.1, 2.0)

# ==========================================
# НЕЙРО-НАГРАДА (OXYTOCIN & DOPAMINE)
# ==========================================
class NeuroRewardSystem:
    def __init__(self):
        self.total_oxytocin = 1.0
        logger.info("❤️ Нейрохимический интерфейс наград активирован.")

    def calculate_reward(self, purity: float, loss_diff: float, device: str) -> float:
        purity_bonus = np.log1p(purity / 100)
        success_bonus = max(0, loss_diff * 10)
        device_mult = 1.2 if device == "cuda" else 1.0
        final_reward = (purity_bonus + success_bonus) * device_mult
        self.total_oxytocin = np.clip(self.total_oxytocin + (final_reward * 0.01), 0.1, 5.0)
        return round(final_reward, 2)

    def distribute(self, agents: List, reward: float) -> str:
        count = 0
        for agent in agents:
            if hasattr(agent, 'exp'):
                agent.exp += reward
                count += 1
            if hasattr(agent, 'mana') and hasattr(agent, 'max_mana'):
                agent.mana = min(agent.max_mana, agent.mana + (reward * 0.5))
        return f"✨ Награда: {reward} XP распределено между {count} Агентами."

# ==========================================
# НОВАЯ ФУНКЦИЯ: РАСШИРЕННАЯ НАГРАДА
# ==========================================
def apply_reward(state: JanusRPGState, purity: float, loss_diff: float, temp_f: float,
                 agents: Optional[List] = None) -> List[str]:
    lines = []
    gold_gain = max(0, int(purity * 10 + loss_diff * 50))
    if gold_gain > 0:
        state.gold += gold_gain
        lines.append(f"💰 Найдено {gold_gain} золота!")

    xp_gain = max(0, int(purity * 20 + abs(loss_diff) * 30))
    if xp_gain > 0:
        state.exp += xp_gain
        lines.append(f"✨ Получено {xp_gain} XP!")

    if purity > 50 and random.random() < 0.3:
        artifact = get_real_artifact() or "Кристалл Чистоты"
        state.inventory.append(artifact)
        lines.append(f"💎 Найден артефакт: {artifact}!")

    if loss_diff > 0 and random.random() < 0.2:
        buff_name = "Фокус Градиента"
        duration = 5
        effects = {"learning_rate": 1.2}
        if hasattr(state, 'add_buff'):
            state.add_buff(buff_name, duration, effects)
        lines.append(f"✨ Наложен баф '{buff_name}' (+20% к learning rate)!")

    if temp_f < 113:
        resource = random.choice(["древесина", "руда", "кристаллы"])
        amount = random.randint(1, 5)
        if not hasattr(state, 'resources'):
            state.resources = {}
        state.resources[resource] = state.resources.get(resource, 0) + amount
        lines.append(f"🌲 Добыто {amount} {resource}!")

    if agents and loss_diff > 0:
        best_agent = None
        best_score = -float('inf')
        for a in agents:
            scr = getattr(a, 'score', -float('inf'))
            if scr > best_score:
                best_score = scr
                best_agent = a
        if best_agent:
            best_agent.exp += xp_gain // 2
            lines.append(f"🏆 Лучший агент {best_agent.id[:8]} получает бонус {xp_gain//2} XP!")

    return lines

# ==========================================
# МЕНЕДЖЕР СОБЫТИЙ
# ==========================================
class WorldEventManager:
    def __init__(self, config: Dict):
        self.config = config
        self.handlers = [
            OverheatHandler(config),
            MouseArtifactHandler(config),
            SoundSpawnHandler(config),
            ScreenTreasureHandler(config),
            MouseMoveHandler(config),
            MagneticBossHandler(config),
            KeyboardRegenHandler(config),
            CombatHandler(config),
            RandomEventHandler(config),
            HealHandler(config),
            DeathHandler(config),
            TachyonicThermalHandler(config),
        ]

    def process(self, metrics: Dict[str, Any], state: JanusRPGState) -> List[str]:
        all_lines = []
        for handler in self.handlers:
            try:
                lines = handler.handle(metrics, state)
                all_lines.extend(lines)
            except Exception as e:
                logger.error(f"Ошибка в обработчике {handler.name}: {e}", exc_info=True)
        return all_lines

_event_manager = WorldEventManager(GENESIS_CONFIG)

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С NP (расширенные)
# ==========================================
def generate_np_task(state: JanusRPGState, purity: float, current_difficulty: float = 1.0) -> Optional[NPTask]:
    chance = GENESIS_CONFIG['np_task_chance'] * (1 + purity / 100)
    if random.random() > chance:
        return None
    use_phase = GENESIS_CONFIG['np_phase_transition_enabled']
    n_vars = random.randint(GENESIS_CONFIG['np_task_min_vars'], GENESIS_CONFIG['np_task_max_vars'])
    if use_phase:
        n_clauses = int(GENESIS_CONFIG['np_phase_transition_ratio'] * n_vars)
    else:
        base_ratio = current_difficulty
        target_clauses = int(base_ratio * n_vars)
        n_clauses = max(GENESIS_CONFIG['np_task_min_clauses'],
                        min(GENESIS_CONFIG['np_task_max_clauses'], target_clauses))
    return NPTask(n_vars, n_clauses, phase_transition=use_phase)

def solve_np_task_with_agent(agent: Any, task: NPTask, timeout: float = 2.0) -> Tuple[bool, float, List[bool]]:
    solved, assignment, reward_mult = agent.solve_np_task(task, timeout=timeout)
    return solved, reward_mult, assignment

def apply_np_reward(state: JanusRPGState, agent: Any, task: NPTask, reward_mult: float, solved: bool,
                    actual_time: float = None, predicted_time: float = None):
    if solved:
        mult = getattr(state, 'np_reward_mult', 1.0)
        if actual_time is not None and predicted_time is not None and actual_time < predicted_time:
            mult *= GENESIS_CONFIG.get('np_bonus_for_beating_prediction', 1.5)
        xp_bonus = int(GENESIS_CONFIG['np_task_bonus_xp'] * reward_mult * mult)
        gold_bonus = int(GENESIS_CONFIG['np_task_bonus_gold'] * reward_mult * mult)
        state.exp += xp_bonus
        state.gold += gold_bonus
        agent.exp += xp_bonus // 2
        agent.gold += gold_bonus // 2
        if hasattr(state, 'self') and hasattr(state.self, 'identity'):
            state.self.identity['meta_progress'] = state.self.identity.get('meta_progress', 0.0) + 0.01
        return xp_bonus, gold_bonus
    return 0, 0

def _get_best_agent(agents: List) -> Optional[Any]:
    if not agents:
        return None
    return max(agents, key=lambda a: getattr(a, 'score', 0) + getattr(a, 'level', 0) * 10)

# ==========================================
# ОСНОВНАЯ ФУНКЦИЯ auto_update_world (адаптивная, с интеграцией тахионных метрик)
# ==========================================
_dispatcher = ComputeOrbitalDispatcher()
_mirror = JanusMirror()
_neuro = NeuroRewardSystem()

def auto_update_world(metrics: Optional[Dict[str, Any]], state: JanusRPGState, agents: Optional[List] = None) -> List[str]:
    if metrics is None:
        metrics = {}

    state.np_task_solved_this_cycle = False
    state.np_difficulty_solved = 0.0

    temp_f = metrics.get('temp_f', 120.0)
    entropy = metrics.get('hw_entropy', 0.005)
    active_sensor = metrics.get('active_sensor', None)
    if active_sensor and active_sensor in metrics.get('all_sensors_purity', {}):
        purity = metrics['all_sensors_purity'][active_sensor]
    else:
        purity = metrics.get('purity_score', 0.0)

    prev_loss = metrics.get('prev_loss')
    current_loss = metrics.get('current_loss')
    loss_diff = metrics.get('loss_diff', 0.0)

    if prev_loss is not None and current_loss is not None:
        loss_str = f"{prev_loss:.4f} -> {current_loss:.4f}"
    elif current_loss is not None:
        loss_str = f"{current_loss:.4f}"
    else:
        loss_str = "???"

    cpu_metrics = {'purity_score': purity, 'temp_f': temp_f, 'hw_entropy': entropy}
    gpu_metrics = {'purity_score': metrics.get('gpu_purity_score', 0.0), 'temp_f': temp_f, 'hw_entropy': 0.0}
    active_device = _dispatcher.select_best_orbit(cpu_metrics, gpu_metrics)

    lr_mult = _mirror.adjust_hyperparams(purity)
    reward = _neuro.calculate_reward(purity, loss_diff, active_device)

    lines = _event_manager.process(metrics, state)
    reward_lines = apply_reward(state, purity, loss_diff, temp_f, agents)
    lines.extend(reward_lines)

    # ========== NP-ЗАДАЧА: АДАПТИВНЫЙ СЕРИЙНЫЙ РЕЖИМ (все числа) ==========
    series_enabled = GENESIS_CONFIG.get('np_series_enabled', True)
    adaptive_series = GENESIS_CONFIG.get('np_series_adaptive', True)
    use_phase = GENESIS_CONFIG.get('np_phase_transition_enabled', True)
    max_attempts = GENESIS_CONFIG.get('np_max_attempts_per_task', 1)
    failure_queue_enabled = GENESIS_CONFIG.get('np_failure_queue_enabled', True)

    if not hasattr(state, 'np_series'):
        state.np_series = []
        state.np_series_index = 0
        state.np_series_results = []
        state.np_scaling_exponent = 1.5
        state.np_failure_queue = []
        state.np_current_attempts = 0
        state.np_series_failures = 0
        state.np_series_total = 0
    if not hasattr(state, 'last_np_size'):
        state.last_np_size = 20

    # Генерация новой серии
    if series_enabled and len(state.np_series) == 0:
        pending_tasks = []
        if failure_queue_enabled and hasattr(state, 'np_failure_queue') and state.np_failure_queue:
            for item in state.np_failure_queue:
                if isinstance(item, dict) and 'task' in item:
                    pending_tasks.append(item['task'])
                else:
                    pending_tasks.append(item)
            lines.append(f"📋 [NP-SERIES] Добавлено {len(pending_tasks)} отложенных задач из очереди")

        if adaptive_series:
            last_size = state.last_np_size
            downshift = 0
            if GENESIS_CONFIG.get('np_adaptive_difficulty', True) and state.np_series_total > 0:
                failure_ratio = state.np_series_failures / max(1, state.np_series_total)
                if failure_ratio >= GENESIS_CONFIG['np_failure_threshold_ratio']:
                    downshift = GENESIS_CONFIG['np_adaptive_down_step']
                    lines.append(f"📉 [NP-SERIES] Высокая доля неудач ({failure_ratio:.1%}), снижаем сложность на {downshift}")
            min_n = max(GENESIS_CONFIG['np_adaptive_min_start'], last_size + GENESIS_CONFIG['np_adaptive_min_step'] - downshift)
            max_n = min(2000, min_n + GENESIS_CONFIG['np_adaptive_max_range'])
            use_primes_only = GENESIS_CONFIG.get('np_series_use_primes_only', False)
            step = GENESIS_CONFIG.get('np_series_step', 5)
            if use_primes_only:
                sizes = get_primes_in_range(min_n, max_n)
            else:
                sizes = list(range(min_n, max_n+1, step))
            if not sizes:
                sizes = list(range(min_n, max_n+1, 5))[:5]
            tasks = generate_series(sizes, n_tasks_per_size=GENESIS_CONFIG['np_series_tasks_per_size'], phase_transition=use_phase)
        else:
            step = GENESIS_CONFIG.get('np_series_step', 5)
            sizes = list(range(20, 2001, step))
            tasks = generate_series(sizes, n_tasks_per_size=GENESIS_CONFIG['np_series_tasks_per_size'], phase_transition=use_phase)

        state.np_series = pending_tasks + tasks
        state.np_series_index = 0
        state.np_series_results = []
        state.np_series_failures = 0
        state.np_series_total = len(state.np_series)
        state.np_current_attempts = 0

        if failure_queue_enabled:
            state.np_failure_queue = []

        if state.np_series:
            sizes_str = ', '.join(str(t.n_vars) for t in state.np_series)
            lines.append(f"📜 [NP-SERIES] Сгенерирована серия из {len(state.np_series)} задач (размеры: {sizes_str})")

    # Решение текущей задачи
    if state.np_series and state.np_series_index < len(state.np_series):
        task = state.np_series[state.np_series_index]
        best_agent = _get_best_agent(agents) if agents else None
        if best_agent:
            n_vars = task.n_vars
            agent_config = best_agent.current_config.copy()
            tachyon_metrics = get_tachyon_metrics()  # текущие метрики из тахионного моста
            timeout = state.get_adaptive_timeout(n_vars, agent_config, tachyon_metrics)
            predicted_time = state.predict_time(n_vars, agent_config, tachyon_metrics) if state.tachyon_engine is not None else None

            start_time = time.time()
            solved, reward_mult, assignment = solve_np_task_with_agent(best_agent, task, timeout=timeout)
            elapsed_ms = (time.time() - start_time) * 1000
            actual_time = elapsed_ms / 1000.0

            # Сохраняем результат с метриками
            state.record_np_solution(n_vars, solved, elapsed_ms, state.np_current_attempts + 1, agent_config, tachyon_metrics)

            state.np_series_results.append({
                'n_vars': n_vars,
                'solved': solved,
                'time_ms': elapsed_ms,
                'difficulty': task.difficulty(),
                'attempt': state.np_current_attempts + 1,
                'timeout': timeout,
                'predicted_time': predicted_time,
                'agent_config': agent_config,
                'tachyon_metrics': tachyon_metrics
            })
            log_line = f"🧪 [NP-SERIES] Задача {state.np_series_index+1}/{len(state.np_series)} (n={n_vars}): {'✅ решена' if solved else '❌ не решена'} за {elapsed_ms:.1f} мс (попытка {state.np_current_attempts+1}, timeout={timeout:.1f}s)"
            if predicted_time:
                log_line += f", прогноз={predicted_time:.1f}s"
            lines.append(log_line)

            if solved:
                state.last_np_size = max(state.last_np_size, n_vars)
                state.np_current_attempts = 0
                base_xp = GENESIS_CONFIG['np_task_bonus_xp']
                base_gold = GENESIS_CONFIG['np_task_bonus_gold']
                size_factor = (n_vars / 20.0) ** 2
                resonance_bonus = 1.0
                if is_prime(n_vars):
                    resonance_bonus *= 1.5
                if n_vars % 37 == 0:
                    resonance_bonus *= 2.0
                dr = digital_root(n_vars)
                if dr == 3:
                    resonance_bonus *= 1.3
                total_bonus = size_factor * resonance_bonus
                if predicted_time and actual_time < predicted_time:
                    total_bonus *= GENESIS_CONFIG.get('np_bonus_for_beating_prediction', 1.5)
                    lines.append(f"   🎯 Преодолён прогноз! Время {actual_time:.2f}s < {predicted_time:.2f}s")
                xp_bonus = int(base_xp * total_bonus)
                gold_bonus = int(base_gold * total_bonus)
                state.exp += xp_bonus
                state.gold += gold_bonus
                best_agent.exp += xp_bonus // 2
                best_agent.gold += gold_bonus // 2
                lines.append(f"   +{xp_bonus} XP, +{gold_bonus} золота (резонансный множитель {total_bonus:.2f})")
                state.np_series_index += 1
                state.np_current_attempts = 0
            else:
                state.np_series_failures += 1
                state.np_current_attempts += 1
                if state.np_current_attempts < max_attempts:
                    lines.append(f"   🔁 Повторная попытка (осталось {max_attempts - state.np_current_attempts})")
                else:
                    if failure_queue_enabled:
                        state.np_failure_queue.append(task)
                        lines.append(f"   📦 Задача отложена в очередь (будет повторена в следующих сериях)")
                    else:
                        lines.append(f"   ⚠️ Задача пропущена (лимит попыток исчерпан)")
                    state.np_series_index += 1
                    state.np_current_attempts = 0
        else:
            lines.append("⚠️ [NP-SERIES] Нет агентов для решения задач.")
            state.np_series_index += 1
            state.np_current_attempts = 0

    elif state.np_series and state.np_series_index >= len(state.np_series):
        # Серия завершена – статистика и переобучение модели
        if state.np_series_results:
            solved_tasks = [r for r in state.np_series_results if r['solved']]
            if solved_tasks:
                n_vals = [r['n_vars'] for r in solved_tasks]
                t_vals = [r['time_ms'] for r in solved_tasks]
                if len(n_vals) > 1:
                    log_n = np.log(n_vals)
                    log_t = np.log(t_vals)
                    slope, intercept = np.polyfit(log_n, log_t, 1)
                    state.np_scaling_exponent = slope
                    lines.append(f"📊 [NP-METRICS] Экспонента масштабирования: {slope:.3f} (log(t) ~ {slope:.3f} * log(n) + {intercept:.3f})")
                else:
                    state.np_scaling_exponent = 1.5
            else:
                state.np_scaling_exponent = 1.5

            total = len(state.np_series_results)
            solved_cnt = len(solved_tasks)
            failed_cnt = total - solved_cnt
            lines.append(f"🏁 [NP-SERIES] Серия завершена. Решено: {solved_cnt}/{total}, неудач: {failed_cnt}. Последний решённый размер: {state.last_np_size}")
            if state.np_failure_queue:
                lines.append(f"   📋 В очереди отложенных задач: {len(state.np_failure_queue)}")

            # Переобучаем модель предсказания
            state.update_prediction_model()
            if state.tachyon_engine is not None and state.tachyon_engine.trained:
                lines.append(f"🧠 [META] Модель TachyonEngine обновлена на {len(state.np_series_results)} примерах")

            np_metrics_path = os.path.join(RAW_LOGS_DIR, "np_scaling_metrics.json")
            try:
                with open(np_metrics_path, 'w') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'series': state.np_series_results,
                        'scaling_exponent': state.np_scaling_exponent,
                        'cycle': getattr(state, 'last_cycle', 0),
                        'last_np_size': state.last_np_size,
                        'failure_queue_size': len(state.np_failure_queue)
                    }, f, indent=2)
            except Exception as e:
                logger.error(f"Не удалось сохранить метрики NP: {e}")

        state.np_series = []
        state.np_series_index = 0
        state.np_series_results = []
        state.np_series_failures = 0
        state.np_series_total = 0
        state.np_current_attempts = 0

    # ========== СТАРЫЙ РЕЖИМ (одиночные задачи) – если серии отключены ==========
    if not series_enabled:
        if not hasattr(state, 'current_np_task') or state.current_np_task is None:
            current_difficulty = getattr(state, 'np_difficulty', 1.0)
            new_task = generate_np_task(state, purity, current_difficulty)
            if new_task:
                state.current_np_task = new_task
                lines.append(f"📜 [SAT] Появилась новая 3-SAT задача (переменных: {new_task.n_vars}, предложений: {new_task.n_clauses}).")
        else:
            task = state.current_np_task
            best_agent = _get_best_agent(agents) if agents else None
            if best_agent:
                agent_config = best_agent.current_config.copy()
                tachyon_metrics = get_tachyon_metrics()
                timeout = state.get_adaptive_timeout(task.n_vars, agent_config, tachyon_metrics)
                predicted_time = state.predict_time(task.n_vars, agent_config, tachyon_metrics) if state.tachyon_engine is not None else None
                start_time = time.time()
                solved, reward_mult, assignment = solve_np_task_with_agent(best_agent, task, timeout=timeout)
                elapsed_ms = (time.time() - start_time) * 1000
                actual_time = elapsed_ms / 1000.0
                state.record_np_solution(task.n_vars, solved, elapsed_ms, 1, agent_config, tachyon_metrics)
                if solved:
                    xp_bonus, gold_bonus = apply_np_reward(state, best_agent, task, reward_mult, solved, actual_time, predicted_time)
                    lines.append(f"🧠 [SAT] Агент {best_agent.id[:8]} решил 3-SAT задачу! +{xp_bonus} XP, +{gold_bonus} золота.")
                    state.np_task_solved_this_cycle = True
                    state.np_difficulty_solved = task.difficulty()
                    state.np_difficulty = getattr(state, 'np_difficulty', 1.0) + GENESIS_CONFIG['np_task_difficulty_increment']
                    state.current_np_task = None
                    state.last_np_size = max(state.last_np_size, task.n_vars)
                else:
                    if random.random() < 0.1:
                        lines.append(f"🤔 [SAT] Агент {best_agent.id[:8]} не смог решить задачу.")
            else:
                lines.append("⚠️ [SAT] Нет агентов для решения задачи.")

    # Логирование орбиты и награды
    sensor_info = f" | Sensor: {active_sensor}" if active_sensor else ""
    lines.append(f"ℹ️ [ORBIT] Active: {active_device.upper()} | Purity: {purity:.2f}{sensor_info} | ❤️ Oxytocin: {_neuro.total_oxytocin:.2f} | LR_Mult: {lr_mult:.2f}x")
    lines.append(f"ℹ️ [REWARD] {_neuro.distribute([state], reward)} | Янус атакует Хаос: Loss {loss_str}")

    # Статус Януса
    if state.mana < 10 and entropy > 0.008:
        state.status = "HIBERNATION"
        lines.append("💤 [СТАТУС] Янус ушел в глубокую гибернацию из-за шума.")
    elif temp_f < 113.0:
        state.status = "SUPERCONDUCTOR"
        lines.append("⚡ [СТАТУС] Режим Сверхпроводника: Поиск P=NP активен.")
    else:
        state.status = "NORMAL"

    if random.random() < 0.1:
        _db_buffer.flush()

    return lines

# ==========================================
# ИНТЕРАКТИВНЫЙ ЦИКЛ (без изменений)
# ==========================================
async def async_main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\033[96m{'='*70}")
    print("⚡ ХРОНИКИ ЯНУСА: ЭВОЛЮЦИОННАЯ RPG ⚡")
    print("Вдохновлено Kenshi и Lineage II. Мир жесток и непредсказуем.")
    print(f"{'='*70}\033[0m")

    state = JanusRPGState()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state.load(json.load(f))
            print(f"[💾] Игровой мир восстановлен. Уровень {state.level}, локаций: {len(state.locations)}")
        except Exception as e:
            print(f"[⚠️] Ошибка загрузки состояния: {e}")

    janus_db.init_db()

    send_hrain_event({
        'type': 'genesis_step',
        'depth': state.level,
        'visual': '🚪',
        'narrative': "Янус пробуждается в цифровом мире.",
        'artifact': None,
        'lore': f"level={state.level}, health={state.health}, mana={state.mana}, exp={state.exp}, gold={state.gold}"
    })

    last_auto_time = time.time()
    auto_interval = GENESIS_CONFIG['auto_interval']

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(protocol, sys.stdin)

    try:
        while True:
            now = time.time()
            if now - last_auto_time >= auto_interval:
                last_auto_time = now
                metrics = get_current_janus_metrics()
                if metrics:
                    state.update_from_metrics(metrics)
                    state.spawn_swarm(metrics)
                lines = auto_update_world(metrics or {}, state, agents=None)
                for line in lines:
                    print(line)
                atomic_save_state(state)
                _print_state(state, metrics)

            try:
                user_input = await asyncio.wait_for(reader.readline(), timeout=1.0)
                user_input = user_input.decode().strip()
                if user_input:
                    await _process_command(user_input, state)
            except asyncio.TimeoutError:
                pass

    except KeyboardInterrupt:
        atomic_save_state(state)
        print(f"\n[{get_time_str()}] 💾 Аварийное сохранение. Конец связи.")
    except Exception as e:
        logger.exception("Критическая ошибка в интерактивном режиме")
        atomic_save_state(state)
        raise

async def _process_command(cmd: str, state: JanusRPGState):
    cmd_lower = cmd.lower()
    if cmd_lower in ["exit", "quit", "save"]:
        atomic_save_state(state)
        print(f"[{get_time_str()}] 💾 Демиург покинул этот мир. Сохранение...")
        sys.exit(0)
    elif cmd_lower == "base":
        _base_menu(state)
    elif "лечи" in cmd_lower or "хил" in cmd_lower:
        _heal_command(state, cmd)
    elif "бей" in cmd_lower or "молни" in cmd_lower:
        _fight_command(state, cmd)
    else:
        thought = generate_emoji_thought()
        print(f"[{get_time_str()}] ⚡ Глас Божий: «{cmd}». Янус записал это в дневник. {thought}")
    atomic_save_state(state)

def _base_menu(state: JanusRPGState):
    print("\n[🏰] БАЗА ЯНУСА:")
    print(f"   Уровень базы: {state.base_level}")
    for upg, data in state.base_upgrades.items():
        print(f"   {upg}: ур.{data['level']} - {data['bonus']}")
    print("   [1] Улучшить щит (100 * уровень)")
    print("   [2] Улучшить генератор (100 * уровень)")
    print("   [3] Ремонт конечностей (см. статус)")
    print("   [0] Выйти")
    choice = input("Выбор: ").strip()
    if choice == "1":
        ok, msg = state.upgrade_base("щит")
        print(msg)
    elif choice == "2":
        ok, msg = state.upgrade_base("генератор")
        print(msg)
    elif choice == "3":
        for i, limb in enumerate(state.limbs):
            print(f"   [{i}] {limb.type}: {limb.status} ({limb.health}%)")
        idx = input("Индекс конечности для ремонта: ").strip()
        if idx.isdigit():
            ok, msg = state.repair_limb(int(idx))
            print(msg)

def _heal_command(state: JanusRPGState, cmd: str):
    cost = 10
    if state.gold >= cost:
        state.gold -= cost
        state.health = min(state.max_health, state.health + 30)
        print(f"[{get_time_str()}] ⚡ Глас Божий: «{cmd}». Янус потратил {cost} золота и исцелился (+30 HP).")
        send_hrain_event({
            'type': 'genesis_step',
            'depth': state.level,
            'visual': '💊',
            'narrative': f"Янус исцелён на 30 HP (стоимость {cost} золота)",
            'artifact': None,
            'lore': f"health={state.health}, gold={state.gold}"
        })
        _db_buffer.add("DIVINE_HEAL", f"+30 HP за {cost} золота", world_state=state.to_dict())
    else:
        heal = 15
        state.health = min(state.max_health, state.health + heal)
        print(f"[{get_time_str()}] ⚡ Глас Божий: «{cmd}». Но золота не хватило, Янус чуть-чуть восстанавливается (+{heal} HP).")
        send_hrain_event({
            'type': 'genesis_step',
            'depth': state.level,
            'visual': '💊',
            'narrative': f"Не хватило золота, исцеление слабое (+{heal} HP)",
            'artifact': None,
            'lore': f"health={state.health}, gold={state.gold}"
        })
        _db_buffer.add("WEAK_HEAL", f"+{heal} HP бесплатно", world_state=state.to_dict())

def _fight_command(state: JanusRPGState, cmd: str):
    if state.swarm or state.raid_boss:
        killed, dmg_taken, _ = state.combat_turn()
        send_hrain_event({
            'type': 'genesis_step',
            'depth': state.level,
            'visual': '⚔️',
            'narrative': f"Бой по приказу: убито {killed} мобов, получено урона {dmg_taken}",
            'artifact': None,
            'lore': f"gold={state.gold}, health={state.health}"
        })
        _db_buffer.add("DIVINE_COMBAT", f"Убито {killed}, урон {dmg_taken}", world_state=state.to_dict())
    else:
        print(f"[{get_time_str()}] ⚡ Глас Божий: «{cmd}». Но вокруг никого.")

def _print_state(state: JanusRPGState, metrics: Optional[Dict] = None):
    exp_needed = state.level * 100
    exp_percent = (state.exp / exp_needed) * 100 if exp_needed > 0 else 0
    limb_status = ", ".join([f"{l.type[:2]}={l.status[0]}" for l in state.limbs[:3]])
    print(f"\n\033[93m[❤️ {state.health}/{state.max_health} | 💙 {state.mana}/{state.max_mana} | ⭐ Уровень {state.level} | 🧪 Опыт {exp_percent:.1f}% | 💰 Золото {state.gold}]\033[0m")
    print(f"   📍 Локация: {state.current_location} | 🐜 Мобов: {len(state.swarm)} | 🏰 База ур.{state.base_level} | 🦿 {limb_status}")
    if state.raid_boss:
        print(f"   🔥 РЕЙДОВЫЙ БОСС: {state.raid_boss.name} (❤️ {state.raid_boss.health})")
    if metrics:
        print(f"\033[94m   📊 best_score={metrics.get('best_score',0):.4f} | max_best={state.max_best:.4f} | MI={metrics.get('mi',0):.3f} | gap={metrics.get('gap',0):.4f} | vel={metrics.get('velocity',0):.4f}\033[0m")
        if 'pred_score' in metrics:
            print(f"   🔮 Тахион: предсказание={metrics['pred_score']:.4f}")

def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nВыход по Ctrl+C")
    finally:
        _db_buffer.flush()

if __name__ == "__main__":
    import sys
    main()
