#!/usr/bin/env python3
"""Exact, bounded, experimental TRUMP/OSIRIS double-spiral meet.

This module has zero proof authority in canonical TRUMP.  It tests one precise
idea: when a CNF primal graph admits a small exact separator S, summarize the
left and right wings independently as feasibility relations over S and meet
only on an exact shared boundary assignment.  Every SAT result must replay on
the original root.  Finite UNSAT results are cross-checked by the runner with
an independent exact root search.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, product
import json
from random import Random
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

Clause = Tuple[int, ...]
CNF = Tuple[Clause, ...]
Assignment = Dict[int, bool]


@dataclass
class SearchWork:
    nodes: int = 0
    prunes: int = 0
    leaves: int = 0

    def as_dict(self) -> dict:
        return {"nodes": self.nodes, "prunes": self.prunes, "leaves": self.leaves}


@dataclass
class SeparatorResult:
    separator: Set[int]
    left: Set[int]
    right: Set[int]
    structural_ops: int
    candidates_tested: int


@dataclass
class MeetResult:
    terminal: str
    witness: Optional[Assignment]
    mode: str
    separator: Optional[List[int]]
    left: Optional[List[int]]
    right: Optional[List[int]]
    boundary_table: List[dict]
    structural_ops: int
    boundary_attempts: int
    exact_wing_nodes: int
    fallback_nodes: int

    @property
    def charged_work(self) -> int:
        return self.structural_ops + self.boundary_attempts + self.exact_wing_nodes + self.fallback_nodes

    def as_dict(self) -> dict:
        return {
            "terminal": self.terminal,
            "witness": None if self.witness is None else {str(k): bool(v) for k, v in sorted(self.witness.items())},
            "mode": self.mode,
            "separator": self.separator,
            "left": self.left,
            "right": self.right,
            "boundary_table": self.boundary_table,
            "work": {
                "structural_ops": self.structural_ops,
                "boundary_attempts": self.boundary_attempts,
                "exact_wing_nodes": self.exact_wing_nodes,
                "fallback_nodes": self.fallback_nodes,
                "charged_abstract_ops": self.charged_work,
            },
        }


def canonicalize(clauses: Iterable[Iterable[int]]) -> CNF:
    out: List[Clause] = []
    for raw in clauses:
        clause = tuple(sorted(set(int(x) for x in raw), key=lambda x: (abs(x), x < 0)))
        if not clause:
            out.append(tuple())
            continue
        # Tautologies carry no constraint and are removed from the exact state.
        lits = set(clause)
        if any(-x in lits for x in lits):
            continue
        out.append(clause)
    return tuple(sorted(set(out)))


def formula_digest(clauses: CNF) -> str:
    payload = json.dumps([list(c) for c in canonicalize(clauses)], separators=(",", ":"), sort_keys=False).encode()
    return sha256(payload).hexdigest()


def variables(clauses: CNF) -> List[int]:
    return sorted({abs(lit) for clause in clauses for lit in clause})


def clause_status(clause: Clause, assignment: Assignment) -> Optional[bool]:
    if not clause:
        return False
    unknown = False
    for lit in clause:
        var = abs(lit)
        if var not in assignment:
            unknown = True
            continue
        value = assignment[var]
        if (lit > 0 and value) or (lit < 0 and not value):
            return True
    return None if unknown else False


def formula_status(clauses: CNF, assignment: Assignment) -> Optional[bool]:
    all_true = True
    for clause in clauses:
        status = clause_status(clause, assignment)
        if status is False:
            return False
        if status is None:
            all_true = False
    return True if all_true else None


def exact_search(
    clauses: CNF,
    order: Optional[Sequence[int]] = None,
    initial: Optional[Assignment] = None,
) -> Tuple[str, Optional[Assignment], SearchWork]:
    """Deterministic exact DFS with partial-clause pruning; false before true."""
    clauses = canonicalize(clauses)
    base = dict(initial or {})
    universe = variables(clauses) if order is None else list(order)
    order2 = [v for v in universe if v not in base]
    work = SearchWork()

    def rec(index: int, assignment: Assignment) -> Optional[Assignment]:
        work.nodes += 1
        status = formula_status(clauses, assignment)
        if status is False:
            work.prunes += 1
            return None
        if status is True:
            witness = dict(assignment)
            for var in order2[index:]:
                witness[var] = False
            return witness
        if index >= len(order2):
            work.leaves += 1
            return dict(assignment) if status is True else None
        var = order2[index]
        for value in (False, True):
            assignment[var] = value
            hit = rec(index + 1, assignment)
            if hit is not None:
                return hit
        assignment.pop(var, None)
        return None

    witness = rec(0, base)
    return ("SAT" if witness is not None else "UNSAT"), witness, work


def verify_root_sat(clauses: CNF, witness: Optional[Assignment]) -> bool:
    if witness is None:
        return False
    complete = dict(witness)
    for var in variables(clauses):
        complete.setdefault(var, False)
    return formula_status(canonicalize(clauses), complete) is True


def build_primal_graph(clauses: CNF) -> Tuple[Dict[int, Set[int]], int]:
    graph = {v: set() for v in variables(clauses)}
    ops = len(graph)
    for clause in clauses:
        clause_vars = sorted({abs(x) for x in clause})
        for i, u in enumerate(clause_vars):
            for v in clause_vars[i + 1 :]:
                ops += 1
                graph[u].add(v)
                graph[v].add(u)
    return graph, ops


def _components_without(graph: Dict[int, Set[int]], separator: Set[int]) -> Tuple[List[Set[int]], int]:
    remaining = set(graph) - separator
    comps: List[Set[int]] = []
    ops = len(remaining)
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        stack = [start]
        comp = {start}
        while stack:
            u = stack.pop()
            for v in graph[u]:
                ops += 1
                if v in separator or v not in remaining:
                    continue
                remaining.remove(v)
                comp.add(v)
                stack.append(v)
        comps.append(comp)
    return comps, ops


def _best_component_bipartition(components: List[Set[int]]) -> Tuple[Optional[Tuple[Set[int], Set[int]]], int]:
    if len(components) < 2:
        return None, 0
    components = sorted(components, key=lambda c: (min(c), len(c)))
    total = sum(len(c) for c in components)
    best = None
    ops = 0
    # Remove L/R mirror symmetry by fixing component zero on the left.
    for mask in range(1 << (len(components) - 1)):
        ops += 1
        left = set(components[0])
        for idx, comp in enumerate(components[1:]):
            if (mask >> idx) & 1:
                left.update(comp)
        if len(left) == total:
            continue
        right = set().union(*(c for c in components if not c.issubset(left)))
        if not right:
            continue
        score = (max(len(left), len(right)), abs(len(left) - len(right)), tuple(sorted(left)), tuple(sorted(right)))
        if best is None or score < best[0]:
            best = (score, left, right)
    return (None if best is None else (best[1], best[2])), ops


def discover_separator(clauses: CNF, max_separator_size: int = 2) -> Optional[SeparatorResult]:
    clauses = canonicalize(clauses)
    graph, structural_ops = build_primal_graph(clauses)
    vs = sorted(graph)
    best = None
    candidates_tested = 0
    if len(vs) < 3:
        return None
    for size in range(1, min(max_separator_size, len(vs) - 2) + 1):
        for raw_sep in combinations(vs, size):
            candidates_tested += 1
            structural_ops += 1
            sep = set(raw_sep)
            comps, ops = _components_without(graph, sep)
            structural_ops += ops
            partition, ops = _best_component_bipartition(comps)
            structural_ops += ops
            if partition is None:
                continue
            left, right = partition
            score = (max(len(left), len(right)), size, abs(len(left) - len(right)), raw_sep)
            if best is None or score < best[0]:
                best = (score, sep, left, right)
    if best is None:
        # We still need to expose the cost incurred during failed discovery.
        return SeparatorResult(set(), set(), set(), structural_ops, candidates_tested)
    return SeparatorResult(best[1], best[2], best[3], structural_ops, candidates_tested)


def split_by_separator(clauses: CNF, separator: Set[int], left: Set[int], right: Set[int]) -> Tuple[CNF, CNF, CNF]:
    left_clauses: List[Clause] = []
    center_clauses: List[Clause] = []
    right_clauses: List[Clause] = []
    for clause in canonicalize(clauses):
        non_sep = {abs(x) for x in clause if abs(x) not in separator}
        if not non_sep:
            center_clauses.append(clause)
        elif non_sep.issubset(left):
            left_clauses.append(clause)
        elif non_sep.issubset(right):
            right_clauses.append(clause)
        else:
            raise ValueError(f"separator is not exact for clause {clause}")
    return canonicalize(left_clauses), canonicalize(center_clauses), canonicalize(right_clauses)


def double_spiral_meet(clauses: CNF, max_separator_size: int = 2) -> MeetResult:
    clauses = canonicalize(clauses)
    sep_result = discover_separator(clauses, max_separator_size=max_separator_size)
    if sep_result is None or not sep_result.separator:
        structural_ops = 0 if sep_result is None else sep_result.structural_ops
        terminal, witness, work = exact_search(clauses)
        return MeetResult(
            terminal=terminal,
            witness=witness,
            mode="NO_MEET_EXACT_FALLBACK",
            separator=None,
            left=None,
            right=None,
            boundary_table=[],
            structural_ops=structural_ops,
            boundary_attempts=0,
            exact_wing_nodes=0,
            fallback_nodes=work.nodes,
        )

    separator = sep_result.separator
    left = sep_result.left
    right = sep_result.right
    left_cnf, center_cnf, right_cnf = split_by_separator(clauses, separator, left, right)
    sep_order = sorted(separator)
    left_order = sorted(left)
    right_order = sorted(right, reverse=True)
    table: List[dict] = []
    wing_nodes = 0
    attempts = 0

    for values_for_s in product((False, True), repeat=len(sep_order)):
        attempts += 1
        boundary = dict(zip(sep_order, values_for_s))
        row = {"S": {str(k): bool(v) for k, v in sorted(boundary.items())}}
        if formula_status(center_cnf, boundary) is False:
            row["blocker"] = "CENTER"
            table.append(row)
            continue

        left_terminal, left_witness, left_work = exact_search(left_cnf, left_order, boundary)
        wing_nodes += left_work.nodes
        row["left_terminal"] = left_terminal
        row["left_nodes"] = left_work.nodes
        if left_terminal == "UNSAT":
            row["blocker"] = "LEFT"
            table.append(row)
            continue

        right_terminal, right_witness, right_work = exact_search(right_cnf, right_order, boundary)
        wing_nodes += right_work.nodes
        row["right_terminal"] = right_terminal
        row["right_nodes"] = right_work.nodes
        if right_terminal == "UNSAT":
            row["blocker"] = "RIGHT"
            table.append(row)
            continue

        combined: Assignment = dict(boundary)
        assert left_witness is not None and right_witness is not None
        combined.update({v: value for v, value in left_witness.items() if v in left})
        combined.update({v: value for v, value in right_witness.items() if v in right})
        for var in variables(clauses):
            combined.setdefault(var, False)
        row["blocker"] = None
        row["root_replay"] = verify_root_sat(clauses, combined)
        table.append(row)
        if not row["root_replay"]:
            # Exact meet is not allowed to promote a non-replaying witness.
            continue
        return MeetResult(
            terminal="SAT",
            witness=combined,
            mode="EXACT_DOUBLE_SPIRAL_MEET",
            separator=sorted(separator),
            left=sorted(left),
            right=sorted(right),
            boundary_table=table,
            structural_ops=sep_result.structural_ops,
            boundary_attempts=attempts,
            exact_wing_nodes=wing_nodes,
            fallback_nodes=0,
        )

    return MeetResult(
        terminal="UNSAT",
        witness=None,
        mode="EXACT_DOUBLE_SPIRAL_MEET",
        separator=sorted(separator),
        left=sorted(left),
        right=sorted(right),
        boundary_table=table,
        structural_ops=sep_result.structural_ops,
        boundary_attempts=attempts,
        exact_wing_nodes=wing_nodes,
        fallback_nodes=0,
    )


def _force_literal_via_aux(literal: int, aux: int) -> List[Clause]:
    # (l OR a) AND (l OR -a) is exactly equivalent to l.
    return [(literal, aux), (literal, -aux)]


def structured_holdout_formula(seed: int, terminal_class: str) -> CNF:
    """Frozen separator family. terminal_class is SAT or UNSAT by construction."""
    rng = Random(seed)
    left = list(range(1, 6))
    right = list(range(6, 11))
    sep = [11, 12]
    clauses: List[Clause] = []

    for idx, s in enumerate(sep):
        clauses.extend(_force_literal_via_aux(s, left[idx]))
        right_literal = s
        if terminal_class == "UNSAT" and idx == 0:
            right_literal = -s
        clauses.extend(_force_literal_via_aux(right_literal, right[idx]))

    # Ten clauses per wing. Every wing variable appears as a positive anchor;
    # the all-true assignment therefore satisfies all noise on SAT instances.
    for wing in (left, right):
        universe = wing + sep
        for round_id in range(2):
            for anchor in wing:
                others = [v for v in universe if v != anchor]
                x, y = rng.sample(others, 2)
                lit_x = x if rng.random() < 0.5 else -x
                lit_y = y if rng.random() < 0.5 else -y
                clauses.append((anchor, lit_x, lit_y))
    return canonicalize(clauses)


def dense_control_formula(seed: int) -> CNF:
    rng = Random(seed)
    clauses: List[Clause] = []
    for _ in range(34):
        xs = rng.sample(range(1, 11), 3)
        clauses.append(tuple(x if rng.random() < 0.5 else -x for x in xs))
    return canonicalize(clauses)
