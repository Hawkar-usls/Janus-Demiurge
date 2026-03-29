import sys
import io
import os
import torch
import numpy as np
import logging

# Устанавливаем кодировку stdout в UTF-8, чтобы избежать ошибок при выводе эмодзи
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==================== АВТООПРЕДЕЛЕНИЕ ЖЕЛЕЗА ====================
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"[⚡ ENGINE] Инициализация на {DEVICE}")

# ==================== ПАРАМЕТРЫ ОБУЧЕНИЯ ====================
VOCAB_SIZE = int(os.environ.get('JANUS_VOCAB_SIZE', 257))
TRAIN_SIZE = int(os.environ.get('JANUS_TRAIN_SIZE', 5003))
VAL_SIZE = int(os.environ.get('JANUS_VAL_SIZE', 1009))
STEPS_PER_CYCLE = int(os.environ.get('JANUS_STEPS_PER_CYCLE', 1999))
SEEDS_PER_CYCLE = int(os.environ.get('JANUS_SEEDS_PER_CYCLE', 2))
BASE_BATCH_SIZE = int(os.environ.get('JANUS_BASE_BATCH_SIZE', 128))
BLOCK_SIZE = int(os.environ.get('JANUS_BLOCK_SIZE', 32))

N_EMBD_OPTIONS = [128, 256, 384, 512, 768]
N_HEAD_OPTIONS = [4, 8, 12, 16]
N_LAYER_RANGE = [4, 6, 8, 10, 12]

LR_RANGE = (1e-5, 5e-3)          # уменьшен верхний порог
GAIN_RANGE = (0.5, 1.5)          # сужено для стабильности
TEMP_RANGE = (0.5, 1.5)          # сужено для стабильности
LR_DECAY_ENABLE = True
HALF_LIFE_STEPS = 1000

ALPHA = 0.1
BETA = 1.0
GAMMA = 0.5

# ========== АДАПТИВНОЕ УПРАВЛЕНИЕ ==========
ADAPTIVE_CONTROL = True
GPU_LOAD_THRESHOLD_HIGH = 80
GPU_LOAD_THRESHOLD_CRITICAL = 95
CPU_LOAD_THRESHOLD_HIGH = 80
MIN_BATCH_SIZE = 32
MAX_PAUSE = 5.0
POLL_INTERVAL = 2.0

# ========== ПАРАМЕТРЫ МОНИТОРИНГА ==========
CACHE_PROBE_INTERVAL = 3600
CACHE_PROBE_SIZE_MB = 50

# ========== ПАРАМЕТРЫ ЛОГИРОВАНИЯ ==========
LOG_INTERVAL = 5
LOG_ON_SUCCESS = True
LOG_FAILURE_SUMMARY = True
FAILURE_THRESHOLD = 3
GENESIS_AUTO_INTERVAL = 31

# ========== ПАРАМЕТРЫ НОВЫХ МОДУЛЕЙ ==========
SWARM_ENABLED = os.environ.get('JANUS_SWARM_ENABLED', '1') == '1'
SWARM_SIZE = int(os.environ.get('JANUS_SWARM_SIZE', 5))
SWARM_INERTIA = float(os.environ.get('JANUS_SWARM_INERTIA', 0.7))
SWARM_COGNITIVE = float(os.environ.get('JANUS_SWARM_COGNITIVE', 1.5))
SWARM_SOCIAL = float(os.environ.get('JANUS_SWARM_SOCIAL', 1.5))

BAYES_ENABLED = os.environ.get('JANUS_BAYES_ENABLED', '1') == '1'
BAYES_INIT_POINTS = int(os.environ.get('JANUS_BAYES_INIT_POINTS', 5))
BAYES_ACQ_FUNC = os.environ.get('JANUS_BAYES_ACQ_FUNC', 'EI')

META_ENABLED = os.environ.get('JANUS_META_ENABLED', '1') == '1'
META_UPDATE_INTERVAL = int(os.environ.get('JANUS_META_UPDATE_INTERVAL', 50))
META_SAMPLE_SIZE = int(os.environ.get('JANUS_META_SAMPLE_SIZE', 200))

ADAPTIVE_TEST_ENABLED = os.environ.get('JANUS_ADAPTIVE_TEST_ENABLED', '1') == '1'
ADAPTIVE_TEST_THRESHOLD = float(os.environ.get('JANUS_ADAPTIVE_TEST_THRESHOLD', 8.0))
ADAPTIVE_TEST_STEPS = int(os.environ.get('JANUS_ADAPTIVE_TEST_STEPS', 50))

SUBCONSCIOUS_ENABLED = os.environ.get('JANUS_SUBCONSCIOUS_ENABLED', '1') == '1'
CHRONOS_INTERVAL = int(os.environ.get('JANUS_CHRONOS_INTERVAL', 100))
HYPNOS_INTERVAL = int(os.environ.get('JANUS_HYPNOS_INTERVAL', 50))
NEBUCHAD_INTERVAL = int(os.environ.get('JANUS_NEBUCHAD_INTERVAL', 30))
OUROBOROS_INTERVAL = int(os.environ.get('JANUS_OUROBOROS_INTERVAL', 500))

# ========== КОНВЕРГЕНЦИЯ ==========
CONVERGENCE_ENABLED = os.environ.get('JANUS_CONVERGENCE_ENABLED', '1') == '1'
CONVERGENCE_WINDOW = int(os.environ.get('JANUS_CONVERGENCE_WINDOW', 100))

# ========== ПУТИ ==========
BASE_DIR = os.environ.get('JANUS_BASE_DIR', r"E:\Janus_BFaiN")
RAW_LOGS_DIR = os.path.join(BASE_DIR, "raw_logs")
MODEL_ZOO_DIR = os.path.join(BASE_DIR, "Model_Zoo")
WORMHOLE_DIR = os.path.join(BASE_DIR, "wormhole")

os.makedirs(RAW_LOGS_DIR, exist_ok=True)
os.makedirs(MODEL_ZOO_DIR, exist_ok=True)
os.makedirs(WORMHOLE_DIR, exist_ok=True)

SYSTEM_METRICS_LOG = os.path.join(RAW_LOGS_DIR, "system_metrics.json")
GPU_TICKET_PATH = os.path.join(RAW_LOGS_DIR, "gpu_ticket.json")

DEBUG_MODE = os.environ.get('JANUS_DEBUG', '0') == '1'
RESUME = os.environ.get('JANUS_RESUME', '0') == '1'

# ========== ФИЛЬТР 37 ==========
FILTER_37_ENABLED = os.environ.get('JANUS_FILTER_37', '1') == '1'
FILTER_37_WEIGHT = 0.5
TACHYON_MONITOR_ENABLED = True
TACHYON_MONITOR_WINDOW = 10
TACHYON_RESONANCE_THRESHOLD = 7
TACHYON_SCALE = 1000

POCKET_DETECTOR_ENABLED = True
POCKET_WINDOW = 20
POCKET_STD_THRESHOLD = 0.01

TACHYON_ACQ_PENALTY = 0.1
REGISTRY_SNAPSHOT_INTERVAL = 10
HARMONIC_37_MULTIPLIER = 37
EXTRA_RESONANT_EMBD = [111, 222, 333, 444, 555, 666, 777, 888, 999]
N_EMBD_OPTIONS_RESONANT = sorted(set(N_EMBD_OPTIONS + EXTRA_RESONANT_EMBD))

def digital_root(n: int) -> int:
    if n == 0:
        return 0
    return 1 + (n - 1) % 9

def is_resonant(value: int) -> bool:
    if not FILTER_37_ENABLED:
        return True
    return (value % 37 == 0) or (digital_root(value) == 3)

def filter_hyperparams(config: dict) -> float:
    if not FILTER_37_ENABLED:
        return 1.0
    params_to_check = ['n_embd', 'n_head', 'n_layer', 'batch_size', 'lr', 'gain', 'temperature']
    resonant_count = 0
    total_checked = 0
    for key in params_to_check:
        if key in config:
            val = config[key]
            if isinstance(val, (int, float)):
                int_val = int(abs(val))
                if is_resonant(int_val):
                    resonant_count += 1
                total_checked += 1
    if total_checked == 0:
        return 1.0
    ratio = resonant_count / total_checked
    return ratio ** 2

def apply_filter_to_candidates(candidates: list) -> list:
    if not FILTER_37_ENABLED:
        return [(c, 1.0) for c in candidates]
    weighted = []
    for cand in candidates:
        weight = filter_hyperparams(cand)
        if weight > 0.01:
            weighted.append((cand, weight))
    return weighted

def is_tachyonic_resonance(metric: float, step: int, history: list) -> bool:
    if not TACHYON_MONITOR_ENABLED:
        return False
    pseudo_freq = int(abs(metric * TACHYON_SCALE))
    dr = digital_root(pseudo_freq)
    if dr == 3:
        history.append(1)
    else:
        history.append(0)
    if len(history) > TACHYON_MONITOR_WINDOW:
        history.pop(0)
    return sum(history) >= TACHYON_RESONANCE_THRESHOLD

def detect_pocket(scores: list, losses: list) -> bool:
    if not POCKET_DETECTOR_ENABLED:
        return False
    if len(scores) < POCKET_WINDOW or len(losses) < POCKET_WINDOW:
        return False
    recent_scores = scores[-POCKET_WINDOW:]
    recent_losses = losses[-POCKET_WINDOW:]
    try:
        if np.std(recent_scores) < POCKET_STD_THRESHOLD and np.std(recent_losses) < POCKET_STD_THRESHOLD:
            return True
    except:
        pass
    return False

# ========== ТЕРМОДИНАМИКА И ТАХИОННАЯ ЧИСТОТА (FAHRENHEIT) ==========
THERMAL_MODE_FAHRENHEIT = True          # Принудительно используем F для гранулярности
TARGET_TEMP_F = 113.0                   # Цель: 45°C (Точка идеального метаболизма)
CRITICAL_TEMP_F = 176.0                 # Порог перегрева: 80°C

# Коэффициенты перевода (для внутреннего зеркала Януса)
C_TO_F_FACTOR = 1.8
C_TO_F_OFFSET = 32.0

# Параметры энтропии железа
HARDWARE_ENTROPY_ENABLED = True
ENTROPY_SAMPLE_WINDOW = 100             # Окно замера джиттера
PURITY_THRESHOLD_GOLD = 1500.0          # Порог для записи в Model_Zoo

# Награды (Oxytocin System)
OXYTOCIN_ENABLED = True
BASE_REWARD_SCALE = 1.0
COLD_EFFICIENCY_BONUS = 2.0             # Множитель наград при T < TARGET_TEMP_F

# ========== ГЕТЕРОГЕННЫЕ ВЫЧИСЛЕНИЯ (ORBIT SELECT) ==========
ADAPTIVE_DEVICE_SWITCH = True           # Разрешить Янусу прыгать между CPU и GPU
GPU_PURITY_BIAS = 1.2                   # GPU должен быть на 20% чище для переключения

# ========== ТЕРМОДИНАМИЧЕСКИЙ РЕЗОНАНС (37 + FAHRENHEIT) ==========

def get_thermal_resonance_weight(temp_f: float, purity: float) -> float:
    """
    Вычисляет множитель удачи на основе резонанса температуры и числа 37.
    Возвращает коэффициент, который можно использовать как дополнительный
    множитель награды или веса решения.
    """
    if not FILTER_37_ENABLED:
        return 1.0

    # 1. Проверка резонанса температуры (целое число Фаренгейтов)
    temp_int = int(abs(temp_f))
    is_temp_resonant = (temp_int % 37 == 0) or (digital_root(temp_int) == 3)

    # 2. Базовый множитель от чистоты (Purity)
    # Чем выше Purity, тем сильнее отклик резонанса
    purity_boost = np.log1p(purity / 100.0)

    # 3. Результирующий вес (Сингулярность)
    # Если температура резонирует с 37, умножаем на HARMONIC_37_MULTIPLIER (37)
    if is_temp_resonant:
        resonance_weight = HARMONIC_37_MULTIPLIER * purity_boost
        # Логирование (будет видно в логах Януса)
        logger = logging.getLogger("JANUS")
        logger.info(f"🌀 [RESONANCE] Температура {temp_int}F вошла в фазу с 37! Boost: {resonance_weight:.2f}")
    else:
        resonance_weight = purity_boost

    return resonance_weight

def apply_tachyonic_filter(config: dict, temp_f: float, purity: float) -> float:
    """
    Объединённый фильтр: параметры (37) * температура (37) * чистота.
    Возвращает коэффициент для награды Агентов и веса в Model_Zoo.
    """
    base_filter = filter_hyperparams(config)
    thermal_res = get_thermal_resonance_weight(temp_f, purity)
    return base_filter * thermal_res

# Небольшая вспомогательная функция для преобразования
def celsius_to_fahrenheit(temp_c: float) -> float:
    return temp_c * C_TO_F_FACTOR + C_TO_F_OFFSET

def fahrenheit_to_celsius(temp_f: float) -> float:
    return (temp_f - C_TO_F_OFFSET) / C_TO_F_FACTOR

# ========== ДОПОЛНИТЕЛЬНЫЙ ЛОГГЕР ДЛЯ КОНФИГА (чтобы не было ошибок) ==========
# Инициализируем логгер, если он ещё не создан
if 'logger' not in locals():
    logger = logging.getLogger("JANUS")
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)
