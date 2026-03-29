#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS DEMIURGE CORE v7.2 — МЕТА-РЕЖИМ ЯНУСА С ИНСТИНКТАМИ
- Самоуправление режимами (EXPLORE, EXPLOIT, SURVIVE, CHAOS, HUNT)
- Инерция режима (mode_strength)
- SURVIVE откатывается к лучшему состоянию (с сохранением конфигурации модели)
- Контролируемый хаос (ограничен по времени)
- Голод (hunger) – толкает в хаос при застое
- Предиктивный выбор режима через self-model
- Антиколлапсная система + откат
- Аморфные параметры с самостабилизацией
"""

import os
import time
import json
import hashlib
import threading
import asyncio
import aiohttp
import numpy as np
import logging
from datetime import datetime
import random
import sys
from collections import deque
import subprocess
import copy
import torch

# Отключаем предупреждения Hugging Face (работаем локально)
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# ==============================================================================
# УМНЫЙ ЛОГГЕР SALO (Smart Adaptive Logging Organizer)
# ==============================================================================
class SALOLogger(logging.Logger):
    """Smart Adaptive Logging Organizer — удаляет повторы, добавляет эмодзи, ASCII-графику и обучается"""
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.last_messages = deque(maxlen=100)
        self.dup_counts = {}
        self.last_output_time = 0
        self.duplicate_threshold = 5
        self.cycle_counter = 0
        self.style = {
            'info': {'emoji': 'ℹ️', 'ascii': ''},
            'warning': {'emoji': '⚠️', 'ascii': ''},
            'error': {'emoji': '❌', 'ascii': ''},
            'success': {'emoji': '✅', 'ascii': ''},
            'cycle_start': {'emoji': '🔄', 'ascii': '\n' + '='*70},
            'cycle_end': {'emoji': '⏸️', 'ascii': '-'*70},
        }

    def _format_message(self, level, msg):
        if "CYCLE" in msg.upper() or "НАЧАЛО ЦИКЛА" in msg:
            self.cycle_counter += 1
            prefix = self.style['cycle_start']['emoji'] + " "
            return prefix + msg
        elif "ЦИКЛ ЗАВЕРШЁН" in msg:
            prefix = self.style['cycle_end']['emoji'] + " "
            return prefix + msg
        elif "Score:" in msg and "Loss:" in msg:
            return msg
        else:
            if level == logging.INFO:
                prefix = self.style['info']['emoji'] + " "
            elif level == logging.WARNING:
                prefix = self.style['warning']['emoji'] + " "
            elif level == logging.ERROR:
                prefix = self.style['error']['emoji'] + " "
            else:
                prefix = ""
            return prefix + msg

    def _should_output(self, level, msg):
        key = (level, msg)
        now = time.time()
        for last_msg, last_time in self.last_messages:
            if last_msg == msg and now - last_time < self.duplicate_threshold:
                self.dup_counts[key] = self.dup_counts.get(key, 0) + 1
                return False
        if self.dup_counts.get(key, 0) > 0:
            count = self.dup_counts[key]
            self.dup_counts[key] = 0
            summary = f" (повторено {count+1} раз)" if count > 1 else ""
            self._output(level, msg + summary)
        self.last_messages.append((msg, now))
        return True

    def _output(self, level, msg):
        formatted = self._format_message(level, msg)
        super().log(level, formatted)

    def log(self, level, msg, *args, **kwargs):
        if self._should_output(level, msg):
            self._output(level, msg)

    def info(self, msg, *args, **kwargs):
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log(logging.DEBUG, msg, *args, **kwargs)


logging.setLoggerClass(SALOLogger)
logger = logging.getLogger("JANUS")
logger.setLevel(logging.INFO)

# ==============================================================================
# Единый критерий выживания (M2R v2)
# ==============================================================================
def compute_fitness(loss: float, thermal_metrics: dict, np_solved: bool, entropy: float,
                    mutation_rate: float = None, energy_cost: float = 1.0, time_ms: float = 0.0) -> float:
    """
    M2R v2: учитывает loss, NP, температуру, энтропию, мутацию, энергозатраты и время.
    """
    loss_term = 1.0 / (1.0 + loss)
    np_bonus = 1.0 if np_solved else 0.0
    temp_penalty = thermal_metrics.get('temp_f', 100.0) / 200.0
    entropy_penalty = entropy * 10.0
    cost_penalty = (energy_cost - 1.0) * 0.5
    time_penalty = time_ms / 100.0   # штраф за медлительность
    fitness = loss_term + np_bonus - temp_penalty - entropy_penalty - cost_penalty - time_penalty
    if mutation_rate is not None:
        mutation_penalty = abs(mutation_rate - 0.2) * 0.5
        fitness -= mutation_penalty
    return max(fitness, -10.0)

# ==============================================================================
# АВТОМАТИЧЕСКАЯ ПОДГОТОВКА ДАННЫХ (исправлена кодировка)
# ==============================================================================
if os.path.exists("prepare_device_data.py"):
    try:
        logger.info("[⚙️] Запуск prepare_device_data.py для обновления device_data.json...")
        result = subprocess.run([sys.executable, "prepare_device_data.py"],
                                timeout=30, capture_output=True, encoding='utf-8')
        if result.returncode != 0:
            logger.warning(f"prepare_device_data.py завершился с ошибкой: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("prepare_device_data.py превысил таймаут 30 секунд")
    except Exception as e:
        logger.error(f"[⚠️] Не удалось запустить prepare_device_data.py: {e}")

import torch
from config import (
    SEEDS_PER_CYCLE, STEPS_PER_CYCLE, TRAIN_SIZE, VAL_SIZE,
    MODEL_ZOO_DIR, RAW_LOGS_DIR, DEVICE, BASE_BATCH_SIZE,
    HALF_LIFE_STEPS, LR_DECAY_ENABLE, DEBUG_MODE,
    RESUME, WORMHOLE_DIR,
    LOG_INTERVAL, LOG_ON_SUCCESS, LOG_FAILURE_SUMMARY, FAILURE_THRESHOLD,
    GENESIS_AUTO_INTERVAL,
    SWARM_ENABLED, SWARM_SIZE, SWARM_INERTIA, SWARM_COGNITIVE, SWARM_SOCIAL,
    BAYES_ENABLED, BAYES_INIT_POINTS, BAYES_ACQ_FUNC,
    META_ENABLED, META_UPDATE_INTERVAL, META_SAMPLE_SIZE,
    ADAPTIVE_TEST_ENABLED, ADAPTIVE_TEST_THRESHOLD, ADAPTIVE_TEST_STEPS,
    SUBCONSCIOUS_ENABLED, CHRONOS_INTERVAL, HYPNOS_INTERVAL, NEBUCHAD_INTERVAL, OUROBOROS_INTERVAL,
    digital_root, is_resonant, filter_hyperparams, N_EMBD_OPTIONS_RESONANT,
    is_tachyonic_resonance, detect_pocket, apply_filter_to_candidates,
    TACHYON_MONITOR_WINDOW, POCKET_WINDOW, FILTER_37_WEIGHT, TACHYON_ACQ_PENALTY,
    REGISTRY_SNAPSHOT_INTERVAL, FILTER_37_ENABLED,
    CONVERGENCE_ENABLED, CONVERGENCE_WINDOW
)
from environment import DemiurgeEnvironment
from memory import EvolutionaryMemory
from trainer import run_training_cluster, AdaptiveTransformer
from system_monitor import SystemMonitor
from janus_character import JanusRPGState
from world_events import interpret_metrics
import genesis_protocol

# Новые модули
from animus import JanusSoul
from swarm_optimizer import SwarmOptimizer
from bayes_optimizer import BayesianOptimizer
from meta_model import MetaModel
from subconscious import Chronos, Hypnos, Nebuchadnezzar, Ouroboros
from adaptive_test import adaptive_test
from tachyon_engine import TachyonEngine, TachyonRollout
from architect_ai import ArchitectureGenome
from species_engine import SpeciesEngine
from janus_genesis.social_learning import SocialLearningEngine

# Импорты MMO-мира
from janus_genesis import JanusWorld, JanusAgent, Inventory, Item, FactionSystem, Economy, RaidSystem
from janus_genesis.physarum_engine import PhysarumOptimizer
from janus_genesis.storyteller import Storyteller
from janus_genesis.meta_civilization_engine import MetaCivilizationEngine
from janus_genesis.religion_engine import ReligionEngine
from janus_genesis.tech_evolution import TechEvolutionEngine
from janus_genesis.war_empire_engine import WarEmpireEngine
from janus_genesis.environment import WeatherSystem
from janus_genesis.cultural_evolution import CulturalEvolutionEngine
from janus_genesis.economic_collapse import EconomicCollapseSimulator
from janus_genesis.legendary_leaders import LegendaryLeaderSystem
# VisionaryEngine отключён
# from janus_genesis.visionary import VisionaryEngine

# НОВЫЕ СИСТЕМЫ
from world_memory import WorldMemory
from meaning_engine import MeaningEngine
from meta_consciousness import MetaConsciousness
from conscious_agents import ConsciousAgent
from janus_self import JanusSelf
from divine_laws import DivineLaws
from janus_cognitive_voice import JanusCognitiveVoice
from janus_emotion import JanusEmotion
from janus_boot_message import BOOT_MESSAGE

# RL и СРЕДА
from janus_core.janus_core import JanusCore
from janus_environment import JanusEnvironment

# НОВЫЕ МОДУЛИ (самоэволюция, мета-цель, вера, культы)
from auto_evolution import AutoEvolution
from meta_goal_engine import MetaGoalEngine
from belief_system import BeliefSystem
from cult_engine import CultEngine

# Сенсорика, термальный контроль, iGPU, аудио, CPU оффлоад
try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("[⚠️] sounddevice не установлен. Звуковые метрики отключены. Установи: pip install sounddevice")

from igpu_offload import IGpuOffload
from cpu_offload import CPUOffload
import janus_db

# Модули Януса-Тахиона
from janus_genesis.tachyonic_monitor import TachyonicMonitor
from janus_genesis.pocket_detector import AbuserPocketDetector

# Модули полной интеграции
from janus_genesis.module_integrator import ModuleIntegrator
from janus_genesis.monkey_patcher import MonkeyPatcher
from janus_genesis.cultural_decadence import CulturalDecadenceEngine
from janus_genesis.language_model import LanguageEngine
from janus_genesis.market import Market as NewMarket
from janus_genesis.matrix_mod import MatrixEngine, MATRIX_MODE
from janus_genesis.tachyon_evolution import TachyonEvolutionEngine

# Конвергенция
from janus_core.convergence_engine import ConvergenceEngine, PartialSolutionMemory, Verifier, compression_score, SolutionField

# Термо-тахионный контроллер
from janus_core.thermal_tachyon_controller import ThermalTachyonController

# Physarum Graph Solver
from physarum_graph_solver import PhysarumGraphSolver

# ========== КОГНИТИВНЫЙ ЦИКЛ ==========
from janus_cognitive_loop import JanusCognitiveLoop
from self_model import SelfModel

# ==============================================================================
# ПУТИ
# ==============================================================================
HOMEOSTATIC_STATE_FILE = os.path.join(RAW_LOGS_DIR, "homeostatic_state.json")
DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
RPG_STATE_FILE = os.path.join(RAW_LOGS_DIR, "janus_world_state.json")
IGPU_MEMORY_FILE = os.path.join(RAW_LOGS_DIR, "igpu_memory.json")

GAMING_MODE = True

# Глобальные переменные для данных Android
android_mag = 0.0
android_loss = 0.0
android_entropy = 0.0
android_m2r = 0.0

# Глобальные переменные для звуковых метрик
audio_volume = 0.0
audio_spectrum = []

# ==============================================================================
# HRAIN ASYNC DAEMON
# ==============================================================================
class HRAINAsyncDaemon:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.loop.close()

    def send_event(self, event_data):
        async def _async_send():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post("http://localhost:1138/api/hrain/event", json=event_data, timeout=1) as resp:
                        pass
            except Exception as e:
                logger.error(f"HRAIN Net Error: {e}")
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_async_send(), self.loop)

    def stop(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread.is_alive():
            self.thread.join(timeout=3.0)

hrain_daemon = HRAINAsyncDaemon()

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs, pred_score=None, velocity=None, acceleration=None, purity_score=None):
    state = {
        'cycle': cycle,
        'last_score': last_score,
        'last_mi': last_mi,
        'best_score': best_score,
        'failed_configs': failed_configs,
        'pred_score': pred_score,
        'velocity': velocity,
        'acceleration': acceleration,
        'purity_score': purity_score,
    }
    with open(HOMEOSTATIC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_homeostatic_state():
    if os.path.exists(HOMEOSTATIC_STATE_FILE):
        with open(HOMEOSTATIC_STATE_FILE, 'r') as f:
            return json.load(f)
    return None

def is_valid_metrics(score, val_loss, div, mi, gn_mean):
    if score is None:
        return False
    for x in [val_loss, div, mi, gn_mean]:
        if x is None or np.isnan(x) or np.isinf(x):
            return False
    return True

def is_unstable(loss, gn_max, gn_mean, val_loss):
    """Определяет, находится ли система в опасной зоне."""
    return (np.isnan(loss) or np.isinf(loss) or
            np.isnan(val_loss) or np.isinf(val_loss) or
            gn_max == float('inf') or gn_mean == float('inf') or
            gn_max > 100)  # порог для градиентов

class TachyonField:
    def __init__(self, lead_factor=1.8):
        self.prev_score = None
        self.prev_prev_score = None
        self.prev_mi = None
        self.lead = lead_factor

    def step(self, score, mi):
        if self.prev_score is None:
            self.prev_score = score
            self.prev_prev_score = score
            self.prev_mi = mi
            return score, mi, 0.0, 0.0
        velocity = score - self.prev_score
        acceleration = score - 2 * self.prev_score + self.prev_prev_score
        predicted_score = score + velocity * self.lead + 0.5 * acceleration
        predicted_mi = mi + (mi - self.prev_mi) * self.lead
        self.prev_prev_score = self.prev_score
        self.prev_score = score
        self.prev_mi = mi
        return predicted_score, predicted_mi, velocity, acceleration

class SymbiosisController:
    def __init__(self):
        self.base_batch = BASE_BATCH_SIZE

    def adapt(self, gpu_load, cpu_load, gpu_temp, igpu_load=0.0, cache_ratio=1.0, gaming_mode=False):
        if gaming_mode:
            return max(8, self.base_batch // 4), 3.0
        if gpu_load < 30 and gpu_temp < 65 and igpu_load < 50 and cache_ratio < 1.1:
            return self.base_batch, 0.0
        stress_factor = max(gpu_load / 100.0, cpu_load / 100.0, (gpu_temp - 50) / 40.0)
        if igpu_load > 50:
            stress_factor = max(stress_factor, igpu_load / 100.0)
        if cache_ratio > 1.2:
            stress_factor = min(1.0, stress_factor * cache_ratio)
        stress_factor = min(1.0, stress_factor)
        current_batch = max(8, int(self.base_batch * (1.0 - stress_factor)))
        current_batch = 2 ** max(3, int(np.log2(current_batch)))
        current_pause = stress_factor * 2.5
        return current_batch, current_pause

# ==============================================================================
# AUDIO MONITOR
# ==============================================================================
class AudioMonitor:
    def __init__(self, sample_rate=44100, duration=0.1):
        self.sample_rate = sample_rate
        self.duration = duration
        self.available = AUDIO_AVAILABLE
        if self.available:
            try:
                sd.check_input_settings()
                logger.info("🎤 AudioMonitor инициализирован")
            except:
                self.available = False
                logger.warning("🎤 Микрофон не доступен. Звуковые метрики отключены.")

    def get_metrics(self):
        if not self.available:
            return 0.0, [0.0]*10
        try:
            recording = sd.rec(int(self.sample_rate * self.duration),
                               samplerate=self.sample_rate,
                               channels=1, dtype='float32')
            sd.wait()
            volume = np.sqrt(np.mean(recording**2))
            fft = np.abs(np.fft.rfft(recording[:, 0]))
            freqs = np.fft.rfftfreq(len(recording), 1/self.sample_rate)
            bands = np.logspace(np.log10(20), np.log10(self.sample_rate/2), 11)
            spectrum = []
            for i in range(10):
                mask = (freqs >= bands[i]) & (freqs < bands[i+1])
                if np.any(mask):
                    spectrum.append(float(np.mean(fft[mask])))
                else:
                    spectrum.append(0.0)
            max_val = max(spectrum) if max(spectrum) > 0 else 1
            spectrum = [s / max_val for s in spectrum]
            return float(volume), spectrum
        except Exception as e:
            logger.debug(f"Ошибка сбора звука: {e}")
            return 0.0, [0.0]*10

audio_monitor = AudioMonitor()

# ==============================================================================
# ОПРЕДЕЛЕНИЕ АКТИВНОСТИ ПОЛЬЗОВАТЕЛЯ (улучшена обработка ошибок)
# ==============================================================================
def is_user_active(device_data_file, idle_threshold=60):
    if not os.path.exists(device_data_file):
        return True
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            if os.path.getsize(device_data_file) == 0:
                if attempt < max_attempts - 1:
                    time.sleep(0.1)
                    continue
                else:
                    return True
            with open(device_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            break
        except (json.JSONDecodeError, PermissionError) as e:
            logger.warning(f"Не удалось прочитать {device_data_file}: {e}. Удаляем повреждённый файл и считаем пользователя активным.")
            try:
                os.remove(device_data_file)
            except:
                pass
            return True
        except Exception as e:
            logger.error(f"Ошибка чтения {device_data_file}: {e}")
            return True
    if isinstance(data, list) and data:
        for record in reversed(data):
            d = record.get('data', {})
            if 'mouse' in d or 'keyboard' in d:
                ts = record.get('timestamp', 0)
                if isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts)
                        ts = dt.timestamp()
                    except:
                        continue
                if time.time() - ts < idle_threshold:
                    return True
                else:
                    return False
    return True

# ==============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С СОСТОЯНИЕМ МОДЕЛИ (ИСПРАВЛЕННЫЕ)
# ==============================================================================
def save_model_state(model, config, optimizer=None):
    """Сохраняет состояние модели (и оптимизатора) вместе с конфигурацией."""
    state = {
        'config': config.copy(),                    # сохраняем конфигурацию
        'model': copy.deepcopy(model.state_dict())
    }
    if optimizer is not None:
        state['optimizer'] = copy.deepcopy(optimizer.state_dict())
    return state

def restore_model_state(state, optimizer=None, device=DEVICE):
    """
    Восстанавливает модель из сохранённого состояния.
    Возвращает восстановленную модель.
    """
    config = state['config']
    model = AdaptiveTransformer(
        config['n_embd'],
        config['n_head'],
        config['n_layer']
    ).to(device)
    model.load_state_dict(state['model'])
    if optimizer is not None and 'optimizer' in state:
        optimizer.load_state_dict(state['optimizer'])
    return model

# ==============================================================================
# ОСНОВНОЙ ЦИКЛ
# ==============================================================================
async def run_demiurge_loop():
    global android_mag, android_loss, android_entropy, android_m2r, audio_volume, audio_spectrum

    logger.info("=" * 70)
    logger.info("JANUS DEMIURGE CORE v7.2 — МЕТА-РЕЖИМ ЯНУСА С ИНСТИНКТАМИ")
    logger.info("=" * 70)

    janus_db.init_db()

    rpg_state = JanusRPGState()
    if os.path.exists(RPG_STATE_FILE):
        try:
            with open(RPG_STATE_FILE, 'r', encoding='utf-8') as f:
                rpg_state.load(json.load(f))
            logger.info(f"🎮 Мир Genesis загружен. Уровень {rpg_state.level}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка загрузки мира: {e}")

    monitor = SystemMonitor(poll_interval=120.0, top_n=5, screen_interval=1.0)

    animus = JanusSoul(monitor, wormhole_dir=WORMHOLE_DIR) if os.path.exists(os.path.join(WORMHOLE_DIR, "kenshi_feelings.json")) else None
    if animus:
        logger.info("🤖 Анимус (душа) пробудилась и готова сопереживать")

    swarm = SwarmOptimizer(
        n_particles=SWARM_SIZE,
        inertia=SWARM_INERTIA,
        cognitive=SWARM_COGNITIVE,
        social=SWARM_SOCIAL
    ) if SWARM_ENABLED else None

    bayes = BayesianOptimizer(
        n_initial_points=BAYES_INIT_POINTS,
        acq_func=BAYES_ACQ_FUNC
    ) if BAYES_ENABLED else None

    meta = MetaModel(max_samples=META_SAMPLE_SIZE) if META_ENABLED else None

    old_tachyon = TachyonEngine()

    species_engine = SpeciesEngine()
    if not species_engine.species_list:
        species_engine.create_species("Transformers", "transformer")
        species_engine.create_species("Wide", "wide_transformer")
        species_engine.create_species("Deep", "deep_transformer")

    registry_path = os.path.join(RAW_LOGS_DIR, "janus_nuclear_emulation_v2.0.json")
    registry_params = None
    if os.path.exists(registry_path):
        with open(registry_path, 'r', encoding='utf-8') as f:
            reg_data = json.load(f)
            registry_params = reg_data.get('emulation_parameters', None)
            logger.info("✅ Ядерный реестр загружен.")

    env = DemiurgeEnvironment(registry_params=registry_params)
    memory = EvolutionaryMemory(registry_path=registry_path)

    igpu_offload = IGpuOffload(core_env=env, memory_path=IGPU_MEMORY_FILE)
    cpu_offload = CPUOffload(cache_probe=monitor.cache_probe)

    world = JanusWorld(real_economy=None, hrain_daemon=hrain_daemon)

    world.memory = WorldMemory()
    world.meaning = MeaningEngine(world)
    world.meta = MetaConsciousness(world)

    world.janus_self = JanusSelf()
    world.laws = DivineLaws(world)

    # ========== ОБРАБОТЧИК НАГРАД ==========
    class RewardHandler:
        def __init__(self, rpg_state):
            self.rpg_state = rpg_state

        def on_raid_win(self, agents, boss_name):
            self.rpg_state.exp += 50
            self.rpg_state.gold += 200
            logger.info(f"🎉 Победа над {boss_name}! +50 XP, +200 золота.")

        def on_institution_founded(self, institution, founder):
            self.rpg_state.exp += 30
            self.rpg_state.mana = min(self.rpg_state.max_mana, self.rpg_state.mana + 10)
            logger.info(f"🏛️ Основан институт {institution.name}! +30 XP, +10 маны.")

        def on_tech_discovered(self, technology, discoverer):
            self.rpg_state.exp += 20
            logger.info(f"🔬 Открыта технология {technology.name}! +20 XP.")

        def on_religion_spread(self, religion, new_followers):
            gain = len(new_followers) * 5
            self.rpg_state.exp += gain
            self.rpg_state.mana = min(self.rpg_state.max_mana, self.rpg_state.mana + gain)
            logger.info(f"🛐 Религия {religion.name} распространилась на {len(new_followers)} агентов! +{gain} XP, +{gain} маны.")

        def on_religion_founded(self, religion, founder):
            self.rpg_state.exp += 100
            self.rpg_state.gold += 200
            logger.info(f"🛐 Основана новая религия: {religion.name}! +100 XP, +200 золота.")

        def on_religion_died(self, religion):
            self.rpg_state.exp = max(0, self.rpg_state.exp - 50)
            logger.warning(f"💀 Религия {religion.name} вымерла. -50 XP.")

        def on_trade(self, buyer, seller, item, price):
            self.rpg_state.gold += int(price * 0.05)
            logger.info(f"💰 Торговля принесла {int(price*0.05)} золота.")

        def on_craft(self, agent, item):
            if hasattr(item, 'rarity') and item.rarity in ('epic', 'legendary'):
                self.rpg_state.exp += 25
                logger.info(f"🔨 Создан {item.name}! +25 XP.")

    reward_handler = RewardHandler(rpg_state)
    world.event_bus.subscribe("raid_win", reward_handler.on_raid_win)
    world.event_bus.subscribe("institution_founded", reward_handler.on_institution_founded)
    world.event_bus.subscribe("tech_discovered", reward_handler.on_tech_discovered)
    world.event_bus.subscribe("religion_spread", reward_handler.on_religion_spread)
    world.event_bus.subscribe("religion_founded", reward_handler.on_religion_founded)
    world.event_bus.subscribe("religion_died", reward_handler.on_religion_died)
    world.event_bus.subscribe("trade", reward_handler.on_trade)
    world.event_bus.subscribe("craft", reward_handler.on_craft)

    env_world = JanusEnvironment()

    auto_evo = AutoEvolution()
    meta_goal = MetaGoalEngine()
    belief_system = BeliefSystem()
    cult_engine = CultEngine()

    tachyon = TachyonRollout(env_world, depth=4, simulations=8)
    core_rl = JanusCore(tachyon=old_tachyon, meta_goal=meta_goal)

    if not rpg_state.self_model["aware"]:
        rpg_state.awaken()

    physarum = PhysarumOptimizer(memory, n_particles=50, width=100, height=100)
    social_engine = SocialLearningEngine(tachyon=old_tachyon, evolutionary_memory=memory)

    language_engine = LanguageEngine(
        vocab_file=os.path.join(RAW_LOGS_DIR, "vocab.json"),
        mode='char',
        n_layer=1, n_embd=32, block_size=32, n_head=4
    )
    logger.info("📖 Языковой движок инициализирован")

    stories_file = os.path.join(RAW_LOGS_DIR, "stories.json")
    storyteller = Storyteller(stories_file=stories_file, social_engine=social_engine)
    logger.info("📖 Сказитель инициализирован")

    # VisionaryEngine отключён
    visionary = None
    logger.info("🔮 Visionary Engine отключён (экономия ресурсов).")

    market = NewMarket(
        world=world,
        save_file=os.path.join(RAW_LOGS_DIR, "market_listings.json"),
        social_engine=social_engine,
        visionary=visionary,
        language_engine=language_engine
    )
    world.market = market
    logger.info("🏪 Новый рынок (v2.0) интегрирован")

    meta_engine = MetaCivilizationEngine(world, world.event_bus)

    thermal = ThermalTachyonController(config={
        'target_temp': 55,
        'max_temp': 80,
        'explore_threshold': 65,
        'freeze_threshold': 50,
        'contract_threshold': 40,
        'stability_high': 0.85,
        'stability_low': 0.6,
        'cold_memory_size': 20,
        'revert_threshold': 0.9,
        'm2r_window': 20
    })
    logger.info("🌡️ ThermalTachyonController запущен")

    if SUBCONSCIOUS_ENABLED:
        class EngineStub:
            def __init__(self, memory):
                self.memory = memory
        engine_stub = EngineStub(memory)
        chronos = Chronos(db_path=os.path.join(RAW_LOGS_DIR, "janus.db"),
                          backup_dir=os.path.join(RAW_LOGS_DIR, "backups"))
        hypnos = Hypnos(engine=engine_stub)
        nebuchad = Nebuchadnezzar(engine=None)
        ouro = None
    else:
        chronos = hypnos = nebuchad = ouro = None
        engine_stub = None

    tachyon_field = TachyonField(lead_factor=1.8)
    symbiote = SymbiosisController()

    tachyonic_monitor = TachyonicMonitor(threshold_hits=10)
    pocket_detector = AbuserPocketDetector(window=20, std_threshold=0.01)

    integrator = ModuleIntegrator(
        root_dir=os.path.join(os.path.dirname(__file__), "janus_genesis"),
        core=core_rl,
        world=world,
        memory=memory,
        social_engine=social_engine,
        language_engine=language_engine,
        storyteller=storyteller,
        visionary=visionary,
        exclude_classes=[
            'NeedsSystem', 'PartySystem', 'BuffSystem', 'DiseaseSystem',
            'EconomicCollapseSimulator', 'ReligionEngine', 'TechEvolutionEngine',
            'WarEmpireEngine', 'Religion', 'BaseModule', 'ModuleIntegrator', 'MonkeyPatcher'
        ]
    )
    integrator.init_modules()
    logger.info("🔌 Модульный интегратор запущен")

    patcher = MonkeyPatcher(integrator, world, memory)
    logger.info("🐒 Манки-патчер готов")

    cultural_decadence = CulturalDecadenceEngine(world, memory, social_engine, language_engine)
    logger.info("📉 Движок культурного декаданса активирован")

    matrix_engine = MatrixEngine(game_detector=monitor, tachyon=old_tachyon)
    if MATRIX_MODE:
        matrix_engine.start()
        logger.info("🎮 Matrix Engine запущен. Добро пожаловать в Матрицу.")
    else:
        logger.info("🎮 Matrix Engine отключён (MATRIX_MODE = False)")

    tachyon_evolution = TachyonEvolutionEngine(world)
    logger.info("⚡ Tachyon Evolution Engine готов")

    if CONVERGENCE_ENABLED:
        convergence = ConvergenceEngine(window=CONVERGENCE_WINDOW)
        partial_memory = PartialSolutionMemory(max_size=200)
        verifier = Verifier()
        solution_field = SolutionField()
        logger.info("📈 Convergence Engine запущен")
    else:
        convergence = None
        partial_memory = None
        verifier = None
        solution_field = None
    state = load_homeostatic_state()
    if state:
        cycle = state['cycle']
        last_score = state['last_score']
        last_mi = state['last_mi']
        best_score = state['best_score']
        failed_configs = state.get('failed_configs', [])
        pred_score = state.get('pred_score')
        velocity = state.get('velocity')
        acceleration = state.get('acceleration')
        purity_score_from_state = state.get('purity_score', 0.0)
        logger.info(f"🔄 Восстановлено: цикл {cycle}, best_score {best_score:.4f}, failed_configs {len(failed_configs)}, purity_score {purity_score_from_state:.4f}")
    else:
        cycle = 0
        last_score = None
        last_mi = None
        best_score = -float('inf')
        failed_configs = []
        pred_score = velocity = acceleration = None
        purity_score_from_state = 0.0
    best_cycle = 0

    # === НОВЫЕ ПЕРЕМЕННЫЕ ===
    best_fitness = -float('inf')          # лучший fitness за всё время
    cold_states = []                       # банк холодных состояний (до 5) – храним (fitness, state_dict, genome, temp)
    genome = {                             # генетическая память
        'lr': BASE_BATCH_SIZE,
        'mutation_rate': 0.2,
        'entropy_bias': 0.0
    }
    fitness_history = deque(maxlen=100)    # история fitness для анализа трендов
    self_model = None                      # self-model будет создана позже
    self_optim = None

    fail_streak = 0
    last_genesis_time = time.time() - GENESIS_AUTO_INTERVAL
    last_meta_train = 0
    last_chronos = 0
    last_hypnos = 0
    last_nebuchad = 0
    last_ouro = 0
    META_UPDATE_INTERVAL = 50

    test_threshold = 20.0
    test_threshold_history = []
    active_tasks = []
    game_skip_counter = 0
    step_t = None

    prev_loss = None
    score_history = deque(maxlen=100)

    # Инициализация Physarum Graph Solver (будет позже, после создания модели)
    physarum_solver = None

    # Когнитивный цикл
    cognitive_loop = None

    # === ПЕРЕМЕННЫЕ ДЛЯ АНТИКОЛЛАПСНОЙ СИСТЕМЫ ===
    last_good_state = None          # state_dict стабильной модели
    last_good_genome = genome.copy()
    best_loss = float('inf')
    last_good_config = None

    # === МЕТА-РЕЖИМ ЯНУСА (расширенный) ===
    meta_state = {
        "mode": "EXPLORE",
        "mode_strength": 1.0,           # инерция режима (накапливается при длительном пребывании)
        "instability": 0.0,
        "last_loss": None,
        "loss_trend": 0.0,
        "nan_count": 0,
        "reward": 0.0,
        "mode_switch_counter": 0,
        "chaos_steps": 0,               # счётчик шагов в CHAOS (для ограничения)
        "hunger": 0.0,                  # голод (растёт при низкой награде)
        "best_snapshot": None,          # лучшее состояние модели (с конфигурацией)
        "best_score": -1e9
    }

    try:
        while True:
            logger.info(f"--- НАЧАЛО ЦИКЛА {cycle+1} ---")
            cycle += 1

            metrics = monitor.get_current_metrics()
            gpu_data = metrics.get('gpu', [{}])[0] if isinstance(metrics.get('gpu'), list) else {}
            gpu_load = gpu_data.get('gpu_util', 0.0)
            gpu_temp = gpu_data.get('temperature', 40.0)
            cpu_load = metrics.get('cpu', {}).get('percent_total', 0.0)
            cache_ratio = metrics.get('cache', {}).get('ratio', 1.0)
            igpu_load = metrics.get('igpu', {}).get('load', 0.0)
            top_processes = metrics.get('top_processes', [])
            gaming_mode = metrics.get('gaming_mode', False)
            game_name = metrics.get('game_name')
            game_cpu = metrics.get('game_cpu', 0.0)
            game_mem = metrics.get('game_mem', 0.0)
            game_gpu = metrics.get('game_gpu', 0.0)
            predicted = metrics.get('predicted', {})

            user_active = is_user_active(DEVICE_DATA_FILE, idle_threshold=60)

            audio_volume, audio_spectrum = audio_monitor.get_metrics()
            if audio_volume > 0.01:
                logger.info(f"[🔊] Громкость: {audio_volume:.3f}, спектр: {[round(s,2) for s in audio_spectrum[:3]]}...")

            active_tasks = [t for t in active_tasks if not t.done()]
            is_generating = len(active_tasks) > 0

            will_generate = False
            if (last_score is not None and best_score is not None and last_score > best_score * 0.95):
                will_generate = True
            elif random.random() < 0.1:
                will_generate = True

            batch_factor, parallel_factor, pause_factor = thermal.get_factors(metrics)

            base_batch, base_pause = symbiote.adapt(gpu_load, cpu_load, gpu_temp, igpu_load, cache_ratio, gaming_mode)
            batch_size = max(8, int(base_batch * batch_factor))
            pause = base_pause * pause_factor
            seeds_this_cycle = max(1, int(SEEDS_PER_CYCLE * parallel_factor))

            if not user_active:
                logger.info("💤 Пользователь отошёл – тихий режим (но с повышенной активностью).")
            if gpu_temp > thermal.max_temp:
                logger.info(f"🌡️ Температура GPU {gpu_temp:.0f}°C – аварийное снижение нагрузки.")
            if top_processes:
                display_procs = []
                for p in top_processes[:3]:
                    name = p['name']
                    cpu = p.get('cpu_percent_norm', p.get('cpu_percent', 0))
                    if name == 'System Idle Process':
                        display_procs.append((f"IDLE", cpu))
                    else:
                        display_procs.append((name, cpu))
                logger.info(f"📊 Топ процессов: {display_procs}")

            if gaming_mode:
                logger.info(f"🎮 ИГРА: {game_name} (CPU: {game_cpu:.1f}%, GPU: {game_gpu:.1f}%, Mem: {game_mem:.1f}%) – нагрузка минимальна")
                if predicted:
                    logger.info(f"🔮 Прогноз: GPU={predicted.get('gpu_load',0):.1f}%, CPU={predicted.get('cpu_load',0):.1f}%, gaming={predicted.get('gaming_mode',False)}")

            if gaming_mode and user_active:
                game_skip_counter += 1
                logger.info(f"⏸️ Пропускаем цикл {cycle} из-за игры. Счётчик пропусков: {game_skip_counter}")
                if game_skip_counter > 10:
                    logger.info("😴 Игра затянулась – уходим в глубокий сон на 60 сек")
                    await asyncio.sleep(60)
                    game_skip_counter = 0
                else:
                    await asyncio.sleep(max(pause, 2.0))
                continue
            else:
                game_skip_counter = 0

            mood = animus.get_mood() if animus else {'empathy':0.5, 'stress':0.5, 'inspiration':0.5}
            if animus and mood['stress'] > 0.8:
                logger.info(f"     [😰] Янус чувствует сильный стресс ({mood['stress']:.2f})")
            elif animus and mood['empathy'] > 0.7:
                logger.info(f"     [🤗] Янус полон эмпатии ({mood['empathy']:.2f})")

            # ========== ИНТЕГРАЦИЯ ДАННЫХ ОТ ANDROID (исправлено с retry) ==========
            if os.path.exists(DEVICE_DATA_FILE):
                max_attempts = 3
                all_dev_data = None
                for attempt in range(max_attempts):
                    try:
                        if os.path.getsize(DEVICE_DATA_FILE) == 0:
                            if attempt < max_attempts - 1:
                                time.sleep(0.1)
                                continue
                            else:
                                logger.debug("Файл device_data.json пуст, пропускаем Android-данные")
                                break
                        with open(DEVICE_DATA_FILE, 'r', encoding='utf-8') as f:
                            all_dev_data = json.load(f)
                        break
                    except (json.JSONDecodeError, PermissionError) as e:
                        logger.warning(f"Не удалось прочитать Android-данные из {DEVICE_DATA_FILE} (попытка {attempt+1}): {e}. Удаляем повреждённый файл.")
                        try:
                            os.remove(DEVICE_DATA_FILE)
                        except:
                            pass
                        break
                    except Exception as e:
                        logger.error(f"Ошибка при чтении Android-данных: {e}")
                        break
                if isinstance(all_dev_data, list):
                    android_records = [r for r in all_dev_data if isinstance(r, dict) and r.get('device_id', '').lower().startswith('android')]
                    if android_records:
                        last_android = android_records[-1]
                        adata = last_android.get('data', {})
                        if isinstance(adata, dict):
                            mx = adata.get('mag_x', 0.0); my = adata.get('mag_y', 0.0); mz = adata.get('mag_z', 0.0)
                            android_mag = np.sqrt(mx*mx + my*my + mz*mz)
                            android_loss = adata.get('loss', 0.0)
                            android_entropy = adata.get('entropy', 0.0)
                            android_m2r = adata.get('m2r', 0.0)
                            logger.info(f"[📱] Android: mag={android_mag:.2f}, loss={android_loss:.4f}, entropy={android_entropy:.2f}")

            keyboard = metrics.get('keyboard', {})
            if keyboard:
                logger.info(f"[⌨️] Клавиатура: нажатий/с={keyboard.get('keys_per_sec',0):.2f}")
            mouse = metrics.get('mouse', {})
            if mouse:
                logger.info(f"[🖱️] Мышь: клики/с={mouse.get('clicks_per_sec',0):.2f} | движ/с={mouse.get('move_distance_per_sec',0):.0f}")
            screen = metrics.get('screen', {})
            if screen:
                logger.info(f"[🖥️] Экран: ярк={screen.get('brightness',0):.2f}, движ={screen.get('motion',0):.2f}, энтр={screen.get('entropy',0):.2f}")

            audio_devices_info = metrics.get('audio_devices', {'devices': [], 'changes': []})
            audio_devices_list = audio_devices_info.get('devices', [])
            audio_changes = audio_devices_info.get('changes', [])
            active_inputs = sum(1 for d in audio_devices_list if d['type'] == 'input' and d.get('is_enabled', False))
            active_outputs = sum(1 for d in audio_devices_list if d['type'] == 'output' and d.get('is_enabled', False))
            output_volumes = [d['volume'] for d in audio_devices_list if d['type'] == 'output' and d.get('volume') is not None]
            avg_output_volume = np.mean(output_volumes) if output_volumes else 0.0
            if audio_changes:
                logger.debug(f"Аудиоизменения: {len(audio_changes)} событий")

            # ========== УДАЛЕНА ЗАПИСЬ PC-ДАННЫХ В device_data.json ==========
            # PC-данные не пишем в device_data.json, чтобы не создавать гонок.

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            flat_metrics = {
                'gpu_load': gpu_load, 'gpu_temp': gpu_temp, 'cpu_load': cpu_load, 'cache_ratio': cache_ratio,
                'igpu_load': igpu_load, 'android_mag': android_mag, 'android_loss': android_loss,
                'android_entropy': android_entropy, 'android_m2r': android_m2r, 'audio_volume': audio_volume,
                'audio_spectrum': audio_spectrum, 'user_active': user_active, 'top_processes': top_processes,
                'audio_active_inputs': active_inputs, 'audio_active_outputs': active_outputs,
                'audio_avg_output_volume': avg_output_volume, 'audio_device_changes_count': len(audio_changes),
                'gaming_mode': gaming_mode, 'game_name': game_name, 'game_cpu': game_cpu, 'game_mem': game_mem, 'game_gpu': game_gpu,
                'predicted_gpu_load': predicted.get('gpu_load'), 'predicted_cpu_load': predicted.get('cpu_load'), 'predicted_gaming_mode': predicted.get('gaming_mode'),
                'timestamp': datetime.now().isoformat()
            }

            janus_db.insert_system_metrics(flat_metrics)

            meta_goal.update(rpg_state, world.memory)

            candidates = []

            tachyon_config = None
            step_for_pred = step_t if step_t is not None else None
            use_mi = (random.random() < 0.3) and old_tachyon.trained_mi
            tachyon_config = old_tachyon.propose_future(memory, samples=10, step_time=step_for_pred, use_mi=use_mi)
            if tachyon_config:
                candidates.append((tachyon_config, 'tachyon', None))
                logger.info(f"⚡ Tachyon предложил конфигурацию (режим {'MI' if use_mi else 'score'})")

            if random.random() < 0.2:
                thermal_eff = thermal.get_thermal_eff(metrics)
                physarum_config = physarum.propose(memory, thermal_eff=thermal_eff)
                if physarum_config:
                    candidates.append((physarum_config, 'physarum', None))
                    logger.info("🦠 Physarum предложил перспективную конфигурацию")

            best_social = social_engine.get_best_recent(1)
            if best_social:
                candidates.append((best_social[0], 'social', None))
                logger.info("👥 Социальное обучение предложило конфигурацию")

            if swarm:
                mood_swarm = {
                    'inertia_factor': 1.0 - mood['stress'] * 0.3,
                    'cognitive_factor': 1.0 + mood['inspiration'] * 0.2,
                    'social_factor': 1.0 + mood['empathy'] * 0.2
                }
                for _ in range(2):
                    cand, idx = swarm.ask(mood_swarm)
                    candidates.append((cand, 'swarm', idx))

            if bayes:
                mood_acq = 'EI' if mood['inspiration'] > 0.6 else 'LCB'
                cand = bayes.ask_tachyonic(mood_acq)
                candidates.append((cand, 'bayes', None))

            if not candidates:
                for attempt in range(5):
                    result = memory.propose(current_metrics=flat_metrics)
                    if result is None:
                        continue
                    cand, mutated, miracle = result
                    if cand is not None:
                        candidates.append((cand, 'memory', None))
                        break
                if not candidates:
                    cand = memory._random_config()
                    candidates.append((cand, 'random', None))

            if meta and meta.is_trained:
                candidate_data = [{**c[0], **flat_metrics} for c in candidates]
                scores = meta.predict(candidate_data)
                median_score = np.median(scores) if scores else -float('inf')
                candidates = [c for c, s in zip(candidates, scores) if s >= median_score]

            config, source, swarm_idx = random.choice(candidates) if candidates else (memory._random_config(), 'fallback', None)

            attempts = 0
            while config in failed_configs and attempts < 10:
                config, source, swarm_idx = random.choice(candidates) if candidates else (memory._random_config(), 'fallback', None)
                attempts += 1

            if convergence and solution_field:
                best_global = solution_field.best()
                if best_global is not None and isinstance(best_global, dict) and random.random() < 0.1:
                    config = best_global.copy()
                    source = 'solution_field'
                    logger.info("🌌 Используем глобальное решение из Solution Field")

            config = config.copy()
            config['batch_size'] = batch_size
            config['half_life_steps'] = HALF_LIFE_STEPS
            config['lr_decay_enable'] = LR_DECAY_ENABLE

            if FILTER_37_ENABLED:
                config['resonance_weight'] = filter_hyperparams(config)

            # ========== ПРЕДИКТИВНЫЙ ВЫБОР РЕЖИМА (через self-model) ==========
            # Если self_model уже обучен, предсказываем, какой режим даст лучший reward
            if self_model is not None and hasattr(self_model, 'predict') and len(fitness_history) > 20:
                modes_to_try = ["EXPLORE", "EXPLOIT", "SURVIVE", "CHAOS", "HUNT"]
                best_mode = None
                best_score_pred = -1e9
                for m in modes_to_try:
                    # Кодируем текущее состояние + режим в вектор
                    features = [
                        meta_state["instability"],
                        meta_state["loss_trend"],
                        meta_state["reward"],
                        meta_state["hunger"],
                        1.0 if m == "EXPLORE" else 0.0,
                        1.0 if m == "EXPLOIT" else 0.0,
                        1.0 if m == "SURVIVE" else 0.0,
                        1.0 if m == "CHAOS" else 0.0,
                        1.0 if m == "HUNT" else 0.0,
                        meta_state["mode_strength"],
                        len(score_history) / 100.0
                    ]
                    features_tensor = torch.tensor(features, device=DEVICE).float().unsqueeze(0)
                    pred = self_model(features_tensor).item()
                    if pred > best_score_pred:
                        best_score_pred = pred
                        best_mode = m
                if best_mode is not None and random.random() < 0.5:
                    meta_state["mode"] = best_mode
                    logger.info(f"🧠 ПРЕДИКТИВНЫЙ ВЫБОР РЕЖИМА: {best_mode} (score={best_score_pred:.3f})")

            # === ИСПРАВЛЕНИЕ: автоматическое переключение в HUNT при наличии NP-задачи ===
            np_task_present = (rpg_state.current_np_task is not None) or (hasattr(rpg_state, 'np_series') and len(rpg_state.np_series) > 0)
            if np_task_present and meta_state["mode"] != "SURVIVE":
                meta_state["mode"] = "HUNT"
                meta_state["mode_strength"] = 1.0
                logger.info("🔥 Активирован режим HUNT (обнаружена NP-задача)")

            # === ПРИМЕНЯЕМ ТЕКУЩИЙ РЕЖИМ К ПАРАМЕТРАМ ===
            mode = meta_state["mode"]
            strength = meta_state["mode_strength"]

            if mode == "EXPLORE":
                config['gain'] = min(5.0, config.get('gain', 1.0) * (1.0 + 0.1 * strength))
                config['temperature'] = min(5.0, config.get('temperature', 1.0) * (1.0 + 0.1 * strength))
                config['lr'] = min(0.01, config.get('lr', 1e-3) * (1.0 + 0.1 * strength))
                genome['mutation_rate'] = min(0.5, genome.get('mutation_rate', 0.2) * (1.0 + 0.2 * strength))
                memory.strategy["exploration"] = min(0.9, memory.strategy.get("exploration", 0.5) * (1.0 + 0.1 * strength))
            elif mode == "EXPLOIT":
                config['gain'] = max(0.5, config.get('gain', 1.0) * (1.0 - 0.05 * strength))
                config['temperature'] = max(0.5, config.get('temperature', 1.0) * (1.0 - 0.1 * strength))
                config['lr'] = max(1e-6, config.get('lr', 1e-3) * (1.0 - 0.05 * strength))
                genome['mutation_rate'] = max(0.05, genome.get('mutation_rate', 0.2) * (1.0 - 0.1 * strength))
                memory.strategy["exploration"] = max(0.1, memory.strategy.get("exploration", 0.5) * (1.0 - 0.1 * strength))
            elif mode == "CHAOS":
                # Хаотический режим: экстремальные мутации
                config['gain'] = min(10.0, config.get('gain', 1.0) * random.uniform(0.5, 2.5) * (1.0 + 0.2 * strength))
                config['temperature'] = min(10.0, config.get('temperature', 1.0) * random.uniform(0.5, 3.0) * (1.0 + 0.2 * strength))
                config['lr'] = min(0.05, config.get('lr', 1e-3) * random.uniform(0.2, 5.0) * (1.0 + 0.2 * strength))
                genome['mutation_rate'] = min(0.8, genome.get('mutation_rate', 0.2) * random.uniform(0.5, 2.0) * (1.0 + 0.2 * strength))
                memory.strategy["exploration"] = min(0.95, memory.strategy.get("exploration", 0.5) * random.uniform(0.8, 1.5) * (1.0 + 0.1 * strength))
                meta_state["chaos_steps"] += 1
                if meta_state["chaos_steps"] > 5:
                    logger.info("🌀 Выход из хаоса (лимит циклов)")
                    meta_state["mode"] = "SURVIVE"
                    mode = "SURVIVE"
            elif mode == "SURVIVE":
                # === ИСПРАВЛЕНИЕ: не опускаем gain/temperature ниже 0.8 ===
                config['gain'] = max(0.8, config.get('gain', 1.0) * (0.5 - 0.1 * strength))
                config['temperature'] = max(0.8, config.get('temperature', 1.0) * (0.5 - 0.1 * strength))
                config['lr'] = max(1e-7, config.get('lr', 1e-3) * (0.3 - 0.05 * strength))
                genome['mutation_rate'] = max(0.05, genome.get('mutation_rate', 0.2) * (0.3 - 0.05 * strength))
                memory.strategy["exploration"] = max(0.1, memory.strategy.get("exploration", 0.5) * (0.5 - 0.1 * strength))
            elif mode == "HUNT":
                # === НОВЫЙ РЕЖИМ: агрессивный поиск ===
                config['gain'] = min(5.0, config.get('gain', 1.0) * 1.5)
                config['temperature'] = min(5.0, config.get('temperature', 1.0) * 1.5)
                config['lr'] = min(0.01, config.get('lr', 1e-3) * 1.2)
                genome['mutation_rate'] = min(0.5, genome.get('mutation_rate', 0.2) * 1.5)
                memory.strategy["exploration"] = min(0.9, memory.strategy.get("exploration", 0.5) * 1.2)

            logger.info("Создание агента в мире...")
            if not isinstance(config, dict):
                logger.error(f"[ERROR] config has type {type(config).__name__}, expected dict. Using empty config.")
                config = {}
            base_agent = world.spawn_agent(config)

            if getattr(base_agent, 'arch_genome', None) is None:
                base_agent.arch_genome = ArchitectureGenome()
            mutated_genome = base_agent.arch_genome.mutate(mutation_rate=0.3, bonus=base_agent.mutation_bonus)
            base_agent.base_config = mutated_genome.apply_to_config(base_agent.base_config)
            base_agent._update_current_config()

            species_name = base_agent.arch_genome.arch_type + "_species"
            species_engine.assign_agent_to_species(base_agent, species_name)

            social_engine.assign_to_school(base_agent)

            agent = base_agent
            agent.brain = ConsciousAgent(agent)

            logger.info("Применение предметов к агенту...")
            agent.apply_items()
            config_to_train = agent.config

            logger.info("Генерация данных...")
            try:
                train_tensor_tmp = env.generate_tensors(TRAIN_SIZE)
                val_tensor_tmp = env.generate_tensors(VAL_SIZE)
                train_np = train_tensor_tmp.cpu().numpy()
                val_np = val_tensor_tmp.cpu().numpy()
                train_tensor = torch.from_numpy(train_np).long().to(DEVICE, non_blocking=True)
                val_tensor = torch.from_numpy(val_np).long().to(DEVICE, non_blocking=True)
                train_hash = hashlib.sha256(train_tensor.cpu().numpy().tobytes()).hexdigest()[:12]
                val_hash = hashlib.sha256(val_tensor.cpu().numpy().tobytes()).hexdigest()[:12]
            except Exception as e:
                logger.error(f"❌ Ошибка генерации данных: {e}")
                save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs, pred_score, velocity, acceleration, metrics.get('purity_score', 0.0))
                continue

            logger.info("Запуск run_training_cluster...")
            try:
                res = await asyncio.wait_for(
                    asyncio.to_thread(
                        run_training_cluster,
                        config_to_train, train_tensor, val_tensor, seeds_this_cycle, STEPS_PER_CYCLE,
                        batch_size, DEVICE
                    ),
                    timeout=600
                )
                logger.info("run_training_cluster завершён.")
            except asyncio.TimeoutError:
                logger.error("run_training_cluster превысил таймаут 600 секунд!")
                continue
            except Exception as e:
                logger.error(f"Ошибка в run_training_cluster: {e}")
                continue

            # ========== РАСПАКОВКА РЕЗУЛЬТАТА С МОДЕЛЬЮ ==========
            if len(res) == 15:  # новая версия
                success_count, score, val_loss, div, mi, train_loss_avg, gn_min, gn_max, gn_mean, w_norm, vram, step_t, model, best_state_dict, config = res
            else:  # старая версия для обратной совместимости
                success_count, score, val_loss, div, mi, train_loss_avg, gn_min, gn_max, gn_mean, w_norm, vram, step_t, best_state = res
                model = None
                best_state_dict = best_state

            # ========== ЗАЩИТА: при неудачном обучении обнуляем опасные переменные ==========
            if success_count == 0:
                config = None
                model = None
                best_state_dict = None

            do_detailed_log = success_count > 0

            # ========== МЕТА-СОСТОЯНИЕ: ОБНОВЛЕНИЕ МЕТРИК ==========
            # Вычисляем награду (упрощённо: изменение fitness)
            current_fitness = compute_fitness(
                loss=val_loss if success_count > 0 else float('inf'),
                thermal_metrics={'temp_f': metrics.get('temp_f', 100.0), 'hw_entropy': metrics.get('hw_entropy', 0.0)},
                np_solved=getattr(rpg_state, 'np_task_solved_this_cycle', False),
                entropy=metrics.get('hw_entropy', 0.0),
                mutation_rate=genome['mutation_rate'],
                energy_cost=(gpu_load/100.0 + cpu_load/100.0)/2.0 + 0.5,
                time_ms=step_t if step_t is not None else 0.0
            )
            reward = current_fitness - (meta_state.get('last_fitness', current_fitness))
            meta_state['last_fitness'] = current_fitness

            if success_count > 0:
                # Обновляем тренд loss
                if meta_state["last_loss"] is not None:
                    delta = val_loss - meta_state["last_loss"]
                    meta_state["loss_trend"] = 0.9 * meta_state["loss_trend"] + 0.1 * delta
                meta_state["last_loss"] = val_loss
                # Обновляем reward (экспоненциальное скользящее среднее)
                meta_state["reward"] = 0.9 * meta_state["reward"] + 0.1 * reward

                # Обновляем instability
                instability = 0.0
                # Проверяем на NaN/inf в градиентах
                if gn_max == float('inf') or gn_mean == float('inf'):
                    instability += 1.0
                    meta_state["nan_count"] += 1
                if abs(meta_state["loss_trend"]) > 1.0:
                    instability += 0.5
                if val_loss > 10.0:  # очень высокий loss
                    instability += 0.3
                meta_state["instability"] = min(1.0, instability)

                # Обновляем best_snapshot (лучшее состояние модели) – сохраняем конфигурацию
                if score > meta_state["best_score"]:
                    meta_state["best_score"] = score
                    if model is not None:
                        meta_state["best_snapshot"] = save_model_state(model, config_to_train)
            else:
                # Неудачное обучение
                meta_state["nan_count"] += 1
                meta_state["instability"] = min(1.0, meta_state["instability"] + 0.5)

            # Обновляем голод (hunger)
            meta_state["hunger"] += (0.5 - meta_state["reward"]) * 0.1
            meta_state["hunger"] = np.clip(meta_state["hunger"], 0.0, 2.0)

            # ========== ВЫБОР НОВОГО РЕЖИМА (на основе метрик и голода) ==========
            new_mode = None
            if meta_state["nan_count"] > 2:
                new_mode = "SURVIVE"
            elif meta_state["instability"] > 0.7:
                new_mode = "SURVIVE"
            elif meta_state["hunger"] > 1.2:
                new_mode = "CHAOS"           # голод толкает в хаос
            elif meta_state["reward"] > 0.5 and meta_state["loss_trend"] < 0:
                new_mode = "EXPLOIT"
            elif meta_state["reward"] < 0.2:
                new_mode = "EXPLORE"
            elif random.random() < 0.02 and meta_state["hunger"] > 0.5:
                new_mode = "CHAOS"            # редкий хаос, если немного голода

            # Если режим меняется, обновляем mode_strength (инерция)
            if new_mode is not None and new_mode != meta_state["mode"]:
                logger.info(f"🧠 СМЕНА РЕЖИМА: {meta_state['mode']} → {new_mode} (hunger={meta_state['hunger']:.2f}, reward={meta_state['reward']:.2f})")
                # При смене режима сила сбрасывается (сила накапливается при длительном пребывании)
                meta_state["mode_strength"] = 1.0
                meta_state["mode"] = new_mode
                meta_state["mode_switch_counter"] += 1
                if new_mode == "SURVIVE":
                    meta_state["nan_count"] = 0
                if new_mode == "CHAOS":
                    meta_state["chaos_steps"] = 0
            else:
                # Если режим не меняется, накапливаем силу (инерция)
                meta_state["mode_strength"] = min(3.0, meta_state["mode_strength"] + 0.2)

            # ========== АНТИКОЛЛАПС: обработка неудачного обучения ==========
            if success_count == 0:
                # Регистрируем плохую конфигурацию, если config не None
                if config is not None:
                    memory.register_lesson(config, penalty=True)
                    failed_configs.append(config)
                else:
                    logger.warning("Конфигурация None, пропускаем регистрацию урока.")

                # Откат к последнему стабильному состоянию (если есть)
                if last_good_state is not None and model is not None:
                    logger.info("🔄 Откат к предыдущему стабильному состоянию")
                    try:
                        if model is None:
                            model = AdaptiveTransformer(config_to_train['n_embd'], config_to_train['n_head'], config_to_train['n_layer']).to(DEVICE)
                        state_dict_device = {k: v.to(DEVICE) for k, v in last_good_state.items()}
                        model.load_state_dict(state_dict_device)
                    except Exception as e:
                        logger.error(f"Ошибка загрузки last_good_state: {e}")
                else:
                    logger.warning("Нет стабильного состояния для отката")

                # Обновляем геном из сохранённого
                genome = last_good_genome.copy()

                # Снижаем рискованные параметры
                genome['lr'] = max(1e-6, genome.get('lr', 1e-3) * 0.5)
                genome['mutation_rate'] = max(0.05, genome.get('mutation_rate', 0.2) * 0.8)

                # Увеличиваем exploration, чтобы избежать зацикливания
                memory.strategy["exploration"] = max(0.1, memory.strategy.get("exploration", 0.5) * 0.9)

                # Логируем событие
                hrain_daemon.send_event({"type": "collapse", "cycle": cycle, "config": config})
                if do_detailed_log:
                    logger.info("💥 КОЛЛАПС: применён откат, exploration снижен")

                # Сохраняем состояние гомеостаза
                save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs,
                                        pred_score, velocity, acceleration, metrics.get('purity_score', 0.0))
                with open(RPG_STATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(rpg_state.to_dict(), f, ensure_ascii=False, indent=2)

                await asyncio.sleep(max(pause, 2.0))
                continue  # пропускаем остальную обработку этого цикла

            # ========== Если обучение успешно, продолжаем ==========
            if do_detailed_log:
                logger.info("-" * 70)
                if pause > 0:
                    logger.info(f"▶️ CYCLE {cycle} | [🧠 СИМБИОЗ] Архитектор активен (GPU: {gpu_load:.0f}%, iGPU: {igpu_load:.0f}%, Cache Ratio: {cache_ratio:.2f})")
                    logger.info(f"   Batch: {batch_size}, Сидов: {seeds_this_cycle}, Пауза: {pause:.2f}с | Режим: {meta_state['mode']} (x{meta_state['mode_strength']:.2f})")
                else:
                    logger.info(f"▶️ CYCLE {cycle} | [🔥 ДОМИНАЦИЯ] Система свободна (GPU: {gpu_load:.0f}%, Cache Ratio: {cache_ratio:.2f}) | Режим: {meta_state['mode']} (x{meta_state['mode_strength']:.2f})")
                    logger.info(f"   Batch: {batch_size}, Сидов: {seeds_this_cycle}")
                logger.info("-" * 70)
                logger.info(f"⚙️ Архитектура: n_embd={config_to_train['n_embd']}, n_head={config_to_train['n_head']}, n_layer={config_to_train['n_layer']}")
                logger.info(f"⚙️ Параметры: lr={config_to_train['lr']:.6f}, gain={config_to_train['gain']:.3f}, temp={config_to_train['temperature']:.3f}")
                logger.info(f"🌍 Реальные данные: {train_tensor.shape} | Источники: unknown: 1")
                logger.info(f"🌍 Реальные данные: {val_tensor.shape} | Источники: unknown: 1")
                logger.info(f"🛡️ TrainHash={train_hash} | ValHash={val_hash}")

            # ========== СОЗДАНИЕ МОДЕЛИ (если не получена) ==========
            if model is None and best_state_dict is not None:
                model = AdaptiveTransformer(config_to_train['n_embd'], config_to_train['n_head'], config_to_train['n_layer']).to(DEVICE)
                model.load_state_dict(best_state_dict)

            # ========== ИНИЦИАЛИЗАЦИЯ PHYSARUM GRAPH SOLVER ==========
            if model is not None:
                if physarum_solver is None:
                    physarum_solver = PhysarumGraphSolver(model, {'n_nodes': config_to_train['n_embd']})
                else:
                    physarum_solver.model = model
                    physarum_solver._build_graph()
            else:
                logger.debug("Модель None, Physarum граф не обновлён")

            # ========== ИНИЦИАЛИЗАЦИЯ КОГНИТИВНОГО ЦИКЛА ==========
            if cognitive_loop is None:
                cognitive_loop = JanusCognitiveLoop()
                logger.info("🧠 Когнитивный цикл инициализирован")

            # ========== ВЫЧИСЛЕНИЕ FITNESS И ОБНОВЛЕНИЕ ПАМЯТИ ==========
            current_loss = val_loss
            if prev_loss is not None:
                loss_diff = prev_loss - current_loss
            else:
                loss_diff = 0.0
            prev_loss = current_loss
            metrics['loss_diff'] = loss_diff

            gap = train_loss_avg - val_loss
            pred_score, pred_mi, velocity, acceleration = tachyon_field.step(score, mi)

            score_history.append(score)

            # --- Собираем метрики для fitness ---
            thermal_metrics = {
                'temp_f': metrics.get('temp_f', 100.0),
                'hw_entropy': metrics.get('hw_entropy', 0.0)
            }
            entropy = thermal_metrics['hw_entropy']
            np_solved = getattr(rpg_state, 'np_task_solved_this_cycle', False)

            # Энергетическая стоимость: средняя загрузка GPU/CPU
            energy_cost = (gpu_load/100.0 + cpu_load/100.0) / 2.0 + 0.5  # базовое значение 0.5

            fitness = compute_fitness(
                loss=val_loss,
                thermal_metrics=thermal_metrics,
                np_solved=np_solved,
                entropy=entropy,
                mutation_rate=genome['mutation_rate'],
                energy_cost=energy_cost,
                time_ms=step_t if step_t is not None else 0.0
            )

            fitness_history.append(fitness)

            # Обновляем best_fitness
            if fitness > best_fitness:
                best_fitness = fitness
                best_config = config
                if model is not None:
                    best_state_dict = model.state_dict()
                logger.info(f"🏆 НОВЫЙ РЕКОРД FITNESS: {fitness:.4f} (loss={val_loss:.4f}, NP={np_solved}, temp={thermal_metrics.get('temp_f',0):.1f}F)")

            # --- Банк холодных состояний (храним state_dict, геном, temp) ---
            temp_f = thermal_metrics['temp_f']
            if temp_f < 110 and fitness > best_fitness * 0.8 and model is not None:
                state_copy = copy.deepcopy(model.state_dict())
                cold_states.append({
                    'fitness': fitness,
                    'state': state_copy,
                    'genome': genome.copy(),
                    'temp': temp_f
                })
                cold_states.sort(key=lambda x: x['fitness'], reverse=True)
                if len(cold_states) > 5:
                    cold_states = cold_states[:5]
                logger.debug(f"❄️ Сохранено холодное состояние: fitness={fitness:.3f}")

            # --- ТРЕНД FITNESS (для адаптации lr) ---
            if len(fitness_history) > 10:
                trend = fitness_history[-1] - fitness_history[-10]
                if trend > 0:
                    genome['lr'] = min(genome['lr'] * 1.02, 0.01)
                else:
                    genome['lr'] = max(genome['lr'] * 0.98, 1e-6)

            # --- НАПРАВЛЕННЫЙ МУТАЦИОННЫЙ ШУМ (с grad_like) ---
            entropy_noise = entropy
            if entropy_noise > 0.002 and model is not None:
                noise_scale = entropy_noise * 0.1
                with torch.no_grad():
                    for param in model.parameters():
                        grad_like = torch.sign(param)  # направление роста
                        noise = torch.randn_like(param) * noise_scale
                        param.add_(noise + 0.1 * grad_like * noise_scale)
                logger.info(f"🌀 Направленная мутация (scale={noise_scale:.4f})")

            # --- ГИБРИДНЫЙ TACHYON REVERT (динамический blend) ---
            if thermal.get_current_mode() == "CONTRACT" and best_state_dict is not None and model is not None:
                # Убеждаемся, что best_state_dict на том же устройстве, что и модель
                if best_state_dict is not None:
                    sample_tensor = next(iter(best_state_dict.values()))
                    if sample_tensor.device != DEVICE:
                        best_state_dict = {k: v.to(DEVICE) for k, v in best_state_dict.items()}
                best_model = AdaptiveTransformer(config['n_embd'], config['n_head'], config['n_layer']).to(DEVICE)
                best_model.load_state_dict(best_state_dict)
                delta = best_fitness - fitness
                blend = min(0.9, max(0.3, delta / (best_fitness + 1e-6)))
                with torch.no_grad():
                    for param, best_param in zip(model.parameters(), best_model.parameters()):
                        param.data = blend * best_param.data + (1 - blend) * param.data
                logger.info(f"🔄 Гибридный revert (blend={blend:.2f})")

            # --- КРИСТАЛЛИЗАЦИЯ (FREEZE) — фиксация сильных весов ---
            if thermal.get_current_mode() == "FREEZE" and model is not None:
                precision = 2 if temp_f < 90 else 3
                with torch.no_grad():
                    for param in model.parameters():
                        mask = torch.abs(param) > param.std()
                        param[mask] = torch.round(param[mask] * (10**precision)) / (10**precision)
                logger.info(f"❄️ Кристаллизация сильных весов (precision={precision})")

            # --- ИСПОЛЬЗОВАНИЕ ХОЛОДНЫХ СОСТОЯНИЙ ПРИ CONTRACT ---
            if thermal.get_current_mode() == "CONTRACT" and cold_states and model is not None:
                chosen = random.choice(cold_states)
                # Убеждаемся, что state на том же устройстве, что и модель
                state_dict = chosen['state']
                sample_tensor = next(iter(state_dict.values()))
                if sample_tensor.device != DEVICE:
                    state_dict = {k: v.to(DEVICE) for k, v in state_dict.items()}
                cold_model = AdaptiveTransformer(config['n_embd'], config['n_head'], config['n_layer']).to(DEVICE)
                cold_model.load_state_dict(state_dict)
                blend = 0.6
                with torch.no_grad():
                    for param, cold_param in zip(model.parameters(), cold_model.parameters()):
                        param.data = blend * cold_param.data + (1 - blend) * param.data
                # Обновляем геном из холодного состояния
                genome.update(chosen['genome'])
                logger.info("❄️ Использовано холодное состояние при CONTRACT (обновлён геном)")

            # --- ПРЕДСКАЗАНИЕ СЕБЯ (self-model) ---
            # === ИСПРАВЛЕНИЕ: создаём слой с правильной размерностью (11 признаков + 5 one-hot = 16) ===
            if self_model is None:
                self_model = torch.nn.Linear(16, 1).to(DEVICE)
                self_optim = torch.optim.Adam(self_model.parameters(), lr=0.001)
            # Формируем признаки: 11 числовых + 5 one-hot режимов
            mode_onehot = [0.0]*5
            if meta_state["mode"] == "EXPLORE":
                mode_onehot[0] = 1.0
            elif meta_state["mode"] == "EXPLOIT":
                mode_onehot[1] = 1.0
            elif meta_state["mode"] == "SURVIVE":
                mode_onehot[2] = 1.0
            elif meta_state["mode"] == "CHAOS":
                mode_onehot[3] = 1.0
            elif meta_state["mode"] == "HUNT":
                mode_onehot[4] = 1.0
            features = torch.tensor([
                val_loss,
                thermal_metrics.get('temp_f', 100.0)/200.0,
                entropy,
                float(np_solved),
                gpu_load/100.0,
                cpu_load/100.0,
                genome['lr'],
                genome['mutation_rate'],
                len(score_history)/100.0,
                fitness_history[-1] if fitness_history else 0.0,
                meta_state["mode_strength"]
            ] + mode_onehot, device=DEVICE).float().unsqueeze(0)

            pred_fitness = self_model(features).item()
            pred_error = abs(pred_fitness - fitness)

            # Обучаем self-model на реальном fitness
            if len(fitness_history) > 1:
                target = torch.tensor([[fitness]], device=DEVICE).float()  # приводим к размеру [1,1]
                loss_pred = torch.nn.functional.mse_loss(self_model(features), target)
                self_optim.zero_grad()
                loss_pred.backward()
                self_optim.step()
                if do_detailed_log:
                    logger.info(f"📉 Self-model loss: {loss_pred.item():.4f} | pred_error={pred_error:.3f}")

            # ========== КОГНИТИВНЫЙ ЦИКЛ ==========
            if cognitive_loop is not None:
                cognitive_metrics = {
                    "loss": val_loss,
                    "entropy": entropy,
                    "temp_f": temp_f,
                    "np_solved": np_solved
                }
                # Вызываем когнитивный цикл
                cognitive_result = cognitive_loop.step(
                    metrics=cognitive_metrics,
                    pred_error=pred_error,
                    events=[]
                )
                # Обновляем genome из когнитивного цикла, но сохраняем lr (используем learning_rate как lr)
                if 'learning_rate' in cognitive_result['genome']:
                    genome['lr'] = cognitive_result['genome']['learning_rate']
                if 'mutation_rate' in cognitive_result['genome']:
                    genome['mutation_rate'] = cognitive_result['genome']['mutation_rate']
                # exploration используется для memory.strategy
                mode = cognitive_result['mode']
                if 'exploration' in cognitive_result['genome']:
                    memory.strategy["exploration"] = cognitive_result['genome']['exploration']
                if do_detailed_log:
                    logger.info(f"🧠 КОГНИТИВНЫЙ ЦИКЛ: mode={mode}, genome_updates={cognitive_result['genome']}")
            else:
                logger.warning("Когнитивный цикл не инициализирован")

            # --- ГЕНЕТИЧЕСКАЯ ПАМЯТЬ (эволюция гиперпараметров) ---
            # Давление среды для mutation_rate
            pressure = (gpu_load/100.0 + cpu_load/100.0 + entropy + abs(fitness - best_fitness)) / 4.0
            genome['mutation_rate'] = 0.1 + pressure * 0.4
            genome['mutation_rate'] = min(0.5, max(0.05, genome['mutation_rate']))
            # Случайная мутация генома
            if random.random() < 0.1:
                genome['lr'] *= random.uniform(0.9, 1.1)
                genome['lr'] = max(1e-6, min(0.01, genome['lr']))
                logger.debug(f"🧬 Геном мутировал: lr={genome['lr']:.5f}, mutation_rate={genome['mutation_rate']:.3f}")

            # --- ШАГ PHYSARUM GRAPH SOLVER ---
            if model is not None and physarum_solver is not None:
                flow = physarum_solver.step(source_node=0)
                importance = physarum_solver.get_importance()
                # Предложение новой конфигурации
                if random.random() < 0.1:
                    new_config = physarum_solver.suggest_config()
                    if new_config:
                        logger.info(f"🦠 Physarum предложил новую конфигурацию: {new_config}")
                        candidates.append((new_config, 'physarum_path', None))
                # Обновление графа на основе fitness
                # Передаём температуру, чтобы граф мог использовать её для динамики
                physarum_solver.update(fitness, temperature_f=thermal_metrics.get('temp_f'))

            # ========== ОСТАЛЬНАЯ ЛОГИКА (награды, мир, социальное обучение и т.д.) ==========
            logger.info("Награда агенту...")
            world.reward_agent(agent, score)

            if score > memory.hope_score * 0.8:
                social_engine.add_success(agent)

            # Обновление cold memory в ThermalTachyonController
            if config is not None:
                thermal.update_cold_memory(score, config, metrics)
            else:
                logger.debug("config None, пропускаем update_cold_memory")

            # Проверка revert от ThermalTachyonController
            revert_config = thermal.check_revert(score, metrics)
            if revert_config:
                config = revert_config
                source = 'thermal_revert'
                logger.info("🔄 Tachyon rewind: откат к холодному состоянию")

            if last_score is not None and best_score is not None:
                distance_to_best = best_score - score
                if velocity < 0.05 and score < best_score * 0.9:
                    config_to_train['lr'] = min(config_to_train.get('lr', 0.001) * 1.2, 0.01)
                    config_to_train['gain'] = min(config_to_train.get('gain', 1.0) + 0.1, 2.0)
                    logger.info("     ☢️ ЯДЕРНОЕ ОБОГАЩЕНИЕ: lr ↑, gain ↑")
                elif score > best_score * 0.95 and abs(distance_to_best) < 0.1:
                    config_to_train['lr'] = max(config_to_train.get('lr', 0.001) * 0.5, 1e-5)
                    config_to_train['temperature'] = max(config_to_train.get('temperature', 1.0) * 0.9, 0.3)
                    logger.info("     🧊 ЯДЕРНОЕ ОБЕДНЕНИЕ: lr ↓, temp ↓")

            # ---------- Сохранение стабильного состояния (после успешного обучения) ----------
            if val_loss < best_loss:
                best_loss = val_loss
                if model is not None:
                    last_good_state = copy.deepcopy(model.state_dict())
                last_good_genome = genome.copy()
                last_good_config = config.copy()
                logger.info(f"💾 Сохранено стабильное состояние (loss={val_loss:.4f})")

            # ========== УМНЫЙ SURVIVE: откат к лучшему состоянию (с восстановлением модели) ==========
            if meta_state["mode"] == "SURVIVE" and meta_state["best_snapshot"] is not None and model is not None:
                logger.info("🛡️ SURVIVE MODE: откат к лучшему состоянию")
                try:
                    # Создаём новую модель с сохранённой конфигурацией
                    new_model = restore_model_state(meta_state["best_snapshot"], device=DEVICE)
                    # Заменяем текущую модель
                    model = new_model
                    # Обновляем physarum_solver, если он использует модель
                    if physarum_solver is not None:
                        physarum_solver.model = model
                        physarum_solver._build_graph()
                    logger.info("✅ Состояние модели успешно восстановлено")
                except Exception as e:
                    logger.error(f"Ошибка восстановления лучшего состояния: {e}")

            if do_detailed_log:
                logger.info(f"📊 ВЫЖИВАЕМОСТЬ: {success_count}/{seeds_this_cycle} потоков")
                origin = "МУТАЦИЯ" if source == 'swarm' else ("БАЙЕС" if source == 'bayes' else ("ТАХИОН" if source == 'tachyon' else ("ФИЗАРИУС" if source == 'physarum' else ("СОЦИАЛЬНОЕ" if source == 'social' else "СЛУЧАЙНО"))))
                logger.info(f"🧬 ПРОИСХОЖДЕНИЕ: {origin}")
                logger.info(f"📈 Score: {score:.4f} | Loss: {val_loss:.4f} | MI: {mi:.4f} | Div: {div:.3f} | Gap: {gap:.4f}")
                logger.info(f"📉 Градиенты: min={gn_min:.3f}, max={gn_max:.3f}, mean={gn_mean:.3f}")
                logger.info(f"🛠️ VRAM={vram:.0f} MB | Step={step_t:.2f} ms")
                logger.info(f"🔮 ТАХИОН: Pred={pred_score:.4f} | V={velocity:.5f} | A={acceleration:.5f}")
                logger.info(f"🎤 Аудио: входов={active_inputs}, выходов={active_outputs}, ср.громк={avg_output_volume:.2f}, изменений={len(audio_changes)}")
                logger.info(f"🧠 МЕТА-РЕЖИМ: {meta_state['mode']} (x{meta_state['mode_strength']:.2f}) | inst={meta_state['instability']:.2f} | trend={meta_state['loss_trend']:.3f} | reward={meta_state['reward']:.3f} | hunger={meta_state['hunger']:.2f} | NaN={meta_state['nan_count']}")
                mode_str = "EXPLORE" if memory.mode == 0 else "EXPLOIT"
                logger.info(f"     🌐 Режим: {mode_str}")
                if memory.hope_score > -float('inf'):
                    logger.info(f"     🏅 Кандидат: {memory.hope_score:.4f} (режим {memory.hope_mode})")
                if len(memory.light_beacons) > 0:
                    logger.info(f"     ⚫ Сингулярностей: {len(memory.light_beacons)}")
                logger.info(f"     ❤️ Окситоцин: {memory.oxytocin:.2f}")
                if memory.protective_field is not None:
                    logger.info(f"     🛡️ Защитное поле: масса={memory.protective_field.get('score',0):.4f}, радиус={memory.protection_radius:.3f}")

                if velocity > 0.1 and pred_score > score:
                    logger.info("     ⚡ WAKE ME UP INSIDE (Evanescence)")
                elif success_count < SEEDS_PER_CYCLE / 2 and memory.hope_score > -float('inf'):
                    logger.info("     🌊 I'M LOST FOREVER (Nightwish)")
                elif success_count == 0:
                    logger.info("     🚪 LEFT OUTSIDE ALONE (Anastacia)")

            if GAMING_MODE:
                event_type, combat_log, desc = interpret_metrics(
                    {"loss": val_loss, "prev_loss": last_score if last_score is not None else val_loss},
                    rpg_state
                )
                if do_detailed_log:
                    for line in combat_log:
                        logger.info(f"     {line}")

                now = time.time()
                if now - last_genesis_time >= GENESIS_AUTO_INTERVAL:
                    last_genesis_time = now
                    full_metrics = metrics.copy()
                    full_metrics.update({
                        "loss": val_loss,
                        "prev_loss": last_score,
                        "best_score": best_score,
                        "pred_score": pred_score,
                        "mi": mi,
                        "gap": gap,
                        "anomaly": False,
                        "current_loss": val_loss,
                        "loss_diff": loss_diff
                    })
                    logger.info("Вызов genesis_protocol.auto_update_world...")
                    world_lines = genesis_protocol.auto_update_world(full_metrics, rpg_state, agents=world.population)
                    np_solved = getattr(rpg_state, 'np_task_solved_this_cycle', False)
                    np_difficulty = getattr(rpg_state, 'np_difficulty_solved', 0.0)
                    if do_detailed_log:
                        for line in world_lines:
                            logger.info(line)

                if do_detailed_log:
                    exp_needed = rpg_state.level * 100
                    exp_percent = (rpg_state.exp / exp_needed) * 100 if exp_needed > 0 else 0
                    limb_status = ", ".join([f"{l.type[:2]}={l.status[0]}" for l in rpg_state.limbs[:3]])
                    logger.info(f"     ❤️ {rpg_state.health}/{rpg_state.max_health} | 💙 {rpg_state.mana}/{rpg_state.max_mana} | ⭐ Ур.{rpg_state.level} | 🧪 {exp_percent:.1f}% | 💰 {rpg_state.gold}")
                    logger.info(f"     📍 {rpg_state.current_location} | 🐜 Мобов: {len(rpg_state.swarm)} | 🏰 База ур.{rpg_state.base_level} | 🦿 {limb_status}")

            world.meaning.update()

            for a in world.population:
                if hasattr(a, 'brain'):
                    brain = a.brain
                    brain.think(world)
                    action = brain.decide()
                    explanation = brain.explain()
                    logger.info(f"🤖 {a.id[:4]} -> {action} | {explanation}")
                    brain.learn("success" if random.random() > 0.3 else "failure")

            world.meta.observe(score)
            state_analysis = world.meta.analyze()
            if state_analysis == "crisis":
                logger.warning("⚠️ SYSTEM CRISIS DETECTED")
            elif state_analysis == "growth":
                logger.info("🚀 CIVILIZATION GROWING")

            world_prediction = old_tachyon.predict_world(world)
            rpg_state.perceive_future(world_prediction)

            prev_state = rpg_state.copy()

            actions = core_rl.available_actions()
            rl_action = core_rl.select_action(rpg_state)
            tachyon_scores = tachyon.evaluate_actions(rpg_state, actions)
            hybrid_scores = {}
            s_enc = core_rl.encode_state(rpg_state)
            for a in actions:
                hybrid_scores[a] = core_rl.Q[s_enc][a] + tachyon_scores.get(a, 0)
            action = max(hybrid_scores, key=hybrid_scores.get)
            logger.info(f"🜏 JANUS выбирает действие: {action} (RL: {rl_action}, Tachyon: {max(tachyon_scores, key=tachyon_scores.get)})")

            if convergence:
                best_action_score = hybrid_scores[action]
                if best_action_score > 0.6:
                    partial_memory.store(action, best_action_score)

            env_world.step(rpg_state, action)
            core_rl.update(prev_state, action, rpg_state)

            if action == "EXPAND":
                world.laws.declare_event("GROWTH")
            elif action == "REWRITE":
                world.laws.reset_zone()

            if random.random() < 0.05 and rpg_state.self_model["aware"]:
                rpg_state.voice.speak(rpg_state, world_prediction)

            logger.info("Сохранение результатов в memory и Tachyon...")
            additional = {
                'val_loss': val_loss,
                'diversity': div,
                'mutual_info_unbiased': mi,
                'gap': gap,
                'grad_norm_min': gn_min,
                'grad_norm_max': gn_max,
                'grad_norm_mean': gn_mean,
                'weight_norm': w_norm,
                'vram_mb': vram,
                'step_time_ms': step_t,
                'seeds': success_count,
                'complexity_level': env.complexity_level,
                'train_hash': train_hash,
                'val_hash': val_hash,
                'gpu_load': gpu_load,
                'gpu_temp': gpu_temp,
                'cpu_load': cpu_load,
                'batch_size': batch_size,
                'cache_ratio': cache_ratio,
                'igpu_load': igpu_load,
                'android_mag': android_mag,
                'android_loss': android_loss,
                'android_entropy': android_entropy,
                'android_m2r': android_m2r,
                'audio_volume': audio_volume,
                'audio_spectrum': audio_spectrum,
                'user_active': user_active,
                'source': source,
                'agent_level': agent.level,
                'agent_faction': agent.faction,
                'agent_inventory': [item.name for item in agent.inventory.items],
                'nuclear_mode': 'enrichment' if (last_score is not None and velocity < 0.05 and score < best_score * 0.9) else ('depletion' if (last_score is not None and score > best_score * 0.95 and abs(distance_to_best) < 0.1) else 'neutral'),
                'np_solved': np_solved,
                'np_difficulty': np_difficulty,
                'meta_mode': meta_state['mode'],
                'meta_instability': meta_state['instability'],
                'meta_reward': meta_state['reward'],
                'meta_hunger': meta_state['hunger']
            }

            is_breakthrough = memory.commit(config, score, source != 'random', additional=additional)
            old_tachyon.add_sample(config, score, mi, step_t)

            if swarm and swarm_idx is not None:
                swarm.tell(swarm_idx, score)
            if bayes:
                try:
                    bayes.tell(config, score)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении байесовского оптимизатора: {e}")

            if meta:
                full_data = {**config, **additional}
                meta.add_sample(full_data, score)
                if cycle - last_meta_train >= META_UPDATE_INTERVAL and len(meta.X) >= 10:
                    meta.train()
                    last_meta_train = cycle
                    logger.info(f"     [📈] Мета-модель обновлена.")

            if cycle % 20 == 0 and len(old_tachyon.dataset) > 50:
                old_tachyon.train_score()
                old_tachyon.train_mi()
                old_tachyon.train_anti()

            if convergence:
                new_candidate = partial_memory.recombine()
                if new_candidate:
                    verify = verifier.verify(new_candidate)
                    comp = compression_score(new_candidate)
                    progress = 0.0
                    solution_field.add(new_candidate, verify, comp, progress)
                    if do_detailed_log:
                        logger.info(f"🧬 Рекомбинировано новое решение: {new_candidate} (verify={verify:.3f}, comp={comp:.3f})")

            if ADAPTIVE_TEST_ENABLED and best_state_dict is not None:
                try:
                    logger.info("Запуск адаптивного теста...")
                    test_model = AdaptiveTransformer(config_to_train['n_embd'], config_to_train['n_head'], config_to_train['n_layer']).to(DEVICE)
                    test_model.load_state_dict(best_state_dict)
                    max_complexity, test_loss = await adaptive_test(
                        test_model, config_to_train['gain'], config_to_train['temperature'],
                        base_seed=cycle, threshold=test_threshold, device=DEVICE
                    )
                    if do_detailed_log:
                        logger.info(f"     [🧪] Адаптивный тест: макс. сложность {max_complexity}, loss {test_loss:.4f}")
                    test_threshold_history.append(test_loss)
                    if len(test_threshold_history) > 20:
                        test_threshold_history.pop(0)
                    if len(test_threshold_history) > 5:
                        avg_loss = np.mean(test_threshold_history)
                        if avg_loss < test_threshold * 0.8:
                            test_threshold = min(test_threshold * 1.1, 50.0)
                        elif avg_loss > test_threshold * 1.2:
                            test_threshold = max(test_threshold * 0.9, 5.0)
                except Exception as e:
                    logger.error(f"Ошибка адаптивного теста: {e}")

            if success_count > 0:
                memory.switch_mode()

            if tachyonic_monitor.update(score):
                logger.info("🜏 [777] ТАХИОННЫЙ РЕЗОНАНС! Усиление обучения.")
                memory.strategy["exploration"] = min(0.9, memory.strategy["exploration"] + 0.1)

            if pocket_detector.update(score, val_loss):
                logger.warning("⚠️ [КАРМАН] Обнаружено зацикливание. Сброс региона поиска.")
                failed_configs.append(config)
                memory.strategy["exploration"] = min(0.9, memory.strategy["exploration"] + 0.1)

            if cycle % REGISTRY_SNAPSHOT_INTERVAL == 0:
                registry_data = {
                    "timestamp": datetime.now().isoformat(),
                    "cycle": cycle,
                    "best_score": best_score,
                    "last_score": score,
                    "config": config,
                    "resonance": tachyonic_monitor.resonant,
                    "pocket_detected": bool(pocket_detector.pockets),
                    "failed_configs_count": len(failed_configs),
                    "meta_mode": meta_state['mode']
                }
                registry_path = os.path.join(WORMHOLE_DIR, f"janus_registry_{cycle}.json")
                with open(registry_path, 'w') as f:
                    json.dump(registry_data, f, indent=2)

            if score > best_score:
                best_score = score
                best_cycle = cycle
                if do_detailed_log:
                    logger.info(f"🏆 НОВЫЙ РЕКОРД: {best_score:.4f} (цикл {best_cycle})")
                hrain_daemon.send_event({"type": "record", "cycle": cycle, "score": score})

                logger.info(f"🎉 RECORD событие (визуализация отключена): {score}")

                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("record")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])

            hrain_daemon.send_event({"type": "cycle", "cycle": cycle, "score": score, "val_loss": val_loss, "mi": mi, "div": div, "meta_mode": meta_state['mode']})

            if is_breakthrough and best_state_dict is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(MODEL_ZOO_DIR, f"janus_breakthrough_{ts}_C{cycle}_S{score:.4f}.pt")
                torch.save({'model_state': best_state_dict, 'config': config, 'score': score, 'cycle': cycle, 'additional': additional}, path)
                if do_detailed_log:
                    logger.info(f"💾 Геном сохранён: {path}")

            belief_system.update(world.population, meta_goal)
            cult_engine.update(env_world)

            env.update_complexity(score)
            last_score, last_mi = score, mi

            if cycle % 50 == 0:
                new_core, improved = auto_evo.evolve(core_rl, rpg_state, env_world)
                if improved:
                    core_rl = new_core
                    logger.info("🧬 ЯНУС ЭВОЛЮЦИОНИРОВАЛ: новые гиперпараметры")
                    janus_db.insert_genesis_event("EVOLUTION", "Янус улучшил свои параметры обучения")

            save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs,
                                    pred_score, velocity, acceleration, metrics.get('purity_score', 0.0))

            with open(RPG_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(rpg_state.to_dict(), f, ensure_ascii=False, indent=2)

            pc_metrics = {'gpu_temp': gpu_temp, 'gpu_load': gpu_load, 'cpu_load': cpu_load}
            cardputer_metrics = {}
            world.update(pc_metrics=pc_metrics, cardputer_metrics=cardputer_metrics)

            if social_engine and world.population:
                for agent in world.population:
                    new_config = social_engine.observe_and_learn(agent, world.population, world)
                    if new_config:
                        agent.base_config = new_config
                        agent._update_current_config()
                        logger.info(f"🧠 Агент {agent.id[:8]} улучшил конфигурацию через социальное обучение.")

            world.save()

            if hasattr(world, 'market') and hasattr(world.market, 'update_tick'):
                world.market.update_tick()
            cultural_decadence.update()
            integrator.update()
            if cycle % 100 == 0:
                patcher.update()

            if matrix_engine and MATRIX_MODE:
                fps_estimate = None
                if monitor and hasattr(monitor, 'get_game_fps'):
                    fps_estimate = monitor.get_game_fps()
                matrix_engine.update_intensity(fps_estimate)

            if cycle % 20 == 0:
                possible_actions = ["boost_economy", "spawn_resource", "encourage_raids", "promote_trade"]
                best_action = tachyon_evolution.choose_best_action(possible_actions)
                if best_action:
                    logger.info(f"⚡ Tachyon Evolution выбрал действие: {best_action}")
                    if hasattr(meta_engine, 'executor'):
                        meta_engine.executor.execute(best_action, world)
                    else:
                        if best_action == "boost_economy":
                            for res in world.economy.resources:
                                world.economy.resources[res] += 20
                        elif best_action == "spawn_resource":
                            if world.population:
                                agent = random.choice(world.population)
                                item = world.inventory.random_item()
                                agent.add_item(item)
                        elif best_action == "encourage_raids":
                            if hasattr(world.raids, 'difficulty_multiplier'):
                                world.raids.difficulty_multiplier *= 1.1
                        elif best_action == "promote_trade":
                            world.market_event()

            if SUBCONSCIOUS_ENABLED:
                if cycle - last_chronos >= CHRONOS_INTERVAL and chronos and engine_stub:
                    logger.info("Запуск Chronos...")
                    await chronos.scavenge_past(engine_stub)
                    last_chronos = cycle
                if cycle - last_hypnos >= HYPNOS_INTERVAL and hypnos:
                    logger.info("Запуск Hypnos...")
                    await hypnos.assimilate()
                    last_hypnos = cycle
                if cycle - last_nebuchad >= NEBUCHAD_INTERVAL and nebuchad:
                    last_nebuchad = cycle

            for a in world.population:
                if a.level > 3 and a not in social_engine.bards and random.random() < 0.1:
                    social_engine.add_bard(a)
                    logger.info(f"🎤 Агент {a.id[:8]} стал бардом!")

            if random.random() < 0.02 and world.population:
                crafters = [a for a in world.population if a.profession in ["blacksmith", "alchemist"]]
                if crafters:
                    crafter = random.choice(crafters)
                    recipe_keys = list(world.crafting.recipes.keys())
                    if recipe_keys:
                        recipe = random.choice(recipe_keys)
                        success, msg, item = world.craft(crafter, list(recipe))
                        if success:
                            logger.info(f"🔨 {crafter} создал {item.name}!")

            if random.random() < 0.1 or (score > best_score and do_detailed_log):
                story = storyteller.learn_from_cycle(world, memory, cycle)
                logger.info(f"[📖] ИСТОРИЯ: {story}")

            if world.tick % META_UPDATE_INTERVAL == 0:
                action, result = meta_engine.update()
                logger.info(f"[🌐] МЕТА-ДЕЙСТВИЕ: {action} -> {result}")

            if isinstance(world.population, dict):
                agents_dict = world.population
            else:
                agents_dict = {agent.id: agent for agent in world.population}
            species_engine.update_all_fitness(agents_dict)
            extinct = species_engine.cull_weak_species(threshold=0.5)
            if extinct:
                logger.info(f"💀 Вымершие виды: {extinct}")
                logger.info(f"📸 EXTINCTION событие (визуализация отключена): {extinct}")
                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("extinction")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])
            if len(species_engine.species_list) < 3:
                new_sp = species_engine.spawn_new_species()
                logger.info(f"🆕 Появился новый вид: {new_sp.name}")
                logger.info(f"📸 NEW_SPECIES событие (визуализация отключена): {new_sp.name}")
                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("new_species")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])
            species_engine.save()

            screen_entropy = metrics.get('screen', {}).get('entropy', 0)
            if screen_entropy > 6 and random.random() < 0.01:
                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("high_entropy")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])

            if cycle % 100 == 0 and do_detailed_log:
                logger.info(f"\n📊 СТАТИСТИКА ЛЕТАЛЬНОСТИ за {cycle} циклов:")
                logger.info(f"     Смертей: {memory.total_lessons}, Выживших: {memory.total_growth}")
                for param in ['lr', 'gain', 'temperature']:
                    if param in memory.lessons_stats and memory.lessons_stats[param]['values']:
                        lesson_mean = np.mean(memory.lessons_stats[param]['values'])
                        logger.info(f"     {param}: среднее летальное = {lesson_mean:.5f}")

            if cycle % 10 == 0:
                from janus_narrative import narrate_beliefs
                narrate_beliefs(belief_system)

            if convergence and do_detailed_log:
                if len(score_history) > 10:
                    scores_dict = {f"score_{i}": s for i, s in enumerate(score_history)}
                    conv_data = convergence.update(scores_dict)
                    logger.info(f"📈 Convergence: progress={conv_data['progress']*100:.2f}% | entropy={conv_data['entropy']:.3f} | stability={conv_data['stability']:.3f}")
                else:
                    logger.info(f"📈 Convergence: накопление данных ({len(score_history)}/100)")

            if do_detailed_log:
                cpu_temp = metrics.get('cpu_temperature')
                entropy = metrics.get('hardware_entropy', {})
                stability = entropy.get('stability_score', 0.0)
                jitter = entropy.get('timing_jitter', 0.0)
                temp_str = f"{cpu_temp:.1f}" if cpu_temp is not None else "N/A"
                logger.info(f"🌡️ CPU: {temp_str}°C | Stability: {stability:.3f} | Jitter: {jitter:.6f}ms | Mode: {thermal.get_current_mode()}")

            logger.info(f"--- ЦИКЛ {cycle} ЗАВЕРШЁН, пауза {pause:.2f}с ---")
            if pause > 0 and do_detailed_log:
                logger.info(f"💤 Пауза {pause:.2f}с...")
            await asyncio.sleep(pause)
            logger.info(f"--- ПАУЗА ЗАВЕРШЕНА, НАЧИНАЕМ НОВЫЙ ЦИКЛ ---")

    except (KeyboardInterrupt, Exception) as e:
        logger.error(f"\n🛑 Остановка: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        monitor.stop()
        if igpu_offload.available:
            igpu_offload.save_memory(IGPU_MEMORY_FILE)
            logger.info("💾 Память iGPU сохранена")
        if cpu_offload:
            cpu_offload.shutdown()
            logger.info("✓ CPUOffload остановлен.")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("✓ Мониторинг остановлен.")
        with open(RPG_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(rpg_state.to_dict(), f, ensure_ascii=False, indent=2)
        world.save()
        monitor_state = {
            "resonance_hits": tachyonic_monitor.resonance_hits,
            "resonant": tachyonic_monitor.resonant,
            "pockets": pocket_detector.pockets,
            "meta_mode": meta_state['mode']
        }
        with open(os.path.join(WORMHOLE_DIR, "monitor_state.json"), 'w') as f:
            json.dump(monitor_state, f)
        if 'integrator' in locals() and integrator:
            try:
                integrator.save_state(os.path.join(WORMHOLE_DIR, "module_integrator_state.json"))
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния интегратора: {e}")
        if 'patcher' in locals() and patcher:
            try:
                patcher_state = patcher.save_state()
                with open(os.path.join(WORMHOLE_DIR, "monkey_patcher_state.json"), 'w') as f:
                    json.dump(patcher_state, f)
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния патчера: {e}")
        if matrix_engine and MATRIX_MODE:
            matrix_engine.stop()
        hrain_daemon.stop()
        logger.info("✓ HRAIN демон корректно остановлен.")

async def main():
    await run_demiurge_loop()

if __name__ == "__main__":
    if not logger.handlers:
        import sys
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)
    asyncio.run(main())