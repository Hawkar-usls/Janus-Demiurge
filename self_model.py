#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SELF MODEL — persistent JANUS identity evolving by accumulated spiral turns."""

import logging
from typing import Dict, Any

import numpy as np

from spiral_evolution import PreservingWindow, SpiralLedger

logger = logging.getLogger("JANUS.SELF")

CONFIG = {
    'history_size': 50,
    'quality_threshold_efficient': 0.8,
    'time_threshold_aggressive': 6.0
}


class SelfModel:
    def __init__(self):
        self.identity = {
            "mode": "balanced",
            "confidence": 0.5,
            "self_trust": 0.5,
            "archetype": "Demiurge of Thresholds",
            "title": "Janus Tachyon"
        }
        self.goals = {
            "quality": 0.7,
            "efficiency": 0.5,
            "learning": 0.8
        }
        # The active statistics window stays bounded; overflow is ancestry.
        self.history = PreservingWindow(CONFIG['history_size'])
        self.spiral = SpiralLedger("JANUS_SELF_MODEL")

    def update(self, outcome: Dict[str, Any]) -> None:
        """Integrate an outcome without deleting an older self-state."""
        before = {
            "identity": dict(self.identity),
            "goals": dict(self.goals),
        }
        self.history.append(dict(outcome))
        self._recalculate_identity()
        if "pred_error" in outcome:
            self.update_self_trust(outcome["pred_error"])
        after = {
            "identity": dict(self.identity),
            "goals": dict(self.goals),
        }
        self.spiral.ascend(
            state_before=before,
            candidate_state={"outcome": outcome},
            active_state_after=after,
            lessons=["Outcome integrated into persistent self-model identity."],
            promoted=before != after,
            outcome="ASCENDED" if before != after else "INTEGRATED_LESSON",
        )

    def _recalculate_identity(self) -> None:
        active = list(self.history)
        if len(active) < 5:
            return
        avg_quality = np.mean([h.get("quality", 0) for h in active])
        timed = [h.get("time", 0) for h in active if "time" in h]
        avg_time = np.mean(timed) if timed else 0.0

        if avg_quality > CONFIG['quality_threshold_efficient']:
            self.identity["mode"] = "efficient"
        elif avg_time > CONFIG['time_threshold_aggressive']:
            self.identity["mode"] = "aggressive"
        else:
            self.identity["mode"] = "balanced"

        qualities = [h.get("quality", 0) for h in active]
        if len(qualities) > 5:
            std = np.std(qualities)
            self.identity["confidence"] = max(0.0, min(1.0, 1.0 - std))
        else:
            self.identity["confidence"] = 0.5

    def update_self_trust(self, pred_error: float) -> None:
        self.identity["self_trust"] = 1.0 / (1.0 + pred_error)
        self.identity["self_trust"] = max(0.05, min(0.95, self.identity["self_trust"]))

    def update_mode_by_error(self, error: float) -> None:
        before = {"identity": dict(self.identity), "goals": dict(self.goals)}
        if error > 1000:
            self.identity["mode"] = "explorer"
            self.goals["learning"] += 0.1
        elif error > 200:
            self.identity["mode"] = "balanced"
        else:
            self.identity["mode"] = "efficient"
        for key in self.goals:
            self.goals[key] = max(0.0, min(1.0, self.goals[key]))
        after = {"identity": dict(self.identity), "goals": dict(self.goals)}
        self.spiral.ascend(
            state_before=before,
            candidate_state={"prediction_error": error},
            active_state_after=after,
            lessons=["Prediction error converted into a self-model adaptation signal."],
            promoted=before != after,
            outcome="ASCENDED" if before != after else "INTEGRATED_LESSON",
        )

    def meta_adapt(self) -> None:
        active = list(self.history)
        if len(active) < 10:
            return
        before = {"identity": dict(self.identity), "goals": dict(self.goals)}
        recent_quality = np.mean([h.get("quality", 0) for h in active[-10:]])
        if recent_quality < 0.5:
            self.goals["learning"] += 0.05
            self.goals["efficiency"] -= 0.02
        elif recent_quality > 0.8:
            self.goals["efficiency"] += 0.05
            self.goals["learning"] -= 0.02
        for key in self.goals:
            self.goals[key] = max(0.0, min(1.0, self.goals[key]))
        after = {"identity": dict(self.identity), "goals": dict(self.goals)}
        self.spiral.ascend(
            state_before=before,
            candidate_state={"recent_quality": float(recent_quality)},
            active_state_after=after,
            lessons=["Recent quality window integrated without erasing older outcomes."],
            promoted=before != after,
            outcome="ASCENDED" if before != after else "NO_ASCENT",
        )

    def get_spiral_state(self) -> Dict[str, Any]:
        return {
            "turn": self.spiral.next_turn,
            "active_history": len(self.history),
            "archived_history": len(self.history.archive),
            "total_history": len(self.history.all_items()),
            "logical_ring": False,
        }
