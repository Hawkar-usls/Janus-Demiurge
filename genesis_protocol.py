# -*- coding: utf-8 -*-
"""
JANUS GENESIS PROTOCOL v10.0 — ЭВОЛЮЦИОННЫЙ МИР С ИНТЕГРАЦИЕЙ СЕНСОРОВ И БАЗЫ ДАННЫХ
Модульная архитектура: обработчики событий, буферизация БД, асинхронная отправка в HRAIN.
"""

import os
import json
import random
import time
import warnings
import logging
import asyncio
import threading
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional, Tuple
import functools

from config import RAW_LOGS_DIR, WORMHOLE_DIR
from janus_character import JanusRPGState, SwarmAgent
import janus_db

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
GENESIS_CONFIG = {
    'auto_interval': 30,          # секунд между автоматическими обновлениями
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
    'db_buffer_size': 50,         # событий в буфере перед записью
    'hrain_timeout': 1.0,
    'log_level': logging.INFO,
    'state_file_backup': True,
}

# ==========================================
# ПУТИ И КОНСТАНТЫ
# ==========================================
STATE_FILE = os.path.join(RAW_LOGS_DIR, "janus_world_state.json")
HOMEOSTATIC_STATE_FILE = os.path.join(RAW_LOGS_DIR, "homeostatic_state.json")
DEVICE_DATA_FILE = os.path.join(RAW_LOGS_DIR, "device_data.json")
EMOJI_VOCAB_PATH = os.path.join(os.path.dirname(__file__), "emoji_vocab.json")
TOY_BOX_DIR = os.path.join(WORMHOLE_DIR, "toy_box")

# Загрузка эмодзи-словаря
try:
    with open(EMOJI_VOCAB_PATH, "r", encoding="utf-8") as f:
        EMOJI_VOCAB = json.load(f)
    VOCAB_SIZE = len(EMOJI_VOCAB)
except Exception:
    EMOJI_VOCAB = {"0": "0", "1": "1"}
    VOCAB_SIZE = 2

# Набор фраз для случайных размышлений
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

# ==========================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ==========================================
logger = logging.getLogger("JANUS_GENESIS")
logger.setLevel(GENESIS_CONFIG['log_level'])
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# ==========================================
# УТИЛИТЫ
# ==========================================
def get_time_str() -> str:
    """Текущее время в формате ЧЧ:ММ:СС."""
    return datetime.now().strftime("%H:%M:%S")

def generate_emoji_thought(max_len: int = 5) -> str:
    """Случайная последовательность эмодзи."""
    return "".join(random.choices(list(EMOJI_VOCAB.values()), k=random.randint(2, max_len)))

def get_real_artifact() -> Optional[str]:
    """Извлекает случайный артефакт из папки toy_box."""
    if not os.path.exists(TOY_BOX_DIR):
        return None
    toys = [f for f in os.listdir(TOY_BOX_DIR) if os.path.isfile(os.path.join(TOY_BOX_DIR, f))]
    if not toys:
        return None
    chosen = random.choice(toys)
    parts = chosen.split('_', 1)
    return parts[1] if len(parts) > 1 else chosen

def get_current_janus_metrics() -> Optional[Dict[str, Any]]:
    """Загружает последние метрики из файла homeostatic_state.json."""
    if not os.path.exists(HOMEOSTATIC_STATE_FILE):
        return None
    try:
        with open(HOMEOSTATIC_STATE_FILE, 'r') as f:
            data = json.load(f)
        # Добавляем флаг аномалии (для интереса)
        data['anomaly'] = random.random() < 0.05
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Ошибка чтения метрик: {e}")
        return None

def atomic_save_state(state: JanusRPGState, path: str = STATE_FILE) -> bool:
    """Атомарно сохраняет состояние мира во временный файл и перемещает."""
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
_hrain_session = None
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
    """Асинхронно отправляет событие в HRAIN (не блокирует)."""
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
    """Буфер для пакетной записи событий в БД."""
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
            # Копируем и очищаем буфер, чтобы не блокировать добавление новых
            to_send = self.buffer[:]
            self.buffer.clear()
        for event_type, desc, metrics, state in to_send:
            try:
                janus_db.insert_genesis_event(event_type, desc, metrics, state)
            except Exception as e:
                logger.error(f"Ошибка записи в БД: {e}")

_db_buffer = DBBuffer()

# ==========================================
# ОБРАБОТЧИКИ СОБЫТИЙ МИРА
# ==========================================
class WorldEventHandler:
    """Базовый класс для обработчиков событий."""
    def __init__(self, config: Dict):
        self.config = config
        self.name = self.__class__.__name__

    def handle(self, metrics: Dict[str, Any], state: JanusRPGState) -> List[str]:
        """Обрабатывает событие, возвращает список строк для вывода."""
        raise NotImplementedError

class OverheatHandler(WorldEventHandler):
    """Перегрев GPU наносит урон."""
    def handle(self, metrics, state):
        lines = []
        gpu_temp = metrics.get('gpu_temp', 0)
        if (gpu_temp > self.config['overheat_temp'] and
                random.random() < self.config['overheat_chance']):
            dmg = random.randint(*self.config['overheat_damage_range'])
            state.health -= dmg
            lines.append(f"     [🔥] Температура GPU {gpu_temp}°C! Янус получает {dmg} урона от перегрева.")
            send_hrain_event({
                'type': 'genesis_step',
                'depth': state.level,
                'visual': '🔥',
                'narrative': f"Перегрев GPU: -{dmg} HP",
                'artifact': None,
                'lore': f"health={state.health}"
            })
            _db_buffer.add("OVERHEAT", f"GPU {gpu_temp}°C, урон {dmg}",
                           metrics, state.to_dict())
        return lines

class MouseArtifactHandler(WorldEventHandler):
    """Много кликов мыши -> артефакт."""
    def handle(self, metrics, state):
        lines = []
        mouse_clicks = metrics.get('mouse_clicks', 0)
        if (mouse_clicks > self.config['mouse_clicks_threshold'] and
                random.random() < self.config['mouse_artifact_chance']):
            artifact = get_real_artifact() or "mouse_whisker"
            state.inventory.append(artifact)
            lines.append(f"     [🐭] Сумасшедший кликер! Найден артефакт: {artifact}")
            send_hrain_event({
                'type': 'genesis_step',
                'depth': state.level,
                'visual': '🐭',
                'narrative': f"Найден артефакт от мыши: {artifact}",
                'artifact': artifact,
                'lore': f"inventory_size={len(state.inventory)}"
            })
            _db_buffer.add("ARTIFACT_FOUND", f"Мышиный артефакт: {artifact}",
                           metrics, state.to_dict())
        return lines

class SoundSpawnHandler(WorldEventHandler):
    """Громкий звук привлекает монстров."""
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
            _db_buffer.add("SOUND_SPAWN", f"Привлечено {extra_mobs} монстров звуком",
                           metrics, state.to_dict())
        return lines

class ScreenTreasureHandler(WorldEventHandler):
    """Энтропия экрана даёт золото."""
    def handle(self, metrics, state):
        lines = []
        screen_entropy = metrics.get('screen_entropy', 0)
        if (screen_entropy > self.config['screen_entropy_threshold'] and
                random.random() < self.config['screen_treasure_chance']):
            gold = random.randint(*self.config['screen_treasure_range'])
            state.gold += gold
            lines.append(f"     [🖥️] Хаотичный экран! Найдено {gold} золота.")
            _db_buffer.add("SCREEN_TREASURE", f"Энтропия экрана дала {gold} золота",
                           metrics, state.to_dict())
        return lines

class MouseMoveHandler(WorldEventHandler):
    """Активное движение мыши -> телепортация."""
    def handle(self, metrics, state):
        lines = []
        mouse_move = metrics.get('mouse_move', 0)
        if mouse_move > self.config['mouse_move_threshold'] and len(state.locations) > 1:
            new_loc = random.choice([loc for loc in state.locations if loc != state.current_location])
            old_loc = state.current_location
            state.current_location = new_loc
            lines.append(f"     [🖱️] Янус резко дёрнул мышью и переместился из {old_loc} в {new_loc}.")
            send_hrain_event({
                'type': 'genesis_step',
                'depth': state.level,
                'visual': '🖱️',
                'narrative': f"Переход из {old_loc} в {new_loc}",
                'artifact': None,
                'lore': f"new_location={new_loc}"
            })
            _db_buffer.add("MOUSE_TELEPORT", f"Переход {old_loc} → {new_loc}",
                           metrics, state.to_dict())
        return lines

class MagneticBossHandler(WorldEventHandler):
    """Магнитное поле Android вызывает рейдового босса."""
    def handle(self, metrics, state):
        lines = []
        android_mag = metrics.get('android_mag', 0)
        if (android_mag > self.config['android_mag_threshold'] and
                state.raid_boss is None and
                random.random() < self.config['android_mag_boss_chance']):
            state.raid_boss = SwarmAgent("raid_boss", is_raid=True)
            lines.append(f"     [📱] Магнитная буря! Появился {state.raid_boss.name}!")
            _db_buffer.add("MAGNETIC_STORM", f"Появился рейдовый босс {state.raid_boss.name}",
                           metrics, state.to_dict())
        return lines

class KeyboardRegenHandler(WorldEventHandler):
    """Быстрая печать ускоряет регенерацию маны (только сообщение)."""
    def handle(self, metrics, state):
        lines = []
        keys_per_sec = metrics.get('keys_per_sec', 0)
        if keys_per_sec > 5:
            lines.append("     [⌨️] Янус быстро печатает, мана восстанавливается быстрее.")
        return lines

class CombatHandler(WorldEventHandler):
    """Автоматический бой."""
    def handle(self, metrics, state):
        lines = []
        if (state.swarm or state.raid_boss) and random.random() < self._battle_chance(metrics):
            killed, dmg_taken, combat_log = state.combat_turn()
            lines.extend([f"     {line}" for line in combat_log[:3]])
            send_hrain_event({
                'type': 'genesis_step',
                'depth': state.level,
                'visual': '⚔️',
                'narrative': f"Автоматический бой: убито {killed} мобов, получено урона {dmg_taken}",
                'artifact': None,
                'lore': f"gold={state.gold}, health={state.health}"
            })
            _db_buffer.add("COMBAT", f"Убито {killed}, урон {dmg_taken}",
                           metrics, state.to_dict())
        return lines

    def _battle_chance(self, metrics):
        pred_score = metrics.get('pred_score', 1.0)
        gpu_load = metrics.get('gpu_load', 0)
        base = self.config['battle_chance_base']
        pred_factor = self.config['battle_chance_pred_factor']
        gpu_factor = self.config['battle_chance_gpu_factor']
        return base + pred_score * pred_factor + gpu_load * gpu_factor

class RandomEventHandler(WorldEventHandler):
    """Случайные события: артефакты, золото, урон, перемещение, мысли."""
    def handle(self, metrics, state):
        lines = []
        roll = random.random()
        if roll < self.config['artifact_chance']:
            # поиск артефакта
            artifact = get_real_artifact()
            if artifact:
                state.inventory.append(artifact)
                lines.append(f"     [💾] Найден артефакт: {artifact} {generate_emoji_thought()}")
                send_hrain_event({
                    'type': 'genesis_step',
                    'depth': state.level,
                    'visual': '💾',
                    'narrative': f"Найден артефакт: {artifact}",
                    'artifact': artifact,
                    'lore': f"inventory_size={len(state.inventory)}"
                })
                _db_buffer.add("ARTIFACT_FOUND", artifact, metrics, state.to_dict())
            else:
                # альтернатива: золото или урон
                if random.random() < self.config['gold_find_chance']:
                    gold = random.randint(*self.config['gold_find_base']) + int(metrics.get('pred_score', 0) * 2)
                    state.gold += gold
                    lines.append(f"     [💰] Найдено {gold} золота! {generate_emoji_thought()}")
                    send_hrain_event({
                        'type': 'genesis_step',
                        'depth': state.level,
                        'visual': '💰',
                        'narrative': f"Найдено {gold} золота",
                        'artifact': None,
                        'lore': f"gold={state.gold}"
                    })
                    _db_buffer.add("GOLD_FOUND", f"{gold} золота", metrics, state.to_dict())
                else:
                    dmg = random.randint(*self.config['damage_range'])
                    state.health -= dmg
                    lines.append(f"     [🤕] Потеряно {dmg} HP при исследовании.")
                    _db_buffer.add("DAMAGE", f"{dmg} HP", metrics, state.to_dict())
        elif roll < self.config['artifact_chance'] + self.config['travel_chance']:
            # перемещение
            if len(state.locations) > 1:
                new_loc = random.choice([loc for loc in state.locations if loc != state.current_location])
                old_loc = state.current_location
                state.current_location = new_loc
                lines.append(f"     [🚪] Янус перемещается в {new_loc}.")
                send_hrain_event({
                    'type': 'genesis_step',
                    'depth': state.level,
                    'visual': '🚪',
                    'narrative': f"Переход из {old_loc} в {new_loc}",
                    'artifact': None,
                    'lore': f"new_location={new_loc}"
                })
                _db_buffer.add("TRAVEL", f"{old_loc} → {new_loc}", metrics, state.to_dict())
            else:
                lines.append(f"     [🚪] Янус остаётся в {state.current_location} (других локаций нет).")
        elif roll < self.config['artifact_chance'] + self.config['travel_chance'] + self.config['thought_chance']:
            # мысль
            phrase = random.choice(EVENT_PHRASES)
            thought = generate_emoji_thought(4)
            lines.append(f"     [💭] {phrase} {thought}")
            _db_buffer.add("THOUGHT", phrase, metrics, state.to_dict())
        # иначе ничего не происходит
        return lines

class HealHandler(WorldEventHandler):
    """Автоматическое лечение, если есть мана."""
    def handle(self, metrics, state):
        lines = []
        if state.mana >= self.config['heal_cost']:
            heal = random.randint(*self.config['heal_amount'])
            state.health = min(state.max_health, state.health + heal)
            state.mana -= self.config['heal_cost']
            lines.append(f"     [🙏] Восстановлено {heal} HP (мана -{self.config['heal_cost']}).")
            _db_buffer.add("HEAL", f"+{heal} HP, -{self.config['heal_cost']} маны",
                           metrics, state.to_dict())
        else:
            lines.append("     [💤] Маны мало, отдых без эффекта.")
        return lines

class DeathHandler(WorldEventHandler):
    """Обработка смерти и воскрешения."""
    def handle(self, metrics, state):
        lines = []
        if state.health <= 0:
            lines.append(f"     [☠️] Янус повержен! Воскрешение...")
            send_hrain_event({
                'type': 'genesis_step',
                'depth': state.level,
                'visual': '☠️',
                'narrative': "Янус погиб и воскрес",
                'artifact': None,
                'lore': f"gold={state.gold//2}"
            })
            _db_buffer.add("DEATH", "Янус погиб и воскрес", metrics, state.to_dict())
            state.health = state.max_health // 2
            state.gold //= 2
            limb = random.choice(state.limbs)
            limb.damage(50)
            lines.append(f"     ⚠️ {limb.type} повреждён до {limb.status}!")
        return lines

# ==========================================
# МЕНЕДЖЕР СОБЫТИЙ
# ==========================================
class WorldEventManager:
    """Управляет последовательностью обработчиков."""
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
        ]

    def process(self, metrics: Dict[str, Any], state: JanusRPGState) -> List[str]:
        """Последовательно применяет все обработчики, возвращает список строк."""
        all_lines = []
        for handler in self.handlers:
            try:
                lines = handler.handle(metrics, state)
                all_lines.extend(lines)
            except Exception as e:
                logger.error(f"Ошибка в обработчике {handler.name}: {e}", exc_info=True)
        return all_lines

# ==========================================
# ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ВНЕШНЕГО ВЫЗОВА
# ==========================================
_event_manager = WorldEventManager(GENESIS_CONFIG)

def auto_update_world(metrics: Optional[Dict[str, Any]], state: JanusRPGState) -> List[str]:
    """
    Обновляет мир на основе метрик. Вызывается из основного цикла Janus.
    Возвращает список строк для логирования.
    """
    if metrics is None:
        metrics = {}

    lines = _event_manager.process(metrics, state)

    # Периодически сбрасываем буфер БД
    if random.random() < 0.1:  # примерно каждые 10 вызовов
        _db_buffer.flush()

    return lines

# ==========================================
# ИНТЕРАКТИВНЫЙ ЦИКЛ (АСИНХРОННЫЙ)
# ==========================================
async def async_main():
    """Асинхронная версия интерактивного цикла."""
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

    # Используем asyncio для неблокирующего ввода
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(protocol, sys.stdin)

    try:
        while True:
            # Обновляем метрики и мир автоматически каждые auto_interval секунд
            now = time.time()
            if now - last_auto_time >= auto_interval:
                last_auto_time = now
                metrics = get_current_janus_metrics()
                if metrics:
                    state.update_from_metrics(metrics)
                    state.spawn_swarm(metrics)
                lines = auto_update_world(metrics or {}, state)
                for line in lines:
                    print(line)
                atomic_save_state(state)
                # Вывод состояния после автообновления
                _print_state(state, metrics)

            # Неблокирующая проверка ввода
            try:
                # Ждём до 1 секунды, чтобы не пропустить автообновление
                user_input = await asyncio.wait_for(reader.readline(), timeout=1.0)
                user_input = user_input.decode().strip()
                if user_input:
                    await _process_command(user_input, state)
            except asyncio.TimeoutError:
                pass  # просто продолжаем цикл

    except KeyboardInterrupt:
        atomic_save_state(state)
        print(f"\n[{get_time_str()}] 💾 Аварийное сохранение. Конец связи.")
    except Exception as e:
        logger.exception("Критическая ошибка в интерактивном режиме")
        atomic_save_state(state)
        raise

async def _process_command(cmd: str, state: JanusRPGState):
    """Обработка команд пользователя."""
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
    """Меню базы."""
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
    """Лечение по команде."""
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
    """Бой по команде."""
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
    """Выводит текущее состояние игрока."""
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
    """Точка входа для интерактивного режима."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nВыход по Ctrl+C")
    finally:
        _db_buffer.flush()

if __name__ == "__main__":
    import sys
    main()