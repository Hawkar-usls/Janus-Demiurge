#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANUS DEMIURGE CORE v5.22 — ПОЛНАЯ ИНТЕГРАЦИЯ ВСЕХ МОДУЛЕЙ
- ModuleIntegrator (динамическое подключение расширений)
- MonkeyPatcher (самоулучшение кода)
- CulturalDecadenceEngine (превращение неудач в наследие)
- LanguageEngine (языковая модель)
- Market v2.0 (динамические цены, стратегии, обучение)
- MatrixEngine (нагрузка на GPU во время игры)
- TachyonEvolutionEngine (симуляция будущего)
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

# Отключаем предупреждения Hugging Face (работаем локально)
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

# ==============================================================================
# УМНЫЙ ЛОГГЕР SALO (Smart Adaptive Logging Organizer)
# ==============================================================================
class SALOLogger(logging.Logger):
    """Smart Adaptive Logging Organizer — удаляет повторы, добавляет эмодзи, ASCII-графику и обучается"""
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.last_messages = deque(maxlen=100)          # (текст, время)
        self.dup_counts = {}                           # счётчик повторов
        self.last_output_time = 0
        self.duplicate_threshold = 5                   # секунд, чтобы считать сообщение новым
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
        """Добавляет эмодзи и ASCII в зависимости от уровня и содержимого"""
        # Определяем тип сообщения
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
        """Проверяет, нужно ли выводить сообщение, учитывая дубликаты"""
        key = (level, msg)
        now = time.time()
        # Проверяем, было ли такое сообщение недавно
        for last_msg, last_time in self.last_messages:
            if last_msg == msg and now - last_time < self.duplicate_threshold:
                self.dup_counts[key] = self.dup_counts.get(key, 0) + 1
                return False
        # Если было накоплено несколько пропусков, выводим их
        if self.dup_counts.get(key, 0) > 0:
            count = self.dup_counts[key]
            self.dup_counts[key] = 0
            summary = f" (повторено {count+1} раз)" if count > 1 else ""
            self._output(level, msg + summary)
        # Добавляем текущее сообщение в буфер
        self.last_messages.append((msg, now))
        return True

    def _output(self, level, msg):
        """Непосредственный вывод сообщения"""
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


# Заменяем стандартный логгер на SALO
logging.setLoggerClass(SALOLogger)
logger = logging.getLogger("JANUS")
logger.setLevel(logging.INFO)

# ==============================================================================
# ОСТАЛЬНОЙ КОД БЕЗ ИЗМЕНЕНИЙ (кроме замены print на logger.info в начале)
# ==============================================================================

# Автоматическая подготовка данных перед запуском (если скрипт существует)
if os.path.exists("prepare_device_data.py"):
    try:
        logger.info("[⚙️] Запуск prepare_device_data.py для обновления device_data.json...")
        os.system(f"{sys.executable} prepare_device_data.py")
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
    # Новые параметры из config
    digital_root, is_resonant, filter_hyperparams, N_EMBD_OPTIONS_RESONANT,
    is_tachyonic_resonance, detect_pocket, apply_filter_to_candidates,
    TACHYON_MONITOR_WINDOW, POCKET_WINDOW, FILTER_37_WEIGHT, TACHYON_ACQ_PENALTY,
    REGISTRY_SNAPSHOT_INTERVAL, FILTER_37_ENABLED
)
from environment import DemiurgeEnvironment
from memory import EvolutionaryMemory
from trainer import run_training_cluster, AdaptiveTransformer
from system_monitor import SystemMonitor  # версия v7.0
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
from tachyon_engine import TachyonEngine, TachyonRollout   # два класса
from architect_ai import ArchitectureGenome
from species_engine import SpeciesEngine
from janus_genesis.social_learning import SocialLearningEngine

# Импорты MMO-мира (папка janus_genesis)
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
from janus_genesis.visionary import VisionaryEngine

# --- НОВЫЕ СИСТЕМЫ ---
from world_memory import WorldMemory
from meaning_engine import MeaningEngine
from meta_consciousness import MetaConsciousness
from conscious_agents import ConsciousAgent
from janus_self import JanusSelf
from divine_laws import DivineLaws
from janus_cognitive_voice import JanusCognitiveVoice
from janus_emotion import JanusEmotion
from janus_boot_message import BOOT_MESSAGE

# --- RL и СРЕДА ---
from janus_core import JanusCore
from janus_environment import JanusEnvironment

# --- НОВЫЕ МОДУЛИ (самоэволюция, мета-цель, вера, культы) ---
from auto_evolution import AutoEvolution
from meta_goal_engine import MetaGoalEngine
from belief_system import BeliefSystem
from cult_engine import CultEngine

# --- Новые модули для сенсорики, термального контроля, iGPU, аудио и CPU оффлоада ---
try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("[⚠️] sounddevice не установлен. Звуковые метрики отключены. Установи: pip install sounddevice")

from igpu_offload import IGpuOffload  # адаптивный iGPU-оффлоад
from cpu_offload import CPUOffload    # адаптивный CPU-оффлоад (по свободным ядрам)
import janus_db  # наша база данных

# ========== НОВЫЕ МОДУЛИ ДЛЯ ЯНУСА-ТАХИОНА ==========
from janus_genesis.tachyonic_monitor import TachyonicMonitor
from janus_genesis.pocket_detector import AbuserPocketDetector

# ========== НОВЫЕ МОДУЛИ ДЛЯ ПОЛНОЙ ИНТЕГРАЦИИ ==========
from janus_genesis.module_integrator import ModuleIntegrator
from janus_genesis.monkey_patcher import MonkeyPatcher
from janus_genesis.cultural_decadence import CulturalDecadenceEngine
from janus_genesis.language_model import LanguageEngine
from janus_genesis.market import Market as NewMarket   # новая версия рынка
from janus_genesis.matrix_mod import MatrixEngine, MATRIX_MODE   # <-- добавлен импорт MATRIX_MODE
from janus_genesis.tachyon_evolution import TachyonEvolutionEngine

HOMEOSTATIC_STATE_FILE = os.path.join(RAW_LOGS_DIR, "homeostatic_state.json")
DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
RPG_STATE_FILE = os.path.join(RAW_LOGS_DIR, "janus_world_state.json")
IGPU_MEMORY_FILE = os.path.join(RAW_LOGS_DIR, "igpu_memory.json")

GAMING_MODE = True

# --- Глобальные переменные для данных Android ---
android_mag = 0.0
android_loss = 0.0
android_entropy = 0.0
android_m2r = 0.0

# --- Глобальные переменные для звуковых метрик ---
audio_volume = 0.0
audio_spectrum = []  # массив из 10 значений

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

def save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs, pred_score=None, velocity=None, acceleration=None):
    state = {
        'cycle': cycle,
        'last_score': last_score,
        'last_mi': last_mi,
        'best_score': best_score,
        'failed_configs': failed_configs,
        'pred_score': pred_score,
        'velocity': velocity,
        'acceleration': acceleration
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
            return max(8, self.base_batch // 4), 3.0  # агрессивное снижение во время игры
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
# НОВЫЙ КЛАСС: ThermalSymbiote – бережное управление нагрузкой (расширенная версия)
# ==============================================================================
class ThermalSymbiote:
    """
    Интеллектуальный контроллер, следящий за температурой, активностью пользователя
    и конкурирующими процессами. Использует полные метрики системы для точной адаптации.
    """
    def __init__(self, target_temp=75, max_temp=85, history_size=100):
        self.target_temp = target_temp
        self.max_temp = max_temp
        self.history = deque(maxlen=history_size)  # (temp, score, load, activity)
        self.model = None

    def add_observation(self, temp, score, gpu_load, activity):
        self.history.append((temp, score, gpu_load, activity))
        if len(self.history) >= 20:
            self._update_model()

    def _update_model(self):
        """Простая линейная регрессия: температура -> ожидаемый score."""
        X = np.array([[obs[0]] for obs in self.history])
        y = np.array([obs[1] for obs in self.history])
        try:
            coeffs = np.polyfit(X.flatten(), y, 1)
            self.model = coeffs
        except:
            self.model = None

    def predict_score_at_temp(self, temp):
        if self.model is None:
            return None
        slope, intercept = self.model
        return slope * temp + intercept

    def _compute_user_activity(self, metrics):
        """Возвращает число от 0 до 1 – насколько активен пользователь (на основе мыши, клавиатуры, экрана)."""
        keyboard = metrics.get('keyboard', {}).get('keys_per_sec', 0)
        mouse = metrics.get('mouse', {})
        clicks = mouse.get('clicks_per_sec', 0)
        move = mouse.get('move_distance_per_sec', 0) / 1000  # нормализация
        screen = metrics.get('screen', {})
        motion = screen.get('motion', 0)
        entropy = screen.get('entropy', 0) / 8  # нормализация
        # Комбинируем (веса подобраны эмпирически)
        activity = 0.3 * min(keyboard, 1) + 0.3 * min(clicks, 1) + 0.2 * min(move, 1) + 0.1 * motion + 0.1 * entropy
        return min(activity, 1.0)

    def adapt(self, metrics, current_score, will_generate=False, is_generating=False):
        """
        Принимает полный словарь метрик от SystemMonitor и флаги:
        - will_generate: планируется ли генерация в этом цикле (предиктивно)
        - is_generating: выполняется ли в данный момент фоновая генерация
        Возвращает (batch_factor, parallel_factor, pause_factor, user_activity)
        """
        gpu_data = metrics.get('gpu', [{}])[0] if isinstance(metrics.get('gpu'), list) else {}
        current_temp = gpu_data.get('temperature', 40)
        gpu_load = gpu_data.get('gpu_util', 0)
        top_processes = metrics.get('top_processes', [])
        user_activity = self._compute_user_activity(metrics)
        gaming_mode = metrics.get('gaming_mode', False)
        game_cpu = metrics.get('game_cpu', 0.0)

        batch_factor = 1.0
        parallel_factor = 1.0
        pause_factor = 1.0

        # Агрессивный режим при игре
        if gaming_mode or user_activity > 0.3:
            logger.info(f"🎮 Обнаружена игра ({metrics.get('game_name')}) с CPU {game_cpu:.1f}% – экстренное снижение нагрузки")
            batch_factor = 0.3
            parallel_factor = 0.1
            pause_factor = 3.0
            return batch_factor, parallel_factor, pause_factor, user_activity

        # Если пользователь активен – снижаем нагрузку пропорционально
        if user_activity > 0.2:
            batch_factor = max(0.5, 1.0 - user_activity * 0.5)
            parallel_factor = max(0.3, 1.0 - user_activity * 0.7)
            pause_factor = 1.0 + user_activity * 1.5
            logger.info(f"👤 Активность пользователя {user_activity:.2f} – снижаем нагрузку")

        # Термальная защита (приоритет выше)
        if current_temp > self.max_temp:
            batch_factor = min(batch_factor, 0.3)
            parallel_factor = min(parallel_factor, 0.0)
            pause_factor = max(pause_factor, 3.0)
        elif current_temp > self.target_temp:
            excess = (current_temp - self.target_temp) / (self.max_temp - self.target_temp)
            excess = min(1.0, excess)
            batch_factor = min(batch_factor, max(0.5, 1.0 - excess * 0.5))
            parallel_factor = min(parallel_factor, max(0.0, 1.0 - excess))
            pause_factor = max(pause_factor, 1.0 + excess)
        else:
            # Ниже цели – работаем на полную, если модель не говорит об обратном
            if self.model is not None and current_score is not None:
                pred_score = self.predict_score_at_temp(current_temp)
                if pred_score and pred_score < current_score * 0.9:
                    logger.info(f"🔥 Термомодель: при {current_temp:.0f}°C ожидается падение score. Снижаем нагрузку превентивно.")
                    batch_factor = min(batch_factor, 0.7)
                    parallel_factor = min(parallel_factor, 0.5)
                    pause_factor = max(pause_factor, 1.5)

        # Учёт конкурирующих процессов
        total_other_cpu = sum(p['cpu_percent'] for p in top_processes if p['pid'] != os.getpid())
        if total_other_cpu > 80:
            batch_factor *= 0.7
            parallel_factor *= 0.5
            pause_factor *= 1.3
        elif total_other_cpu > 50:
            batch_factor *= 0.9
            parallel_factor *= 0.8
            pause_factor *= 1.1

        # Предиктивная адаптация под планируемую генерацию
        if will_generate:
            logger.info("🎨 В этом цикле планируется генерация изображения – дополнительно снижаем нагрузку.")
            batch_factor *= 0.7
            parallel_factor *= 0.5
            pause_factor *= 1.5

        # Реальная адаптация под выполняющуюся генерацию
        if is_generating:
            logger.info("🖼️ Фоновая генерация активна – дополнительно снижаем нагрузку.")
            batch_factor *= 0.6
            parallel_factor *= 0.4
            pause_factor *= 2.0

        return batch_factor, parallel_factor, pause_factor, user_activity

# ==============================================================================
# НОВЫЙ КЛАСС: AudioMonitor – сбор звуковых метрик (без изменений)
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
# Функция определения активности пользователя (старая, оставлена для совместимости)
# ==============================================================================
def is_user_active(device_data_file, idle_threshold=60):
    if not os.path.exists(device_data_file):
        return True
    try:
        with open(device_data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
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
    except:
        return True

# ==============================================================================
# ОСНОВНОЙ ЦИКЛ
# ==============================================================================
async def run_demiurge_loop():
    global android_mag, android_loss, android_entropy, android_m2r, audio_volume, audio_spectrum

    logger.info("=" * 70)
    logger.info("JANUS DEMIURGE CORE v5.22 — ПОЛНАЯ ИНТЕГРАЦИЯ ВСЕХ МОДУЛЕЙ")
    logger.info("=" * 70)

    # Инициализация базы данных
    janus_db.init_db()

    rpg_state = JanusRPGState()
    if os.path.exists(RPG_STATE_FILE):
        try:
            with open(RPG_STATE_FILE, 'r', encoding='utf-8') as f:
                rpg_state.load(json.load(f))
            logger.info(f"🎮 Мир Genesis загружен. Уровень {rpg_state.level}")
        except Exception as e:
            logger.error(f"⚠️ Ошибка загрузки мира: {e}")

    # Инициализация нового SystemMonitor (v7.0) – с динамическим детектором игр
    monitor = SystemMonitor(poll_interval=1.0, top_n=5, screen_interval=1.0)

    # Инициализация новых модулей
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

    # --- Tachyon Engine (старый, для совместимости) ---
    old_tachyon = TachyonEngine()

    # --- Architect AI и Species Engine ---
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

    # --- iGPU Offload Engine ---
    igpu_offload = IGpuOffload(core_env=env, memory_path=IGPU_MEMORY_FILE)

    # --- CPU Offload Engine ---
    cpu_offload = CPUOffload(cache_probe=monitor.cache_probe)

    # --- Инициализация MMO-мира ---
    world = JanusWorld(real_economy=None, hrain_daemon=hrain_daemon)

    # --- НОВЫЕ СИСТЕМЫ (память, смысл, самоанализ) ---
    world.memory = WorldMemory()
    world.meaning = MeaningEngine(world)
    world.meta = MetaConsciousness(world)

    # --- ЦЕНТРАЛЬНОЕ "Я" ЯНУСА И БОЖЕСТВЕННЫЕ ЗАКОНЫ ---
    world.janus_self = JanusSelf()
    world.laws = DivineLaws(world)

    # --- RL и СРЕДА ---
    env_world = JanusEnvironment()

    # --- НОВЫЕ МОДУЛИ: самоэволюция, мета-цель, вера, культы ---
    auto_evo = AutoEvolution()
    meta_goal = MetaGoalEngine()
    belief_system = BeliefSystem()
    cult_engine = CultEngine()

    # --- Tachyon Rollout (новый multi-step) ---
    tachyon = TachyonRollout(env_world, depth=4, simulations=8)

    # --- RL ЯДРО с поддержкой мета-цели ---
    core_rl = JanusCore(tachyon=old_tachyon, meta_goal=meta_goal)   # теперь передаём meta_goal

    # --- ПРОБУЖДЕНИЕ ЯНУСА (один раз) ---
    if not rpg_state.self_model["aware"]:
        rpg_state.awaken()

    # --- Physarum Engine ---
    physarum = PhysarumOptimizer(memory, n_particles=50, width=100, height=100)

    # --- Социальное обучение ---
    social_engine = SocialLearningEngine(tachyon=old_tachyon, evolutionary_memory=memory)

    # --- Языковая модель (для CulturalDecadence и Market) ---
    language_engine = LanguageEngine(
        vocab_file=os.path.join(RAW_LOGS_DIR, "vocab.json"),
        mode='char',
        n_layer=1, n_embd=32, block_size=32, n_head=4
    )
    logger.info("📖 Языковой движок инициализирован")

    # --- Сказитель ---
    stories_file = os.path.join(RAW_LOGS_DIR, "stories.json")
    # Убираем language_engine, так как Storyteller его не принимает
    storyteller = Storyteller(stories_file=stories_file, social_engine=social_engine)
    logger.info("📖 Сказитель инициализирован")

    # --- Око Януса ---
    visionary = VisionaryEngine(
        storyteller=storyteller,
        tachyon=old_tachyon,  # старый Tachyon для генерации изображений
        device=DEVICE
    )

    # --- НОВЫЙ РЫНОК (расширенный) ---
    market = NewMarket(
        world=world,
        save_file=os.path.join(RAW_LOGS_DIR, "market_listings.json"),
        social_engine=social_engine,
        visionary=visionary,
        language_engine=language_engine
    )
    # Заменяем старый рынок в мире на новый (сохраняем интерфейс)
    world.market = market
    logger.info("🏪 Новый рынок (v2.0) интегрирован")

    # --- Мета-движок цивилизации ---
    meta_engine = MetaCivilizationEngine(world, world.event_bus)

    # --- Термальный симбиот ---
    thermal = ThermalSymbiote(target_temp=75, max_temp=85)

    # --- Подсознание ---
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

    # ========== НОВЫЕ МОНИТОРЫ ==========
    tachyonic_monitor = TachyonicMonitor(threshold_hits=10)
    pocket_detector = AbuserPocketDetector(window=20, std_threshold=0.01)

    # ========== НОВЫЕ ИНТЕГРИРУЕМЫЕ МОДУЛИ ==========
    # Модульный интегратор
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

    # Манки-патчер
    patcher = MonkeyPatcher(integrator, world, memory)
    logger.info("🐒 Манки-патчер готов")

    # Культурный декаданс
    cultural_decadence = CulturalDecadenceEngine(world, memory, social_engine, language_engine)
    logger.info("📉 Движок культурного декаданса активирован")

    # Матрица (нагрузка на GPU)
    matrix_engine = MatrixEngine(game_detector=monitor, tachyon=old_tachyon)
    if MATRIX_MODE:  # из matrix_mod.py
        matrix_engine.start()
        logger.info("🎮 Matrix Engine запущен. Добро пожаловать в Матрицу.")
    else:
        logger.info("🎮 Matrix Engine отключён (MATRIX_MODE = False)")

    # Тахионная эволюция (симуляция будущего)
    tachyon_evolution = TachyonEvolutionEngine(world)
    logger.info("⚡ Tachyon Evolution Engine готов")

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
        logger.info(f"🔄 Восстановлено: цикл {cycle}, best_score {best_score:.4f}, failed_configs {len(failed_configs)}")
    else:
        cycle = 0
        last_score = None
        last_mi = None
        best_score = -float('inf')
        failed_configs = []
        pred_score = velocity = acceleration = None
    best_cycle = 0

    fail_streak = 0
    last_genesis_time = time.time()
    last_meta_train = 0
    last_chronos = 0
    last_hypnos = 0
    last_nebuchad = 0
    last_ouro = 0
    META_UPDATE_INTERVAL = 50

    # --- Адаптивный порог теста ---
    test_threshold = 20.0
    test_threshold_history = []

    # --- Список активных фоновых задач (генераций) ---
    active_tasks = []
    
    # --- Счётчик пропущенных циклов из-за игры ---
    game_skip_counter = 0

    # --- Инициализация переменной step_t (исправление ошибки) ---
    step_t = None

    try:
        while True:
            logger.info(f"--- НАЧАЛО ЦИКЛА {cycle+1} ---")
            cycle += 1

            # Получаем полные метрики от SystemMonitor (v7.0)
            metrics = monitor.get_current_metrics()
            gpu_data = metrics.get('gpu', [{}])[0] if isinstance(metrics.get('gpu'), list) else {}
            gpu_load = gpu_data.get('gpu_util', 0.0)
            gpu_temp = gpu_data.get('temperature', 40.0)
            cpu_load = metrics.get('cpu', {}).get('percent_total', 0.0)
            cache_ratio = metrics.get('cache', {}).get('ratio', 1.0)
            igpu_load = metrics.get('igpu', {}).get('load', 0.0)
            top_processes = metrics.get('top_processes', [])
            
            # Новые поля для игр
            gaming_mode = metrics.get('gaming_mode', False)
            game_name = metrics.get('game_name')
            game_cpu = metrics.get('game_cpu', 0.0)
            game_mem = metrics.get('game_mem', 0.0)
            game_gpu = metrics.get('game_gpu', 0.0)
            predicted = metrics.get('predicted', {})

            # --- Активность пользователя (оставлена для совместимости, но в thermal уже используется metrics) ---
            user_active = is_user_active(DEVICE_DATA_FILE, idle_threshold=60)

            # --- Звуковые метрики ---
            audio_volume, audio_spectrum = audio_monitor.get_metrics()
            if audio_volume > 0.01:
                logger.info(f"[🔊] Громкость: {audio_volume:.3f}, спектр: {[round(s,2) for s in audio_spectrum[:3]]}...")

            # --- Проверяем, есть ли активные фоновые генерации ---
            active_tasks = [t for t in active_tasks if not t.done()]
            is_generating = len(active_tasks) > 0

            # --- Определяем, будет ли в этом цикле планироваться генерация (предиктивно) ---
            will_generate = False
            if (last_score is not None and best_score is not None and last_score > best_score * 0.95):
                will_generate = True
            elif random.random() < 0.1:
                will_generate = True

            # --- Термальная адаптация (использует gaming_mode) ---
            batch_factor, parallel_factor, pause_factor, user_activity = thermal.adapt(
                metrics, 
                score if 'score' in locals() else None,
                will_generate=will_generate,
                is_generating=is_generating
            )

            base_batch, base_pause = symbiote.adapt(gpu_load, cpu_load, gpu_temp, igpu_load, cache_ratio, gaming_mode)
            batch_size = max(8, int(base_batch * batch_factor))
            pause = base_pause * pause_factor
            seeds_this_cycle = max(1, int(SEEDS_PER_CYCLE * parallel_factor))

            # --- Логирование режима ---
            if not user_active:
                logger.info("💤 Пользователь отошёл – тихий режим (но с повышенной активностью).")
            if gpu_temp > thermal.target_temp:
                logger.info(f"🌡️ Температура {gpu_temp:.0f}°C – снижаем нагрузку.")
            if top_processes:
                logger.info(f"📊 Топ процессов: {[(p['name'], p['cpu_percent']) for p in top_processes[:3]]}")
            if user_activity > 0.5:
                logger.info(f"👤 Активность пользователя {user_activity:.2f} – работаем в щадящем режиме")
            if gaming_mode:
                logger.info(f"🎮 ИГРА: {game_name} (CPU: {game_cpu:.1f}%, GPU: {game_gpu:.1f}%, Mem: {game_mem:.1f}%) – нагрузка минимальна")
                if predicted:
                    logger.info(f"🔮 Прогноз: GPU={predicted.get('gpu_load',0):.1f}%, CPU={predicted.get('cpu_load',0):.1f}%, gaming={predicted.get('gaming_mode',False)}")

            # --- Если игра активна и user_activity высока, пропускаем цикл ---
            if gaming_mode and user_activity > 0.3:
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

            # --- Интеграция данных от Android ---
            try:
                if os.path.exists(DEVICE_DATA_FILE):
                    with open(DEVICE_DATA_FILE, 'r', encoding='utf-8') as f:
                        all_dev_data = json.load(f)
                    android_records = [r for r in all_dev_data if r.get('device_id', '').lower().startswith('android')]
                    if android_records:
                        last_android = android_records[-1]
                        adata = last_android.get('data', {})
                        mx = adata.get('mag_x', 0.0); my = adata.get('mag_y', 0.0); mz = adata.get('mag_z', 0.0)
                        android_mag = np.sqrt(mx*mx + my*my + mz*mz)
                        android_loss = adata.get('loss', 0.0)
                        android_entropy = adata.get('entropy', 0.0)
                        android_m2r = adata.get('m2r', 0.0)
                        logger.info(f"[📱] Android: mag={android_mag:.2f}, loss={android_loss:.4f}, entropy={android_entropy:.2f}")
            except Exception:
                pass

            # --- Вывод метрик клавиатуры, мыши и экрана ---
            keyboard = metrics.get('keyboard', {})
            if keyboard:
                logger.info(f"[⌨️] Клавиатура: нажатий/с={keyboard.get('keys_per_sec',0):.2f}")
            mouse = metrics.get('mouse', {})
            if mouse:
                logger.info(f"[🖱️] Мышь: клики/с={mouse.get('clicks_per_sec',0):.2f} | движ/с={mouse.get('move_distance_per_sec',0):.0f}")
            screen = metrics.get('screen', {})
            if screen:
                logger.info(f"[🖥️] Экран: ярк={screen.get('brightness',0):.2f}, движ={screen.get('motion',0):.2f}, энтр={screen.get('entropy',0):.2f}")

            # --- Агрегированные метрики аудиоустройств ---
            audio_devices_info = metrics.get('audio_devices', {'devices': [], 'changes': []})
            audio_devices_list = audio_devices_info.get('devices', [])
            audio_changes = audio_devices_info.get('changes', [])
            active_inputs = sum(1 for d in audio_devices_list if d['type'] == 'input' and d.get('is_enabled', False))
            active_outputs = sum(1 for d in audio_devices_list if d['type'] == 'output' and d.get('is_enabled', False))
            output_volumes = [d['volume'] for d in audio_devices_list if d['type'] == 'output' and d.get('volume') is not None]
            avg_output_volume = np.mean(output_volumes) if output_volumes else 0.0
            if audio_changes:
                logger.debug(f"Аудиоизменения: {len(audio_changes)} событий")

            # --- Фьюжн данных ---
            try:
                d_data = {}
                if os.path.exists(DEVICE_DATA_FILE):
                    with open(DEVICE_DATA_FILE, 'r', encoding='utf-8') as f:
                        d_data = json.load(f)
                if isinstance(d_data, dict) and "data" in d_data:
                    d_data["data"]["pc_gpu_load"] = gpu_load
                    d_data["data"]["pc_gpu_temp"] = gpu_temp
                    d_data["data"]["pc_cpu_load"] = cpu_load
                elif isinstance(d_data, dict):
                    d_data["pc_gpu_load"] = gpu_load
                    d_data["pc_gpu_temp"] = gpu_temp
                    d_data["pc_cpu_load"] = cpu_load
                tmp = DEVICE_DATA_FILE + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(d_data, f)
                os.replace(tmp, DEVICE_DATA_FILE)
            except Exception:
                pass

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

            # --- Обновление мета-цели Януса ---
            meta_goal.update(rpg_state, world.memory)

            # --- Генерация кандидатов от оптимизаторов ---
            candidates = []

            tachyon_config = None
            step_for_pred = step_t if step_t is not None else None
            use_mi = (random.random() < 0.3) and old_tachyon.trained_mi
            tachyon_config = old_tachyon.propose_future(memory, samples=10, step_time=step_for_pred, use_mi=use_mi)
            if tachyon_config:
                candidates.append((tachyon_config, 'tachyon', None))
                logger.info(f"⚡ Tachyon предложил конфигурацию (режим {'MI' if use_mi else 'score'})")

            if random.random() < 0.2:
                physarum_config = physarum.propose(memory)
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
                # Используем тахионную версию ask
                cand = bayes.ask_tachyonic(mood_acq)   # заменено на ask_tachyonic
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

            config = config.copy()
            config['batch_size'] = batch_size
            config['half_life_steps'] = HALF_LIFE_STEPS
            config['lr_decay_enable'] = LR_DECAY_ENABLE

            # ========== ИСПРАВЛЕНИЕ: фильтр 37 ==========
            # Применяем фильтр 37: вычисляем вес резонанса и добавляем в конфигурацию
            if FILTER_37_ENABLED:
                config['resonance_weight'] = filter_hyperparams(config)
            # ============================================

            # --- СОЗДАНИЕ АГЕНТА В MMO-МИРЕ ---
            logger.info("Создание агента в мире...")
            # Дополнительная защита: если config вдруг не словарь, превращаем в пустой
            if not isinstance(config, dict):
                logger.error(f"[ERROR] config has type {type(config).__name__}, expected dict. Using empty config.")
                config = {}
            base_agent = world.spawn_agent(config)

            # Проверяем наличие arch_genome, создаём если отсутствует или None
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

            # --- Генерация данных ---
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
                save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs)
                continue

            # --- Обучение ---
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

            success_count = res[0]
            do_detailed_log = success_count > 0

            if do_detailed_log:
                logger.info("-" * 70)
                if pause > 0:
                    logger.info(f"▶️ CYCLE {cycle} | [🧠 СИМБИОЗ] Архитектор активен (GPU: {gpu_load:.0f}%, iGPU: {igpu_load:.0f}%, Cache Ratio: {cache_ratio:.2f})")
                    logger.info(f"   Batch: {batch_size}, Сидов: {seeds_this_cycle}, Пауза: {pause:.2f}с")
                else:
                    logger.info(f"▶️ CYCLE {cycle} | [🔥 ДОМИНАЦИЯ] Система свободна (GPU: {gpu_load:.0f}%, Cache Ratio: {cache_ratio:.2f})")
                    logger.info(f"   Batch: {batch_size}, Сидов: {seeds_this_cycle}")
                logger.info("-" * 70)
                logger.info(f"⚙️ Архитектура: n_embd={config_to_train['n_embd']}, n_head={config_to_train['n_head']}, n_layer={config_to_train['n_layer']}")
                logger.info(f"⚙️ Параметры: lr={config_to_train['lr']:.6f}, gain={config_to_train['gain']:.3f}, temp={config_to_train['temperature']:.3f}")
                logger.info(f"🌍 Реальные данные: {train_tensor.shape} | Источники: unknown: 1")
                logger.info(f"🌍 Реальные данные: {val_tensor.shape} | Источники: unknown: 1")
                logger.info(f"🛡️ TrainHash={train_hash} | ValHash={val_hash}")

            if success_count == 0:
                failed_configs.append(config)
                memory.register_lesson(config)
                hrain_daemon.send_event({"type": "learning_challenge", "cycle": cycle, "config": config})
                if do_detailed_log:
                    logger.info("💥 УРОК: Эта конфигурация оказалась сложной. Запомним.")
                if GAMING_MODE:
                    event_type, combat_log, desc = interpret_metrics({"lethal": True, "loss": None}, rpg_state)
                    if do_detailed_log:
                        for line in combat_log:
                            logger.info(f"     {line}")
                save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs,
                                        pred_score, velocity, acceleration)
                with open(RPG_STATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(rpg_state.to_dict(), f, ensure_ascii=False, indent=2)
                await asyncio.sleep(max(pause, 2.0))
                continue

            score, val_loss, div, mi, train_loss_avg, gn_min, gn_max, gn_mean, w_norm, vram, step_t, best_state = res[1:]

            if not is_valid_metrics(score, val_loss, div, mi, gn_mean):
                await asyncio.sleep(pause)
                continue

            gap = train_loss_avg - val_loss
            pred_score, pred_mi, velocity, acceleration = tachyon_field.step(score, mi)

            thermal.add_observation(gpu_temp, score, gpu_load, user_activity)

            # --- НАГРАДА АГЕНТА В МИРЕ ---
            logger.info("Награда агенту...")
            world.reward_agent(agent, score)

            if score > memory.hope_score * 0.8:
                social_engine.add_success(agent)

            # ==========================================
            # ☢️ ЯДЕРНЫЙ ЦИКЛ
            # ==========================================
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

            if do_detailed_log:
                logger.info(f"📊 ВЫЖИВАЕМОСТЬ: {success_count}/{seeds_this_cycle} потоков")
                origin = "МУТАЦИЯ" if source == 'swarm' else ("БАЙЕС" if source == 'bayes' else ("ТАХИОН" if source == 'tachyon' else ("ФИЗАРИУС" if source == 'physarum' else ("СОЦИАЛЬНОЕ" if source == 'social' else "СЛУЧАЙНО"))))
                logger.info(f"🧬 ПРОИСХОЖДЕНИЕ: {origin}")
                logger.info(f"📈 Score: {score:.4f} | Loss: {val_loss:.4f} | MI: {mi:.4f} | Div: {div:.3f} | Gap: {gap:.4f}")
                logger.info(f"📉 Градиенты: min={gn_min:.3f}, max={gn_max:.3f}, mean={gn_mean:.3f}")
                logger.info(f"🛠️ VRAM={vram:.0f} MB | Step={step_t:.2f} ms")
                logger.info(f"🔮 ТАХИОН: Pred={pred_score:.4f} | V={velocity:.5f} | A={acceleration:.5f}")
                logger.info(f"🎤 Аудио: входов={active_inputs}, выходов={active_outputs}, ср.громк={avg_output_volume:.2f}, изменений={len(audio_changes)}")
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
                    world_metrics = {
                        "loss": val_loss,
                        "prev_loss": last_score,
                        "best_score": best_score,
                        "pred_score": pred_score,
                        "mi": mi,
                        "gap": gap,
                        "anomaly": False
                    }
                    logger.info("Вызов genesis_protocol.auto_update_world...")
                    world_lines = genesis_protocol.auto_update_world(world_metrics, rpg_state)
                    if do_detailed_log:
                        for line in world_lines:
                            logger.info(line)

                if do_detailed_log:
                    exp_needed = rpg_state.level * 100
                    exp_percent = (rpg_state.exp / exp_needed) * 100 if exp_needed > 0 else 0
                    limb_status = ", ".join([f"{l.type[:2]}={l.status[0]}" for l in rpg_state.limbs[:3]])
                    logger.info(f"     ❤️ {rpg_state.health}/{rpg_state.max_health} | 💙 {rpg_state.mana}/{rpg_state.max_mana} | ⭐ Ур.{rpg_state.level} | 🧪 {exp_percent:.1f}% | 💰 {rpg_state.gold}")
                    logger.info(f"     📍 {rpg_state.current_location} | 🐜 Мобов: {len(rpg_state.swarm)} | 🏰 База ур.{rpg_state.base_level} | 🦿 {limb_status}")

            # --- Обновление глобального смысла ---
            world.meaning.update()

            # --- Цикл сознательных агентов ---
            for a in world.population:
                if hasattr(a, 'brain'):
                    brain = a.brain
                    brain.think(world)
                    action = brain.decide()
                    explanation = brain.explain()
                    logger.info(f"🤖 {a.id[:4]} -> {action} | {explanation}")
                    brain.learn("success" if random.random() > 0.3 else "failure")

            # --- Самоанализ Януса ---
            world.meta.observe(score)
            state_analysis = world.meta.analyze()
            if state_analysis == "crisis":
                logger.warning("⚠️ SYSTEM CRISIS DETECTED")
            elif state_analysis == "growth":
                logger.info("🚀 CIVILIZATION GROWING")

            # --- ПРЕДСКАЗАНИЕ МИРА (старый Tachyon) ---
            world_prediction = old_tachyon.predict_world(world)
            rpg_state.perceive_future(world_prediction)

            # --- RL: сохраняем состояние до действия ---
            prev_state = rpg_state.copy()

            # --- ВЫБОР ДЕЙСТВИЯ: гибрид RL + Tachyon ---
            actions = core_rl.available_actions()
            # RL предлагает действие
            rl_action = core_rl.select_action(rpg_state)
            # Tachyon оценивает все действия
            tachyon_scores = tachyon.evaluate_actions(rpg_state, actions)
            # Гибрид: выбираем действие, максимизирующее сумму Q и оценки Tachyon
            hybrid_scores = {}
            s_enc = core_rl.encode_state(rpg_state)
            for a in actions:
                hybrid_scores[a] = core_rl.Q[s_enc][a] + tachyon_scores.get(a, 0)
            action = max(hybrid_scores, key=hybrid_scores.get)

            logger.info(f"🜏 JANUS выбирает действие: {action} (RL: {rl_action}, Tachyon: {max(tachyon_scores, key=tachyon_scores.get)})")

            # --- ПРИМЕНЯЕМ ДЕЙСТВИЕ ЧЕРЕЗ СРЕДУ ---
            env_world.step(rpg_state, action)

            # --- ОБУЧЕНИЕ RL ---
            core_rl.update(prev_state, action, rpg_state)

            # --- БОЖЕСТВЕННЫЕ ЗАКОНЫ (если нужно) ---
            if action == "EXPAND":
                world.laws.declare_event("GROWTH")
            elif action == "REWRITE":
                world.laws.reset_zone()

            # --- ГОЛОС ЯНУСА (периодически) ---
            if random.random() < 0.05 and rpg_state.self_model["aware"]:
                rpg_state.voice.speak(rpg_state, world_prediction)

            # --- Сохранение результатов ---
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
                'nuclear_mode': 'enrichment' if (last_score is not None and velocity < 0.05 and score < best_score * 0.9) else ('depletion' if (last_score is not None and score > best_score * 0.95 and abs(distance_to_best) < 0.1) else 'neutral')
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

            if ADAPTIVE_TEST_ENABLED and best_state is not None:
                try:
                    logger.info("Запуск адаптивного теста...")
                    test_model = AdaptiveTransformer(config_to_train['n_embd'], config_to_train['n_head'], config_to_train['n_layer']).to(DEVICE)
                    test_model.load_state_dict(best_state)
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

            # ========== НОВЫЕ МОНИТОРЫ ==========
            if tachyonic_monitor.update(score):
                logger.info("🜏 [777] ТАХИОННЫЙ РЕЗОНАНС! Усиление обучения.")
                # Увеличиваем exploration, чтобы исследовать новые области
                memory.strategy["exploration"] = min(0.9, memory.strategy["exploration"] + 0.1)

            if pocket_detector.update(score, val_loss):
                logger.warning("⚠️ [КАРМАН] Обнаружено зацикливание. Сброс региона поиска.")
                # Добавляем текущую конфигурацию в failed_configs
                failed_configs.append(config)
                # Увеличиваем exploration
                memory.strategy["exploration"] = min(0.9, memory.strategy["exploration"] + 0.1)

            # ========== СОХРАНЕНИЕ СНЭПШОТОВ РЕЕСТРА ==========
            if cycle % REGISTRY_SNAPSHOT_INTERVAL == 0:
                registry_data = {
                    "timestamp": datetime.now().isoformat(),
                    "cycle": cycle,
                    "best_score": best_score,
                    "last_score": score,
                    "config": config,
                    "resonance": tachyonic_monitor.resonant,
                    "pocket_detected": bool(pocket_detector.pockets),
                    "failed_configs_count": len(failed_configs)
                }
                registry_path = os.path.join(WORMHOLE_DIR, f"janus_registry_{cycle}.json")
                with open(registry_path, 'w') as f:
                    json.dump(registry_data, f, indent=2)

            # ========== ОСТАЛЬНОЙ КОД (без изменений) ==========

            if score > best_score:
                best_score = score
                best_cycle = cycle
                if do_detailed_log:
                    logger.info(f"🏆 НОВЫЙ РЕКОРД: {best_score:.4f} (цикл {best_cycle})")
                hrain_daemon.send_event({"type": "record", "cycle": cycle, "score": score})

                task = asyncio.create_task(visionary.on_event("RECORD", {
                    "agent": agent.id[:8] if agent else "unknown",
                    "score": score
                }, world))
                active_tasks.append(task)
                task.add_done_callback(lambda t: active_tasks.remove(t) if t in active_tasks else None)

                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("record")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])

            hrain_daemon.send_event({"type": "cycle", "cycle": cycle, "score": score, "val_loss": val_loss, "mi": mi, "div": div})

            if is_breakthrough and best_state is not None:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(MODEL_ZOO_DIR, f"janus_breakthrough_{ts}_C{cycle}_S{score:.4f}.pt")
                torch.save({'model_state': best_state, 'config': config, 'score': score, 'cycle': cycle, 'additional': additional}, path)
                if do_detailed_log:
                    logger.info(f"💾 Геном сохранён: {path}")

            # --- Обновление веры агентов и влияние культов ---
            belief_system.update(world.population, meta_goal)
            cult_engine.update(env_world)   # культы влияют на параметры среды (economy, chaos и т.д.)

            env.update_complexity(score)
            last_score, last_mi = score, mi

            # --- Самоэволюция Януса (каждые 50 циклов) ---
            if cycle % 50 == 0:
                new_core, improved = auto_evo.evolve(core_rl, rpg_state, env_world)
                if improved:
                    core_rl = new_core
                    logger.info("🧬 ЯНУС ЭВОЛЮЦИОНИРОВАЛ: новые гиперпараметры")
                    janus_db.insert_genesis_event("EVOLUTION", "Янус улучшил свои параметры обучения")

            save_homeostatic_state(cycle, last_score, last_mi, best_score, failed_configs,
                                    pred_score, velocity, acceleration)

            with open(RPG_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(rpg_state.to_dict(), f, ensure_ascii=False, indent=2)

            pc_metrics = {'gpu_temp': gpu_temp, 'gpu_load': gpu_load, 'cpu_load': cpu_load}
            cardputer_metrics = {}
            world.update(pc_metrics=pc_metrics, cardputer_metrics=cardputer_metrics)

            # ========== ВЫЗОВЫ НОВЫХ МОДУЛЕЙ ==========
            # Обновление рынка
            if hasattr(world, 'market') and hasattr(world.market, 'update_tick'):
                world.market.update_tick()

            # Культурный декаданс
            cultural_decadence.update()

            # Интегратор модулей (вызов update всех найденных модулей)
            integrator.update()

            # Манки-патчер (раз в 100 циклов)
            if cycle % 100 == 0:
                patcher.update()

            # Matrix Engine – адаптация интенсивности
            if matrix_engine and MATRIX_MODE:
                # Оценка FPS игры (можно передать из game_detector)
                fps_estimate = None
                if monitor and hasattr(monitor, 'get_game_fps'):
                    fps_estimate = monitor.get_game_fps()
                matrix_engine.update_intensity(fps_estimate)

            # Tachyon Evolution – выбор лучшего стратегического действия
            if cycle % 20 == 0:
                possible_actions = ["boost_economy", "spawn_resource", "encourage_raids", "promote_trade"]
                best_action = tachyon_evolution.choose_best_action(possible_actions)
                if best_action:
                    logger.info(f"⚡ Tachyon Evolution выбрал действие: {best_action}")
                    # Применяем выбранное действие через meta_engine (если есть executor)
                    if hasattr(meta_engine, 'executor'):
                        meta_engine.executor.execute(best_action, world)
                    else:
                        # fallback: прямое выполнение
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

            # ========== КОНЕЦ ВЫЗОВОВ НОВЫХ МОДУЛЕЙ ==========

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
                task = asyncio.create_task(visionary.on_event("EXTINCTION", {"species": extinct}, world))
                active_tasks.append(task)
                task.add_done_callback(lambda t: active_tasks.remove(t) if t in active_tasks else None)

                if monitor.screen_monitor:
                    snap_meta = monitor.screen_monitor.get_snapshot_metadata("extinction")
                    janus_db.insert_screen_snapshot(snap_meta['reason'], snap_meta['brightness'],
                                                     snap_meta['motion'], snap_meta['entropy'],
                                                     snap_meta['histogram'])
            if len(species_engine.species_list) < 3:
                new_sp = species_engine.spawn_new_species()
                logger.info(f"🆕 Появился новый вид: {new_sp.name}")
                task = asyncio.create_task(visionary.on_event("NEW_SPECIES", {
                    "name": new_sp.name,
                    "arch_type": new_sp.arch_type
                }, world))
                active_tasks.append(task)
                task.add_done_callback(lambda t: active_tasks.remove(t) if t in active_tasks else None)

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

            # --- Нарратив о доминирующей вере (каждые 10 циклов) ---
            if cycle % 10 == 0:
                from janus_narrative import narrate_beliefs
                narrate_beliefs(belief_system)

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
        # Сохраняем состояние мониторов (опционально)
        monitor_state = {
            "resonance_hits": tachyonic_monitor.resonance_hits,
            "resonant": tachyonic_monitor.resonant,
            "pockets": pocket_detector.pockets
        }
        with open(os.path.join(WORMHOLE_DIR, "monitor_state.json"), 'w') as f:
            json.dump(monitor_state, f)
        # Сохраняем состояние интегратора (с проверкой)
        if 'integrator' in locals() and integrator:
            try:
                integrator.save_state(os.path.join(WORMHOLE_DIR, "module_integrator_state.json"))
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния интегратора: {e}")
        # Сохраняем состояние патчера (с проверкой)
        if 'patcher' in locals() and patcher:
            try:
                patcher_state = patcher.save_state()
                with open(os.path.join(WORMHOLE_DIR, "monkey_patcher_state.json"), 'w') as f:
                    json.dump(patcher_state, f)
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния патчера: {e}")
        # Останавливаем Matrix Engine
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