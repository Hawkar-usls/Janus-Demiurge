# -*- coding: utf-8 -*-
"""JANUS Slime balanced incidence branch-tree producer v4.

v4 changes exactly one axis relative to the validated amortized v3 producer:
**tree topology**.  The 16 source-only Slime leaf orders are unchanged; each is
converted deterministically into a balanced full binary branch-decomposition
shape by recursively bisecting the order.

No SAT, truth table, PS-width, branch assignment, exact probe feedback, or cap
information enters generation.  This module is a candidate producer only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from slime_semantic_candidate_swarm_v3_amortized import (  # noqa: E402
    SlimeSemanticCandidateSwarmV3Amortized,
)


@dataclass
class BalancedTreeCandidate:
    name: str
    leaf_order: list[str]
    tree: dict[str, Any]
    leaf_order_digest: str
    tree_digest: str
    source_generation_ops: int
    topology_generation_ops: int
    role: str = "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"


@dataclass
class BalancedTreeManifest:
    artifact_id: str
    source_sha256: str
    source_variables: int
    source_clauses: int
    source_v3_manifest_sha256: str
    candidates: list[BalancedTreeCandidate]
    source_generation_ops: int
    topology_generation_ops: int
    total_generation_ops: int
    topology_transform: str = "RECURSIVE_CONTIGUOUS_BISECTION_OF_FROZEN_V3_ORDER"
    frozen_before_probe: bool = True
    exact_ps_width_computed_inside_generator: bool = False
    sat_oracle_used: bool = False
    probe_feedback_used: bool = False
    manifest_sha256: str = ""

    def payload_without_hash(self):
        payload = asdict(self)
        payload.pop("manifest_sha256", None)
        return payload

    def seal(self):
        self.manifest_sha256 = digest(self.payload_without_hash())
        return self

    def to_dict(self):
        return asdict(self)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def balanced_tree(order: Sequence[str]):
    """Build a deterministic full binary tree by recursive contiguous bisection."""
    order = list(order)
    if not order:
        raise ValueError("empty leaf order")
    ops = 0

    def build(lo: int, hi: int):
        nonlocal ops
        ops += 1
        if hi - lo == 1:
            return {"leaf": order[lo]}
        mid = lo + (hi - lo) // 2
        return {
            "left": build(lo, mid),
            "right": build(mid, hi),
        }

    tree = build(0, len(order))
    # A full binary tree with r leaves has exactly 2r-1 nodes.
    assert ops == 2 * len(order) - 1
    return tree, ops


def tree_leaves(tree):
    if "leaf" in tree:
        return [tree["leaf"]]
    return tree_leaves(tree["left"]) + tree_leaves(tree["right"])


def tree_height(tree):
    if "leaf" in tree:
        return 0
    return 1 + max(tree_height(tree["left"]), tree_height(tree["right"]))


class SlimeBalancedBranchTreeV4:
    """Wrap the exact v3 16-order manifest in balanced binary topology."""

    def __init__(self):
        self.v3 = SlimeSemanticCandidateSwarmV3Amortized()

    def generate_manifest(self, clauses):
        source = self.v3.generate_manifest(clauses)
        candidates: list[BalancedTreeCandidate] = []
        topology_ops = 0
        for candidate in source.candidates:
            order = list(candidate.linear_leaf_order)
            tree, ops = balanced_tree(order)
            topology_ops += ops
            assert tree_leaves(tree) == order
            candidates.append(
                BalancedTreeCandidate(
                    name=candidate.name,
                    leaf_order=order,
                    tree=tree,
                    leaf_order_digest=digest(order),
                    tree_digest=digest(tree),
                    source_generation_ops=candidate.charged_ops,
                    topology_generation_ops=ops,
                )
            )

        assert len(candidates) == 16
        assert len({c.name for c in candidates}) == 16
        assert all(c.role == "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE" for c in candidates)

        manifest = BalancedTreeManifest(
            artifact_id="JANUS-SLIME-BALANCED-BRANCH-TREE-V4",
            source_sha256=source.source_sha256,
            source_variables=source.source_variables,
            source_clauses=source.source_clauses,
            source_v3_manifest_sha256=source.manifest_sha256,
            candidates=candidates,
            source_generation_ops=source.total_generation_ops,
            topology_generation_ops=topology_ops,
            total_generation_ops=source.total_generation_ops + topology_ops,
        )
        return manifest.seal()


def selftest():
    formula = (
        (1, 2, 3),
        (-1, 2, 4),
        (2, -3, 5),
        (-2, 4, 5),
        (1, -4, 6),
    )
    producer = SlimeBalancedBranchTreeV4()
    first = producer.generate_manifest(formula)
    second = producer.generate_manifest(formula)
    assert first.manifest_sha256 == second.manifest_sha256
    assert len(first.candidates) == 16
    for candidate in first.candidates:
        assert tree_leaves(candidate.tree) == candidate.leaf_order
        r = len(candidate.leaf_order)
        assert candidate.topology_generation_ops == 2 * r - 1
        # Contiguous bisection is logarithmic-height up to rounding.
        assert tree_height(candidate.tree) <= (r - 1).bit_length()
    return {
        "status": "PASS",
        "candidate_count": 16,
        "manifest_sha256": first.manifest_sha256,
        "source_v3_manifest_sha256": first.source_v3_manifest_sha256,
        "topology_generation_ops": first.topology_generation_ops,
        "probe_feedback_used": first.probe_feedback_used,
        "p_vs_np": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
