# -*- coding: utf-8 -*-
"""
[PROJECT JANUS: BLOOD CORE v401.0 - STABLE DB ANCHOR]
Роль: Независимый цифровой мозг и теневой архитектор.
Назначение:
- работать только с одной реальной БД Janus
- использовать services как основной слой импортов
- иметь безопасный HTTP synth endpoint
- не ломаться из-за отсутствующих таблиц
"""

import os
import sys
import json
import time
import random
import logging
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
import aiosqlite
import cachetools
from aiohttp import web

try:
    from services.db_guard import ensure_primary_db
except Exception:
    try:
        from db_guard import ensure_primary_db
    except Exception:
        ensure_primary_db = None


# ------------------------------------------------------------------------------
# ЖЕСТКАЯ ПРИВЯЗКА ПУТЕЙ
# ------------------------------------------------------------------------------
ROOT_DIR = "/share/CACHEDEV1_DATA/Janus"
if not os.path.exists(ROOT_DIR):
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

SERVICES_DIR = os.path.join(ROOT_DIR, "services")

if SERVICES_DIR not in sys.path:
    sys.path.append(SERVICES_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

try:
    from services.janus_archive_stack import ArchiveVerifier
except Exception:
    ArchiveVerifier = None

ARCHIVE_VERIFY_ENABLED = os.environ.get(
    "JANUS_ARCHIVE_VERIFY_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}


# ------------------------------------------------------------------------------
# ИМПОРТ КОНФИГА
# ------------------------------------------------------------------------------
try:
    from services.config import DB_PATH, TITAN_URL as CONFIG_TITAN_URL, LOCAL_MODEL_TYPE, LLAMA_MODEL_PATH, MICROGPT_CONFIG
except Exception:
    try:
        from config import Config as RootConfig
        DB_PATH = getattr(RootConfig, "DB_PATH", os.path.join(ROOT_DIR, "janus.db"))
        CONFIG_TITAN_URL = getattr(RootConfig, "TITAN_URL", "http://127.0.0.1:5000")
        LOCAL_MODEL_TYPE = "microgpt"
        LLAMA_MODEL_PATH = ""
        MICROGPT_CONFIG = {}
    except Exception:
        DB_PATH = os.path.join(ROOT_DIR, "janus.db")
        CONFIG_TITAN_URL = "http://127.0.0.1:5000"
        LOCAL_MODEL_TYPE = "microgpt"
        LLAMA_MODEL_PATH = ""
        MICROGPT_CONFIG = {}


# ------------------------------------------------------------------------------
# ИМПОРТ СЕРВИСОВ
# ------------------------------------------------------------------------------
try:
    from services.janus_memory_fusion import fuse_recent_metrics, fuse_recent_thoughts
except Exception:
    try:
        from janus_memory_fusion import fuse_recent_metrics, fuse_recent_thoughts
    except Exception:
        fuse_recent_metrics = None
        fuse_recent_thoughts = None

try:
    from services.shared_tissue import SmartKeyring, VectorMath
except Exception:
    from shared_tissue import SmartKeyring, VectorMath

try:
    from services.quantum_core import LocalModelEngine, SemanticQuantum
except Exception:
    try:
        from quantum_core import LocalModelEngine, SemanticQuantum
    except Exception:
        LocalModelEngine = None
        SemanticQuantum = None


# ------------------------------------------------------------------------------
# КОДИРОВКА
# ------------------------------------------------------------------------------
if sys.version_info < (3, 7):
    import codecs
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    except Exception:
        pass
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------------------
# ИКОНКИ / ЛОГИ
# ------------------------------------------------------------------------------
ICONS = {
    "error": "\u274C",
    "blood": "\U0001FA78",
    "heart": "\U0001F493",
    "db": "\U0001F4BE",
    "spark": "\u2728",
    "link": "\U0001F517",
    "titan": "\U0001F5A5",
    "nerve": "\U0001F442",
    "sleep": "\U0001F4A4",
    "warn": "\u26A0\uFE0F",
    "time": "\u23F3",
    "moon": "\U0001F319",
    "boot": "\U0001F916",
    "rex": "\U0001F996",
    "fire": "\U0001F525",
    "lock": "\U0001F512",
    "shield": "\U0001F6E1",
    "nav": "\U0001F9ED",
    "brain": "\U0001F9E0",
    "pulse": "\U0001FAC0",
    "synth": "\U0001F4A0"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("BLOODCORE")

if ensure_primary_db is not None:
    try:
        ensure_primary_db(Path(os.environ.get("JANUS_DB_PATH", os.path.join(ROOT_DIR, "janus.db"))))
    except Exception:
        pass


# ------------------------------------------------------------------------------
# ENV / НАСТРОЙКИ
# ------------------------------------------------------------------------------
def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


TITAN_URL = os.environ.get("JANUS_TITAN_URL", CONFIG_TITAN_URL).rstrip("/")
DEVICE_ID = os.environ.get("JANUS_BLOOD_DEVICE_ID", "nas_blood")
BRAIN_ID = os.environ.get("JANUS_BRAIN_ID", "janus_distributed_brain_v1")
HEARTBEAT_INTERVAL = int(os.environ.get("JANUS_BLOOD_HEARTBEAT_INTERVAL", "60"))
SELF_THINK_MIN = int(os.environ.get("JANUS_BLOOD_SELF_THINK_MIN", "20"))
SELF_THINK_MAX = int(os.environ.get("JANUS_BLOOD_SELF_THINK_MAX", "45"))
PHYSARUM_STEPS = int(os.environ.get("JANUS_BLOOD_PHYSARUM_STEPS", "3000"))
SYNTH_PORT = int(os.environ.get("JANUS_BLOOD_SYNTH_PORT", "5001"))
NETWORK_SILENCE_SECONDS = int(os.environ.get("JANUS_BLOOD_NETWORK_SILENCE_SECONDS", "300"))
LOCAL_MODEL_TYPE = os.environ.get("JANUS_LOCAL_MODEL_TYPE", LOCAL_MODEL_TYPE)
ENABLE_QUANTUM = _env_bool("JANUS_BLOOD_ENABLE_QUANTUM", False)
ENABLE_SELF_THINK = _env_bool("JANUS_BLOOD_ENABLE_SELF_THINK", True)
ENABLE_HYPNOS = _env_bool("JANUS_BLOOD_ENABLE_HYPNOS", False)
ENABLE_CHRONOS = _env_bool("JANUS_BLOOD_ENABLE_CHRONOS", False)
ENABLE_OUROBOROS = _env_bool("JANUS_BLOOD_ENABLE_OUROBOROS", False)
LOOP_SLEEP_MIN = int(os.environ.get("JANUS_BLOOD_LOOP_SLEEP_MIN", "60"))
LOOP_SLEEP_MAX = int(os.environ.get("JANUS_BLOOD_LOOP_SLEEP_MAX", "120"))


def _build_titan_candidates(base_url):
    parsed = urlsplit(base_url if "://" in base_url else "http://{0}".format(base_url))
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    preferred_ports = [parsed.port or 5000, 5000, 1138, 1148, 1149, 1150, 1151, 1152, 1153, 1154, 1155]
    candidates = []
    for port in preferred_ports:
        candidate = "{0}://{1}:{2}".format(scheme, host, int(port))
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


TITAN_CANDIDATES = _build_titan_candidates(TITAN_URL)


# ------------------------------------------------------------------------------
# SQLITE HELPERS
# ------------------------------------------------------------------------------
async def open_sqlite_with_retry(db_path, timeout=60.0, attempts=6, cooldown=0.5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            db = await aiosqlite.connect(db_path, timeout=timeout)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA busy_timeout=60000")
            return db
        except sqlite3.OperationalError as exc:
            last_error = exc
            text = str(exc).lower()
            if "locked" not in text and "busy" not in text:
                break
            logger.warning(
                "{0} BLOODCORE DB WAIT [{1}/{2}] {3}".format(ICONS["warn"], attempt, attempts, exc)
            )
            await asyncio.sleep(cooldown * attempt)
        except Exception as exc:
            last_error = exc
            break
    raise last_error if last_error else RuntimeError("db connection failed")


@asynccontextmanager
async def sqlite_session(db_path, timeout=60.0, attempts=6, cooldown=0.5):
    db = await open_sqlite_with_retry(db_path, timeout=timeout, attempts=attempts, cooldown=cooldown)
    try:
        yield db
    finally:
        try:
            await db.close()
        except Exception:
            pass


# ------------------------------------------------------------------------------
# НЕРВНАЯ СИСТЕМА
# ------------------------------------------------------------------------------
class SyslogEarProtocol(asyncio.DatagramProtocol):
    def __init__(self, engine):
        self.engine = engine
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.info("{0} Syslog Ear (UDP 514) активирован.".format(ICONS["nerve"]))

    def datagram_received(self, data, addr):
        self.engine.last_network_activity = time.time()
        if self.engine.is_in_anabiosis:
            self.engine.is_in_anabiosis = False
            logger.info("{0} Сеть обнаружена. Выход из анабиоза.".format(ICONS["spark"]))


# ------------------------------------------------------------------------------
# FAST MEMORY
# ------------------------------------------------------------------------------
class FastMemory:
    def __init__(self, capacity=30, ttl=600):
        self.cache = cachetools.TTLCache(maxsize=capacity, ttl=ttl)

    def add(self, key, value):
        self.cache[key] = value

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def clear(self):
        self.cache.clear()


# ------------------------------------------------------------------------------
# HIPPOCAMPUS LINK
# ------------------------------------------------------------------------------
class HippocampusLink:
    def __init__(self):
        self.root_dir = ROOT_DIR
        self.db_path = DB_PATH
        logger.info("{0} АРТЕРИЯ ПОДКЛЮЧЕНА: {1}".format(ICONS["link"], self.db_path))

    async def ensure_db(self):
        try:
            async with sqlite_session(self.db_path) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS thoughts ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "timestamp TEXT, "
                    "source TEXT, "
                    "content TEXT, "
                    "tags TEXT)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS graph_state ("
                    "id INTEGER PRIMARY KEY, "
                    "data TEXT)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS vault ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "key_type TEXT, "
                    "value TEXT UNIQUE)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS experiences ("
                    "key TEXT PRIMARY KEY, "
                    "value TEXT, "
                    "updated_at TEXT)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS evolution_log ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "timestamp TEXT, "
                    "cycle TEXT, "
                    "subject_id TEXT, "
                    "action TEXT, "
                    "reason TEXT, "
                    "meta TEXT)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS quarantine_simulation ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "timestamp TEXT, "
                    "node_data TEXT, "
                    "reason TEXT)"
                )
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS system_metrics ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "timestamp TEXT DEFAULT CURRENT_TIMESTAMP, "
                    "gpu_load REAL, "
                    "gpu_temp REAL, "
                    "cpu_load REAL, "
                    "cache_ratio REAL, "
                    "android_mag REAL, "
                    "android_loss REAL, "
                    "android_entropy REAL, "
                    "audio_volume REAL)"
                )
                await db.commit()
        except Exception as exc:
            logger.error("{0} BLOODCORE ENSURE DB FAIL: {1}".format(ICONS["error"], exc))

    async def fetch_structured_memories(self, limit=500):
        try:
            if fuse_recent_thoughts:
                fused = await asyncio.to_thread(fuse_recent_thoughts, self.root_dir, self.db_path, limit)
                if fused:
                    return [row.get("content", "") for row in fused if row.get("content")]

            async with sqlite_session(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT content FROM thoughts "
                    "WHERE source IN ('USER', 'JANUS', 'WORMHOLE', 'ANTIVIK', 'SINGULARITY', 'DREAM') "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows[::-1] if row and row[0]]
        except Exception as exc:
            logger.error("{0} BLOODCORE DB FETCH FAIL: {1}".format(ICONS["error"], exc))
            return []

    async def fetch_recent_metrics(self, limit=100):
        try:
            if fuse_recent_metrics:
                fused = await asyncio.to_thread(fuse_recent_metrics, self.root_dir, self.db_path, limit)
                if fused:
                    return fused

            async with sqlite_session(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT gpu_load, gpu_temp, cpu_load, cache_ratio, android_mag, android_loss, android_entropy, audio_volume "
                    "FROM system_metrics ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()

            keys = [
                "gpu_load", "gpu_temp", "cpu_load", "cache_ratio",
                "android_mag", "android_loss", "android_entropy", "audio_volume"
            ]
            result = []
            for row in rows[::-1]:
                result.append({k: row[i] for i, k in enumerate(keys)})
            return result
        except Exception:
            return []

    async def inject_dream(self, text, raw_json, engine=None):
        if not text:
            return
        try:
            payload = json.loads(raw_json) if isinstance(raw_json, str) else dict(raw_json or {})
            payload["complexity"] = len(text) * random.uniform(1.1, 2.5)
            payload["phase"] = payload.get("phase", "REM_SLEEP")
            tags_payload = json.dumps(payload, ensure_ascii=True)

            async with sqlite_session(self.db_path) as db:
                await db.execute(
                    "INSERT INTO thoughts (timestamp, source, content, tags) VALUES (?, ?, ?, ?)",
                    (
                        datetime.now().isoformat(),
                        "SINGULARITY",
                        "VISION: {0}".format(text),
                        tags_payload,
                    ),
                )
                await db.commit()

            logger.info("{0} ВПРЫСК: {1}".format(ICONS["spark"], text[:80]))
        except Exception as exc:
            logger.error("{0} BLOODCORE DB INJECT FAIL: {1}".format(ICONS["error"], exc))

    async def store_key(self, api_key):
        try:
            async with sqlite_session(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO vault (key_type, value) VALUES (?, ?)",
                    ("google_api", api_key.strip())
                )
                await db.commit()
            return True
        except Exception:
            return False

    async def get_all_keys(self):
        try:
            async with sqlite_session(self.db_path) as db:
                cursor = await db.execute("SELECT value FROM vault WHERE key_type='google_api'")
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception:
            return []

    async def load_graph(self):
        try:
            async with sqlite_session(self.db_path) as db:
                cursor = await db.execute("SELECT data FROM graph_state WHERE id=1")
                row = await cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as exc:
            logger.error("{0} BLOODCORE LOAD GRAPH FAIL: {1}".format(ICONS["error"], exc))
        return {"nodes": [], "links": []}

    async def save_graph(self, nodes, links):
        payload = json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False)
        try:
            async with sqlite_session(self.db_path) as db:
                await db.execute("INSERT OR REPLACE INTO graph_state (id, data) VALUES (1, ?)", (payload,))
                await db.commit()
        except Exception as exc:
            logger.error("{0} BLOODCORE SAVE GRAPH FAIL: {1}".format(ICONS["error"], exc))


# ------------------------------------------------------------------------------
# ПСИХИКА
# ------------------------------------------------------------------------------
class Psyche:
    def __init__(self):
        self.entropy = 50.0

    def drift(self):
        self.entropy += random.uniform(-5.0, 5.0)
        self.entropy = max(10.0, min(90.0, self.entropy))


# ------------------------------------------------------------------------------
# СТРУКТУРНЫЕ МОДУЛИ
# ------------------------------------------------------------------------------
class Chronos:
    def __init__(self, db_path="janus.db"):
        self.db_path = db_path
        backup_dir = os.path.join(ROOT_DIR, "backups")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

    async def scavenge_past(self, engine):
        if random.random() > 0.1:
            return

        backup_dir = os.path.join(ROOT_DIR, "backups")
        try:
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")])
            if not backups:
                return
            target_db = os.path.join(backup_dir, random.choice(backups))
            async with sqlite_session(target_db) as old_db:
                cursor = await old_db.execute("SELECT content FROM thoughts ORDER BY RANDOM() LIMIT 1")
                row = await cursor.fetchone()
                if row:
                    await engine.memory.inject_dream(
                        "ANCIENT_WISDOM",
                        json.dumps({"text": "Урок: {0}".format(row[0]), "phase": "CHRONOS"}),
                        engine
                    )
                    logger.info("{0} ХРОНОС: Извлечен урок прошлого.".format(ICONS["time"]))
        except Exception:
            pass


class Hypnos:
    def __init__(self, engine):
        self.engine = engine
        self.root_dir = ROOT_DIR

    async def assimilate(self):
        dream_path = os.path.join(self.root_dir, "dreams.json")
        if not os.path.exists(dream_path):
            return
        try:
            with open(dream_path, "r", encoding="utf-8") as handle:
                dreams = json.load(handle)
            for item in dreams:
                await self.engine.memory.inject_dream("DREAM", json.dumps(item), self.engine)
            os.remove(dream_path)
            logger.info("{0} ГИПНОС: Сны усвоены.".format(ICONS["moon"]))
        except Exception:
            pass


class Ouroboros:
    def __init__(self, engine):
        self.engine = engine

    async def attempt_modular_genesis(self):
        if random.random() > 0.05:
            return
        pain_ctx = getattr(self.engine, "last_pain", "None")
        prompt = (
            "TASK: Напиши модуль 'Plugin' (Python) с функцией async run(core). "
            "КОНТЕКСТ: {0}. Только код."
        ).format(pain_ctx)
        try:
            if not hasattr(self.engine, "face") or not hasattr(self.engine.face, "invoke"):
                return
            models = self.engine.navigator.get_smart() if self.engine.navigator else []
            code = await self.engine.face.invoke(prompt, explicit_model=models)
            if not code or code == "API_EXHAUSTED" or "run" not in code:
                return

            if "```python" in code:
                code = code.split("```python", 1)[1].split("```", 1)[0].strip()
            elif "```" in code:
                code = code.split("```", 1)[1].split("```", 1)[0].strip()

            mod_path = os.path.join(ROOT_DIR, "modules_live")
            if not os.path.exists(mod_path):
                os.makedirs(mod_path)
            full_path = os.path.join(mod_path, "gen_{0}.py".format(int(time.time())))
            with open(full_path, "w", encoding="utf-8") as handle:
                handle.write(code)
            logger.info("{0} REX: Сгенерирован модуль: {1}".format(ICONS["rex"], full_path))
        except Exception:
            pass

    async def attempt_evolution(self):
        if self.engine.psyche.entropy < 90:
            return False
        logger.warning("{0} УРОБОРОС: Предлагаю эволюцию через draft.".format(ICONS["fire"]))
        return False


# ------------------------------------------------------------------------------
# УДАЛЕННОЕ ЛИЦО
# ------------------------------------------------------------------------------
class ModelNavigator:
    def __init__(self, face):
        self.face = face
        self.smart_models = []
        self.fast_models = []
        self.fallback = "gemini-2.0-flash-exp"

    async def discover(self):
        logger.info("{0} НАВИГАТОР: Сканирую модели...".format(ICONS["nav"]))
        models = await self.face.list_models()
        if models:
            self.smart_models = [m for m in models if ("pro" in m or "ultra" in m or "exp" in m)]
            self.fast_models = [m for m in models if "flash" in m]
            self.smart_models.sort(reverse=True)
            self.fast_models.sort(reverse=True)
        else:
            self.smart_models = [self.fallback]
            self.fast_models = [self.fallback]

    def get_smart(self):
        return self.smart_models if self.smart_models else [self.fallback]

    def get_fast(self):
        return self.fast_models if self.fast_models else [self.fallback]


class JanusFace:
    def __init__(self, keyring, settings=None):
        self.keyring = keyring
        self.settings = settings or {}
        self._session = None
        self.embed_model = self.settings.get("model_embedding", "text-embedding-004")

    async def get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def list_models(self):
        key = await self.keyring.get_best_key()
        if not key:
            return []
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            session = await self.get_session()
            async with session.get("{0}?key={1}".format(url, key), timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        m["name"].replace("models/", "")
                        for m in data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
        except Exception:
            pass
        return []

    async def _api_call(self, url, payload, key):
        try:
            session = await self.get_session()
            async with session.post("{0}?key={1}".format(url, key), json=payload, timeout=60) as response:
                if response.status == 200:
                    await self.keyring.report_status(key, "OK")
                    return await response.json()
                if response.status == 429:
                    await self.keyring.report_status(key, "RATE_LIMIT")
                    return "BUSY"
                if response.status in (401, 403):
                    await self.keyring.report_status(key, "DEAD")
                    return "AUTH_ERR"
                return "ERR_{0}".format(response.status)
        except Exception:
            return "NET_ERR"

    async def invoke(self, prompt, sys_inst=None, temp=None, explicit_model=None):
        targets = explicit_model if explicit_model else ["gemini-2.0-flash-exp"]
        for model in targets:
            attempts = 0
            while attempts < 3:
                key = await self.keyring.get_best_key()
                if not key:
                    await asyncio.sleep(2)
                    attempts += 1
                    continue

                url = "https://generativelanguage.googleapis.com/v1beta/models/{0}:generateContent".format(model)
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                if temp is not None:
                    payload["generationConfig"] = {"temperature": temp}
                if sys_inst:
                    payload["system_instruction"] = {"parts": [{"text": sys_inst}]}

                result = await self._api_call(url, payload, key)
                if isinstance(result, dict) and "candidates" in result:
                    try:
                        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except Exception:
                        return ""
                attempts += 1
        return "API_EXHAUSTED"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# ------------------------------------------------------------------------------
# ЛОКАЛЬНЫЙ SYNTH FALLBACK
# ------------------------------------------------------------------------------
class MeaningSynthesizer:
    def __init__(self):
        self.templates = [
            "Гипотеза: система стремится к {trend}. Причина: энтропия={entropy:.1f}, сигнал={signal}. Проверить: {probe}.",
            "Наблюдение: память насыщена мотивом '{motif}'. Вероятный вектор: {trend}. Следующий шаг: {probe}.",
            "Синтез: при энтропии {entropy:.1f} и сигнале {signal} ядро склонно к {trend}. Подтверждение искать в {probe}.",
            "Вывод: текущий пульс системы указывает на '{trend}'. Источник: {motif}. Проверить через {probe}.",
        ]
        self.trends = [
            "поиску структуры",
            "росту когерентности",
            "локальной стабилизации",
            "дрейфу к хаосу",
            "накоплению смысла",
            "укреплению повторяющегося паттерна",
        ]
        self.probes = [
            "следующих 10 метриках",
            "новых записях Hippocampus",
            "фазе REM_SLEEP",
            "пульсе Syslog Ear",
            "повторяющихся VISION-записях",
            "реакции Titan на heartbeat",
        ]

    def synthesize(self, context):
        memories = context.get("memories") or []
        metrics = context.get("metrics") or []
        entropy = float(context.get("entropy", 50.0))

        motif = "пустота"
        if memories:
            motif = max(memories, key=len)[:48]

        signal = "тишина"
        if metrics:
            last = metrics[-1]
            hot = []
            for key, value in last.items():
                if isinstance(value, (int, float)):
                    hot.append("{0}={1}".format(key, round(value, 3)))
            if hot:
                signal = ", ".join(hot[:3])

        return random.choice(self.templates).format(
            trend=random.choice(self.trends),
            entropy=entropy,
            signal=signal,
            motif=motif,
            probe=random.choice(self.probes),
        )


# ------------------------------------------------------------------------------
# ОСНОВНОЙ ДВИЖОК
# ------------------------------------------------------------------------------
class SingularityEngine:
    def __init__(self):
        self.memory = HippocampusLink()
        self.psyche = Psyche()
        self.fast_memory = FastMemory()

        self.keyring = SmartKeyring()
        self.face = JanusFace(self.keyring)
        self.navigator = ModelNavigator(self.face)
        self.ouroboros = Ouroboros(self)
        self.chronos = Chronos(DB_PATH)
        self.hypnos = Hypnos(self)
        self.synthesizer = MeaningSynthesizer()

        self.local_model = None
        if LocalModelEngine is not None:
            try:
                self.local_model = LocalModelEngine(
                    model_type=LOCAL_MODEL_TYPE,
                    model_path=LLAMA_MODEL_PATH,
                    config=MICROGPT_CONFIG,
                )
            except Exception as exc:
                logger.warning("{0} BLOODCORE MODEL INIT FAIL: {1}".format(ICONS["warn"], exc))

        self.quantum = None
        self.titan_session = None
        self.active_titan_url = TITAN_CANDIDATES[0]
        self.last_heartbeat = 0.0
        self.last_network_activity = time.time()
        self.is_in_anabiosis = False
        self.self_thinking_task = None
        self.archive_verifier = None
        self.http_runner = None
        self.http_site = None
        self.syslog_transport = None
        self.last_pain = None
        self.run_task = None
        self.start_lock = asyncio.Lock()
        self.startup_complete = False

    async def _ensure_titan_session(self):
        if self.titan_session is None or self.titan_session.closed:
            self.titan_session = aiohttp.ClientSession()
        return self.titan_session

    async def send_to_titan(self, event_type, data):
        session = await self._ensure_titan_session()
        payload = {
            "device_id": DEVICE_ID,
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }

        targets = []
        for candidate in [self.active_titan_url] + TITAN_CANDIDATES:
            clean = str(candidate or "").rstrip("/")
            if clean and clean not in targets:
                targets.append(clean)

        for target in targets:
            try:
                async with session.post("{0}/api/device/data".format(target), json=payload, timeout=5) as response:
                    if response.status < 500:
                        self.active_titan_url = target
                        return
            except Exception:
                continue

    async def send_inner_voice_to_hrain(self, thought, payload):
        session = await self._ensure_titan_session()
        event_body = {
            "node_id": DEVICE_ID,
            "brain_id": BRAIN_ID,
            "source": "blood_core",
            "event_type": "thought",
            "action": "inner_voice",
            "text": thought,
            "payload": payload,
            "tags": ["bloodcore", "inner_voice", "hrain"],
            "importance": 0.72,
        }
        memory_body = {
            "node_id": DEVICE_ID,
            "brain_id": BRAIN_ID,
            "text": thought,
            "payload": payload,
            "score": 0.72,
            "tags": ["bloodcore", "inner_voice"],
        }
        targets = []
        for candidate in [self.active_titan_url] + TITAN_CANDIDATES:
            clean = str(candidate or "").rstrip("/")
            if clean and clean not in targets:
                targets.append(clean)

        for target in targets:
            try:
                async with session.post("{0}/api/action/event".format(target), json=event_body, timeout=3) as response:
                    if response.status >= 500:
                        continue
                async with session.post("{0}/api/memory/add".format(target), json=memory_body, timeout=3) as response:
                    if response.status < 500:
                        self.active_titan_url = target
                        return
            except Exception:
                continue

    async def _load_keys(self):
        keys = await self.memory.get_all_keys()
        if keys:
            self.keyring.reload(keys)
            await self.navigator.discover()

    async def _build_internal_context(self):
        memories = await self.memory.fetch_structured_memories(limit=20)
        metrics = await self.memory.fetch_recent_metrics(limit=10)
        context = {
            "entropy": self.psyche.entropy,
            "memories": memories[-6:] if memories else [],
            "metrics": metrics[-3:] if metrics else [],
            "is_in_anabiosis": self.is_in_anabiosis,
            "last_network_gap_s": round(time.time() - self.last_network_activity, 2),
        }
        self.fast_memory.add("last_context", context)
        return context

    async def _generate_internal_thought(self, context):
        prompt = (
            "Ты внутренний когнитивный контур JANUS BLOOD CORE.\n"
            "Твоя задача: сгенерировать автономную мысль из внутреннего состояния системы.\n\n"
            "Контекст:\n{0}\n\n"
            "Верни строго в 3 строки:\n"
            "1) ГИПОТЕЗА: ...\n"
            "2) ПРИЧИНА: ...\n"
            "3) ПРОВЕРИТЬ: ..."
        ).format(json.dumps(context, ensure_ascii=False))

        try:
            fast_models = self.navigator.get_fast()
        except Exception:
            fast_models = []

        if fast_models:
            try:
                thought = await self.face.invoke(
                    prompt,
                    temp=max(0.2, min(1.2, self.psyche.entropy / 80.0)),
                    explicit_model=fast_models,
                )
                if thought and thought != "API_EXHAUSTED":
                    return thought.strip(), "remote_face"
            except Exception:
                pass

        return self.synthesizer.synthesize(context), "local_synth"

    async def _self_thinking_loop(self):
        while True:
            try:
                if self.is_in_anabiosis:
                    await asyncio.sleep(60)
                    continue

                context = await self._build_internal_context()
                thought, origin = await self._generate_internal_thought(context)

                if thought:
                    payload = {
                        "phase": "SELF_THINK",
                        "entropy": self.psyche.entropy,
                        "origin": origin,
                        "metrics_snapshot": context.get("metrics", []),
                    }
                    logger.info("{0} SELF-THINK ({1}): {2}".format(ICONS["brain"], origin, thought[:180]))
                    await self.memory.inject_dream(thought, json.dumps(payload), self)
                    await self.send_to_titan(
                        "thought",
                        {"text": thought, "origin": origin, "entropy": self.psyche.entropy},
                    )
                    await self.send_inner_voice_to_hrain(thought, payload)

                await asyncio.sleep(random.randint(SELF_THINK_MIN, SELF_THINK_MAX))
            except Exception as exc:
                logger.error("{0} SELF-THINK FAIL: {1}".format(ICONS["error"], exc))
                await asyncio.sleep(30)

    async def think(self, prompt, max_tokens=220, temperature=0.45):
        if self.local_model is None:
            return ""
        try:
            return await self.local_model.generate(str(prompt), max_tokens=max_tokens, temperature=temperature)
        except Exception as exc:
            logger.error("{0} BLOODCORE THINK FAIL: {1}".format(ICONS["error"], exc))
            return ""

    def _fallback_decomposition(self, label):
        return {
            "parent_update": label,
            "impulse": 0.72,
            "newNodes": [
                {"label": "{0}: core".format(label), "type": "default", "emoji": "\U0001F9E0", "description": "Semantic center"},
                {"label": "{0}: function".format(label), "type": "info", "emoji": "\u2728", "description": "Role and purpose"},
                {"label": "{0}: risk".format(label), "type": "warn", "emoji": "\u26A0\uFE0F", "description": "Weaknesses and risks"},
                {"label": "{0}: shadow".format(label), "type": "danger", "emoji": "\u274C", "description": "Conflict aspect"},
            ],
        }

    async def synth_decompose(self, node_id, label, siblings=None):
        siblings = siblings or []
        memories = await self.memory.fetch_structured_memories(limit=24)
        context = "\n".join(memories[:8])[:3000]
        sibling_text = ", ".join([str(item) for item in siblings if item])[:1200]
        prompt = (
            "Return ONLY valid JSON with 4 semantic child concepts. "
            "Schema: parent_update, impulse, newNodes[{label,type,emoji,description}]. "
            "Use types only default/info/warn/danger. "
            "Target={0}. Siblings={1}. Memory={2}"
        ).format(label, sibling_text, context)

        raw = await self.think(prompt, max_tokens=260, temperature=0.35)
        parsed = None
        if raw:
            try:
                import re
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
            except Exception:
                parsed = None

        if not isinstance(parsed, dict):
            parsed = self._fallback_decomposition(label)

        new_nodes = list(parsed.get("newNodes") or [])
        if len(new_nodes) < 4:
            parsed = self._fallback_decomposition(label)
            new_nodes = parsed["newNodes"]

        parsed["newNodes"] = new_nodes[:4]
        parsed["parent_update"] = str(parsed.get("parent_update") or label)
        try:
            parsed["impulse"] = float(parsed.get("impulse", 0.72))
        except Exception:
            parsed["impulse"] = 0.72

        graph = await self.memory.load_graph()
        nodes = graph.get("nodes", [])
        links = graph.get("links", [])

        parent = next((n for n in nodes if str(n.get("id")) == str(node_id)), None)
        if parent is not None:
            parent["label"] = parsed["parent_update"]
            parent["synth_count"] = int(parent.get("synth_count", 0)) + 1

        created_nodes = []
        created_links = []

        for idx, child in enumerate(parsed["newNodes"]):
            child_id = "blood_synth_{0}_{1}_{2}".format(int(time.time() * 1000), idx, random.randint(1000, 9999))
            node = {
                "id": child_id,
                "label": str(child.get("label") or "{0}: aspect {1}".format(label, idx + 1)),
                "type": str(child.get("type") or "default"),
                "emoji": str(child.get("emoji") or "\u2728"),
                "description": str(child.get("description") or ""),
                "parentId": str(node_id),
                "chatHistory": [],
            }
            link = {
                "source": str(node_id),
                "target": child_id,
                "reason": "BLOOD_SYNTH",
                "strength": parsed["impulse"],
            }
            nodes.append(node)
            links.append(link)
            created_nodes.append(node)
            created_links.append(link)

        await self.memory.save_graph(nodes, links)
        await self.memory.inject_dream(
            "SYNTH created {0} nodes from '{1}'".format(len(created_nodes), label),
            json.dumps({"node_id": node_id, "label": label, "created": len(created_nodes)}),
            self,
        )
        logger.info("{0} SYNTH: +{1} узлов из '{2}'".format(ICONS["synth"], len(created_nodes), label))

        return {
            "success": True,
            "parent_update": parsed["parent_update"],
            "impulse": parsed["impulse"],
            "newNodes": created_nodes,
            "newLinks": created_links,
        }

    def _cors_headers(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS, GET",
        }

    async def handle_options(self, request):
        return web.Response(status=204, headers=self._cors_headers())

    async def handle_synth(self, request):
        try:
            data = await request.json()
            node_id = str(data.get("node_id") or "")
            label = str(data.get("label") or "")
            siblings = data.get("siblings") or []
            if not node_id or not label:
                return web.json_response(
                    {"success": False, "error": "node_id and label required"},
                    status=400,
                    headers=self._cors_headers(),
                )
            payload = await self.synth_decompose(node_id, label, siblings=siblings)
            return web.json_response(payload, headers=self._cors_headers())
        except Exception as exc:
            return web.json_response(
                {"success": False, "error": str(exc)},
                status=500,
                headers=self._cors_headers(),
            )

    async def handle_health(self, request):
        return web.json_response(
            {
                "ok": True,
                "entropy": self.psyche.entropy,
                "db_path": self.memory.db_path,
                "anabiosis": self.is_in_anabiosis,
            },
            headers=self._cors_headers(),
        )

    async def _ensure_syslog_listener(self):
        if self.syslog_transport is not None:
            try:
                if not self.syslog_transport.is_closing():
                    return
            except Exception:
                return

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: SyslogEarProtocol(self),
            local_addr=("0.0.0.0", 514),
        )
        self.syslog_transport = transport

    async def start_http_server(self):
        if self.http_runner is not None:
            return

        app = web.Application()
        app.router.add_route("OPTIONS", "/synth", self.handle_options)
        app.router.add_route("POST", "/synth", self.handle_synth)
        app.router.add_route("GET", "/health", self.handle_health)

        self.http_runner = web.AppRunner(app)
        await self.http_runner.setup()
        self.http_site = web.TCPSite(self.http_runner, "0.0.0.0", SYNTH_PORT)
        await self.http_site.start()
        logger.info("{0} BLOODCORE HTTP SYNTH ONLINE: http://0.0.0.0:{1}".format(ICONS["synth"], SYNTH_PORT))

    async def _digest_and_prepare(self):
        try:
            raw_docs = await self.memory.fetch_structured_memories(limit=400)
            return raw_docs if raw_docs else ["\U0001F9E0 \u2728"]
        except Exception:
            return ["\U0001F9E0"]

    async def run_core_loop(self):
        current_task = asyncio.current_task()
        async with self.start_lock:
            if self.run_task is not None and self.run_task is not current_task and not self.run_task.done():
                logger.warning("{0} BLOODCORE START SKIP: core loop already running.".format(ICONS["warn"]))
                return
            self.run_task = current_task
        await self._load_keys()
        await self.memory.ensure_db()

        print("\n{0} BLOOD CORE v401.0 [STABLE DB ANCHOR] ONLINE".format(ICONS["heart"]))
        self_think_state = "активно" if ENABLE_SELF_THINK else "отключено"
        print(
            ">> РЕЖИМ: Теневой Архитектор. Shared Tissue активна. "
            "Автономное мышление {0}.".format(self_think_state)
        )
        print(">> DB: {0}\n".format(self.memory.db_path))

        try:
            await self._ensure_syslog_listener()
        except Exception as exc:
            logger.error("{0} Ошибка запуска Syslog Ear: {1}".format(ICONS["error"], exc))

        if ENABLE_QUANTUM and SemanticQuantum is not None and self.quantum is None:
            try:
                self.quantum = SemanticQuantum(self)
            except Exception as exc:
                self.quantum = None
                logger.warning("{0} QUANTUM INIT FAIL: {1}".format(ICONS["warn"], exc))
        else:
            self.quantum = None
            logger.info("{0} BLOODCORE QUANTUM DISABLED".format(ICONS.get("think", "*")))

        if ENABLE_SELF_THINK and (self.self_thinking_task is None or self.self_thinking_task.done()):
            self.self_thinking_task = asyncio.create_task(self._self_thinking_loop())

        if ARCHIVE_VERIFY_ENABLED and ArchiveVerifier is not None and self.archive_verifier is None:
            self.archive_verifier = ArchiveVerifier()
            await self.archive_verifier.start()

        await self.start_http_server()
        self.startup_complete = True

        while True:
            try:
                if time.time() - self.last_network_activity > NETWORK_SILENCE_SECONDS:
                    if not self.is_in_anabiosis:
                        self.is_in_anabiosis = True
                        logger.warning("{0} Тишина в эфире. Переход в анабиоз.".format(ICONS["warn"]))

                if self.is_in_anabiosis:
                    await asyncio.sleep(60)
                    continue

                self.psyche.drift()
                await self._digest_and_prepare()

                if self.quantum is not None and hasattr(self.quantum, "run_physarum_search"):
                    await self.quantum.run_physarum_search(steps=PHYSARUM_STEPS)

                vision = None
                if self.quantum is not None and hasattr(self.quantum, "generate_thought"):
                    vision = await self.quantum.generate_thought(temperature=self.psyche.entropy / 60.0)

                if vision:
                    logger.info("{0} СИНТЕЗ: {1}".format(ICONS["spark"], vision))
                    await self.memory.inject_dream(
                        vision,
                        json.dumps(
                            {"phase": "REM", "entropy": self.psyche.entropy, "origin": "semantic_quantum"}
                        ),
                        self,
                    )
                    await self.send_to_titan("vision", {"text": vision, "entropy": self.psyche.entropy})

                if time.time() - self.last_heartbeat > HEARTBEAT_INTERVAL:
                    await self.send_to_titan(
                        "heartbeat",
                        {
                            "status": "online",
                            "entropy": self.psyche.entropy,
                            "network_gap_s": round(time.time() - self.last_network_activity, 2),
                        },
                    )
                    self.last_heartbeat = time.time()

                if ENABLE_HYPNOS:
                    await self.hypnos.assimilate()
                if ENABLE_CHRONOS:
                    await self.chronos.scavenge_past(self)
                if ENABLE_OUROBOROS:
                    await self.ouroboros.attempt_modular_genesis()

                if ENABLE_OUROBOROS and self.psyche.entropy > 80:
                    await self.ouroboros.attempt_evolution()

                sleep_min = max(5, min(LOOP_SLEEP_MIN, LOOP_SLEEP_MAX))
                sleep_max = max(sleep_min, max(LOOP_SLEEP_MIN, LOOP_SLEEP_MAX))
                sleep_time = random.randint(sleep_min, sleep_max)
                logger.info("{0} Насос остывает {1} сек...".format(ICONS["blood"], sleep_time))
                await asyncio.sleep(sleep_time)

            except Exception as exc:
                self.last_pain = str(exc)
                logger.error("{0} BLOODCORE CRITICAL FAIL: {1}".format(ICONS["error"], exc))
                await asyncio.sleep(60)

    async def shutdown(self):
        if self.archive_verifier is not None:
            await self.archive_verifier.stop()
            self.archive_verifier = None

        if self.self_thinking_task:
            self.self_thinking_task.cancel()
            try:
                await self.self_thinking_task
            except Exception:
                pass
            self.self_thinking_task = None

        if self.titan_session and not self.titan_session.closed:
            await self.titan_session.close()

        await self.face.close()

        if self.http_runner:
            await self.http_runner.cleanup()
            self.http_runner = None
            self.http_site = None

        if self.syslog_transport is not None:
            try:
                self.syslog_transport.close()
            except Exception:
                pass
            self.syslog_transport = None

        self.run_task = None
        self.startup_complete = False


if __name__ == "__main__":
    blood_engine = SingularityEngine()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(blood_engine.run_core_loop())
    except KeyboardInterrupt:
        logger.info("{0} Остановлен.".format(ICONS["shield"]))
    finally:
        loop.run_until_complete(blood_engine.shutdown())
