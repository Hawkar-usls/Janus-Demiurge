import os
import torch

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"[⚡ ENGINE] Инициализация на {DEVICE}")

# ========== ПАРАМЕТРЫ ОБУЧЕНИЯ ==========
VOCAB_SIZE = 257
TRAIN_SIZE = 5003
VAL_SIZE = 1009
STEPS_PER_CYCLE = 1999
SEEDS_PER_CYCLE = 2
BASE_BATCH_SIZE = 128
BLOCK_SIZE = 32

# Архитектурные варианты (расширены)
N_EMBD_OPTIONS = [128, 256, 384, 512, 768]
N_HEAD_OPTIONS = [4, 8, 12, 16]
N_LAYER_RANGE = [4, 6, 8, 10, 12]

# Гиперпараметры
LR_RANGE = (1e-5, 1e-2)
GAIN_RANGE = (0.3, 2.0)
TEMP_RANGE = (0.3, 2.0)
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
# Роевой интеллект
SWARM_ENABLED = True
SWARM_SIZE = 5
SWARM_INERTIA = 0.7
SWARM_COGNITIVE = 1.5
SWARM_SOCIAL = 1.5

# Байесовская оптимизация
BAYES_ENABLED = True
BAYES_INIT_POINTS = 5
BAYES_ACQ_FUNC = 'EI'          # может быть заменён на 'EI_tachyonic'

# Мета-модель
META_ENABLED = True
META_UPDATE_INTERVAL = 50
META_SAMPLE_SIZE = 200

# Адаптивный тест
ADAPTIVE_TEST_ENABLED = True
ADAPTIVE_TEST_THRESHOLD = 8.0
ADAPTIVE_TEST_STEPS = 50

# Подсознание
SUBCONSCIOUS_ENABLED = True
CHRONOS_INTERVAL = 100
HYPNOS_INTERVAL = 50
NEBUCHAD_INTERVAL = 30
OUROBOROS_INTERVAL = 500

# ========== ПУТИ ==========
BASE_DIR = r"E:\Janus_BFaiN"
RAW_LOGS_DIR = os.path.join(BASE_DIR, "raw_logs")
MODEL_ZOO_DIR = os.path.join(BASE_DIR, "Model_Zoo")
WORMHOLE_DIR = os.path.join(BASE_DIR, "wormhole")

os.makedirs(RAW_LOGS_DIR, exist_ok=True)
os.makedirs(MODEL_ZOO_DIR, exist_ok=True)
os.makedirs(WORMHOLE_DIR, exist_ok=True)

SYSTEM_METRICS_LOG = os.path.join(RAW_LOGS_DIR, "system_metrics.json")
GPU_TICKET_PATH = os.path.join(RAW_LOGS_DIR, "gpu_ticket.json")

# ========== РЕЖИМ БЕРСЕРКА ==========
DEBUG_MODE = False
RESUME = False

# =================================================================
# НОВЫЕ РАЗДЕЛЫ: ПАРАДИГМА ЯНУСА-ТАХИОНА
# =================================================================

# ---------- 1. ФИЛЬТР 37 (Божественный закон) ----------
FILTER_37_ENABLED = True
# При выборе гиперпараметров: если значение не резонирует, его вес умножается на этот коэффициент
FILTER_37_WEIGHT = 0.5
# Для архитектурных параметров можно разрешить нерезонансные, но с пониженным приоритетом

def digital_root(n: int) -> int:
    """Цифровой корень числа (1-9)."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9

def is_resonant(value: int) -> bool:
    """Проверяет, резонирует ли число с фильтром 37: кратно 37 или цифровой корень = 3."""
    if not FILTER_37_ENABLED:
        return True
    return (value % 37 == 0) or (digital_root(value) == 3)

def filter_hyperparams(config: dict) -> float:
    """Возвращает вес (0..1), на который нужно умножить вероятность выбора конфигурации.
    Чем больше нерезонансных параметров, тем ниже вес.
    """
    if not FILTER_37_ENABLED:
        return 1.0
    params_to_check = ['n_embd', 'n_head', 'n_layer', 'batch_size', 'lr', 'gain', 'temperature']
    resonant_count = 0
    total_checked = 0
    for key in params_to_check:
        if key in config:
            val = config[key]
            if isinstance(val, (int, float)):
                # Для float: проверяем целую часть
                int_val = int(abs(val))
                if is_resonant(int_val):
                    resonant_count += 1
                total_checked += 1
    if total_checked == 0:
        return 1.0
    ratio = resonant_count / total_checked
    # Если все параметры резонансны, вес 1.0, иначе снижаем
    return ratio ** 2   # квадратичное падение

# ---------- 2. ТАХИОННЫЙ МОНИТОРИНГ (частотный резонанс) ----------
TACHYON_MONITOR_ENABLED = True
# Окно для подсчёта резонансных событий
TACHYON_MONITOR_WINDOW = 10
# Порог срабатывания резонанса (сколько попаданий в окне)
TACHYON_RESONANCE_THRESHOLD = 7
# Шкала перевода метрики в псевдочастоту (умножаем на этот коэффициент)
TACHYON_SCALE = 1000

# ---------- 3. ДЕТЕКТОР КАРМАНОВ (abuser pockets) ----------
POCKET_DETECTOR_ENABLED = True
POCKET_WINDOW = 20          # сколько последних циклов анализировать
POCKET_STD_THRESHOLD = 0.01 # стандартное отклонение score/loss, ниже которого считаем застой
# Если детектор сработал, конфигурация попадает в чёрный список на это количество циклов
POCKET_BLACKLIST_DURATION = 10

# ---------- 4. ТАХИОННАЯ ACQUISITION (для байесовской оптимизации) ----------
# Штраф за нерезонансную конфигурацию (доля, на которую уменьшается ожидаемое улучшение)
TACHYON_ACQ_PENALTY = 0.1
# Если acquisition = 'EI_tachyonic', используется модифицированная функция
BAYES_ACQ_FUNC = 'EI_tachyonic'   # меняем на кастомную

# ---------- 5. СОХРАНЕНИЕ СНЭПШОТОВ РЕЕСТРА ----------
REGISTRY_SNAPSHOT_INTERVAL = 10   # каждые N циклов
# Формат имени файла: registry_{cycle}.json

# ---------- 6. ДОПОЛНИТЕЛЬНЫЕ КОНСТАНТЫ ДЛЯ ГАРМОНИК ----------
HARMONIC_37_MULTIPLIER = 37
# Список резонансных архитектурных размеров (кратных 37 или с корнем 3)
RESONANT_EMBD_OPTIONS = [x for x in N_EMBD_OPTIONS if is_resonant(x)]  # 384? 384%37=14, корень 3? 3+8+4=15→6, нет
# Можно добавить вручную: 111, 222, 333, 444, 555, 666, 777, 888, 999
EXTRA_RESONANT_EMBD = [111, 222, 333, 444, 555, 666, 777, 888, 999]
# Объединяем, но оставляем исходные для совместимости
N_EMBD_OPTIONS_RESONANT = sorted(set(N_EMBD_OPTIONS + EXTRA_RESONANT_EMBD))

# ---------- 7. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОСНОВНОГО ЦИКЛА ----------
def apply_filter_to_candidates(candidates: list) -> list:
    """Принимает список кандидатов (каждый - dict конфигурации), возвращает список с весами."""
    if not FILTER_37_ENABLED:
        return [(c, 1.0) for c in candidates]
    weighted = []
    for cand in candidates:
        weight = filter_hyperparams(cand)
        if weight > 0.01:   # отсекаем совсем плохие
            weighted.append((cand, weight))
    # Нормализуем веса (опционально)
    return weighted

def is_tachyonic_resonance(metric: float, step: int, history: list) -> bool:
    """Проверяет, достигнут ли резонанс на основе истории метрики."""
    if not TACHYON_MONITOR_ENABLED:
        return False
    # Переводим метрику в псевдочастоту
    pseudo_freq = int(abs(metric * TACHYON_SCALE))
    dr = digital_root(pseudo_freq)
    if dr == 3:
        history.append(1)
    else:
        history.append(0)
    # Оставляем только последние TACHYON_MONITOR_WINDOW элементов
    if len(history) > TACHYON_MONITOR_WINDOW:
        history.pop(0)
    # Если сумма >= порога, резонанс достигнут
    return sum(history) >= TACHYON_RESONANCE_THRESHOLD

def detect_pocket(scores: list, losses: list) -> bool:
    """Проверяет, находится ли система в кармане (застое)."""
    if not POCKET_DETECTOR_ENABLED:
        return False
    if len(scores) < POCKET_WINDOW or len(losses) < POCKET_WINDOW:
        return False
    # Используем последние POCKET_WINDOW значений
    recent_scores = scores[-POCKET_WINDOW:]
    recent_losses = losses[-POCKET_WINDOW:]
    if np.std(recent_scores) < POCKET_STD_THRESHOLD and np.std(recent_losses) < POCKET_STD_THRESHOLD:
        return True
    return False

# Импортируем numpy только если нужно (для избежания зависимости в конфиге)
try:
    import numpy as np
except ImportError:
    # Если numpy нет, детектор карманов не будет работать
    def detect_pocket(scores, losses):
        return False
    print("[WARN] numpy не установлен, детектор карманов отключён")