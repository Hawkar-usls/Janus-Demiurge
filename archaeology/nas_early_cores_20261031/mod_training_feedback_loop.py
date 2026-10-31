# -*- coding: utf-8 -*-
"""
mod_training_feedback_loop.py
JANUS NAS — TRAINING FEEDBACK LOOP
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("JANUS.TRAINING_FEEDBACK")

ROOT_DIR = os.environ.get("JANUS_ROOT_DIR", "/app")
RUNTIME_PATH = os.environ.get("JANUS_RUNTIME_DIR") or os.path.join(ROOT_DIR, "runtime")
LAST_IMPORTED_JSON = os.path.join(RUNTIME_PATH, "last_imported.json")
LAST_IMPORT_ERROR_JSON = os.path.join(RUNTIME_PATH, "last_import_error.json")
TRAINING_FEEDBACK_JSON = os.path.join(RUNTIME_PATH, "training_feedback.json")
SCAN_INTERVAL = 150


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


class TrainingFeedbackLoop:
    def __init__(self, core: Any) -> None:
        self.core = core
        self.regression_streak = 0

    async def run_loop(self) -> None:
        logger.info("TRAINING_FEEDBACK: online.")
        while True:
            try:
                await self.tick()
                await asyncio.sleep(SCAN_INTERVAL)
            except asyncio.CancelledError:
                logger.info("TRAINING_FEEDBACK: stopping.")
                raise
            except Exception:
                logger.exception("TRAINING_FEEDBACK LOOP ERROR")
                await asyncio.sleep(60)

    async def tick(self) -> None:
        imported = _read_json(LAST_IMPORTED_JSON) or {}
        import_error = _read_json(LAST_IMPORT_ERROR_JSON) or {}

        feedback = self._build_feedback(imported, import_error)
        self._write_json(TRAINING_FEEDBACK_JSON, feedback)
        await self._publish_feedback(feedback)

    def _build_feedback(self, imported: Dict[str, Any], import_error: Dict[str, Any]) -> Dict[str, Any]:
        meta = imported.get("meta", {}) if isinstance(imported.get("meta"), dict) else {}
        event_id = meta.get("event_id") or imported.get("event_id")
        best_val = _safe_float(meta.get("best_val", imported.get("best_val", 0.0)), 0.0)
        search_mode = meta.get("search_mode", imported.get("search_mode", "unknown"))
        quant_mode = imported.get("quant_mode", meta.get("quant_mode", "unknown"))
        swarm_success_rate = _safe_float(meta.get("swarm_success_rate", 0.0), 0.0)

        has_error = bool(import_error)
        if has_error:
            self.regression_streak += 1
        else:
            self.regression_streak = max(0, self.regression_streak - 1)

        directives = []
        if has_error:
            directives.append("prefer_smb_fallback")
            directives.append("suppress_aggressive_export")
        if self.regression_streak >= 2:
            directives.append("disable_geometry_explorer_temporarily")
            directives.append("force_safe_hyperparam_branch")
        if swarm_success_rate < 0.25:
            directives.append("reduce_swarm_geometry_ratio")
        if best_val and best_val < 2.0:
            directives.append("lock_hunt_on_best_region")
        elif best_val and best_val > 4.0:
            directives.append("expand_recovery_search")
        if search_mode == "RECOVERY_EXPAND":
            directives.append("rollback_if_no_gain")
        if quant_mode == "int8":
            directives.append("keep_nas_quant_contract")

        return {
            "updated_at": int(time.time()),
            "event_id": event_id,
            "regression_streak": self.regression_streak,
            "best_val": best_val,
            "search_mode": search_mode,
            "quant_mode": quant_mode,
            "swarm_success_rate": swarm_success_rate,
            "import_error_present": has_error,
            "import_error": import_error,
            "directives": directives,
        }

    async def _publish_feedback(self, feedback: Dict[str, Any]) -> None:
        try:
            if hasattr(self.core, "context") and isinstance(self.core.context, dict):
                self.core.context["training_feedback"] = feedback
        except Exception:
            logger.debug("TRAINING_FEEDBACK: context publish skipped.", exc_info=True)

        try:
            memory = getattr(self.core, "memory", None)
            if memory is not None and hasattr(memory, "remember"):
                text = (
                    f"event={feedback.get('event_id')} mode={feedback.get('search_mode')} "
                    f"best_val={feedback.get('best_val')} directives={feedback.get('directives')}"
                )
                res = memory.remember("TRAINING_FEEDBACK", text, tags="TRAINING_FEEDBACK,JGPT,NAS")
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            logger.debug("TRAINING_FEEDBACK: memory publish skipped.", exc_info=True)

    def _write_json(self, path: str, data: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


async def run(core: Any) -> None:
    loop = TrainingFeedbackLoop(core)
    core.training_feedback = loop

    nexus = getattr(core, "nexus", None)
    if nexus is not None:
        active = getattr(nexus, "active_services", None)
        if hasattr(active, "add"):
            try:
                active.add("mod_training_feedback_loop")
            except Exception:
                pass

    await loop.run_loop()
