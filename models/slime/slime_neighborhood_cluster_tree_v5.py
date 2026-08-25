# -*- coding: utf-8 -*-
"""JANUS Slime source-driven neighborhood cluster trees v5.

This producer changes the partition axis rather than merely re-shaping a frozen
linear order. It builds several deterministic agglomerative binary incidence
branch trees from assignment-independent source neighborhoods.

The design is motivated by the PS-width / MIM-width bridge: similar incidence
neighborhoods are grouped before the branch-decomposition verifier sees them.
This is only a heuristic candidate generator. It computes no SAT result,
truth table, PS-width, cap outcome, witness, or probe feedback.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from slime_semantic_candidate_router import (  # noqa: E402
    canonical_cnf,
    incidence,
    source_digest,
    variables_of,
)


VARIANTS = (
    "COMMON_NEIGHBORS",
    "JACCARD_NEIGHBORS",
    "SYMDIFF_NEIGHBORS",
    "SIGNED_JACCARD",
    "HYBRID_SIGNED_ADJACENCY",
)


@dataclass
class ClusterTreeCandidate:
    name: str
    tree: dict[str, Any]
    tree_digest: str
    generation_ops: int
    merge_count: int
    role: str = "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"


@dataclass
class ClusterTreeManifest:
    artifact_id: str
    source_sha256: str
    source_variables: int
    source_clauses: int
    candidates: list[ClusterTreeCandidate]
    total_generation_ops: int
    frozen_before_probe: bool = True
    assignment_independent: bool = True
    exact_ps_width_computed_inside_generator: bool = False
    sat_oracle_used: bool = False
    probe_feedback_used: bool = False
    manifest_sha256: str = ""

    def seal(self):
        payload = asdict(self)
        payload.pop("manifest_sha256", None)
        self.manifest_sha256 = digest(payload)
        return self

    def to_dict(self):
        return asdict(self)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def signed_tokens(cnf, leaf: str):
    if leaf.startswith("v:"):
        variable = int(leaf.split(":", 1)[1])
        out = set()
        for clause_index, clause in enumerate(cnf):
            if variable in clause:
                out.add(("c", clause_index, 1))
            if -variable in clause:
                out.add(("c", clause_index, -1))
        return frozenset(out)
    clause_index = int(leaf.split(":", 1)[1])
    return frozenset(
        ("v", abs(lit), 1 if lit > 0 else -1)
        for lit in cnf[clause_index]
    )


def jaccard(a, b):
    union = a | b
    if not union:
        return Fraction(1, 1)
    return Fraction(len(a & b), len(union))


def similarity_factory(cnf, adjacency, leaves, variant):
    signed = {leaf: signed_tokens(cnf, leaf) for leaf in leaves}

    def similarity(left, right):
        ln = adjacency[left]
        rn = adjacency[right]
        common = len(ln & rn)
        adjacent = int(right in ln)
        if variant == "COMMON_NEIGHBORS":
            return Fraction(common, 1)
        if variant == "JACCARD_NEIGHBORS":
            return jaccard(ln, rn)
        if variant == "SYMDIFF_NEIGHBORS":
            # Larger is better, so negate symmetric-difference distance.
            return Fraction(-len(ln ^ rn), 1)
        if variant == "SIGNED_JACCARD":
            return jaccard(signed[left], signed[right])
        if variant == "HYBRID_SIGNED_ADJACENCY":
            return (
                4 * jaccard(signed[left], signed[right])
                + Fraction(common, 1)
                + Fraction(2 * adjacent, 1)
            )
        raise ValueError(variant)

    return similarity


def tree_leaves(tree):
    if "leaf" in tree:
        return [tree["leaf"]]
    return tree_leaves(tree["left"]) + tree_leaves(tree["right"])


def tree_height(tree):
    if "leaf" in tree:
        return 0
    return 1 + max(tree_height(tree["left"]), tree_height(tree["right"]))


def agglomerative_tree(cnf, variant):
    adjacency_raw = incidence(cnf)
    adjacency = {leaf: frozenset(neighbors) for leaf, neighbors in adjacency_raw.items()}
    leaves = tuple(sorted(adjacency))
    similarity = similarity_factory(cnf, adjacency, leaves, variant)
    ops = 0

    # Stable integer IDs; initial IDs follow lexical leaf order.
    clusters = {
        index: {
            "members": (index,),
            "tree": {"leaf": leaf},
            "min_leaf": leaf,
        }
        for index, leaf in enumerate(leaves)
    }
    active = set(clusters)
    next_id = len(leaves)

    # Cross-cluster sums are sufficient for exact average-linkage updates.
    pair_sum: dict[tuple[int, int], Fraction] = {}
    for left in range(len(leaves)):
        for right in range(left + 1, len(leaves)):
            pair_sum[(left, right)] = similarity(leaves[left], leaves[right])
            ops += 1

    def pair_key(a, b):
        return (a, b) if a < b else (b, a)

    while len(active) > 1:
        ids = sorted(active)
        best = None
        best_pair = None
        for ai in range(len(ids)):
            a = ids[ai]
            for bi in range(ai + 1, len(ids)):
                b = ids[bi]
                ca = clusters[a]
                cb = clusters[b]
                numerator = pair_sum[pair_key(a, b)]
                denominator = len(ca["members"]) * len(cb["members"])
                average = numerator / denominator
                balance = -abs(len(ca["members"]) - len(cb["members"]))
                combined = -(len(ca["members"]) + len(cb["members"]))
                lexical = tuple(sorted((ca["min_leaf"], cb["min_leaf"])))
                score = (average, balance, combined, tuple(-ord(ch) for ch in "|".join(lexical)))
                ops += 1
                if best is None or score > best:
                    best = score
                    best_pair = (a, b)

        assert best_pair is not None
        a, b = best_pair
        ca = clusters[a]
        cb = clusters[b]
        # Canonical left/right orientation by minimum lexical leaf.
        if ca["min_leaf"] <= cb["min_leaf"]:
            left_tree, right_tree = ca["tree"], cb["tree"]
        else:
            left_tree, right_tree = cb["tree"], ca["tree"]
        merged = {
            "members": ca["members"] + cb["members"],
            "tree": {"left": left_tree, "right": right_tree},
            "min_leaf": min(ca["min_leaf"], cb["min_leaf"]),
        }
        clusters[next_id] = merged

        for other in sorted(active - {a, b}):
            pair_sum[pair_key(next_id, other)] = (
                pair_sum[pair_key(a, other)] + pair_sum[pair_key(b, other)]
            )
            ops += 1

        active.remove(a)
        active.remove(b)
        active.add(next_id)
        next_id += 1
        ops += 3

    root = clusters[next(iter(active))]["tree"]
    assert sorted(tree_leaves(root)) == sorted(leaves)
    return root, ops, len(leaves) - 1


class SlimeNeighborhoodClusterTreeV5:
    """Five frozen source-neighborhood hierarchical branch-tree candidates."""

    def generate_manifest(self, clauses):
        cnf = canonical_cnf(clauses)
        candidates = []
        for variant in VARIANTS:
            tree, ops, merges = agglomerative_tree(cnf, variant)
            candidates.append(
                ClusterTreeCandidate(
                    name=f"NCT_{variant}",
                    tree=tree,
                    tree_digest=digest(tree),
                    generation_ops=ops,
                    merge_count=merges,
                )
            )
        manifest = ClusterTreeManifest(
            artifact_id="JANUS-SLIME-NEIGHBORHOOD-CLUSTER-TREE-V5",
            source_sha256=source_digest(cnf),
            source_variables=len(variables_of(cnf)),
            source_clauses=len(cnf),
            candidates=candidates,
            total_generation_ops=sum(c.generation_ops for c in candidates),
        )
        return manifest.seal()


def selftest():
    formula = (
        (1, 2, 3),
        (-1, 2, 4),
        (2, -3, 5),
        (-2, 4, 5),
        (1, -4, 6),
        (2, 5, 6),
    )
    producer = SlimeNeighborhoodClusterTreeV5()
    first = producer.generate_manifest(formula)
    second = producer.generate_manifest(formula)
    assert first.manifest_sha256 == second.manifest_sha256
    assert len(first.candidates) == len(VARIANTS) == 5
    expected = sorted([f"v:{v}" for v in range(1, 7)] + [f"c:{i}" for i in range(6)])
    for candidate in first.candidates:
        assert sorted(tree_leaves(candidate.tree)) == expected
        assert candidate.merge_count == len(expected) - 1
        assert candidate.role == "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"
    return {
        "status": "PASS",
        "candidate_count": len(first.candidates),
        "manifest_sha256": first.manifest_sha256,
        "total_generation_ops": first.total_generation_ops,
        "assignment_independent": first.assignment_independent,
        "p_vs_np": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
