# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate swarm v3: amortized pressure engine.

Scientific contract
-------------------
v3 is an accounting/implementation repair of the frozen v2 producer.  It must
emit the *same 16 candidate leaf orders* as v2 for the same CNF source while
reducing discovery work.  No portfolio widening, retuning, PS-width feedback,
SAT oracle, truth table, or post-probe repair is allowed.

The key exact incremental identities are:

  cross(S ∪ {u}) = cross(S) + deg(u) - 2*|N(u) ∩ S|

and, for semantic frontier pressure, maintain a counter for every directed
crossing group pair (group(selected endpoint), group(outside endpoint)).  A
trial addition of u changes only pairs touched by edges incident to u:

  v in S       : decrement (group(v), group(u))
  v not in S   : increment (group(u), group(v))

Thus the exact v2 edge and semantic trial pressures are recovered by scanning
only N(u), instead of rescanning all currently selected adjacency lists for
all trial candidates.

For one front with r incidence leaves and e incidence edges, summing degrees of
all remaining trial leaves in any round is at most 2e; across at most r rounds
this gives O(r*e) incident-edge trial work.  The number of structured fronts is
frozen at eight, so the portfolio remains O(r*e) up to a fixed factor, plus
linear static indexing and the eight cheap deterministic exploration orders.

This is only candidate discovery.  It does not prove that any emitted order has
polynomial PS-width on arbitrary CNF.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Dict, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from slime_semantic_candidate_router import (  # noqa: E402
    Candidate,
    Manifest,
    all_leaves,
    canonical_cnf,
    clause_group_map,
    incidence,
    source_digest,
    variable_profiles,
    variables_of,
)
from slime_semantic_candidate_swarm_v2 import (  # noqa: E402
    EXPLORATION_FRONTS,
    STRUCTURED_FRONTS,
    _exploration_order,
)


@dataclass(frozen=True)
class SharedSourceIndex:
    adjacency: Mapping[str, frozenset[str]]
    degree: Mapping[str, int]
    leaf_group: Mapping[str, str]
    leaves: tuple[str, ...]
    incidence_edges: int
    charged_static_ops: int


def build_shared_index(cnf, clause_to_group, profiles) -> SharedSourceIndex:
    """Build source-only static data once and share it across all eight fronts."""
    raw = incidence(cnf)
    adjacency = {leaf: frozenset(neighbors) for leaf, neighbors in raw.items()}
    degree = {leaf: len(neighbors) for leaf, neighbors in adjacency.items()}

    unique_profiles = sorted(set(profiles.values()))
    profile_ids = {profile: index for index, profile in enumerate(unique_profiles)}
    leaf_group: Dict[str, str] = {
        f"v:{variable}": f"VP:{profile_ids[profile]}"
        for variable, profile in profiles.items()
    }
    leaf_group.update(
        {
            f"c:{clause_index}": f"CG:{group_id}"
            for clause_index, group_id in clause_to_group.items()
        }
    )
    leaves = tuple(sorted(adjacency))
    twice_edges = sum(degree.values())
    assert twice_edges % 2 == 0
    incidence_edges = twice_edges // 2

    # Explicit static ledger: one visit per adjacency endpoint, one degree store
    # per leaf, and one group-label store per leaf.
    charged_static_ops = twice_edges + 2 * len(leaves)
    return SharedSourceIndex(
        adjacency=adjacency,
        degree=degree,
        leaf_group=leaf_group,
        leaves=leaves,
        incidence_edges=incidence_edges,
        charged_static_ops=charged_static_ops,
    )


class IncrementalCutState:
    """Exact crossing-edge and crossing-group-pair state for one Slime front."""

    def __init__(self, index: SharedSourceIndex):
        self.index = index
        self.selected: set[str] = set()
        self.remaining: set[str] = set(index.leaves)
        self.crossing_edges = 0
        self.pair_counts: dict[tuple[str, str], int] = {}
        self.nonzero_pairs = 0
        self.charged_ops = 0

    def trial_pressures(self, leaf: str):
        """Return exact v2 pressures plus a local delta certificate for leaf."""
        if leaf not in self.remaining:
            raise ValueError("trial leaf is not remaining")
        selected_neighbors = 0
        delta: dict[tuple[str, str], int] = {}
        leaf_group = self.index.leaf_group[leaf]

        for neighbor in self.index.adjacency[leaf]:
            # Charge one selected-membership test and one pair-delta update.
            self.charged_ops += 2
            if neighbor in self.selected:
                selected_neighbors += 1
                key = (self.index.leaf_group[neighbor], leaf_group)
                delta[key] = delta.get(key, 0) - 1
            else:
                # leaf has no self-loop; every non-selected neighbor is outside
                # the trial selected side after adding leaf.
                key = (leaf_group, self.index.leaf_group[neighbor])
                delta[key] = delta.get(key, 0) + 1

        edge_pressure = (
            self.crossing_edges
            + self.index.degree[leaf]
            - 2 * selected_neighbors
        )

        semantic_pressure = self.nonzero_pairs
        for key, change in delta.items():
            # Charge one current-count read and one zero/nonzero transition test.
            self.charged_ops += 2
            before = self.pair_counts.get(key, 0)
            after = before + change
            if after < 0:
                raise AssertionError((leaf, key, before, change))
            if before == 0 and after > 0:
                semantic_pressure += 1
            elif before > 0 and after == 0:
                semantic_pressure -= 1

        return edge_pressure, semantic_pressure, delta

    def commit(self, leaf: str, edge_pressure: int, delta):
        """Commit exactly the already-scored trial leaf."""
        self.crossing_edges = edge_pressure
        for key, change in delta.items():
            self.charged_ops += 1
            before = self.pair_counts.get(key, 0)
            after = before + change
            if after < 0:
                raise AssertionError((leaf, key, before, change))
            if before == 0 and after > 0:
                self.nonzero_pairs += 1
            elif before > 0 and after == 0:
                self.nonzero_pairs -= 1
            if after:
                self.pair_counts[key] = after
            else:
                self.pair_counts.pop(key, None)
        self.selected.add(leaf)
        self.remaining.remove(leaf)
        # Charge the two set updates.
        self.charged_ops += 2


def _amortized_structured_front(
    index: SharedSourceIndex,
    *,
    semantic_weight: float,
    trace_ema: float,
    shortlist_fraction: float,
    policy: str,
):
    state = IncrementalCutState(index)
    trace = {leaf: 0.5 for leaf in index.leaves}
    order: list[str] = []
    scalar_ops = len(index.leaves)  # trace initialization

    while state.remaining:
        rows = []
        trial_delta = {}
        for leaf in sorted(state.remaining):
            edge_pressure, semantic_pressure, delta = state.trial_pressures(leaf)
            scale = max(1.0, float(len(index.leaves)))
            error = (edge_pressure + semantic_weight * semantic_pressure) / scale
            bond = math.exp(-min(20.0, error))
            trace[leaf] = trace_ema * trace[leaf] + (1.0 - trace_ema) * bond
            scalar_ops += 6  # scale/error/min-exp/EMA arithmetic bookkeeping
            rows.append((leaf, edge_pressure, semantic_pressure, trace[leaf]))
            trial_delta[leaf] = delta

        if policy.startswith("TRACE"):
            keep = max(1, int(math.ceil(len(rows) * shortlist_fraction)))
            pool = sorted(
                rows,
                key=lambda row: (-row[3], row[2], row[1], row[0]),
            )[:keep]
            scalar_ops += len(rows)
        else:
            pool = rows

        if policy in ("TRACE_SEM_EDGE", "SEM_EDGE"):
            key = lambda row: (row[2], row[1], -row[3], row[0])
        elif policy in ("TRACE_EDGE_SEM", "EDGE_SEM"):
            key = lambda row: (row[1], row[2], -row[3], row[0])
        elif policy == "TRACE_ONLY":
            key = lambda row: (-row[3], row[2], row[1], row[0])
        elif policy == "BALANCED":
            key = lambda row: (
                row[1] + semantic_weight * row[2],
                -row[3],
                row[0],
            )
        else:
            raise ValueError(policy)

        # Charge one comparison-key evaluation per pool row as a conservative
        # deterministic ledger unit; Python's actual sorting/min comparisons are
        # implementation details, not hidden semantic work.
        scalar_ops += len(pool)
        chosen_row = min(pool, key=key)
        chosen = chosen_row[0]
        state.commit(chosen, chosen_row[1], trial_delta[chosen])
        order.append(chosen)

    return order, state.charged_ops + scalar_ops


class SlimeSemanticCandidateSwarmV3Amortized:
    """Same v2 candidate orders, cheaper exact source-pressure discovery."""

    def generate_manifest(self, clauses):
        cnf = canonical_cnf(clauses)
        groups, clause_to_group = clause_group_map(cnf)
        profiles = variable_profiles(cnf, clause_to_group)
        source_sha = source_digest(cnf)
        index = build_shared_index(cnf, clause_to_group, profiles)

        candidates: list[Candidate] = []
        front_metadata = []
        for (
            name,
            semantic_weight,
            trace_ema,
            shortlist_fraction,
            policy,
        ) in STRUCTURED_FRONTS:
            order, ops = _amortized_structured_front(
                index,
                semantic_weight=semantic_weight,
                trace_ema=trace_ema,
                shortlist_fraction=shortlist_fraction,
                policy=policy,
            )
            candidates.append(
                Candidate(
                    name=name,
                    linear_leaf_order=order,
                    generation_reason=(
                        "v2-order-equivalent incremental pressure front; "
                        f"policy={policy}, semantic_weight={semantic_weight}, "
                        f"trace_ema={trace_ema}, shortlist={shortlist_fraction}"
                    ),
                    charged_ops=ops,
                )
            )
            front_metadata.append(
                {
                    "name": name,
                    "kind": "AMORTIZED_STRUCTURED_SLIME_FRONT",
                    "semantic_weight": semantic_weight,
                    "trace_ema": trace_ema,
                    "shortlist_fraction": shortlist_fraction,
                    "policy": policy,
                }
            )

        # Reuse the exact v2 exploration constructor/domain so these eight leaf
        # orders are bit-for-bit unchanged as well.
        leaves = all_leaves(cnf)
        for index_number in range(EXPLORATION_FRONTS):
            order, ops, seed = _exploration_order(leaves, source_sha, index_number)
            name = f"MF_HASH_EXPLORE_{index_number:02d}"
            candidates.append(
                Candidate(
                    name=name,
                    linear_leaf_order=order,
                    generation_reason=(
                        "v2-identical deterministic source-hash exploration front"
                    ),
                    charged_ops=ops,
                )
            )
            front_metadata.append(
                {
                    "name": name,
                    "kind": "V2_IDENTICAL_HASH_EXPLORATION_FRONT",
                    "seed": seed,
                }
            )

        expected = sorted(leaves)
        for candidate in candidates:
            assert len(candidate.linear_leaf_order) == len(expected)
            assert sorted(candidate.linear_leaf_order) == expected
            assert candidate.role == "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"

        feature_certificate = {
            "clause_groups": groups,
            "variable_profiles": {
                str(variable): [list(row) for row in profiles[variable]]
                for variable in sorted(profiles)
            },
            "front_metadata": front_metadata,
            "feature_classes": [
                "CLAUSE_INCIDENCE",
                "EXACT_CLAUSE_FINGERPRINT",
                "SIGNED_INCIDENCE_PROFILE",
                "DETERMINISTIC_SOURCE_HASH_EXPLORATION",
            ],
            "assignment_independent": True,
            "truth_table_free": True,
            "probe_feedback_free": True,
            "v2_portfolio_parameters_unchanged": True,
            "shared_static_index": True,
            "incremental_edge_pressure_identity": (
                "cross(S+u)=cross(S)+deg(u)-2*|N(u) intersect S|"
            ),
            "incremental_semantic_frontier": (
                "update only directed crossing group-pair counts touched by N(u)"
            ),
            "source_incidence_leaves": len(index.leaves),
            "source_incidence_edges": index.incidence_edges,
            "static_index_ops": index.charged_static_ops,
            "per_structured_front_incident_scan_upper_bound": (
                "O(r*e) where r=incidence leaves and e=incidence edges"
            ),
        }

        # Static source indexing is performed once for the portfolio, rather
        # than silently recharged to each front.
        total_generation_ops = (
            index.charged_static_ops + sum(c.charged_ops for c in candidates)
        )
        return Manifest(
            artifact_id="JANUS-SLIME-SEMANTIC-CANDIDATE-SWARM-V3-AMORTIZED",
            source_sha256=source_sha,
            source_variables=len(variables_of(cnf)),
            source_clauses=len(cnf),
            feature_certificate=feature_certificate,
            candidates=candidates,
            total_generation_ops=total_generation_ops,
        ).seal()


def candidate_orders(manifest):
    return {c.name: tuple(c.linear_leaf_order) for c in manifest.candidates}


def selftest():
    from slime_semantic_candidate_swarm_v2 import SlimeSemanticCandidateSwarmV2

    formulas = [
        (
            (1, 2, 3),
            (-1, 2, 4),
            (2, -3, 5),
            (-2, 4, 5),
            (1, -4, 6),
        ),
        (
            (1, 2, 3),
            (1, 2, 3),
            (-1, 3, 4),
            (2, -4, 5),
            (-2, 5, 6),
            (3, -5, 6),
        ),
    ]
    v2 = SlimeSemanticCandidateSwarmV2()
    v3 = SlimeSemanticCandidateSwarmV3Amortized()
    ratios = []
    for formula in formulas:
        old = v2.generate_manifest(formula)
        new = v3.generate_manifest(formula)
        assert candidate_orders(old) == candidate_orders(new)
        assert len(new.candidates) == 16
        assert new.total_generation_ops < old.total_generation_ops
        ratios.append(new.total_generation_ops / old.total_generation_ops)
    return {
        "status": "PASS",
        "v2_candidate_orders_preserved": True,
        "candidate_count": 16,
        "example_new_over_old_cost_ratios": ratios,
        "p_vs_np": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
