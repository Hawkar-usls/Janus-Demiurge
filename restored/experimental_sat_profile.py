#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experimental SAT occupancy profile inspired by Han's TechRxiv preprint.

This module does not treat the paper as an established proof of P=NP.
Instead, it extracts the usable mathematical core:

1. expand a partial clause into the set of full "vested" clauses,
2. build an occurrence vector over the 2^n full assignments,
3. compute power sums S_e = sum_i v_i^e,
4. recover a multiplicity histogram through a Vandermonde system.

We use that machinery as a graph / idea saturation heuristic inside HRAIN.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from typing import Dict, Iterable, List, Sequence

import numpy as np


Literal = int
Clause = Sequence[Literal]

# Bounded research heuristic ONLY. Exponential enumeration, NOT a SAT solver.
MAX_VARIABLES = 8
MAX_CLAUSES = 32
MAX_POWER_ORDER = 12


def _validate_variables(n_vars: int) -> None:
    if isinstance(n_vars, bool) or not isinstance(n_vars, int) or not 1 <= n_vars <= MAX_VARIABLES:
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_VARIABLE_LIMIT_HOLD")



@dataclass
class ClauseOccupancyProfile:
    n_vars: int
    clause_count: int
    universe_size: int
    expanded_clause_count: int
    distinct_vested_clauses: int
    saturation_ratio: float
    power_sums: List[int]
    multiplicity_histogram: Dict[int, int]
    recovered_histogram: Dict[int, int]
    open_space: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _normalize_clause(clause: Clause) -> List[Literal]:
    normalized = []
    for literal in clause:
        if literal == 0:
            raise ValueError("Literal 0 is not valid in CNF encoding.")
        normalized.append(int(literal))
    if len({abs(literal) for literal in normalized}) != len(normalized):
        raise ValueError(f"Clause contains repeated variables: {clause!r}")
    return normalized


def _assignment_to_index(bits: Sequence[int]) -> int:
    value = 0
    for idx, bit in enumerate(bits):
        if bit:
            value |= 1 << idx
    return value


def clause_to_vested_indices(n_vars: int, clause: Clause) -> List[int]:
    """Expand a partial clause to all full-length sign patterns consistent with it."""
    _validate_variables(n_vars)
    normalized = _normalize_clause(clause)
    if any(abs(literal) > n_vars for literal in normalized):
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_LITERAL_RANGE_HOLD")
    fixed: Dict[int, int] = {}
    for literal in normalized:
        fixed[abs(literal) - 1] = 1 if literal > 0 else 0

    free_positions = [idx for idx in range(n_vars) if idx not in fixed]
    vested_indices: List[int] = []
    for free_bits in product((0, 1), repeat=len(free_positions)):
        assignment = [0] * n_vars
        for idx, value in fixed.items():
            assignment[idx] = value
        for idx, value in zip(free_positions, free_bits):
            assignment[idx] = value
        vested_indices.append(_assignment_to_index(assignment))
    return vested_indices


def build_occurrence_vector(n_vars: int, clauses: Sequence[Clause]) -> np.ndarray:
    _validate_variables(n_vars)
    if len(clauses) > MAX_CLAUSES:
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_CLAUSE_LIMIT_HOLD")
    counts = np.zeros(1 << n_vars, dtype=np.int64)
    for clause in clauses:
        for index in clause_to_vested_indices(n_vars, clause):
            counts[index] += 1
    return counts


def power_sums(counts: np.ndarray, max_order: int | None = None) -> List[int]:
    max_order = max_order or int(counts.max(initial=0))
    if max_order <= 0:
        return []
    if max_order > MAX_POWER_ORDER:
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_POWER_ORDER_HOLD")
    sums: List[int] = []
    for exponent in range(1, max_order + 1):
        # Convert to arbitrary precision Python integers before exponentiation.
        sums.append(sum(int(value)**exponent for value in counts))
    return sums


def multiplicity_histogram(counts: np.ndarray) -> Dict[int, int]:
    histogram: Dict[int, int] = {}
    for value in counts.tolist():
        if value <= 0:
            continue
        histogram[int(value)] = histogram.get(int(value), 0) + 1
    return histogram


def recover_histogram_from_power_sums(
    power_sum_values: Sequence[int],
    max_multiplicity: int,
) -> Dict[int, int]:
    if max_multiplicity <= 0 or not power_sum_values:
        return {}
    if max_multiplicity > MAX_POWER_ORDER:
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_RECOVERY_ORDER_HOLD")

    order = min(len(power_sum_values), max_multiplicity)
    vandermonde = np.array(
        [[(col + 1) ** (row + 1) for col in range(order)] for row in range(order)],
        dtype=np.float64,
    )
    rhs = np.array(power_sum_values[:order], dtype=np.float64)
    solution, *_ = np.linalg.lstsq(vandermonde, rhs, rcond=None)

    histogram: Dict[int, int] = {}
    for idx, value in enumerate(solution, start=1):
        rounded = int(max(0, round(float(value))))
        if rounded:
            histogram[idx] = rounded
    return histogram


def clause_occupancy_profile(n_vars: int, clauses: Sequence[Clause]) -> ClauseOccupancyProfile:
    _validate_variables(n_vars)
    if len(clauses) > MAX_CLAUSES:
        raise ValueError("HRAIN_EXPERIMENTAL_SAT_CLAUSE_LIMIT_HOLD")

    counts = build_occurrence_vector(n_vars, clauses)
    universe_size = int(counts.size)
    distinct = int(np.count_nonzero(counts))
    expanded_clause_count = int(np.sum(counts))
    histogram = multiplicity_histogram(counts)
    sums = power_sums(counts, max_order=max(histogram.keys(), default=0))
    recovered = recover_histogram_from_power_sums(sums, max(histogram.keys(), default=0))
    saturation = distinct / float(universe_size)

    return ClauseOccupancyProfile(
        n_vars=n_vars,
        clause_count=len(clauses),
        universe_size=universe_size,
        expanded_clause_count=expanded_clause_count,
        distinct_vested_clauses=distinct,
        saturation_ratio=saturation,
        power_sums=sums,
        multiplicity_histogram=histogram,
        recovered_histogram=recovered,
        open_space=distinct < universe_size,
    )


def graph_fragment_to_clauses(children: Sequence[Dict[str, object]]) -> tuple[int, List[List[int]]]:
    """Project a local HRAIN fragment into a toy CNF-like system.

    Each child becomes a variable. The sign is derived from the semantic type:
    positive for ally/intel/info/janus, negative for threat/sleeper, plug depends
    on its score sign. Clauses are generated in rolling triples.
    """

    usable = list(children)[:8]
    if not usable:
        return 0, []

    literals: List[int] = []
    for idx, child in enumerate(usable, start=1):
        node_type = str(child.get("type", "ally"))
        score = float(child.get("score", 0.0) or 0.0)
        if node_type in {"threat", "sleeper"}:
            literals.append(-idx)
        elif node_type == "plug":
            literals.append(idx if score >= 0 else -idx)
        else:
            literals.append(idx)

    clauses: List[List[int]] = []
    if len(literals) == 1:
        clauses.append([literals[0]])
    elif len(literals) == 2:
        clauses.append([literals[0], literals[1]])
    else:
        for start in range(len(literals) - 2):
            clauses.append([literals[start], literals[start + 1], literals[start + 2]])
        clauses.append([literals[0], literals[-2], literals[-1]])

    return len(usable), clauses
