# -*- coding: utf-8 -*-
"""
mod_model_selector.py
JANUS NAS — MODEL SELECTOR
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("JANUS.MODEL_SELECTOR")

ROOT_DIR = os.environ.get("JANUS_ROOT_DIR", "/app")
MODEL_ZOO_PATH = os.environ.get("JANUS_MODEL_ZOO_DIR") or os.path.join(ROOT_DIR, "model_zoo")
RUNTIME_PATH = os.environ.get("JANUS_RUNTIME_DIR") or os.path.join(ROOT_DIR, "runtime")
SELECTOR_STATE_JSON = os.path.join(RUNTIME_PATH, "model_selector_state.json")
SELECTOR_SHORTLIST_JSON = os.path.join(RUNTIME_PATH, "model_selector_shortlist.json")
SCAN_INTERVAL = 180
TOP_K = 12


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


class ModelSelector:
    def __init__(self, core: Any) -> None:
        self.core = core
        self.best_entry: Optional[Dict[str, Any]] = None
        self.last_digest: Optional[str] = None

    async def run_loop(self) -> None:
        logger.info("MODEL_SELECTOR: online.")
        while True:
            try:
                await self.scan_once()
                await asyncio.sleep(SCAN_INTERVAL)
            except asyncio.CancelledError:
                logger.info("MODEL_SELECTOR: stopping.")
                raise
            except Exception:
                logger.exception("MODEL_SELECTOR LOOP ERROR")
                await asyncio.sleep(60)

    async def scan_once(self) -> None:
        if not os.path.isdir(MODEL_ZOO_PATH):
            logger.warning("MODEL_SELECTOR: model_zoo missing: %s", MODEL_ZOO_PATH)
            return

        entries: List[Dict[str, Any]] = []
        for name in os.listdir(MODEL_ZOO_PATH):
            if not name.endswith(".json"):
                continue
            path = os.path.join(MODEL_ZOO_PATH, name)
            payload = self._read_json(path)
            if not isinstance(payload, dict):
                continue
            entry = self._normalize_entry(name, path, payload)
            if entry:
                entries.append(entry)

        if not entries:
            logger.info("MODEL_SELECTOR: no candidate json found.")
            return

        ranked = sorted(entries, key=self._rank_key, reverse=True)
        shortlist = ranked[:TOP_K]
        best = shortlist[0]

        os.makedirs(RUNTIME_PATH, exist_ok=True)
        self._write_json(SELECTOR_SHORTLIST_JSON, shortlist)
        self._write_json(
            SELECTOR_STATE_JSON,
            {
                "updated_at": int(time.time()),
                "best": best,
                "shortlist_count": len(shortlist),
                "model_zoo_path": MODEL_ZOO_PATH,
            },
        )

        if best.get("digest") != self.last_digest:
            self.last_digest = best.get("digest")
            self.best_entry = best
            logger.info(
                "MODEL_SELECTOR: new best -> %s | score=%.4f | loss=%.4f | quality=%.4f",
                best.get("name"),
                best.get("score", 0.0),
                best.get("loss", 0.0),
                best.get("quality", 0.0),
            )
            await self._publish_best(best)

    def _normalize_entry(self, name: str, path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
        score = _safe_float(payload.get("score", meta.get("score", 0.0)), 0.0)
        loss = _safe_float(payload.get("loss", meta.get("loss", 999999.0)), 999999.0)
        cycle = _safe_int(payload.get("cycle", meta.get("cycle", 0)), 0)
        quant_mode = payload.get("quant_mode", meta.get("quant_mode", "unknown"))
        search_mode = meta.get("search_mode", "unknown")
        swarm_success_rate = _safe_float(meta.get("swarm_success_rate", 0.0), 0.0)
        val = _safe_float(meta.get("best_val", meta.get("val", loss)), loss)

        quality = score - (loss * 0.65) - (val * 0.35) + (swarm_success_rate * 0.25)

        return {
            "name": name,
            "path": path,
            "digest": f"{name}:{cycle}:{quant_mode}:{score:.6f}:{loss:.6f}",
            "score": score,
            "loss": loss,
            "val": val,
            "cycle": cycle,
            "quant_mode": quant_mode,
            "search_mode": search_mode,
            "swarm_success_rate": swarm_success_rate,
            "quality": quality,
            "meta": meta,
        }

    def _rank_key(self, entry: Dict[str, Any]) -> Tuple[float, float, float]:
        return (
            _safe_float(entry.get("quality", 0.0)),
            _safe_float(entry.get("score", 0.0)),
            -_safe_float(entry.get("loss", 999999.0)),
        )

    async def _publish_best(self, best: Dict[str, Any]) -> None:
        try:
            if hasattr(self.core, "context") and isinstance(self.core.context, dict):
                self.core.context["model_selector_best"] = best
        except Exception:
            logger.debug("MODEL_SELECTOR: context publish skipped.", exc_info=True)

        try:
            settings = getattr(self.core, "settings", None)
            if settings is not None and hasattr(settings, "set"):
                settings.set("model_selector_best", best.get("name"))
        except Exception:
            logger.debug("MODEL_SELECTOR: settings publish skipped.", exc_info=True)

        try:
            memory = getattr(self.core, "memory", None)
            if memory is not None and hasattr(memory, "remember"):
                res = memory.remember(
                    "MODEL_SELECTOR",
                    f"BEST={best.get('name')} score={best.get('score')} loss={best.get('loss')} mode={best.get('search_mode')}",
                    tags="MODEL_SELECTOR,MODEL_ZOO,SHORTLIST",
                )
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            logger.debug("MODEL_SELECTOR: memory publish skipped.", exc_info=True)

    def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.debug("MODEL_SELECTOR: read failed for %s", path, exc_info=True)
            return None

    def _write_json(self, path: str, data: Any) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


async def run(core: Any) -> None:
    selector = ModelSelector(core)
    core.model_selector = selector

    nexus = getattr(core, "nexus", None)
    if nexus is not None:
        active = getattr(nexus, "active_services", None)
        if hasattr(active, "add"):
            try:
                active.add("mod_model_selector")
            except Exception:
                pass

    await selector.run_loop()
