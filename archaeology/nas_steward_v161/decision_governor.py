# -*- coding: utf-8 -*-
"""
mod_janus_decision_governor.py
JANUS NAS — decision governor

Связывает:
- self_awareness
- entropy_policy
- training_feedback
- quant_guardian

И даёт единый decision contract для остальных модулей.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("JANUS.DECISION_GOVERNOR")

ROOT = os.environ.get("JANUS_ROOT_DIR", "/app")
RUNTIME = os.environ.get("JANUS_RUNTIME_DIR") or os.path.join(ROOT, "runtime")

SELF_AWARENESS_JSON = os.path.join(RUNTIME, "self_awareness_state.json")
ENTROPY_POLICY_JSON = os.path.join(RUNTIME, "entropy_policy.json")
TRAINING_FEEDBACK_JSON = os.path.join(RUNTIME, "training_feedback.json")
QUANT_GUARDIAN_JSON = os.path.join(RUNTIME, "quant_guardian_state.json")
GOVERNOR_JSON = os.path.join(RUNTIME, "decision_governor_state.json")

SCAN_INTERVAL = 75


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class DecisionGovernor:
    def __init__(self, core: Any) -> None:
        self.core = core

    async def run_loop(self) -> None:
        logger.info("DECISION_GOVERNOR: online.")
        while True:
            try:
                await self.tick()
                await asyncio.sleep(SCAN_INTERVAL)
            except asyncio.CancelledError:
                logger.info("DECISION_GOVERNOR: stopping.")
                raise
            except Exception:
                logger.exception("DECISION_GOVERNOR LOOP ERROR")
                await asyncio.sleep(60)

    async def tick(self) -> None:
        sa = _read_json(SELF_AWARENESS_JSON) or {}
        ep = _read_json(ENTROPY_POLICY_JSON) or {}
        tf = _read_json(TRAINING_FEEDBACK_JSON) or {}
        qg = _read_json(QUANT_GUARDIAN_JSON) or {}

        directives = []
        directives.extend(sa.get("directives", []))
        directives.extend(tf.get("directives", []))
        directives.extend(qg.get("directives", []))
        if ep.get("mode") == "SURVIVAL":
            directives.append("suppress_optional_jobs")
        if sa.get("mood") in ("PAIN", "ANXIOUS"):
            directives.append("prefer_best_runtime")
        if sa.get("mood") == "EUPHORIA":
            directives.append("allow_light_exploration")

        state = {
            "updated_at": int(time.time()),
            "mood": sa.get("mood"),
            "guardian_status": qg.get("status"),
            "entropy_mode": ep.get("mode"),
            "search_mode": tf.get("search_mode"),
            "directives": sorted(set(directives)),
        }

        os.makedirs(os.path.dirname(GOVERNOR_JSON), exist_ok=True)
        tmp = GOVERNOR_JSON + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, GOVERNOR_JSON)

        try:
            if hasattr(self.core, "context") and isinstance(self.core.context, dict):
                self.core.context["decision_governor"] = state
        except Exception:
            logger.debug("DECISION_GOVERNOR: context publish skipped.", exc_info=True)

        logger.info(
            "DECISION_GOVERNOR | mood=%s | guardian=%s | entropy=%s | search=%s | directives=%s",
            state.get("mood"),
            state.get("guardian_status"),
            state.get("entropy_mode"),
            state.get("search_mode"),
            state.get("directives"),
        )


async def run(core: Any) -> None:
    gov = DecisionGovernor(core)
    core.decision_governor = gov
    nexus = getattr(core, "nexus", None)
    if nexus is not None:
        active = getattr(nexus, "active_services", None)
        if hasattr(active, "add"):
            try:
                active.add("mod_janus_decision_governor")
            except Exception:
                pass
    await gov.run_loop()
