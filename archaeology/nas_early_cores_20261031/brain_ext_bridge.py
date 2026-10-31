# -*- coding: utf-8 -*-
"""
Optional bridge that brings selected "Titan brain" donor modules into NAS runtime
as a non-blocking advisory layer.

The layer is intentionally lightweight and disabled by default.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime

from .config import (
    BRAIN_EXT_COOLDOWN,
    BRAIN_EXT_ENABLED,
    BRAIN_EXT_LR_NUDGE,
    BRAIN_EXT_TEMP_NUDGE,
    BRAIN_EXT_VERBOSE,
)


class BrainExtLayer:
    def __init__(self) -> None:
        self.enabled = BRAIN_EXT_ENABLED
        self.verbose = BRAIN_EXT_VERBOSE
        self.cooldown = 0
        self.last_mode = "idle"
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.runtime_dir = os.path.join(self.base_dir, "runtime")
        self.journal_path = os.path.join(self.runtime_dir, "brain_ext_journal.jsonl")
        self.module_index_path = os.path.join(self.base_dir, "donor_modules", "module_index.json")
        self.module_index = self._load_module_index()

        os.makedirs(self.runtime_dir, exist_ok=True)

    def _load_module_index(self):
        if not os.path.exists(self.module_index_path):
            return []
        try:
            with open(self.module_index_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _journal(self, payload: dict) -> None:
        try:
            record = {"ts": datetime.now().isoformat(), **payload}
            with open(self.journal_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def pre_cycle(self, cycle: int, config: dict, progress: dict) -> tuple[dict, str]:
        """
        Returns adjusted config (or original) + mode reason for log.
        """
        if not self.enabled:
            return config, "brain_ext=off"

        cfg = dict(config)
        stagnation = int(progress.get("stagnation_counter", 0) or 0)
        score_window = list(progress.get("score_window", []) or [])
        score_var = 0.0
        if len(score_window) >= 3:
            mean = sum(score_window) / len(score_window)
            score_var = sum((x - mean) ** 2 for x in score_window) / len(score_window)

        mode = "hold"
        if self.cooldown > 0:
            self.cooldown -= 1
            mode = "cooldown"
        elif stagnation >= 3 or score_var < 1e-4:
            # Gentle structured nudge inspired by donor optimizers.
            sign = random.choice([-1.0, 1.0])
            cfg["lr"] = max(0.0002, min(0.02, float(cfg.get("lr", 0.004)) * (1.0 + sign * BRAIN_EXT_LR_NUDGE)))
            cfg["temperature"] = max(
                0.25,
                min(2.2, float(cfg.get("temperature", 1.0)) + sign * BRAIN_EXT_TEMP_NUDGE),
            )
            mode = "nudge"
            self.cooldown = BRAIN_EXT_COOLDOWN

        self.last_mode = mode
        self._journal(
            {
                "kind": "pre_cycle",
                "cycle": cycle,
                "mode": mode,
                "stagnation": stagnation,
                "score_var": score_var,
                "config": cfg,
            }
        )
        return cfg, mode

    def post_cycle(self, cycle: int, config: dict, score: float, metrics: dict, progress: dict, is_record: bool) -> dict:
        if not self.enabled:
            return {"enabled": False, "mode": "off"}

        payload = {
            "kind": "post_cycle",
            "cycle": cycle,
            "mode": self.last_mode,
            "is_record": bool(is_record),
            "score": float(score),
            "metrics": {
                "val_loss": float(metrics.get("val_loss", 0.0)),
                "mutual_info": float(metrics.get("mutual_info", 0.0)),
                "diversity": float(metrics.get("diversity", 0.0)),
                "storj_signal_entropy": float(metrics.get("storj_signal_entropy", 0.0)),
            },
            "progress": {
                "best_score": progress.get("best_score"),
                "stagnation_counter": progress.get("stagnation_counter"),
                "cooldown_cycles": progress.get("cooldown_cycles"),
            },
        }
        self._journal(payload)
        return {"enabled": True, "mode": self.last_mode, "module_count": len(self.module_index)}
