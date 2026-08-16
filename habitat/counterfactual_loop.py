#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic closed-loop laboratory for the bounded Demiurge Habitat face.

This is a safe descendant of the legacy AutoEvolution/Tachyon ideas:

    STATE -> PROPOSE -> COUNTERFACTUAL SCORE -> RANK
          -> ADOPT-IF-BETTER -> RECEIPT -> NEXT GENERATION

The loop changes only an in-memory experimental configuration. It does not
mutate source, write files, open network connections, spawn processes, train
models, or claim that the counterfactual objective predicts the real future.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from habitat.demiurge_face import (
    CORE_RANGES,
    REQUEST_SCHEMA,
    DemiurgeFaceError,
    HabitatDemiurgeFace,
    canonical_sha256,
)


LOOP_SCHEMA = "janus.habitat.demiurge_counterfactual_loop.v1"
MAX_GENERATIONS = 64
MAX_CANDIDATES = 16


class CounterfactualLoopError(ValueError):
    pass


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CounterfactualLoopError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise CounterfactualLoopError(f"{label} must be finite")
    return result


def _validate_core_config(value: Mapping[str, Any], label: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise CounterfactualLoopError(f"{label} must be an object")
    if set(value) != set(CORE_RANGES):
        raise CounterfactualLoopError(f"{label} must contain exactly {sorted(CORE_RANGES)}")
    result: dict[str, float] = {}
    for key, (low, high) in CORE_RANGES.items():
        number = _finite(value.get(key), f"{label}.{key}")
        if not low <= number <= high:
            raise CounterfactualLoopError(f"{label}.{key} outside admitted range")
        result[key] = number
    return result


def _validate_weights(value: Mapping[str, Any] | None) -> dict[str, float]:
    if value is None:
        return {key: 1.0 for key in CORE_RANGES}
    if not isinstance(value, Mapping) or set(value) != set(CORE_RANGES):
        raise CounterfactualLoopError("weights must contain exactly alpha/gamma/epsilon")
    out: dict[str, float] = {}
    for key in CORE_RANGES:
        weight = _finite(value.get(key), f"weights.{key}")
        if weight <= 0:
            raise CounterfactualLoopError("weights must be > 0")
        out[key] = weight
    return out


def score_core_config(
    config: Mapping[str, Any],
    target: Mapping[str, Any],
    weights: Mapping[str, Any] | None = None,
) -> float:
    """Closed deterministic counterfactual objective; maximum is 0.0.

    Distance is normalized by each admitted parameter range so unlike scales do
    not dominate. This score is a laboratory objective, not empirical evidence.
    """
    cfg = _validate_core_config(config, "config")
    tgt = _validate_core_config(target, "target")
    w = _validate_weights(weights)
    total = 0.0
    norm = 0.0
    for key, (low, high) in CORE_RANGES.items():
        span = high - low
        delta = (cfg[key] - tgt[key]) / span
        total += w[key] * delta * delta
        norm += w[key]
    return -float(total / norm)


@dataclass(frozen=True)
class DemiurgeCounterfactualLoop:
    """Autonomous local evolution loop with zero external-effect authority."""

    face: HabitatDemiurgeFace = HabitatDemiurgeFace()

    def run(
        self,
        *,
        base_config: Mapping[str, Any],
        target_config: Mapping[str, Any],
        generations: int = 12,
        candidate_count: int = 8,
        seed: int = 0,
        weights: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(generations, bool) or not isinstance(generations, int):
            raise CounterfactualLoopError("generations must be an integer")
        if not 1 <= generations <= MAX_GENERATIONS:
            raise CounterfactualLoopError(f"generations must be 1..{MAX_GENERATIONS}")
        if isinstance(candidate_count, bool) or not isinstance(candidate_count, int):
            raise CounterfactualLoopError("candidate_count must be an integer")
        if not 1 <= candidate_count <= MAX_CANDIDATES:
            raise CounterfactualLoopError(f"candidate_count must be 1..{MAX_CANDIDATES}")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise CounterfactualLoopError("seed must be an integer")

        current = _validate_core_config(base_config, "base_config")
        target = _validate_core_config(target_config, "target_config")
        normalized_weights = _validate_weights(weights)
        initial = dict(current)
        incumbent_score = score_core_config(current, target, normalized_weights)
        initial_score = incumbent_score
        lineage: list[dict[str, Any]] = []
        adopted_count = 0

        for generation in range(generations):
            generation_seed_material = {
                "root_seed": seed,
                "generation": generation,
                "current": current,
                "target": target,
                "weights": normalized_weights,
            }
            generation_seed = int(canonical_sha256(generation_seed_material)[:16], 16)
            request = {
                "schema": REQUEST_SCHEMA,
                "request_id": f"counterfactual-generation-{generation:04d}",
                "mode": "CORE_PARAMETER_VARIATION",
                "seed": generation_seed,
                "candidate_count": candidate_count,
                "base_config": current,
            }
            try:
                proposal_set = self.face.propose(request)
            except DemiurgeFaceError as exc:
                raise CounterfactualLoopError(f"proposal generation failed: {exc}") from exc

            config_by_id = {
                row["proposal_id"]: dict(row["config"])
                for row in proposal_set["proposals"]
            }
            evaluations = [
                {
                    "proposal_id": proposal_id,
                    "score": score_core_config(config, target, normalized_weights),
                }
                for proposal_id, config in config_by_id.items()
            ]
            ranking = self.face.rank_evaluated(
                proposal_set,
                evaluations,
                objective="score",
                maximize=True,
            )
            selected_id = ranking["selected_proposal_id"]
            selected_config = config_by_id[selected_id]
            selected_score = float(ranking["ranking"][0]["score"])
            adopted = selected_score > incumbent_score
            previous_score = incumbent_score
            if adopted:
                current = dict(selected_config)
                incumbent_score = selected_score
                adopted_count += 1

            generation_record = {
                "generation": generation,
                "generation_seed": generation_seed,
                "incumbent_score_before": previous_score,
                "selected_proposal_id": selected_id,
                "selected_score": selected_score,
                "adopted": adopted,
                "incumbent_score_after": incumbent_score,
                "incumbent_config_after": dict(current),
                "proposal_receipt_sha256": proposal_set["receipt_sha256"],
                "ranking_receipt_sha256": ranking["receipt_sha256"],
            }
            generation_record["receipt_sha256"] = canonical_sha256(generation_record)
            lineage.append(generation_record)

        result = {
            "schema": LOOP_SCHEMA,
            "mode": "LOCAL_COUNTERFACTUAL_EVOLUTION",
            "initial_config": initial,
            "target_config": target,
            "weights": normalized_weights,
            "initial_score": initial_score,
            "final_config": dict(current),
            "final_score": incumbent_score,
            "generations": generations,
            "candidate_count": candidate_count,
            "adopted_generations": adopted_count,
            "lineage": lineage,
            "simulation_only": True,
            "future_prediction_claimed": False,
            "scientific_validation_claimed": False,
            "source_writeback": False,
            "external_effect": False,
            "authorized": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
