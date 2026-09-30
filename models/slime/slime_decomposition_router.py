# -*- coding: utf-8 -*-
"""JANUS Slime decomposition candidate router.

Candidate generator only. It proposes elimination orders for an undirected graph
using the historical Slime operator:

    REMEMBER_USEFULNESS -> PRUNE_WEAK -> GROW_IF_NEEDED -> SPEND_PRECISION_WHERE_TRACE_IS_HIGH

The router has NO theorem authority. Every proposal must be checked by an
independent exact verifier before use in TOPA/Fundamentum.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import math
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

Edge = Tuple[str, str]


def canonical_edge(a: str, b: str) -> Edge:
    if a == b:
        raise ValueError("self edge")
    return (a, b) if a < b else (b, a)


def build_graph(vertices: Sequence[str], edges: Iterable[Edge]) -> Dict[str, Set[str]]:
    g = {str(v): set() for v in vertices}
    for a0, b0 in edges:
        a, b = canonical_edge(str(a0), str(b0))
        if a not in g or b not in g:
            raise ValueError("edge endpoint missing from vertices")
        g[a].add(b)
        g[b].add(a)
    return g


@dataclass
class StepReceipt:
    step: int
    chosen: str
    degree: int
    fill_edges: int
    trace: float
    live_candidates: int
    pruned_candidates: int


@dataclass
class SlimeProposal:
    order: List[str]
    heuristic_width: int
    receipts: List[StepReceipt]
    scored_candidates: int
    role: str = "HEURISTIC_CANDIDATE_GENERATOR_NOT_PROOF"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class SlimeDecompositionRouter:
    """Deterministic Slime-inspired elimination-order proposer.

    Trace update rewards low local degree/fill. Low-trace candidates are pruned
    from the *selection shortlist* only; they remain in the graph and can be
    selected later. This is intentionally heuristic and fail-open only as a
    proposal source.
    """

    def __init__(self, trace_ema: float = 0.85, shortlist_fraction: float = 0.35):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0,1)")
        if not 0.0 < shortlist_fraction <= 1.0:
            raise ValueError("shortlist_fraction must be in (0,1]")
        self.trace_ema = float(trace_ema)
        self.shortlist_fraction = float(shortlist_fraction)

    @staticmethod
    def _fill_count(g: Mapping[str, Set[str]], v: str) -> int:
        ns = sorted(g[v])
        missing = 0
        for i, a in enumerate(ns):
            ga = g[a]
            for b in ns[i + 1 :]:
                if b not in ga:
                    missing += 1
        return missing

    @staticmethod
    def _bond(degree: int, fill: int, remaining: int) -> float:
        scale = max(1.0, float(remaining - 1))
        error = (float(degree) + 2.0 * float(fill)) / scale
        return math.exp(-min(20.0, error))

    def propose(self, vertices: Sequence[str], edges: Iterable[Edge]) -> SlimeProposal:
        g = build_graph(vertices, edges)
        trace = {v: 0.5 for v in g}
        order: List[str] = []
        receipts: List[StepReceipt] = []
        scored = 0
        width = 0

        while g:
            local = []
            n = len(g)
            for v in sorted(g):
                deg = len(g[v])
                fill = self._fill_count(g, v)
                trace[v] = self.trace_ema * trace[v] + (1.0 - self.trace_ema) * self._bond(deg, fill, n)
                local.append((v, deg, fill, trace[v]))
                scored += 1

            # Slime cleanup: keep the strongest trace band as the shortlist.
            keep = max(1, int(math.ceil(len(local) * self.shortlist_fraction)))
            shortlist = sorted(local, key=lambda x: (-x[3], x[2], x[1], x[0]))[:keep]
            # Within the live slime front, minimize exact local fill first.
            chosen, deg, fill, tr = min(shortlist, key=lambda x: (x[2], x[1], -x[3], x[0]))
            width = max(width, deg)

            ns = sorted(g[chosen])
            for i, a in enumerate(ns):
                for b in ns[i + 1 :]:
                    g[a].add(b)
                    g[b].add(a)
            for u in ns:
                g[u].discard(chosen)
            del g[chosen]
            order.append(chosen)
            receipts.append(StepReceipt(len(order) - 1, chosen, deg, fill, tr, len(shortlist), len(local) - len(shortlist)))

        return SlimeProposal(order, width, receipts, scored)


def selftest() -> dict:
    r = SlimeDecompositionRouter()
    vertices = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    p = r.propose(vertices, edges)
    assert sorted(p.order) == sorted(vertices)
    assert p.heuristic_width == 1
    assert p.role == "HEURISTIC_CANDIDATE_GENERATOR_NOT_PROOF"
    return {
        "status": "PASS",
        "order": p.order,
        "heuristic_width": p.heuristic_width,
        "scored_candidates": p.scored_candidates,
        "authority": p.role,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
