#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded deterministic Physarum proposal heuristic for JANUS Habitat.

Derived from the user-supplied ``physarum_engine.py`` concept, but deliberately
separates evaluation from optimization. The active face consumes only an
already-computed finite numeric landscape; it never calls arbitrary fitness
functions and has no network/process/filesystem effect surface.

The original coordinate bug where an upper-bound value could map to grid index
``size`` is eliminated by using the closed discrete domain ``0 .. size-1`` and
explicit clamping in both coordinate directions.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SCHEMA = "janus.habitat.physarum_proposal.v1"
MAX_GRID_SIDE = 64
MIN_GRID_SIDE = 2
MAX_AGENTS = 4096
MAX_ITERATIONS = 512
MAX_CANDIDATES = 32
_SAFE_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


class PhysarumProposalError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PhysarumProposalError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise PhysarumProposalError(f"{label} must be finite")
    return result


def _bounded_int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise PhysarumProposalError(f"{label} must be {low}..{high}")
    return value


def _parameter_name(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 64
        or any(char not in _SAFE_NAME_CHARS for char in value)
    ):
        raise PhysarumProposalError(f"{label} is invalid")
    return value


def _range(value: Sequence[Any], label: str) -> tuple[float, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise PhysarumProposalError(f"{label} must contain [low, high]")
    low = _finite(value[0], f"{label}.low")
    high = _finite(value[1], f"{label}.high")
    if not high > low:
        raise PhysarumProposalError(f"{label}.high must be > low")
    return low, high


def _validate_landscape(value: Any) -> list[list[float]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PhysarumProposalError("landscape must be a rectangular numeric grid")
    rows = list(value)
    height = _bounded_int(len(rows), "landscape height", MIN_GRID_SIDE, MAX_GRID_SIDE)
    parsed: list[list[float]] = []
    width: int | None = None
    for y, row in enumerate(rows):
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence):
            raise PhysarumProposalError("landscape rows must be sequences")
        cells = list(row)
        if width is None:
            width = _bounded_int(len(cells), "landscape width", MIN_GRID_SIDE, MAX_GRID_SIDE)
        elif len(cells) != width:
            raise PhysarumProposalError("landscape must be rectangular")
        parsed.append([_finite(cell, f"landscape[{y}][]") for cell in cells])
    assert width is not None and height == len(parsed)
    return parsed


def coordinate_to_cell(value: float, bounds: Sequence[float], size: int) -> int:
    """Map a closed real interval to exactly ``0 .. size-1``."""
    low, high = _range(bounds, "bounds")
    size = _bounded_int(size, "size", MIN_GRID_SIDE, MAX_GRID_SIDE)
    value = _finite(value, "coordinate")
    if value <= low:
        return 0
    if value >= high:
        return size - 1
    position = (value - low) / (high - low)
    index = int(round(position * (size - 1)))
    return max(0, min(size - 1, index))


def cell_to_coordinate(index: int, bounds: Sequence[float], size: int) -> float:
    low, high = _range(bounds, "bounds")
    size = _bounded_int(size, "size", MIN_GRID_SIDE, MAX_GRID_SIDE)
    index = _bounded_int(index, "index", 0, size - 1)
    return low + (index / (size - 1)) * (high - low)


def _desirability(landscape: list[list[float]], *, minimize: bool) -> list[list[float]]:
    flat = [cell for row in landscape for cell in row]
    low = min(flat)
    high = max(flat)
    if high == low:
        return [[1.0 for _ in row] for row in landscape]
    span = high - low
    if minimize:
        return [[(high - cell) / span for cell in row] for row in landscape]
    return [[(cell - low) / span for cell in row] for row in landscape]


@dataclass(frozen=True)
class PhysarumGridProposer:
    """Pure in-memory slime-inspired grid search heuristic."""

    def propose(
        self,
        *,
        landscape: Sequence[Sequence[float]],
        x_name: str,
        x_range: Sequence[float],
        y_name: str,
        y_range: Sequence[float],
        seed: int,
        agents: int = 256,
        iterations: int = 80,
        candidate_count: int = 8,
        minimize: bool = True,
        evaporation: float = 0.08,
        landscape_bias: float = 0.20,
        deposit_strength: float = 0.75,
    ) -> dict[str, Any]:
        grid = _validate_landscape(landscape)
        height = len(grid)
        width = len(grid[0])
        x_name = _parameter_name(x_name, "x_name")
        y_name = _parameter_name(y_name, "y_name")
        if x_name == y_name:
            raise PhysarumProposalError("x_name and y_name must differ")
        x_bounds = _range(x_range, "x_range")
        y_bounds = _range(y_range, "y_range")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise PhysarumProposalError("seed must be an integer")
        agents = _bounded_int(agents, "agents", 1, MAX_AGENTS)
        iterations = _bounded_int(iterations, "iterations", 1, MAX_ITERATIONS)
        candidate_count = _bounded_int(
            candidate_count,
            "candidate_count",
            1,
            min(MAX_CANDIDATES, width * height),
        )
        evaporation = _finite(evaporation, "evaporation")
        landscape_bias = _finite(landscape_bias, "landscape_bias")
        deposit_strength = _finite(deposit_strength, "deposit_strength")
        if not 0.0 <= evaporation < 1.0:
            raise PhysarumProposalError("evaporation must be in [0, 1)")
        if landscape_bias < 0 or deposit_strength < 0:
            raise PhysarumProposalError(
                "landscape_bias and deposit_strength must be >= 0"
            )

        desired = _desirability(grid, minimize=bool(minimize))
        rng = random.Random(seed)
        trail = [
            [1e-9 + landscape_bias * desired[y][x] for x in range(width)]
            for y in range(height)
        ]
        swarm = [
            [rng.randrange(width), rng.randrange(height)] for _ in range(agents)
        ]
        final_density = [[0 for _ in range(width)] for _ in range(height)]

        for _ in range(iterations):
            density = [[0 for _ in range(width)] for _ in range(height)]
            for agent in swarm:
                x, y = agent
                neighbors: list[tuple[int, int, float]] = []
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx = max(0, min(width - 1, x + dx))
                        ny = max(0, min(height - 1, y + dy))
                        weight = (
                            trail[ny][nx]
                            + landscape_bias * desired[ny][nx]
                            + 1e-9
                        )
                        neighbors.append((nx, ny, weight))
                total = sum(item[2] for item in neighbors)
                pick = rng.random() * total
                cumulative = 0.0
                chosen_x, chosen_y = x, y
                for nx, ny, weight in neighbors:
                    cumulative += weight
                    if pick <= cumulative:
                        chosen_x, chosen_y = nx, ny
                        break
                agent[0], agent[1] = chosen_x, chosen_y
                density[chosen_y][chosen_x] += 1

            for y in range(height):
                for x in range(width):
                    occupancy = density[y][x] / agents
                    trail[y][x] = (
                        (1.0 - evaporation) * trail[y][x]
                        + deposit_strength * occupancy
                        + landscape_bias * desired[y][x]
                    )
            final_density = density

        ranked_cells: list[tuple[float, int, int]] = []
        for y in range(height):
            for x in range(width):
                occupancy = final_density[y][x] / agents
                heuristic = trail[y][x] + occupancy + desired[y][x]
                ranked_cells.append((heuristic, x, y))
        ranked_cells.sort(key=lambda row: (-row[0], row[2], row[1]))

        proposals = []
        for rank, (heuristic, x, y) in enumerate(ranked_cells[:candidate_count]):
            raw_score = grid[y][x]
            proposal = {
                "proposal_id": canonical_sha256(
                    {
                        "seed": seed,
                        "rank": rank,
                        "x": x,
                        "y": y,
                        "landscape_sha256": canonical_sha256(grid),
                    }
                )[:24],
                "rank": rank,
                "cell": {"x": x, "y": y},
                "parameters": {
                    x_name: cell_to_coordinate(x, x_bounds, width),
                    y_name: cell_to_coordinate(y, y_bounds, height),
                },
                "observed_landscape_value": raw_score,
                "heuristic_score": heuristic,
                "tested": False,
                "selected": False,
                "authorized": False,
            }
            proposals.append(proposal)

        result = {
            "schema": SCHEMA,
            "algorithm": "BOUNDED_PHYSARUM_GRID_HEURISTIC",
            "seed": seed,
            "grid": {"width": width, "height": height},
            "x_parameter": {"name": x_name, "range": list(x_bounds)},
            "y_parameter": {"name": y_name, "range": list(y_bounds)},
            "minimize": bool(minimize),
            "agents": agents,
            "iterations": iterations,
            "candidate_count": candidate_count,
            "landscape_sha256": canonical_sha256(grid),
            "proposals": proposals,
            "landscape_was_precomputed": True,
            "fitness_callable_executed": False,
            "selection_authority_claimed": False,
            "execution_requested": False,
            "source_writeback_requested": False,
            "future_prediction_claimed": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result


__all__ = [
    "PhysarumGridProposer",
    "PhysarumProposalError",
    "canonical_sha256",
    "cell_to_coordinate",
    "coordinate_to_cell",
]
