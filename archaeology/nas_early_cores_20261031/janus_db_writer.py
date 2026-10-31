from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sqlite3
import time
from typing import Any, Awaitable, Callable

import aiosqlite


logger = logging.getLogger("JANUS.DBWRITER")

DB_WRITER_BATCH_SIZE = max(1, min(int(os.environ.get("JANUS_DB_WRITER_BATCH_SIZE", "4") or "4"), 16))
DB_WRITER_FLUSH_INTERVAL = max(0.05, min(float(os.environ.get("JANUS_DB_WRITER_FLUSH_INTERVAL", "0.25") or "0.25"), 2.0))
DB_WRITER_MIN_BATCH_INTERVAL = max(0.1, min(float(os.environ.get("JANUS_DB_WRITER_MIN_BATCH_INTERVAL", "0.2") or "0.2"), 2.0))
DB_WRITER_RETRIES = max(1, min(int(os.environ.get("JANUS_DB_WRITER_RETRIES", "5") or "5"), 10))
DB_WRITER_TIMEOUT = max(5.0, min(float(os.environ.get("JANUS_DB_WRITER_TIMEOUT", "65") or "65"), 300.0))

DbWork = Callable[[aiosqlite.Connection], Awaitable[Any]]

_WRITERS: dict[str, "JanusDbWriter"] = {}


class JanusDbWriter:
    def __init__(self, db_path: str) -> None:
        self.db_path = str(db_path or "").strip()
        self.queue: asyncio.Queue[tuple[DbWork, asyncio.Future[Any]]] = asyncio.Queue()
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[Any] | None = None
        self.connection: aiosqlite.Connection | None = None
        self.last_batch_at = 0.0

    async def start(self) -> None:
        if self.task is not None:
            return
        self.connection = await aiosqlite.connect(self.db_path, timeout=60.0)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA synchronous=NORMAL")
        await self.connection.execute("PRAGMA busy_timeout=60000")
        self.task = asyncio.create_task(self._worker(), name="janus-db-writer")
        logger.info("DB WRITER ONLINE | db=%s | batch=%s", self.db_path, DB_WRITER_BATCH_SIZE)

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task is not None:
            with contextlib.suppress(Exception):
                await self.task
            self.task = None
        if self.connection is not None:
            with contextlib.suppress(Exception):
                await self.connection.close()
            self.connection = None

    async def submit(self, work: DbWork, timeout: float = DB_WRITER_TIMEOUT) -> Any:
        await self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        await self.queue.put((work, future))
        return await asyncio.wait_for(future, timeout=max(1.0, float(timeout or DB_WRITER_TIMEOUT)))

    async def execute(self, statements: list[tuple[str, tuple[Any, ...]]], timeout: float = DB_WRITER_TIMEOUT) -> Any:
        async def _work(connection: aiosqlite.Connection) -> Any:
            last_row_id = None
            for query, params in statements:
                cursor = await connection.execute(query, params)
                try:
                    if getattr(cursor, "lastrowid", None):
                        last_row_id = cursor.lastrowid
                finally:
                    await cursor.close()
            return last_row_id

        return await self.submit(_work, timeout=timeout)

    async def _drain_batch(self) -> list[tuple[DbWork, asyncio.Future[Any]]]:
        batch = [await self.queue.get()]
        deadline = time.monotonic() + DB_WRITER_FLUSH_INTERVAL
        while len(batch) < DB_WRITER_BATCH_SIZE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            batch.append(item)
        return batch

    async def _execute_batch(self, batch: list[tuple[DbWork, asyncio.Future[Any]]]) -> None:
        if not batch:
            return
        assert self.connection is not None
        last_exc: Exception | None = None
        for attempt in range(DB_WRITER_RETRIES):
            try:
                await self.connection.execute("BEGIN IMMEDIATE")
                results = []
                for work, future in batch:
                    if future.cancelled():
                        results.append(None)
                        continue
                    results.append(await work(self.connection))
                await self.connection.commit()
                for (_, future), result in zip(batch, results):
                    if not future.done():
                        future.set_result(result)
                return
            except sqlite3.Error as exc:
                last_exc = exc
                with contextlib.suppress(Exception):
                    await self.connection.rollback()
                if "locked" in str(exc).lower() and attempt < DB_WRITER_RETRIES - 1:
                    logger.warning("DB WRITER LOCK RETRY [%s/%s] %s", attempt + 1, DB_WRITER_RETRIES, exc)
                    await asyncio.sleep(min(2.0, 0.25 * (attempt + 1)))
                    continue
                break
            except Exception as exc:
                last_exc = exc
                with contextlib.suppress(Exception):
                    await self.connection.rollback()
                break
        for _, future in batch:
            if not future.done():
                future.set_exception(last_exc or RuntimeError("db_writer_batch_failed"))

    async def _worker(self) -> None:
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                batch = await self._drain_batch()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("DB WRITER DRAIN FAIL | %s", exc)
                await asyncio.sleep(0.5)
                continue

            now = time.monotonic()
            if self.last_batch_at and (now - self.last_batch_at) < DB_WRITER_MIN_BATCH_INTERVAL:
                await asyncio.sleep(DB_WRITER_MIN_BATCH_INTERVAL - (now - self.last_batch_at))
            await self._execute_batch(batch)
            self.last_batch_at = time.monotonic()


def get_db_writer(db_path: str) -> JanusDbWriter:
    key = str(db_path or "").strip()
    writer = _WRITERS.get(key)
    if writer is None:
        writer = JanusDbWriter(key)
        _WRITERS[key] = writer
    return writer


async def close_all_writers() -> None:
    writers = list(_WRITERS.values())
    _WRITERS.clear()
    for writer in writers:
        with contextlib.suppress(Exception):
            await writer.stop()
