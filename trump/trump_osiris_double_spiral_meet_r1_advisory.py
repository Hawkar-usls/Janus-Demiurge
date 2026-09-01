#!/usr/bin/env python3
"""R1 advisory separator proposal over the exact R0 double-spiral meet.

R1 changes only how a meeting boundary is proposed.  Proposal has no truth
or proof authority.  Every admitted pair is exact-checked as a primal-graph
separator, every SAT witness replays on the root, and experiment UNSAT is
independently cross-checked by the frozen runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Dict, List, Optional, Set, Tuple

from trump_osiris_double_spiral_meet_r0 import (
    Assignment,
    CNF,
    _components_without,
    build_primal_graph,
    canonicalize,
    exact_search,
    formula_status,
    split_by_separator,
    variables,
    verify_root_sat,
)

DENSITY_SKIP_THRESHOLD = 0.70
MAX_PAIR_PROPOSALS = 12


@dataclass
class AdvisorySeparator:
    separator: Set[int]
    left: Set[int]
    right: Set[int]
    structural_ops: int
    graph_density: float
    proposals_tested: int
    proposal_rank: int


@dataclass
class R1MeetResult:
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
    advisory: dict

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
            "advisory": self.advisory,
            "work": {
                "structural_ops": self.structural_ops,
                "boundary_attempts": self.boundary_attempts,
                "exact_wing_nodes": self.exact_wing_nodes,
                "fallback_nodes": self.fallback_nodes,
                "charged_abstract_ops": self.charged_work,
            },
        }


def _greedy_component_split(components: List[Set[int]]) -> Tuple[Optional[Tuple[Set[int], Set[int]]], int]:
    """Exact because components are disconnected; balancing is advisory only."""
    if len(components) < 2:
        return None, 0
    ordered = sorted(components, key=lambda c: (-len(c), min(c)))
    left: Set[int] = set()
    right: Set[int] = set()
    ops = 0
    for comp in ordered:
        ops += 1
        if len(left) <= len(right):
            left.update(comp)
        else:
            right.update(comp)
    if not left or not right:
        return None, ops
    return (left, right), ops


def advisory_discover_separator(
    clauses: CNF,
    density_skip_threshold: float = DENSITY_SKIP_THRESHOLD,
    max_pair_proposals: int = MAX_PAIR_PROPOSALS,
) -> Tuple[Optional[AdvisorySeparator], dict]:
    clauses = canonicalize(clauses)
    graph, structural_ops = build_primal_graph(clauses)
    n = len(graph)
    edge_count = sum(len(neighbors) for neighbors in graph.values()) // 2
    structural_ops += n
    density = 0.0 if n < 2 else (2.0 * edge_count) / (n * (n - 1))

    if density > density_skip_threshold:
        return None, {
            "decision": "DENSITY_SKIP_TO_EXACT_FALLBACK",
            "graph_density": density,
            "density_skip_threshold": density_skip_threshold,
            "proposals_tested": 0,
            "structural_ops": structural_ops,
        }

    ranked = []
    for u, v in combinations(sorted(graph), 2):
        structural_ops += 1
        score = len(graph[u]) + len(graph[v])
        ranked.append((-score, (u, v)))
    ranked.sort(key=lambda row: (row[0], row[1]))

    proposals_tested = 0
    for rank, (_, pair) in enumerate(ranked[:max_pair_proposals], start=1):
        proposals_tested += 1
        sep = set(pair)
        components, ops = _components_without(graph, sep)
        structural_ops += ops
        if len(components) < 2:
            continue
        split, ops = _greedy_component_split(components)
        structural_ops += ops
        if split is None:
            continue
        left, right = split
        # split_by_separator is an exact assertion: any hidden crossing clause rejects.
        try:
            split_by_separator(clauses, sep, left, right)
        except ValueError:
            continue
        admitted = AdvisorySeparator(
            separator=sep,
            left=left,
            right=right,
            structural_ops=structural_ops,
            graph_density=density,
            proposals_tested=proposals_tested,
            proposal_rank=rank,
        )
        return admitted, {
            "decision": "EXACT_VERIFIED_SEPARATOR_ADMITTED",
            "graph_density": density,
            "density_skip_threshold": density_skip_threshold,
            "pair_score": "degree_sum",
            "max_pair_proposals": max_pair_proposals,
            "proposals_tested": proposals_tested,
            "proposal_rank": rank,
            "proposed_separator": sorted(sep),
            "structural_ops": structural_ops,
        }

    return None, {
        "decision": "NO_EXACT_VERIFIED_PROPOSAL_TO_EXACT_FALLBACK",
        "graph_density": density,
        "density_skip_threshold": density_skip_threshold,
        "pair_score": "degree_sum",
        "max_pair_proposals": max_pair_proposals,
        "proposals_tested": proposals_tested,
        "structural_ops": structural_ops,
    }


def double_spiral_meet_r1(clauses: CNF) -> R1MeetResult:
    clauses = canonicalize(clauses)
    admitted, advisory = advisory_discover_separator(clauses)
    if admitted is None:
        terminal, witness, work = exact_search(clauses)
        return R1MeetResult(
            terminal=terminal,
            witness=witness,
            mode="ADVISORY_SKIP_EXACT_FALLBACK",
            separator=None,
            left=None,
            right=None,
            boundary_table=[],
            structural_ops=int(advisory["structural_ops"]),
            boundary_attempts=0,
            exact_wing_nodes=0,
            fallback_nodes=work.nodes,
            advisory=advisory,
        )

    separator = admitted.separator
    left = admitted.left
    right = admitted.right
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

        assert left_witness is not None and right_witness is not None
        combined: Assignment = dict(boundary)
        combined.update({v: value for v, value in left_witness.items() if v in left})
        combined.update({v: value for v, value in right_witness.items() if v in right})
        for var in variables(clauses):
            combined.setdefault(var, False)
        row["blocker"] = None
        row["root_replay"] = verify_root_sat(clauses, combined)
        table.append(row)
        if not row["root_replay"]:
            continue
        return R1MeetResult(
            terminal="SAT",
            witness=combined,
            mode="ADVISORY_PROPOSAL_EXACT_DOUBLE_SPIRAL_MEET",
            separator=sorted(separator),
            left=sorted(left),
            right=sorted(right),
            boundary_table=table,
            structural_ops=admitted.structural_ops,
            boundary_attempts=attempts,
            exact_wing_nodes=wing_nodes,
            fallback_nodes=0,
            advisory=advisory,
        )

    return R1MeetResult(
        terminal="UNSAT",
        witness=None,
        mode="ADVISORY_PROPOSAL_EXACT_DOUBLE_SPIRAL_MEET",
        separator=sorted(separator),
        left=sorted(left),
        right=sorted(right),
        boundary_table=table,
        structural_ops=admitted.structural_ops,
        boundary_attempts=attempts,
        exact_wing_nodes=wing_nodes,
        fallback_nodes=0,
        advisory=advisory,
    )
