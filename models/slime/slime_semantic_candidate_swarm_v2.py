# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate swarm v2.

v1 showed useful finite routing signal but a single greedy front was falsified
by TOPA PF5 v10: fixed random candidate orders beat it on many connected 3-CNF
controls.  v2 therefore emits a deterministic polynomial-size *portfolio* of
source-only fronts.  It still has zero theorem authority and never computes SAT,
PS-width, truth tables, branch assignments, or post-probe scores.

All front parameters below are frozen calibration choices derived before the
fresh v11 validation.  Every emitted candidate must be checked by an external
proof-carrying compiler / exact audit.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random
import sys
from typing import Mapping

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


STRUCTURED_FRONTS = (
    # name, semantic_weight, trace_ema, shortlist_fraction, policy
    ("MF_DEFAULT", 2.0, 0.85, 0.35, "TRACE_SEM_EDGE"),
    ("MF_EDGE_TIGHT", 0.5, 0.80, 0.25, "TRACE_EDGE_SEM"),
    ("MF_EDGE_GLOBAL", 1.0, 0.90, 1.00, "EDGE_SEM"),
    ("MF_SEM_TIGHT", 4.0, 0.80, 0.25, "TRACE_SEM_EDGE"),
    ("MF_SEM_GLOBAL", 8.0, 0.90, 1.00, "SEM_EDGE"),
    ("MF_BALANCED_EDGE", 1.0, 0.75, 1.00, "BALANCED"),
    ("MF_BALANCED_SEM", 4.0, 0.90, 1.00, "BALANCED"),
    ("MF_TRACE_NARROW", 2.0, 0.95, 0.15, "TRACE_ONLY"),
)

EXPLORATION_FRONTS = 8
DOMAIN = "JANUS-SLIME-SEMANTIC-CANDIDATE-SWARM-V2"


def _crossing(adjacency: Mapping[str, set[str]], selected: set[str]) -> int:
    return sum(
        1
        for left in selected
        for right in adjacency[left]
        if right not in selected
    )


def _semantic_frontier(
    adjacency: Mapping[str, set[str]],
    selected: set[str],
    leaf_group: Mapping[str, str],
) -> int:
    pairs: set[tuple[str, str]] = set()
    for left in selected:
        for right in adjacency[left]:
            if right not in selected:
                pairs.add((leaf_group[left], leaf_group[right]))
    return len(pairs)


def _structured_front(
    cnf,
    clause_to_group,
    profiles,
    *,
    semantic_weight: float,
    trace_ema: float,
    shortlist_fraction: float,
    policy: str,
):
    adjacency = incidence(cnf)
    remaining = set(adjacency)
    selected: set[str] = set()
    trace = {leaf: 0.5 for leaf in adjacency}
    order: list[str] = []
    charged_ops = 0

    unique_profiles = sorted(set(profiles.values()))
    profile_ids = {profile: index for index, profile in enumerate(unique_profiles)}
    leaf_group: dict[str, str] = {
        f"v:{variable}": f"VP:{profile_ids[profile]}"
        for variable, profile in profiles.items()
    }
    leaf_group.update(
        {
            f"c:{clause_index}": f"CG:{group_id}"
            for clause_index, group_id in clause_to_group.items()
        }
    )

    while remaining:
        rows = []
        for leaf in sorted(remaining):
            trial = selected | {leaf}
            edge_pressure = _crossing(adjacency, trial)
            semantic_pressure = _semantic_frontier(
                adjacency, trial, leaf_group
            )
            charged_ops += 2 * (
                1 + sum(len(adjacency[node]) for node in trial)
            )
            scale = max(1.0, float(len(adjacency)))
            error = (
                edge_pressure + semantic_weight * semantic_pressure
            ) / scale
            bond = math.exp(-min(20.0, error))
            trace[leaf] = (
                trace_ema * trace[leaf]
                + (1.0 - trace_ema) * bond
            )
            rows.append((leaf, edge_pressure, semantic_pressure, trace[leaf]))

        if policy.startswith("TRACE"):
            keep = max(1, int(math.ceil(len(rows) * shortlist_fraction)))
            pool = sorted(
                rows,
                key=lambda row: (-row[3], row[2], row[1], row[0]),
            )[:keep]
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

        chosen = min(pool, key=key)[0]
        order.append(chosen)
        selected.add(chosen)
        remaining.remove(chosen)

    return order, charged_ops


def _exploration_order(leaves, source_sha256: str, index: int):
    payload = f"{DOMAIN}|{source_sha256}|{index}".encode()
    seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    order = list(leaves)
    random.Random(seed).shuffle(order)
    # Charge one unit per moved/visited leaf plus one seed derivation unit.
    return order, len(order) + 1, seed


class SlimeSemanticCandidateSwarmV2:
    """Deterministic multi-front source-only candidate producer."""

    def generate_manifest(self, clauses):
        cnf = canonical_cnf(clauses)
        groups, clause_to_group = clause_group_map(cnf)
        profiles = variable_profiles(cnf, clause_to_group)
        leaves = all_leaves(cnf)
        source_sha = source_digest(cnf)
        candidates: list[Candidate] = []
        front_metadata = []

        for (
            name,
            semantic_weight,
            trace_ema,
            shortlist_fraction,
            policy,
        ) in STRUCTURED_FRONTS:
            order, ops = _structured_front(
                cnf,
                clause_to_group,
                profiles,
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
                        "frozen assignment-independent Slime pressure front "
                        f"policy={policy}, semantic_weight={semantic_weight}, "
                        f"trace_ema={trace_ema}, shortlist={shortlist_fraction}"
                    ),
                    charged_ops=ops,
                )
            )
            front_metadata.append(
                {
                    "name": name,
                    "kind": "STRUCTURED_SLIME_FRONT",
                    "semantic_weight": semantic_weight,
                    "trace_ema": trace_ema,
                    "shortlist_fraction": shortlist_fraction,
                    "policy": policy,
                }
            )

        for index in range(EXPLORATION_FRONTS):
            order, ops, seed = _exploration_order(leaves, source_sha, index)
            name = f"MF_HASH_EXPLORE_{index:02d}"
            candidates.append(
                Candidate(
                    name=name,
                    linear_leaf_order=order,
                    generation_reason=(
                        "deterministic source-hash exploration front; no probe feedback"
                    ),
                    charged_ops=ops,
                )
            )
            front_metadata.append(
                {
                    "name": name,
                    "kind": "HASH_DETERMINISTIC_EXPLORATION_FRONT",
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
            "calibration_lineage": "PF5_SLIME_ADVERSARIAL_SWARM_V10",
        }

        manifest = Manifest(
            artifact_id="JANUS-SLIME-SEMANTIC-CANDIDATE-SWARM-V2",
            source_sha256=source_sha,
            source_variables=len(variables_of(cnf)),
            source_clauses=len(cnf),
            feature_certificate=feature_certificate,
            candidates=candidates,
            total_generation_ops=sum(c.charged_ops for c in candidates),
        ).seal()
        return manifest


def selftest():
    router = SlimeSemanticCandidateSwarmV2()
    formula = (
        (1, 2, 3),
        (-1, 2, 4),
        (2, -3, 5),
        (-2, 4, 5),
        (1, -4, 6),
    )
    a = router.generate_manifest(formula)
    b = router.generate_manifest(formula)
    assert a.manifest_sha256 == b.manifest_sha256
    assert len(a.candidates) == 16
    assert len({c.name for c in a.candidates}) == 16
    assert a.frozen_before_probe is True
    assert a.exact_ps_width_computed_inside_generator is False
    assert a.sat_oracle_used is False
    assert a.feature_certificate["probe_feedback_free"] is True
    return {
        "status": "PASS",
        "candidate_count": len(a.candidates),
        "manifest_sha256": a.manifest_sha256,
        "total_generation_ops": a.total_generation_ops,
        "authority": "POLYNOMIAL_CANDIDATE_SWARM_NOT_WIDTH_CERTIFICATE",
        "p_vs_np": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
