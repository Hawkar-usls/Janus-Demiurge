#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded supervisor for the Demiurge counterfactual laboratory.

The supervisor removes manual intervention *within one admitted objective*:
it repeatedly runs deterministic counterfactual windows until a fixed point,
a configurable plateau, or a hard budget is reached. It then returns WAIT or
BUDGET_EXHAUSTED with a resumable checkpoint.

It never invents an objective and never performs external effects.
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
MAX_WINDOWS = 64
MAX_TOTAL_GENERATIONS = 4096
MAX_PATIENCE_WINDOWS = 16


class LabSupervisorError(ValueError):
    pass


def _positive_int(name: str, value: Any, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LabSupervisorError(f"{name} must be an integer")
    if not 1 <= value <= maximum:
        raise LabSupervisorError(f"{name} must be 1..{maximum}")
    return value


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LabSupervisorError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise LabSupervisorError(f"{name} must be finite and >= 0")
    return result


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
        total_budget = generation_window * max_windows
        if total_budget > MAX_TOTAL_GENERATIONS:
            raise LabSupervisorError(
                f"generation_window * max_windows exceeds {MAX_TOTAL_GENERATIONS}"
            )

        # Reuse the loop's own closed-domain validation before starting work.
        try:
            initial_score = score_core_config(base_config, target_config, weights)
        except CounterfactualLoopError as exc:
            raise LabSupervisorError(str(exc)) from exc

        current_config = dict(base_config)
        current_score = initial_score
        window_receipts: list[dict[str, Any]] = []
        no_meaningful_progress = 0
        total_generations = 0
        total_adoptions = 0
        state = "BUDGET_EXHAUSTED"

        for window_index in range(max_windows):
            window_seed = int(
                canonical_sha256(
                    {
                        "objective_id": objective_id,
                        "root_seed": root_seed,
                        "window_index": window_index,
                        "current_config": current_config,
                        "target_config": dict(target_config),
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
            total_generations += int(loop_result["generations"])
            total_adoptions += int(loop_result["adopted_generations"])

            meaningful = improvement > min_window_improvement
            no_meaningful_progress = 0 if meaningful else no_meaningful_progress + 1
            row = {
                "window_index": window_index,
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

        checkpoint = {
            "schema": "janus.habitat.demiurge_lab_checkpoint.v1",
            "objective_id": objective_id,
            "resume_config": dict(current_config),
            "resume_score": current_score,
            "next_window_index": len(window_receipts),
            "root_seed": root_seed,
            "target_config": dict(target_config),
            "state": state,
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
            "initial_score": initial_score,
            "final_score": current_score,
            "generation_window": generation_window,
            "windows_executed": len(window_receipts),
            "max_windows": max_windows,
            "total_generations": total_generations,
            "total_adoptions": total_adoptions,
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
