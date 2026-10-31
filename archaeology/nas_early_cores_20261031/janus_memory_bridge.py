#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


VERSION = "janus_memory_bridge_v1"
SOURCE_DB = Path(os.environ.get("JANUS_MEMORY_SOURCE_DB", "/source/janus.db"))
WIKI_DB = Path(os.environ.get("JANUS_MEMORY_WIKI_DB", "/wiki/janus.db"))
MEME_DB = Path(os.environ.get("JANUS_MEMORY_MEME_DB", "/source/meme_radar.db"))
STATE_PATH = Path(os.environ.get("JANUS_MEMORY_STATE", "/state/state.json"))
HRAIN_URL = os.environ.get("JANUS_MEMORY_HRAIN_URL", "http://127.0.0.1:5000").rstrip("/")
BRAIN_ID = os.environ.get("JANUS_BRAIN_ID", "janus_distributed_brain_v1")
NODE_ID = os.environ.get("JANUS_MEMORY_NODE_ID", "NAS_MEMORY_BRIDGE")
POLL_SECONDS = max(1.0, float(os.environ.get("JANUS_MEMORY_POLL_SECONDS", "3")))
MODULE_SCAN_SECONDS = max(15.0, float(os.environ.get("JANUS_MEMORY_MODULE_SCAN_SECONDS", "45")))
MODULE_EVENT_COOLDOWN = max(30.0, float(os.environ.get("JANUS_MEMORY_MODULE_EVENT_COOLDOWN", "60")))
EVENT_BATCH = max(1, min(100, int(os.environ.get("JANUS_MEMORY_EVENT_BATCH", "30"))))
GRAPH_BATCH = max(10, min(300, int(os.environ.get("JANUS_MEMORY_GRAPH_BATCH", "120"))))
REQUEST_TIMEOUT = max(1.0, float(os.environ.get("JANUS_MEMORY_REQUEST_TIMEOUT", "5")))
BACKFILL_THROTTLE = max(0.0, float(os.environ.get("JANUS_MEMORY_BACKFILL_THROTTLE", "0.025")))
GRAPH_PAUSE_SECONDS = max(0.1, float(os.environ.get("JANUS_MEMORY_GRAPH_PAUSE_SECONDS", "2")))
MAX_LOAD_PER_CPU = max(0.0, float(os.environ.get("JANUS_MEMORY_MAX_LOAD_PER_CPU", "2.0")))
MAX_CPU_PERCENT = max(1.0, float(os.environ.get("JANUS_MEMORY_MAX_CPU_PERCENT", "70")))
MAX_IOWAIT_PERCENT = max(1.0, float(os.environ.get("JANUS_MEMORY_MAX_IOWAIT_PERCENT", "20")))
MIN_MEMORY_AVAILABLE_PERCENT = max(1.0, float(os.environ.get("JANUS_MEMORY_MIN_MEMORY_AVAILABLE_PERCENT", "10")))
MAX_API_LATENCY_SECONDS = max(0.5, float(os.environ.get("JANUS_MEMORY_MAX_API_LATENCY_SECONDS", "3")))
SLOW_API_PAUSE_SECONDS = max(15.0, float(os.environ.get("JANUS_MEMORY_SLOW_API_PAUSE_SECONDS", "90")))

ROOT_UID = "janus-memory:federated"
TELEGRAM_UID = "janus-memory:telegram"
MODULES_UID = "janus-memory:modules"
WIKI_UID = "janus-memory:wikipedia-antivik"

MODULES = {
    "janus_titan_core": "Titan / HRAIN Core",
    "janus_bloodrayne": "Bloodrayne",
    "janus_bot_hub": "Golden Janus BotHub",
    "janus_meme_radar": "Meme Radar",
    "janus_bomzhe_guard": "Lenchik Guard",
    "janus_trashcoin": "TrashCoin Economy",
    "janus_radio": "Radio ANUS",
    "janus_video_cinema": "Kino ANUS",
    "janus_music_stream": "Music Stream",
    "janus_hash_ritual": "Hash Ritual",
    "janus_ollama": "Local Ollama",
    "janus_nas_brain": "NAS Brain",
    "janus_sync_worker": "NAS Sync Worker",
}

STOP = False
LOG = logging.getLogger("JANUS.MEMORY_BRIDGE")
SECRET_MARKERS = ("token", "secret", "password", "api_key", "apikey", "authorization", "session_string")
VOLATILE_KEYS = {
    "ts",
    "timestamp",
    "updated_at",
    "updated_epoch",
    "last_seen",
    "last_seen_epoch",
    "expires_epoch",
    "heartbeat",
}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def digest(value: Any, size: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:size]


def clip(value: Any, limit: int = 320) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)] + "..."


def safe_name(value: Any) -> str:
    text = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value or "unknown"))
    return text.strip("_")[:80] or "unknown"


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return clip(value, 240)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 48:
                result["_truncated_keys"] = max(0, len(value) - 48)
                break
            key_text = str(key)
            if any(marker in key_text.lower() for marker in SECRET_MARKERS):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = sanitize(item, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [sanitize(item, depth + 1) for item in items[:16]]
        if len(items) > 16:
            result.append({"_truncated_items": len(items) - 16})
        return result
    if isinstance(value, str):
        return value.replace("\x00", "")[:2400]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return clip(value, 600)


def stable_state(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): stable_state(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [stable_state(item) for item in value]
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    os.replace(temp, path)


def default_state() -> dict[str, Any]:
    return {
        "version": VERSION,
        "telegram_event_cursor": 0,
        "telegram_graph_cursor": 0,
        "experience_cursor": 0,
        "initial_telegram_high_watermark": 0,
        "roots_registered": False,
        "wiki_registered": False,
        "module_state": {},
        "counters": {
            "telegram_events": 0,
            "telegram_graph_rows": 0,
            "module_events": 0,
            "api_failures": 0,
        },
        "started_at": utc_now(),
        "heartbeat_epoch": 0.0,
        "last_api_success_epoch": 0.0,
        "last_error": "",
    }


def read_state() -> dict[str, Any]:
    base = default_state()
    try:
        saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict) and str(saved.get("version") or "") == VERSION:
            base.update(saved)
            if isinstance(saved.get("counters"), dict):
                base["counters"].update(saved["counters"])
            if not isinstance(base.get("module_state"), dict):
                base["module_state"] = {}
    except Exception:
        pass
    return base


def connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def edge(src: str, dst: str, kind: str, payload: dict[str, Any] | None = None, weight: float = 1.0) -> dict[str, Any]:
    return {
        "uid": f"edge:{digest([src, dst, kind], 32)}",
        "src": src,
        "dst": dst,
        "kind": kind,
        "weight": weight,
        "payload": payload or {},
    }


def graph_node(uid: str, kind: str, label: str, text: str = "", payload: dict[str, Any] | None = None, source: str = "janus_memory_bridge", importance: float = 0.5) -> dict[str, Any]:
    return {
        "uid": uid,
        "kind": kind,
        "label": clip(label, 140),
        "text": clip(text, 2400),
        "payload": sanitize(payload or {}),
        "source": source,
        "node_id": NODE_ID,
        "brain_id": BRAIN_ID,
        "importance": importance,
    }


class MemoryBridge:
    def __init__(self) -> None:
        self.state = read_state()
        self.state["started_at"] = utc_now()
        self.state.pop("stopped_at", None)
        self.state["last_error"] = ""
        self.last_module_scan = 0.0
        self.wiki_meta: dict[str, Any] = {}
        self._cpu_sample = self.read_cpu_sample()

    def save(self) -> None:
        self.state["version"] = VERSION
        self.state["heartbeat_epoch"] = time.time()
        self.state["heartbeat_at"] = utc_now()
        atomic_write_json(STATE_PATH, self.state)

    def api_post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        request = urllib.request.Request(
            HRAIN_URL + endpoint,
            data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": VERSION},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                body = response.read(512_000).decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            if not isinstance(data, dict) or data.get("ok") is False:
                raise RuntimeError(f"bad response: {clip(body, 240)}")
            if data.get("db") not in (None, "ok") or data.get("fallback"):
                raise RuntimeError(f"HRain DB fallback: {clip(data, 240)}")
            self.state["last_api_success_epoch"] = time.time()
            self.state["last_api_success_at"] = utc_now()
            self.state["last_error"] = ""
            latency = time.monotonic() - started
            self.state["last_api_latency_ms"] = round(latency * 1000.0, 1)
            if latency > MAX_API_LATENCY_SECONDS:
                self.state["api_slow_until_epoch"] = time.time() + SLOW_API_PAUSE_SECONDS
                self.state["api_slow_reason"] = f"latency={latency:.3f}s"
            return data
        except Exception as exc:
            self.state["counters"]["api_failures"] = int(self.state["counters"].get("api_failures", 0)) + 1
            self.state["last_error"] = clip(repr(exc), 500)
            self.state["last_error_at"] = utc_now()
            self.state["api_slow_until_epoch"] = time.time() + SLOW_API_PAUSE_SECONDS
            self.state["api_slow_reason"] = self.state["last_error"]
            raise

    def telegram_max_id(self) -> int:
        with connect_readonly(SOURCE_DB) as conn:
            if not table_exists(conn, "bot_chat_memory"):
                return 0
            row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM bot_chat_memory").fetchone()
            return int(row[0] or 0)

    def telegram_rows(self, after_id: int, limit: int, up_to: int | None = None) -> list[dict[str, Any]]:
        with connect_readonly(SOURCE_DB) as conn:
            params: list[Any] = [after_id]
            clause = "id > ?"
            if up_to is not None:
                clause += " AND id <= ?"
                params.append(up_to)
            params.append(limit)
            rows = conn.execute(
                "SELECT id, bot_name, chat_id, user_id, author_name, role, content_type, text, created_at "
                f"FROM bot_chat_memory WHERE {clause} ORDER BY id ASC LIMIT ?",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def telegram_event_id(row: dict[str, Any]) -> str:
        return f"telegram:{safe_name(row.get('bot_name'))}:{int(row['id'])}"

    def telegram_event(self, row: dict[str, Any]) -> dict[str, Any]:
        role = str(row.get("role") or "user").lower()
        bot_name = safe_name(row.get("bot_name"))
        content_type = safe_name(row.get("content_type") or "text")
        chat_hash = digest(str(row.get("chat_id") or "unknown"), 20)
        assistant = role == "assistant"
        event_type = f"{bot_name}_reply" if assistant else "telegram_message"
        action = "reply" if assistant else "observe"
        return {
            "event_id": self.telegram_event_id(row),
            "timestamp": str(row.get("created_at") or utc_now()),
            "node_id": f"telegram:{bot_name}:{chat_hash}",
            "brain_id": BRAIN_ID,
            "source": f"telegram/{bot_name}/{role}",
            "event_type": event_type,
            "action": action,
            "text": str(row.get("text") or ""),
            "payload": {
                "source_table": "bot_chat_memory",
                "source_row_id": int(row["id"]),
                "bot_name": bot_name,
                "role": role,
                "content_type": content_type,
                "author_name": str(row.get("author_name") or "unknown"),
                "chat_id": row.get("chat_id"),
                "user_id": row.get("user_id"),
                "module": "janus_bot_hub",
            },
            "tags": ["telegram", bot_name, role, content_type, "living_memory"],
            "importance": 0.78 if assistant else (0.62 if content_type != "text" else 0.52),
            "privacy_level": "local",
        }

    def telegram_graph(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        def add_node(item: dict[str, Any]) -> None:
            nodes[str(item["uid"])] = item

        def add_edge(item: dict[str, Any]) -> None:
            edges[str(item["uid"])] = item

        for row in rows:
            role = str(row.get("role") or "user").lower()
            bot = safe_name(row.get("bot_name"))
            event_uid = "event:" + self.telegram_event_id(row)
            chat_uid = "telegram-chat:" + digest(str(row.get("chat_id") or "unknown"), 24)
            bot_uid = "telegram-persona:" + bot
            author = str(row.get("author_name") or "participant")
            text = str(row.get("text") or "")
            event_label = f"{bot.title()}: {clip(text, 74)}" if role == "assistant" else f"{author}: {clip(text, 74)}"
            add_node(
                graph_node(
                    event_uid,
                    f"telegram_{role}",
                    event_label,
                    text,
                    {
                        "telegram_row_id": int(row["id"]),
                        "timestamp": row.get("created_at"),
                        "role": role,
                        "content_type": row.get("content_type"),
                        "bot_name": bot,
                        "author_name": author,
                    },
                    f"telegram/{bot}",
                    0.78 if role == "assistant" else 0.52,
                )
            )
            add_node(graph_node(chat_uid, "telegram_chat", "Telegram chat", payload={"scope": "local", "chat_hash": chat_uid.rsplit(":", 1)[-1]}, importance=0.7))
            add_node(graph_node(bot_uid, "janus_persona", bot.title(), payload={"bot_name": bot}, importance=0.85))
            add_edge(edge(TELEGRAM_UID, event_uid, "contains_message"))
            add_edge(edge(event_uid, chat_uid, "occurred_in"))
            add_edge(edge(TELEGRAM_UID, chat_uid, "contains_chat"))
            add_edge(edge(TELEGRAM_UID, bot_uid, "contains_persona"))
            if role == "assistant":
                add_edge(edge(event_uid, bot_uid, "spoken_by"))
            else:
                add_edge(edge(event_uid, bot_uid, "observed_by"))
            if row.get("user_id") is not None:
                user_uid = "telegram-user:" + digest(str(row.get("user_id")), 24)
                add_node(graph_node(user_uid, "telegram_participant", author, payload={"author_name": author}, importance=0.48))
                add_edge(edge(TELEGRAM_UID, user_uid, "knows_participant"))
                add_edge(edge(event_uid, user_uid, "replied_to" if role == "assistant" else "authored_by"))
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    def process_telegram_events(self) -> tuple[int, bool]:
        # Telegram is already durably stored by BotHub in this same janus.db.
        # This cursor only marks which source rows are ready for graph projection.
        cursor = int(self.state.get("telegram_event_cursor") or 0)
        current = self.telegram_max_id()
        if current <= cursor:
            return 0, False
        observed = current - cursor
        self.state["telegram_event_cursor"] = current
        self.state["counters"]["telegram_source_rows"] = current
        self.save()
        return observed, False

    def process_telegram_graph(self) -> tuple[int, bool]:
        graph_cursor = int(self.state.get("telegram_graph_cursor") or 0)
        event_cursor = int(self.state.get("telegram_event_cursor") or 0)
        if graph_cursor >= event_cursor:
            return 0, False
        rows = self.telegram_rows(graph_cursor, GRAPH_BATCH, event_cursor)
        if not rows:
            return 0, False
        self.api_post("/api/graph", self.telegram_graph(rows))
        self.state["telegram_graph_cursor"] = int(rows[-1]["id"])
        self.state["counters"]["telegram_graph_rows"] = int(self.state["counters"].get("telegram_graph_rows", 0)) + len(rows)
        self.save()
        time.sleep(GRAPH_PAUSE_SECONDS)
        return len(rows), len(rows) == GRAPH_BATCH

    def wiki_metadata(self) -> dict[str, Any]:
        if self.wiki_meta:
            return self.wiki_meta
        meta: dict[str, Any] = {"path": WIKI_DB.name, "read_only": True, "source": "ANTIVIK/Wikipedia"}
        try:
            meta["bytes"] = WIKI_DB.stat().st_size
            with connect_readonly(WIKI_DB) as conn:
                if table_exists(conn, "thoughts"):
                    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM thoughts").fetchone()
                    meta["thoughts_max_id"] = int(row[0] or 0)
                    latest = conn.execute("SELECT timestamp, source, tags FROM thoughts ORDER BY id DESC LIMIT 1").fetchone()
                    if latest:
                        meta["latest_timestamp"] = latest[0]
                        meta["latest_source"] = latest[1]
                        meta["latest_tags"] = latest[2]
        except Exception as exc:
            meta["error"] = clip(repr(exc), 240)
        self.wiki_meta = sanitize(meta)
        return self.wiki_meta

    def base_graph(self, module_snapshots: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        module_snapshots = module_snapshots or {}
        wiki = self.wiki_metadata()
        nodes = [
            graph_node(ROOT_UID, "memory_root", "JANUS Federated Memory", "Living memory and immutable knowledge in one HRAIN.", {"version": VERSION}, importance=1.0),
            graph_node(TELEGRAM_UID, "living_memory", "Telegram Living Memory", "Incoming Telegram context and Janus replies.", importance=0.95),
            graph_node(MODULES_UID, "module_memory", "Janus Module Memory", "Operational traces produced by Janus modules.", importance=0.9),
            graph_node(WIKI_UID, "knowledge_corpus", "Wikipedia / ANTIVIK", f"Immutable corpus, max thought id {wiki.get('thoughts_max_id', 'unknown')}.", wiki, source="wikipedia_antivik", importance=0.92),
        ]
        edges = [
            edge(ROOT_UID, TELEGRAM_UID, "contains"),
            edge(ROOT_UID, MODULES_UID, "contains"),
            edge(ROOT_UID, WIKI_UID, "grounds_in"),
            edge(TELEGRAM_UID, WIKI_UID, "coexists_with"),
        ]
        for module, label in MODULES.items():
            uid = "janus-module:" + module
            snapshot = sanitize(module_snapshots.get(module) or {"observed": False, "status": "registered"})
            nodes.append(graph_node(uid, "janus_module", label, clip(snapshot, 900), snapshot, source=module, importance=0.72))
            edges.append(edge(MODULES_UID, uid, "contains_module"))
        return {"nodes": nodes, "edges": edges}

    def register_roots(self) -> None:
        self.api_post("/api/graph", self.base_graph())
        self.state["wiki_registered"] = True
        self.state["roots_registered"] = True
        self.save()

    def bot_hub_summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {"observed": False}
        try:
            with connect_readonly(SOURCE_DB) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS rows, COALESCE(MAX(id), 0) AS max_id, "
                    "SUM(CASE WHEN role='assistant' THEN 1 ELSE 0 END) AS replies "
                    "FROM bot_chat_memory"
                ).fetchone()
                result = {"observed": True, "memory_rows": int(row[0] or 0), "max_row_id": int(row[1] or 0), "assistant_replies": int(row[2] or 0)}
        except Exception as exc:
            result["error"] = clip(repr(exc), 180)
        return result

    def hrain_summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {"observed": False}
        try:
            with connect_readonly(SOURCE_DB) as conn:
                values = {}
                for table in ("memory_items", "action_events", "hrain_nodes", "hrain_edges"):
                    if table_exists(conn, table):
                        row = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
                        values[table] = int(row[0] or 0)
                result = {"observed": True, **values}
        except Exception as exc:
            result["error"] = clip(repr(exc), 180)
        return result

    def bloodrayne_summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {"observed": False}
        try:
            with connect_readonly(SOURCE_DB) as conn:
                if table_exists(conn, "device_latest"):
                    rows = [dict(row) for row in conn.execute("SELECT device_id, device_kind, ts, payload_json, updated_at FROM device_latest ORDER BY updated_at DESC LIMIT 12")]
                    for row in rows:
                        try:
                            row["payload"] = json.loads(row.pop("payload_json") or "{}")
                        except Exception:
                            row.pop("payload_json", None)
                    result = {"observed": bool(rows), "devices": sanitize(rows)}
        except Exception as exc:
            result["error"] = clip(repr(exc), 180)
        return result

    def meme_radar_summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {"observed": False}
        try:
            with connect_readonly(MEME_DB) as conn:
                row = conn.execute("SELECT COUNT(*), MAX(posted_at) FROM posted_memes").fetchone()
                latest = conn.execute(
                    "SELECT reddit_id, subreddit, title, score, comments, upvote_ratio, posted_at "
                    "FROM posted_memes ORDER BY posted_at DESC LIMIT 1"
                ).fetchone()
                result = {
                    "observed": True,
                    "posted_total": int(row[0] or 0),
                    "last_posted_at": row[1],
                    "latest": sanitize(dict(latest) if latest else {}),
                }
        except Exception as exc:
            result["error"] = clip(repr(exc), 180)
        return result

    @staticmethod
    def cinema_summary() -> dict[str, Any]:
        raw = load_json(Path("/module_runtime/video_cinema_active.json"))
        return {
            "observed": bool(raw),
            "active": bool(raw.get("active")),
            "title": raw.get("title") or "",
            "file": Path(str(raw.get("path") or "")).name,
            "updated_at": raw.get("updated_at"),
        }

    @staticmethod
    def video_playlist_summary() -> dict[str, Any]:
        raw = load_json(Path("/video_state/video_playlist_state.json"))
        active = raw.get("last_active_session") if isinstance(raw.get("last_active_session"), dict) else {}
        return sanitize(
            {
                "observed": bool(raw),
                "last_announced_title": raw.get("last_announced_title"),
                "last_finished_title": raw.get("last_finished_title"),
                "active_session": {
                    "active": active.get("active"),
                    "title": active.get("title"),
                    "video_key": active.get("video_key"),
                    "start_offset": active.get("start_offset"),
                    "batch_keys": active.get("batch_keys"),
                    "cleared_reason": active.get("cleared_reason"),
                },
                "planned_titles": raw.get("planned_session_titles") or [],
                "prepared_titles": raw.get("prepared_session_titles") or [],
                "prepared_showtime": raw.get("prepared_session_showtime"),
                "watched_total": len(raw.get("watched_keys") or []),
                "collection_cycle": raw.get("collection_cycle"),
                "updated_at": raw.get("updated_at"),
            }
        )

    @staticmethod
    def hash_ritual_summary() -> dict[str, Any]:
        raw = load_json(Path("/module_runtime/hash_ritual/state.json"))
        keys = (
            "version",
            "event_type",
            "authorized",
            "has_job",
            "best_bits",
            "accepted",
            "rejected",
            "submitted",
            "hps_avg",
            "max_hps",
            "video_active",
            "pool",
            "worker",
            "updated_at",
        )
        return sanitize({"observed": bool(raw), **{key: raw.get(key) for key in keys}})

    @staticmethod
    def trashcoin_summary() -> dict[str, Any]:
        raw = load_json(Path("/source/trashcoin_status.json"))
        keys = ("mode", "accounts", "titled", "total_minted", "total_transferred", "total_burned_fees", "ledger_rows", "ts")
        return sanitize({"observed": bool(raw), **{key: raw.get(key) for key in keys}})

    def module_snapshots(self) -> dict[str, dict[str, Any]]:
        cinema = self.cinema_summary()
        trashcoin = self.trashcoin_summary()
        snapshots = {
            "janus_titan_core": self.hrain_summary(),
            "janus_bloodrayne": self.bloodrayne_summary(),
            "janus_bot_hub": self.bot_hub_summary(),
            "janus_meme_radar": self.meme_radar_summary(),
            "janus_bomzhe_guard": {"observed": trashcoin.get("observed", False), "economy": trashcoin},
            "janus_trashcoin": trashcoin,
            "janus_radio": {"observed": True, "coordination": "cinema_silent" if cinema.get("active") else "radio_expected", "cinema": cinema},
            "janus_video_cinema": {**cinema, "playlist": self.video_playlist_summary()},
            "janus_hash_ritual": self.hash_ritual_summary(),
            "janus_sync_worker": {"observed": True, "memory_bus": "memory_items"},
        }
        return {key: sanitize(value) for key, value in snapshots.items()}

    def latest_memory_streams_graph(self) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        try:
            with connect_readonly(SOURCE_DB) as conn:
                if not table_exists(conn, "memory_items"):
                    return {"nodes": [], "edges": []}
                rows = conn.execute(
                    "SELECT m.id, m.memory_id, m.timestamp, m.node_id, m.text, m.payload_json, m.tags_json "
                    "FROM memory_items m JOIN (SELECT node_id, MAX(id) AS max_id FROM memory_items "
                    "WHERE node_id IS NOT NULL AND node_id != '' GROUP BY node_id) latest ON latest.max_id=m.id "
                    "ORDER BY m.id DESC LIMIT 64"
                ).fetchall()
                for row in rows:
                    item = dict(row)
                    node_id = str(item.get("node_id") or "unknown")
                    uid = "memory-stream:" + digest(node_id, 24)
                    payload: dict[str, Any] = {"node_id": node_id, "latest_memory_id": item.get("memory_id"), "timestamp": item.get("timestamp")}
                    for key in ("payload_json", "tags_json"):
                        try:
                            payload[key.removesuffix("_json")] = json.loads(item.get(key) or ("[]" if key == "tags_json" else "{}"))
                        except Exception:
                            pass
                    nodes.append(graph_node(uid, "module_memory_stream", node_id, item.get("text") or "", payload, source=node_id, importance=0.62))
                    edges.append(edge(MODULES_UID, uid, "receives_memory_from"))
                    memory_id = str(item.get("memory_id") or "")
                    if memory_id and not memory_id.startswith("mem:"):
                        edges.append(edge(uid, "memory:" + memory_id, "latest_memory"))
        except Exception as exc:
            LOG.warning("memory stream scan failed: %s", clip(repr(exc), 220))
        return {"nodes": nodes, "edges": edges}

    def emit_module_event(self, module: str, snapshot: dict[str, Any]) -> bool:
        state_map = self.state.setdefault("module_state", {})
        entry = state_map.setdefault(module, {"sequence": 0, "emitted_hash": "", "last_emit_epoch": 0.0})
        fingerprint = digest(stable_state(snapshot), 32)
        entry["observed_hash"] = fingerprint
        entry["last_observed_at"] = utc_now()
        if fingerprint == entry.get("emitted_hash"):
            return False
        now = time.time()
        if now - float(entry.get("last_emit_epoch") or 0.0) < MODULE_EVENT_COOLDOWN:
            return False
        sequence = int(entry.get("sequence") or 0) + 1
        label = MODULES.get(module, module)
        entry["sequence"] = sequence
        entry["emitted_hash"] = fingerprint
        entry["last_emit_epoch"] = now
        entry["last_emit_at"] = utc_now()
        entry["label"] = label
        self.state["counters"]["module_events"] = int(self.state["counters"].get("module_events", 0)) + 1
        return True

    @staticmethod
    def read_cpu_sample() -> tuple[float, ...] | None:
        try:
            line = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0]
            values = tuple(float(item) for item in line.split()[1:9])
            return values if len(values) >= 5 else None
        except Exception:
            return None

    @staticmethod
    def memory_available_percent() -> float | None:
        try:
            values: dict[str, float] = {}
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                key, _, raw = line.partition(":")
                if key in {"MemTotal", "MemAvailable"}:
                    values[key] = float(raw.strip().split()[0])
            total = values.get("MemTotal", 0.0)
            return (values.get("MemAvailable", 0.0) / total) * 100.0 if total > 0 else None
        except Exception:
            return None

    def pressure(self) -> tuple[bool, dict[str, Any]]:
        try:
            if hasattr(os, "getloadavg"):
                load1, load5, load15 = os.getloadavg()
            else:
                load1, load5, load15 = [float(item) for item in Path("/proc/loadavg").read_text(encoding="ascii").split()[:3]]
            cpu_count = max(1, int(os.cpu_count() or 1))
            limit = MAX_LOAD_PER_CPU * cpu_count
            current_cpu = self.read_cpu_sample()
            cpu_percent = None
            iowait_percent = None
            if current_cpu is not None and self._cpu_sample is not None and len(current_cpu) == len(self._cpu_sample):
                deltas = [max(0.0, current - previous) for current, previous in zip(current_cpu, self._cpu_sample)]
                total_delta = sum(deltas)
                if total_delta > 0:
                    idle_delta = deltas[3]
                    iowait_delta = deltas[4]
                    cpu_percent = ((total_delta - idle_delta - iowait_delta) / total_delta) * 100.0
                    iowait_percent = (iowait_delta / total_delta) * 100.0
            self._cpu_sample = current_cpu
            memory_available = self.memory_available_percent()
            slow_until = float(self.state.get("api_slow_until_epoch") or 0.0)
            reasons = []
            if MAX_LOAD_PER_CPU > 0 and load1 > limit:
                reasons.append("hard_load")
            if cpu_percent is not None and cpu_percent > MAX_CPU_PERCENT:
                reasons.append("cpu")
            if iowait_percent is not None and iowait_percent > MAX_IOWAIT_PERCENT:
                reasons.append("iowait")
            if memory_available is not None and memory_available < MIN_MEMORY_AVAILABLE_PERCENT:
                reasons.append("memory")
            if time.time() < slow_until:
                reasons.append("slow_api_backoff")
            details = {
                "load1": round(float(load1), 3),
                "load5": round(float(load5), 3),
                "load15": round(float(load15), 3),
                "cpu_count": cpu_count,
                "hard_load_limit": round(float(limit), 3),
                "cpu_percent": round(cpu_percent, 2) if cpu_percent is not None else None,
                "cpu_limit": MAX_CPU_PERCENT,
                "iowait_percent": round(iowait_percent, 2) if iowait_percent is not None else None,
                "iowait_limit": MAX_IOWAIT_PERCENT,
                "memory_available_percent": round(memory_available, 2) if memory_available is not None else None,
                "memory_available_min": MIN_MEMORY_AVAILABLE_PERCENT,
                "api_slow_until_epoch": slow_until,
                "reasons": reasons,
            }
            return bool(reasons), details
        except Exception as exc:
            return True, {"error": clip(repr(exc), 180), "fail_safe": "paused"}

    def scan_modules(self) -> None:
        snapshots = self.module_snapshots()
        graph = self.base_graph(snapshots)
        streams = self.latest_memory_streams_graph()
        graph["nodes"].extend(streams["nodes"])
        graph["edges"].extend(streams["edges"])
        self.api_post("/api/graph", graph)
        event_modules = ("janus_meme_radar", "janus_trashcoin", "janus_video_cinema", "janus_hash_ritual")
        for module in event_modules:
            self.emit_module_event(module, snapshots.get(module, {"observed": False}))
        self.state["last_module_scan_epoch"] = time.time()
        self.state["last_module_scan_at"] = utc_now()
        self.save()

    def process_experience(self) -> int:
        cursor = int(self.state.get("experience_cursor") or 0)
        try:
            with connect_readonly(SOURCE_DB) as conn:
                if not table_exists(conn, "janus_experience"):
                    return 0
                rows = [dict(row) for row in conn.execute("SELECT * FROM janus_experience WHERE id>? ORDER BY id ASC LIMIT ?", (cursor, EVENT_BATCH)).fetchall()]
        except Exception:
            return 0
        processed = 0
        for row in rows:
            source = safe_name(row.get("source") or "janus_module")
            try:
                summary = json.loads(row.get("summary_json") or "{}")
            except Exception:
                summary = {"raw": clip(row.get("summary_json"), 1600)}
            self.api_post(
                "/api/action/event",
                {
                    "event_id": f"module-experience:{source}:{int(row['id'])}",
                    "timestamp": row.get("ts") or utc_now(),
                    "node_id": f"module:{source}",
                    "brain_id": BRAIN_ID,
                    "source": source,
                    "event_type": str(row.get("event_type") or "module_experience"),
                    "action": "remember_experience",
                    "text": clip(summary, 1200),
                    "payload": {"module": source, "source_row_id": row["id"], "summary": sanitize(summary)},
                    "tags": ["module", source, "experience"],
                    "importance": max(0.2, min(0.9, float(row.get("score") or 0.5))),
                    "privacy_level": "local",
                },
            )
            cursor = int(row["id"])
            self.state["experience_cursor"] = cursor
            processed += 1
        if processed:
            self.save()
        return processed

    def run(self) -> None:
        LOG.info("bridge online version=%s source=%s target=%s", VERSION, SOURCE_DB, HRAIN_URL)
        if not int(self.state.get("initial_telegram_high_watermark") or 0):
            self.state["initial_telegram_high_watermark"] = self.telegram_max_id()
            self.save()
        while not STOP:
            backlog = False
            try:
                processed, more_events = self.process_telegram_events()
                high = int(self.state.get("initial_telegram_high_watermark") or 0)
                initial_caught_up = int(self.state.get("telegram_event_cursor") or 0) >= high
                if initial_caught_up:
                    pressured, pressure = self.pressure()
                    self.state["pressure"] = pressure
                    if pressured:
                        self.state["bridge_status"] = "paused_for_nas_load"
                        self.state["last_cycle_at"] = utc_now()
                        self.save()
                        time.sleep(POLL_SECONDS)
                        continue
                    self.state["bridge_status"] = "projecting_to_hrain"
                    if not self.state.get("roots_registered"):
                        self.register_roots()
                    if time.time() < float(self.state.get("api_slow_until_epoch") or 0.0):
                        self.state["bridge_status"] = "paused_for_slow_hrain"
                        self.save()
                        time.sleep(POLL_SECONDS)
                        continue
                    graph_rows, more_graph = self.process_telegram_graph()
                    now = time.time()
                    if now - self.last_module_scan >= MODULE_SCAN_SECONDS:
                        self.scan_modules()
                        self.last_module_scan = now
                    backlog = more_events or more_graph or graph_rows >= GRAPH_BATCH
                else:
                    backlog = more_events or processed > 0
                if not backlog:
                    self.state["bridge_status"] = "watching"
                self.state["last_cycle_at"] = utc_now()
                self.save()
            except Exception as exc:
                LOG.warning("cycle failed: %s", clip(repr(exc), 300))
                try:
                    self.save()
                except Exception:
                    pass
                time.sleep(min(15.0, POLL_SECONDS * 2.0))
                continue
            time.sleep(0.08 if backlog else POLL_SECONDS)
        self.state["stopped_at"] = utc_now()
        self.save()
        LOG.info("bridge stopped")


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    MemoryBridge().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
