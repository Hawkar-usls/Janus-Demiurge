from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from typing import Any

SCHEMA = "janus.config_neighborhood_estimator.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite numeric")
    try:
        out = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be finite numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite numeric")
    return out


class ConfigNeighborhoodEstimator:
    """Source-bounded descendant of TOWER_GPT TachyonPredictor.

    Historical behavior used only learning-rate proximity (|delta lr| < 0.005)
    despite accepting gain/temp in the config. This restoration preserves that
    narrow estimator while making its evidence boundary explicit.
    """

    def __init__(self, max_history: int = 500, min_history: int = 10, lr_tolerance: float = 0.005, fallback_window: int = 20):
        if max_history < 1 or min_history < 1 or fallback_window < 1:
            raise ValueError("history/window sizes must be positive")
        self.max_history = int(max_history)
        self.min_history = int(min_history)
        self.lr_tolerance = _finite("lr_tolerance", lr_tolerance)
        if self.lr_tolerance <= 0:
            raise ValueError("lr_tolerance must be positive")
        self.fallback_window = int(fallback_window)
        self.history: deque[tuple[dict[str, float], float]] = deque(maxlen=self.max_history)

    def observe(self, config: dict[str, Any], score: Any) -> dict[str, Any]:
        if not isinstance(config, dict):
            raise ValueError("config must be a dict")
        lr = _finite("config.lr", config.get("lr", 0.01))
        score_f = _finite("score", score)
        clean = {"lr": lr}
        for key in ("gain", "temp"):
            if key in config:
                clean[key] = _finite(f"config.{key}", config[key])
        self.history.append((clean, score_f))
        body = {
            "schema": SCHEMA,
            "status": "OBSERVATION_RECORDED",
            "history_size": len(self.history),
            "config": clean,
            "score": score_f,
            "authority": {"changes_runtime": False, "chooses_config": False, "claims_future_information": False},
        }
        body["receipt_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
        return body

    def estimate(self, config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(config, dict):
            raise ValueError("config must be a dict")
        lr = _finite("config.lr", config.get("lr", 0.01))
        if len(self.history) < self.min_history:
            body = {
                "schema": SCHEMA,
                "status": "INSUFFICIENT_HISTORY",
                "estimate": None,
                "history_size": len(self.history),
                "min_history": self.min_history,
                "query_lr": lr,
                "authority": {"chooses_config": False, "claims_improvement_probability": False, "claims_future_information": False},
                "laws": ["INSUFFICIENT_HISTORY_NE_NUMERIC_PRIOR", "EMPIRICAL_ESTIMATE_NE_IMPROVEMENT_PROBABILITY", "CONFIG_NEIGHBORHOOD_NE_CAUSAL_MODEL"],
            }
            body["estimate_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
            return body

        neighbors = [score for cfg, score in self.history if abs(cfg.get("lr", 0.01) - lr) < self.lr_tolerance]
        if neighbors:
            used = neighbors
            method = "LR_NEIGHBOR_MEAN"
        else:
            used = [score for _, score in list(self.history)[-self.fallback_window:]]
            method = "RECENT_MEAN_FALLBACK"

        estimate = sum(used) / len(used)
        body = {
            "schema": SCHEMA,
            "status": "EMPIRICAL_ESTIMATE",
            "method": method,
            "estimate": estimate,
            "query_lr": lr,
            "history_size": len(self.history),
            "sample_count": len(used),
            "lr_tolerance": self.lr_tolerance,
            "ignored_dimensions_by_historical_design": ["gain", "temp"],
            "authority": {"chooses_config": False, "claims_improvement_probability": False, "claims_future_information": False},
            "laws": ["EMPIRICAL_ESTIMATE_NE_IMPROVEMENT_PROBABILITY", "CONFIG_NEIGHBORHOOD_NE_CAUSAL_MODEL", "ESTIMATOR_MUST_BE_SCORED_PROSPECTIVELY"],
        }
        body["estimate_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
        return body
