#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded supervisor for the Demiurge counterfactual laboratory.

The supervisor removes manual intervention *within one admitted objective*:
it repeatedly runs deterministic counterfactual windows until a fixed point,
a configurable plateau, or a hard budget is reached. It then returns WAIT or
BUDGET_EXHAUSTED with an exact continuation checkpoint.

A BUDGET_EXHAUSTED checkpoint can be resumed without restarting the deterministic
window sequence. WAIT_PLATEAU and WAIT_FIXED_POINT are terminal for the current
objective: continuing them requires a new admitted objective rather than hidden
self-generated purpose.

The supervisor never performs external effects or source mutation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from habitat.counterfactual_loop import (
    MAX_CANDIDATES,
    MAX_GENERATIONS,
    CounterfactualLoopError,
    DemiurgeCounterfactualLoop,
    canonical_sha256,
    score_core_config,
)


SUPERVISOR_SCHEMA = "janus.habitat.demiurge_lab_supervisor.v1"
CHECKPOINT_SCHEMA = "janus.habitat.demiurge_lab_checkpoint.v1"
MAX_WINDOWS = 64
MAX_TOTAL_GENERATIONS = 4096
MAX_PATIENCE_WINDOWS = 16
_PARAM_KEYS = ("alpha", "gamma", "epsilon")


class LabSupervisorError(ValueError):
    pass


def _positive_int(name: str, value: Any, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LabSupervisorError(f"{name} must be an integer")
    if not 1 <= value <= maximum:
        raise LabSupervisorError(f"{name} must be 1..{maximum}")
    return value


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LabSupervisorError(f"{name} must be a non-negative integer")
    return value


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LabSupervisorError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise LabSupervisorError(f"{name} must be finite and >= 0")
    return result


def _normalize_weights(weights: Mapping[str, Any] | None) -> dict[str, float]:
    if weights is None:
        return {key: 1.0 for key in _PARAM_KEYS}
    if not isinstance(weights, Mapping) or set(weights) != set(_PARAM_KEYS):
        raise LabSupervisorError("weights must contain exactly alpha/gamma/epsilon")
    normalized: dict[str, float] = {}
    for key in _PARAM_KEYS:
        value = weights.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LabSupervisorError(f"weights.{key} must be finite and > 0")
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise LabSupervisorError(f"weights.{key} must be finite and > 0")
        normalized[key] = value
    return normalized


def _receipt_matches(value: Mapping[str, Any], label: str) -> str:
    receipt = value.get("receipt_sha256")
    if (
        not isinstance(receipt, str)
        or len(receipt) != 64
        or any(char not in "0123456789abcdef" for char in receipt)
    ):
        raise LabSupervisorError(f"{label}.receipt_sha256 must be 64 lowercase hex chars")
    unsigned = dict(value)
    unsigned.pop("receipt_sha256", None)
    if canonical_sha256(unsigned) != receipt:
        raise LabSupervisorError(f"{label} receipt mismatch")
    return receipt


@dataclass(frozen=True)
class DemiurgeLabSupervisor:
    loop: DemiurgeCounterfactualLoop = DemiurgeCounterfactualLoop()

    def wait_without_objective(self) -> dict[str, Any]:
        result = {
            "schema": SUPERVISOR_SCHEMA,
            "state": "WAIT_NO_ADMITTED_OBJECTIVE",
            "objective_present": False,
            "self_generated_objective": False,
            "work_performed": False,
            "authorized": False,
            "external_effect": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result

    def run_objective(
        self,
        *,
        objective_id: str,
        base_config: Mapping[str, Any],
        target_config: Mapping[str, Any],
        root_seed: int,
        generation_window: int = 16,
        max_windows: int = 16,
        candidate_count: int = 8,
        patience_windows: int = 2,
        min_window_improvement: float = 0.0,
        weights: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = self._validate_policy(
            objective_id=objective_id,
            root_seed=root_seed,
            generation_window=generation_window,
            max_windows=max_windows,
            candidate_count=candidate_count,
            patience_windows=patience_windows,
            min_window_improvement=min_window_improvement,
            weights=weights,
        )
        try:
            initial_score = score_core_config(
                base_config, target_config, normalized["weights"]
            )
        except CounterfactualLoopError as exc:
            raise LabSupervisorError(str(exc)) from exc
        return self._run_segment(
            objective_id=objective_id,
            base_config=base_config,
            target_config=target_config,
            root_seed=root_seed,
            generation_window=normalized["generation_window"],
            max_windows=normalized["max_windows"],
            candidate_count=normalized["candidate_count"],
            patience_windows=normalized["patience_windows"],
            min_window_improvement=normalized["min_window_improvement"],
            weights=normalized["weights"],
            window_offset=0,
            prior_total_generations=0,
            prior_total_adoptions=0,
            parent_checkpoint_receipt=None,
            expected_initial_score=initial_score,
        )

    def resume_from_checkpoint(
        self,
        checkpoint: Mapping[str, Any],
        *,
        additional_windows: int = 16,
    ) -> dict[str, Any]:
        cp = self._validate_checkpoint(checkpoint)
        if cp["state"] != "BUDGET_EXHAUSTED":
            raise LabSupervisorError(
                "only BUDGET_EXHAUSTED checkpoints may continue the same objective"
            )
        additional_windows = _positive_int(
            "additional_windows", additional_windows, MAX_WINDOWS
        )
        if cp["generation_window"] * additional_windows > MAX_TOTAL_GENERATIONS:
            raise LabSupervisorError(
                f"generation_window * additional_windows exceeds {MAX_TOTAL_GENERATIONS}"
            )
        return self._run_segment(
            objective_id=cp["objective_id"],
            base_config=cp["resume_config"],
            target_config=cp["target_config"],
            root_seed=cp["root_seed"],
            generation_window=cp["generation_window"],
            max_windows=additional_windows,
            candidate_count=cp["candidate_count"],
            patience_windows=cp["patience_windows"],
            min_window_improvement=cp["min_window_improvement"],
            weights=cp["weights"],
            window_offset=cp["next_window_index"],
            prior_total_generations=cp["total_generations"],
            prior_total_adoptions=cp["total_adoptions"],
            parent_checkpoint_receipt=cp["receipt_sha256"],
            expected_initial_score=cp["resume_score"],
        )

    def _validate_policy(
        self,
        *,
        objective_id: Any,
        root_seed: Any,
        generation_window: Any,
        max_windows: Any,
        candidate_count: Any,
        patience_windows: Any,
        min_window_improvement: Any,
        weights: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(objective_id, str) or not objective_id or len(objective_id) > 128:
            raise LabSupervisorError("objective_id must be a non-empty string <= 128 chars")
        if isinstance(root_seed, bool) or not isinstance(root_seed, int):
            raise LabSupervisorError("root_seed must be an integer")
        generation_window = _positive_int("generation_window", generation_window, MAX_GENERATIONS)
        max_windows = _positive_int("max_windows", max_windows, MAX_WINDOWS)
        candidate_count = _positive_int("candidate_count", candidate_count, MAX_CANDIDATES)
        patience_windows = _positive_int("patience_windows", patience_windows, MAX_PATIENCE_WINDOWS)
        min_window_improvement = _finite_nonnegative(
            "min_window_improvement", min_window_improvement
        )
        if generation_window * max_windows > MAX_TOTAL_GENERATIONS:
            raise LabSupervisorError(
                f"generation_window * max_windows exceeds {MAX_TOTAL_GENERATIONS}"
            )
        return {
            "generation_window": generation_window,
            "max_windows": max_windows,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "weights": _normalize_weights(weights),
        }

    def _run_segment(
        self,
        *,
        objective_id: str,
        base_config: Mapping[str, Any],
        target_config: Mapping[str, Any],
        root_seed: int,
        generation_window: int,
        max_windows: int,
        candidate_count: int,
        patience_windows: int,
        min_window_improvement: float,
        weights: Mapping[str, float],
        window_offset: int,
        prior_total_generations: int,
        prior_total_adoptions: int,
        parent_checkpoint_receipt: str | None,
        expected_initial_score: float,
    ) -> dict[str, Any]:
        try:
            recomputed_score = score_core_config(base_config, target_config, weights)
        except CounterfactualLoopError as exc:
            raise LabSupervisorError(str(exc)) from exc
        if recomputed_score != expected_initial_score:
            raise LabSupervisorError("checkpoint/base score does not replay exactly")

        current_config = dict(base_config)
        current_score = recomputed_score
        window_receipts: list[dict[str, Any]] = []
        no_meaningful_progress = 0
        segment_generations = 0
        segment_adoptions = 0
        state = "BUDGET_EXHAUSTED"

        for local_window_index in range(max_windows):
            absolute_window_index = window_offset + local_window_index
            window_seed = int(
                canonical_sha256(
                    {
                        "objective_id": objective_id,
                        "root_seed": root_seed,
                        "window_index": absolute_window_index,
                        "current_config": current_config,
                        "target_config": dict(target_config),
                        "weights": dict(weights),
                    }
                )[:16],
                16,
            )
            loop_result = self.loop.run(
                base_config=current_config,
                target_config=target_config,
                generations=generation_window,
                candidate_count=candidate_count,
                seed=window_seed,
                weights=weights,
            )
            before = current_score
            after = float(loop_result["final_score"])
            if after < before:
                raise LabSupervisorError("child loop violated monotonic supervisor invariant")
            improvement = after - before
            current_config = dict(loop_result["final_config"])
            current_score = after
            segment_generations += int(loop_result["generations"])
            segment_adoptions += int(loop_result["adopted_generations"])

            meaningful = improvement > min_window_improvement
            no_meaningful_progress = 0 if meaningful else no_meaningful_progress + 1
            row = {
                "window_index": absolute_window_index,
                "window_seed": window_seed,
                "score_before": before,
                "score_after": after,
                "improvement": improvement,
                "meaningful_improvement": meaningful,
                "no_meaningful_progress_windows": no_meaningful_progress,
                "final_config": dict(current_config),
                "loop_receipt_sha256": loop_result["receipt_sha256"],
            }
            row["receipt_sha256"] = canonical_sha256(row)
            window_receipts.append(row)

            # score_core_config has mathematical maximum 0.0.
            if after == 0.0:
                state = "WAIT_FIXED_POINT"
                break
            if no_meaningful_progress >= patience_windows:
                state = "WAIT_PLATEAU"
                break

        cumulative_generations = prior_total_generations + segment_generations
        cumulative_adoptions = prior_total_adoptions + segment_adoptions
        next_window_index = window_offset + len(window_receipts)
        checkpoint = {
            "schema": CHECKPOINT_SCHEMA,
            "objective_id": objective_id,
            "resume_config": dict(current_config),
            "resume_score": current_score,
            "next_window_index": next_window_index,
            "root_seed": root_seed,
            "target_config": dict(target_config),
            "weights": dict(weights),
            "generation_window": generation_window,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "total_generations": cumulative_generations,
            "total_adoptions": cumulative_adoptions,
            "state": state,
            "parent_checkpoint_receipt_sha256": parent_checkpoint_receipt,
        }
        checkpoint["receipt_sha256"] = canonical_sha256(checkpoint)

        result = {
            "schema": SUPERVISOR_SCHEMA,
            "state": state,
            "objective_present": True,
            "objective_id": objective_id,
            "self_generated_objective": False,
            "initial_config": dict(base_config),
            "final_config": dict(current_config),
            "initial_score": recomputed_score,
            "final_score": current_score,
            "weights": dict(weights),
            "generation_window": generation_window,
            "window_offset": window_offset,
            "windows_executed": len(window_receipts),
            "segment_generations": segment_generations,
            "segment_adoptions": segment_adoptions,
            "cumulative_generations": cumulative_generations,
            "cumulative_adoptions": cumulative_adoptions,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "windows": window_receipts,
            "checkpoint": checkpoint,
            "work_performed": True,
            "simulation_only": True,
            "authorized": False,
            "external_effect": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result

    def _validate_checkpoint(self, checkpoint: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(checkpoint, Mapping):
            raise LabSupervisorError("checkpoint must be an object")
        expected = {
            "schema", "objective_id", "resume_config", "resume_score",
            "next_window_index", "root_seed", "target_config", "weights",
            "generation_window", "candidate_count", "patience_windows",
            "min_window_improvement", "total_generations", "total_adoptions",
            "state", "parent_checkpoint_receipt_sha256", "receipt_sha256"
        }
        if set(checkpoint) != expected:
            raise LabSupervisorError("checkpoint schema is not closed")
        if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
            raise LabSupervisorError("unsupported checkpoint schema")
        receipt = _receipt_matches(checkpoint, "checkpoint")
        objective_id = checkpoint.get("objective_id")
        if not isinstance(objective_id, str) or not objective_id or len(objective_id) > 128:
            raise LabSupervisorError("checkpoint objective_id invalid")
        root_seed = checkpoint.get("root_seed")
        if isinstance(root_seed, bool) or not isinstance(root_seed, int):
            raise LabSupervisorError("checkpoint root_seed invalid")
        next_window_index = _nonnegative_int(
            "checkpoint.next_window_index", checkpoint.get("next_window_index")
        )
        total_generations = _nonnegative_int(
            "checkpoint.total_generations", checkpoint.get("total_generations")
        )
        total_adoptions = _nonnegative_int(
            "checkpoint.total_adoptions", checkpoint.get("total_adoptions")
        )
        state = checkpoint.get("state")
        if state not in {"BUDGET_EXHAUSTED", "WAIT_PLATEAU", "WAIT_FIXED_POINT"}:
            raise LabSupervisorError("checkpoint state invalid")
        parent = checkpoint.get("parent_checkpoint_receipt_sha256")
        if parent is not None:
            if (
                not isinstance(parent, str)
                or len(parent) != 64
                or any(char not in "0123456789abcdef" for char in parent)
            ):
                raise LabSupervisorError("parent checkpoint receipt invalid")

        normalized = self._validate_policy(
            objective_id=objective_id,
            root_seed=root_seed,
            generation_window=checkpoint.get("generation_window"),
            max_windows=1,
            candidate_count=checkpoint.get("candidate_count"),
            patience_windows=checkpoint.get("patience_windows"),
            min_window_improvement=checkpoint.get("min_window_improvement"),
            weights=checkpoint.get("weights"),
        )
        resume_score = checkpoint.get("resume_score")
        if isinstance(resume_score, bool) or not isinstance(resume_score, (int, float)):
            raise LabSupervisorError("checkpoint resume_score invalid")
        resume_score = float(resume_score)
        if not math.isfinite(resume_score):
            raise LabSupervisorError("checkpoint resume_score must be finite")
        try:
            replayed_score = score_core_config(
                checkpoint.get("resume_config"),
                checkpoint.get("target_config"),
                normalized["weights"],
            )
        except CounterfactualLoopError as exc:
            raise LabSupervisorError(str(exc)) from exc
        if replayed_score != resume_score:
            raise LabSupervisorError("checkpoint resume score does not match config/target")

        return {
            "receipt_sha256": receipt,
            "objective_id": objective_id,
            "resume_config": dict(checkpoint["resume_config"]),
            "resume_score": resume_score,
            "next_window_index": next_window_index,
            "root_seed": root_seed,
            "target_config": dict(checkpoint["target_config"]),
            "weights": normalized["weights"],
            "generation_window": normalized["generation_window"],
            "candidate_count": normalized["candidate_count"],
            "patience_windows": normalized["patience_windows"],
            "min_window_improvement": normalized["min_window_improvement"],
            "total_generations": total_generations,
            "total_adoptions": total_adoptions,
            "state": state,
        }
