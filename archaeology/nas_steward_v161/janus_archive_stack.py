from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


logger = logging.getLogger("JANUS.ARCHIVE")

SCHEMA_VERSION = "JANUS/archive-object/v1"
DESCRIPTOR_SCHEMA = "JANUS/archive-ingest-descriptor/v1"
MANIFEST_SCHEMA = "JANUS/archive-manifest/v1"

ROOT_DIR = Path(os.environ.get("JANUS_ROOT_DIR", "/share/CACHEDEV1_DATA/Janus")).resolve()
ARCHIVE_ROOT = Path(
    os.environ.get("JANUS_ARCHIVE_ROOT", str(ROOT_DIR / "archive"))
).resolve()
INBOX_DIR = ARCHIVE_ROOT / "inbox"
MANIFEST_DIR = ARCHIVE_ROOT / "manifests"
SNAPSHOT_DIR = ARCHIVE_ROOT / "snapshots"
QUARANTINE_DIR = ARCHIVE_ROOT / "quarantine"
MANIFEST_PATH = MANIFEST_DIR / "archive_objects.json"
STATUS_PATH = MANIFEST_DIR / "archive_status.json"

ARCHIVE_CATEGORIES = {
    "weights",
    "corpus",
    "telemetry",
    "proof_of_observation",
    "proofpacks",
    "physical_artifacts",
    "manifests",
    "snapshots",
    "experiments",
}

RETENTION_CLASSES = {
    "CANONICAL_KEEP",
    "ACTIVE_RUNTIME",
    "HISTORICAL_KEEP",
    "REGENERATABLE_CACHE",
    "ROTATABLE_LOG",
    "UNKNOWN_PRESERVE",
}

PROTECTED_RELATIVE_PREFIXES = (
    "radio_node/",
    "video_node/",
    "janus_music_stream/",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)) or str(default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)) or str(default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical_json(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_relative_source(raw_path: Any) -> str:
    value = str(raw_path or "").replace("\\", "/").strip().lstrip("/")
    if not value or value.startswith("../") or "/../" in value:
        raise ValueError("invalid_source_relative_path")
    if any(value == prefix[:-1] or value.startswith(prefix) for prefix in PROTECTED_RELATIVE_PREFIXES):
        raise ValueError("protected_source_path")
    source = (ROOT_DIR / value).resolve()
    if not _is_within(source, ROOT_DIR):
        raise ValueError("source_outside_janus_root")
    if _is_within(source, ARCHIVE_ROOT):
        raise ValueError("archive_source_recursion")
    return value


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (cleaned or "object")[:120]


class ArchiveManifestStore:
    def __init__(self, path: Path = MANIFEST_PATH) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": MANIFEST_SCHEMA,
                "updated_at": None,
                "objects": [],
            }
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema") != MANIFEST_SCHEMA or not isinstance(payload.get("objects"), list):
            raise ValueError("invalid_archive_manifest")
        return payload

    def save(self, payload: Dict[str, Any]) -> None:
        normalized = dict(payload)
        normalized["schema"] = MANIFEST_SCHEMA
        normalized["updated_at"] = utc_now()
        normalized["objects"] = sorted(
            list(normalized.get("objects") or []),
            key=lambda item: str(item.get("object_id") or ""),
        )
        _atomic_write_json(self.path, normalized)

    def upsert(self, item: Dict[str, Any]) -> None:
        payload = self.load()
        objects = [
            existing
            for existing in payload.get("objects", [])
            if existing.get("object_id") != item.get("object_id")
        ]
        objects.append(item)
        payload["objects"] = objects
        self.save(payload)

    def summary(self) -> Dict[str, Any]:
        payload = self.load()
        categories: Dict[str, Dict[str, int]] = {}
        total_bytes = 0
        for item in payload.get("objects", []):
            category = str(item.get("category") or "unknown")
            bucket = categories.setdefault(category, {"objects": 0, "bytes": 0})
            size = int(item.get("size") or 0)
            bucket["objects"] += 1
            bucket["bytes"] += size
            total_bytes += size
        return {
            "ok": True,
            "schema": MANIFEST_SCHEMA,
            "object_count": len(payload.get("objects", [])),
            "total_bytes": total_bytes,
            "categories": categories,
            "updated_at": payload.get("updated_at"),
        }


class ArchiveIngestor:
    def __init__(self) -> None:
        self.queue_max = _env_int("JANUS_ARCHIVE_QUEUE_MAX", 16, 1, 128)
        self.max_per_cycle = _env_int("JANUS_ARCHIVE_MAX_PER_CYCLE", 4, 1, 32)
        self.poll_seconds = _env_float("JANUS_ARCHIVE_POLL_SECONDS", 300.0, 30.0, 86400.0)
        self.retry_limit = _env_int("JANUS_ARCHIVE_RETRY_LIMIT", 3, 1, 8)
        self.queue: asyncio.Queue[Path] = asyncio.Queue(maxsize=self.queue_max)
        self.store = ArchiveManifestStore()
        self.stop_event = asyncio.Event()
        self.producer_task: Optional[asyncio.Task[Any]] = None
        self.worker_task: Optional[asyncio.Task[Any]] = None
        self.queued: Set[str] = set()

    def ensure_layout(self) -> None:
        for path in (ARCHIVE_ROOT, INBOX_DIR, MANIFEST_DIR, SNAPSHOT_DIR, QUARANTINE_DIR):
            path.mkdir(parents=True, exist_ok=True)
        for category in sorted(ARCHIVE_CATEGORIES):
            (ARCHIVE_ROOT / category).mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self.producer_task is not None:
            return
        await asyncio.to_thread(self.ensure_layout)
        self.producer_task = asyncio.create_task(self._producer_loop(), name="janus-archive-producer")
        self.worker_task = asyncio.create_task(self._worker_loop(), name="janus-archive-worker")
        logger.info(
            "ARCHIVE INGESTOR ONLINE | root=%s | queue=%s | per_cycle=%s | poll=%.1fs",
            ARCHIVE_ROOT,
            self.queue_max,
            self.max_per_cycle,
            self.poll_seconds,
        )

    async def stop(self) -> None:
        self.stop_event.set()
        for task in (self.producer_task, self.worker_task):
            if task is not None:
                task.cancel()
        for task in (self.producer_task, self.worker_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self.producer_task = None
        self.worker_task = None

    def _descriptor_paths(self) -> List[Path]:
        if not INBOX_DIR.exists():
            return []
        return sorted(
            [path for path in INBOX_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".json"],
            key=lambda path: path.name,
        )

    async def _producer_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                paths = await asyncio.to_thread(self._descriptor_paths)
                added = 0
                for path in paths:
                    key = str(path)
                    if key in self.queued or self.queue.full() or added >= self.max_per_cycle:
                        continue
                    self.queue.put_nowait(path)
                    self.queued.add(key)
                    added += 1
            except Exception as exc:
                logger.warning("ARCHIVE PRODUCER FAIL | %s", exc)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass

    async def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            descriptor = await self.queue.get()
            key = str(descriptor)
            try:
                last_error = None
                for attempt in range(self.retry_limit):
                    try:
                        await asyncio.to_thread(self.process_descriptor, descriptor)
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt + 1 < self.retry_limit:
                            await asyncio.sleep(min(30.0, float(2 ** attempt)))
                if last_error is not None:
                    self._write_failure(descriptor, last_error)
            finally:
                self.queued.discard(key)
                self.queue.task_done()

    def _write_failure(self, descriptor: Path, exc: Exception) -> None:
        payload = {
            "schema": "JANUS/archive-ingest-failure/v1",
            "descriptor": descriptor.name,
            "error": type(exc).__name__ + ":" + str(exc)[:300],
            "ts_utc": utc_now(),
            "source_preserved": True,
            "descriptor_preserved": True,
        }
        digest = hashlib.sha256(_canonical_json(payload)).hexdigest()[:16]
        _atomic_write_json(QUARANTINE_DIR / ("ingest_failure_" + digest + ".json"), payload)

    def process_descriptor(self, descriptor_path: Path) -> Dict[str, Any]:
        descriptor_path = descriptor_path.resolve()
        if descriptor_path.parent != INBOX_DIR.resolve():
            raise ValueError("descriptor_outside_inbox")
        if descriptor_path.stat().st_size > 1024 * 1024:
            raise ValueError("descriptor_too_large")
        descriptor_bytes = descriptor_path.read_bytes()
        descriptor_sha256 = hashlib.sha256(descriptor_bytes).hexdigest()
        with descriptor_path.open("r", encoding="utf-8") as handle:
            descriptor = json.load(handle)
        if descriptor.get("schema") != DESCRIPTOR_SCHEMA:
            raise ValueError("invalid_descriptor_schema")

        category = str(descriptor.get("category") or "").strip()
        if category not in ARCHIVE_CATEGORIES:
            raise ValueError("invalid_archive_category")
        retention_class = str(descriptor.get("retention_class") or "UNKNOWN_PRESERVE")
        if retention_class not in RETENTION_CLASSES:
            raise ValueError("invalid_retention_class")
        source_relative = _safe_relative_source(descriptor.get("source_relative_path"))
        source_path = (ROOT_DIR / source_relative).resolve()
        if not source_path.is_file():
            raise FileNotFoundError("source_not_found")

        source_stat = source_path.stat()
        source_size = source_stat.st_size
        source_mtime_ns = source_stat.st_mtime_ns
        for existing in self.store.load().get("objects", []):
            if (
                existing.get("descriptor_name") == descriptor_path.name
                and existing.get("descriptor_sha256") == descriptor_sha256
                and existing.get("size") == source_size
                and existing.get("source_mtime_ns") == source_mtime_ns
            ):
                cached = dict(existing)
                cached["cached_unchanged"] = True
                return cached
        disk_usage = shutil.disk_usage(str(ARCHIVE_ROOT.parent if not ARCHIVE_ROOT.exists() else ARCHIVE_ROOT))
        required_free = max(64 * 1024 * 1024, int(source_size * 1.20))
        if disk_usage.free < required_free:
            raise OSError("insufficient_archive_free_space")

        source_sha256 = sha256_file(source_path)
        object_id = "sha256:" + source_sha256
        destination_dir = ARCHIVE_ROOT / category / source_sha256[:2]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / (source_sha256 + "__" + _safe_name(source_path.name))

        if destination.exists():
            if destination.stat().st_size != source_size or sha256_file(destination) != source_sha256:
                raise ValueError("content_address_collision")
            deduplicated = True
        else:
            temporary = destination.with_name(destination.name + ".part")
            try:
                with source_path.open("rb") as source_handle, temporary.open("wb") as target_handle:
                    shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
                    target_handle.flush()
                    os.fsync(target_handle.fileno())
                if temporary.stat().st_size != source_size or sha256_file(temporary) != source_sha256:
                    raise ValueError("copy_hash_mismatch")
                os.replace(str(temporary), str(destination))
            finally:
                if temporary.exists():
                    temporary.unlink()
            deduplicated = False

        item = {
            "schema": SCHEMA_VERSION,
            "object_id": object_id,
            "category": category,
            "source": str(descriptor.get("source") or "unknown")[:160],
            "created_at": descriptor.get("created_at"),
            "archived_at": utc_now(),
            "size": source_size,
            "source_mtime_ns": source_mtime_ns,
            "sha256": source_sha256,
            "schema_version": descriptor.get("schema_version"),
            "run_id": descriptor.get("run_id"),
            "profile_hash": descriptor.get("profile_hash"),
            "privacy_status": str(descriptor.get("privacy_status") or "unknown")[:80],
            "retention_class": retention_class,
            "original_safe_alias": source_relative,
            "archive_relative_path": destination.relative_to(ROOT_DIR).as_posix(),
            "descriptor_name": descriptor_path.name,
            "descriptor_sha256": descriptor_sha256,
            "deduplicated": deduplicated,
            "source_preserved": True,
        }
        self.store.upsert(item)
        _atomic_write_json(
            STATUS_PATH,
            {
                "schema": "JANUS/archive-status/v1",
                "ok": True,
                "last_object_id": object_id,
                "last_descriptor": descriptor_path.name,
                "queue_depth": self.queue.qsize(),
                "ts_utc": utc_now(),
            },
        )
        return item


class ArchiveVerifier:
    def __init__(self) -> None:
        self.interval_seconds = _env_float("JANUS_ARCHIVE_VERIFY_SECONDS", 21600.0, 900.0, 604800.0)
        self.max_objects = _env_int("JANUS_ARCHIVE_VERIFY_MAX_OBJECTS", 16, 1, 256)
        self.store = ArchiveManifestStore()
        self.stop_event = asyncio.Event()
        self.task: Optional[asyncio.Task[Any]] = None

    async def start(self) -> None:
        if self.task is not None:
            return
        self.task = asyncio.create_task(self._loop(), name="janus-archive-verifier")
        logger.info(
            "ARCHIVE VERIFIER ONLINE | interval=%.1fs | max_objects=%s",
            self.interval_seconds,
            self.max_objects,
        )

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
            self.task = None

    def verify_once(self) -> Dict[str, Any]:
        payload = self.store.load()
        objects = sorted(payload.get("objects", []), key=lambda item: str(item.get("object_id") or ""))
        checked = []
        for item in objects[: self.max_objects]:
            relative = str(item.get("archive_relative_path") or "")
            path = (ROOT_DIR / relative).resolve()
            valid_path = _is_within(path, ARCHIVE_ROOT)
            actual_size = path.stat().st_size if valid_path and path.is_file() else None
            actual_hash = sha256_file(path) if actual_size is not None else None
            checked.append(
                {
                    "object_id": item.get("object_id"),
                    "exists": actual_size is not None,
                    "size_matches": actual_size == item.get("size") if actual_size is not None else False,
                    "hash_matches": actual_hash == item.get("sha256") if actual_hash else False,
                }
            )
        report = {
            "schema": "JANUS/archive-integrity-snapshot/v1",
            "ts_utc": utc_now(),
            "manifest_object_count": len(objects),
            "checked_count": len(checked),
            "complete_scan": len(checked) == len(objects),
            "ok": all(row["exists"] and row["size_matches"] and row["hash_matches"] for row in checked),
            "checked": checked,
        }
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        _atomic_write_json(SNAPSHOT_DIR / ("integrity_snapshot_" + stamp + ".json"), report)
        return report

    async def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.to_thread(self.verify_once)
            except Exception as exc:
                logger.warning("ARCHIVE VERIFY FAIL | %s", exc)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass


def archive_summary() -> Dict[str, Any]:
    return ArchiveManifestStore().summary()


def archive_objects(limit: int = 100, category: Optional[str] = None) -> Dict[str, Any]:
    payload = ArchiveManifestStore().load()
    objects: Iterable[Dict[str, Any]] = payload.get("objects", [])
    if category:
        objects = [item for item in objects if item.get("category") == category]
    selected = list(objects)[: max(1, min(int(limit), 500))]
    return {
        "ok": True,
        "schema": MANIFEST_SCHEMA,
        "count": len(selected),
        "objects": selected,
        "updated_at": payload.get("updated_at"),
    }
