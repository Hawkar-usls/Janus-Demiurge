# -*- coding: utf-8 -*-
"""JANUS Slime semantic decomposition candidate router.

This module is a *candidate generator only*.  It deliberately does not compute
SAT, #SAT, PS-width, semantic cut tables, or any other post-hoc exact score.
Its job is to emit a polynomial-size, assignment-independent candidate manifest
that can later be probed by an independent TOPA/Fundamentum verifier.

The source features are intentionally proof-carrying and cheap:
  * clause incidence;
  * exact clause fingerprints / duplicate-clause classes;
  * exact signed variable-incidence profiles over those clause classes.

The historical Slime operator is reused only as a routing heuristic:

    REMEMBER_USEFULNESS -> PRUNE_WEAK -> GROW_IF_NEEDED ->
    SPEND_PRECISION_WHERE_TRACE_IS_HIGH

No Slime score has theorem authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Iterable, List, Mapping, Sequence, Tuple

Clause = Tuple[int, ...]
CNF = Tuple[Clause, ...]
Leaf = str


def canonical_clause(clause: Sequence[int]) -> Clause:
    lits = sorted(set(int(x) for x in clause), key=lambda x: (abs(x), x < 0))
    if any(x == 0 for x in lits):
        raise ValueError("literal 0 is not admitted")
    if any(-x in lits for x in lits):
        raise ValueError("tautological clause not admitted in semantic-router source")
    return tuple(lits)


def canonical_cnf(clauses: Iterable[Sequence[int]]) -> CNF:
    return tuple(canonical_clause(c) for c in clauses)


def variables_of(cnf: CNF) -> List[int]:
    return sorted({abs(lit) for clause in cnf for lit in clause})


def source_digest(cnf: CNF) -> str:
    payload = json.dumps(cnf, separators=(",", ":"), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()


def clause_group_map(cnf: CNF) -> tuple[list[dict], dict[int, int]]:
    by_fingerprint: dict[Clause, list[int]] = {}
    for index, clause in enumerate(cnf):
        by_fingerprint.setdefault(clause, []).append(index)

    groups: list[dict] = []
    clause_to_group: dict[int, int] = {}
    for group_id, fingerprint in enumerate(sorted(by_fingerprint)):
        members = tuple(by_fingerprint[fingerprint])
        groups.append(
            {
                "group_id": group_id,
                "fingerprint": list(fingerprint),
                "members": list(members),
            }
        )
        for index in members:
            clause_to_group[index] = group_id
    return groups, clause_to_group


def variable_profiles(
    cnf: CNF,
    clause_to_group: Mapping[int, int],
) -> dict[int, tuple[tuple[int, int, int], ...]]:
    """Exact signed occurrence profile over exact clause-fingerprint classes."""
    profiles: dict[int, tuple[tuple[int, int, int], ...]] = {}
    for variable in variables_of(cnf):
        occurrences: dict[tuple[int, int], int] = {}
        for clause_index, clause in enumerate(cnf):
            group_id = clause_to_group[clause_index]
            positive = variable in clause
            negative = -variable in clause
            if positive or negative:
                key = (group_id, 1 if positive else -1)
                occurrences[key] = occurrences.get(key, 0) + 1
        profiles[variable] = tuple(
            sorted(
                (group_id, sign, count)
                for (group_id, sign), count in occurrences.items()
            )
        )
    return profiles


def incidence(cnf: CNF) -> dict[Leaf, set[Leaf]]:
    adjacency: dict[Leaf, set[Leaf]] = {
        f"v:{variable}": set() for variable in variables_of(cnf)
    }
    for clause_index, clause in enumerate(cnf):
        clause_leaf = f"c:{clause_index}"
        adjacency[clause_leaf] = set()
        for literal in clause:
            variable_leaf = f"v:{abs(literal)}"
            adjacency[clause_leaf].add(variable_leaf)
            adjacency[variable_leaf].add(clause_leaf)
    return adjacency


def all_leaves(cnf: CNF) -> list[Leaf]:
    return [f"v:{v}" for v in variables_of(cnf)] + [
        f"c:{index}" for index in range(len(cnf))
    ]


@dataclass
class Candidate:
    name: str
    linear_leaf_order: List[Leaf]
    generation_reason: str
    charged_ops: int
    role: str = "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"


@dataclass
class Manifest:
    artifact_id: str
    source_sha256: str
    source_variables: int
    source_clauses: int
    feature_certificate: dict
    candidates: List[Candidate]
    total_generation_ops: int
    frozen_before_probe: bool = True
    exact_ps_width_computed_inside_generator: bool = False
    sat_oracle_used: bool = False
    manifest_sha256: str = ""

    def payload_without_hash(self) -> dict:
        payload = asdict(self)
        payload.pop("manifest_sha256", None)
        return payload

    def seal(self) -> "Manifest":
        payload = json.dumps(
            self.payload_without_hash(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        self.manifest_sha256 = hashlib.sha256(payload).hexdigest()
        return self

    def to_dict(self) -> dict:
        return asdict(self)


class SlimeSemanticCandidateRouter:
    """Deterministic, assignment-independent semantic candidate producer."""

    def __init__(self, trace_ema: float = 0.85, shortlist_fraction: float = 0.35):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0,1)")
        if not 0.0 < shortlist_fraction <= 1.0:
            raise ValueError("shortlist_fraction must be in (0,1]")
        self.trace_ema = float(trace_ema)
        self.shortlist_fraction = float(shortlist_fraction)

    @staticmethod
    def _lexical(leaves: Sequence[Leaf]) -> list[Leaf]:
        return sorted(leaves)

    @staticmethod
    def _duplicate_blocks(cnf: CNF, groups: Sequence[dict]) -> list[Leaf]:
        variable_order = [f"v:{v}" for v in variables_of(cnf)]
        clause_order: list[Leaf] = []
        for group in groups:
            clause_order.extend(f"c:{index}" for index in group["members"])
        return variable_order + clause_order

    @staticmethod
    def _profile_blocks(
        cnf: CNF,
        groups: Sequence[dict],
        profiles: Mapping[int, tuple],
    ) -> list[Leaf]:
        variable_order = [
            f"v:{variable}"
            for variable in sorted(profiles, key=lambda v: (profiles[v], v))
        ]
        clause_order: list[Leaf] = []
        for group in groups:
            clause_order.extend(f"c:{index}" for index in group["members"])
        return variable_order + clause_order

    @staticmethod
    def _crossing(adjacency: Mapping[Leaf, set[Leaf]], selected: set[Leaf]) -> int:
        return sum(
            1
            for left in selected
            for right in adjacency[left]
            if right not in selected
        )

    @staticmethod
    def _semantic_frontier(
        adjacency: Mapping[Leaf, set[Leaf]],
        selected: set[Leaf],
        leaf_group: Mapping[Leaf, str],
    ) -> int:
        crossing_group_pairs: set[tuple[str, str]] = set()
        for left in selected:
            for right in adjacency[left]:
                if right not in selected:
                    crossing_group_pairs.add((leaf_group[left], leaf_group[right]))
        return len(crossing_group_pairs)

    def _slime_pressure_order(
        self,
        cnf: CNF,
        clause_to_group: Mapping[int, int],
        profiles: Mapping[int, tuple],
    ) -> tuple[list[Leaf], int]:
        adjacency = incidence(cnf)
        remaining = set(adjacency)
        selected: set[Leaf] = set()
        trace = {leaf: 0.5 for leaf in adjacency}
        order: list[Leaf] = []
        charged_ops = 0

        unique_profiles = sorted(set(profiles.values()))
        profile_ids = {profile: index for index, profile in enumerate(unique_profiles)}
        leaf_group: dict[Leaf, str] = {}
        for variable, profile in profiles.items():
            leaf_group[f"v:{variable}"] = f"VP:{profile_ids[profile]}"
        for clause_index, group_id in clause_to_group.items():
            leaf_group[f"c:{clause_index}"] = f"CG:{group_id}"

        while remaining:
            local = []
            for leaf in sorted(remaining):
                trial = selected | {leaf}
                edge_pressure = self._crossing(adjacency, trial)
                semantic_pressure = self._semantic_frontier(
                    adjacency,
                    trial,
                    leaf_group,
                )
                # Conservative explicit accounting of the scans above.
                charged_ops += 2 * (
                    1 + sum(len(adjacency[node]) for node in trial)
                )

                scale = max(1.0, float(len(adjacency)))
                error = (edge_pressure + 2.0 * semantic_pressure) / scale
                bond = math.exp(-min(20.0, error))
                trace[leaf] = (
                    self.trace_ema * trace[leaf]
                    + (1.0 - self.trace_ema) * bond
                )
                local.append(
                    (leaf, edge_pressure, semantic_pressure, trace[leaf])
                )

            keep = max(1, int(math.ceil(len(local) * self.shortlist_fraction)))
            shortlist = sorted(
                local,
                key=lambda row: (-row[3], row[2], row[1], row[0]),
            )[:keep]
            chosen = min(
                shortlist,
                key=lambda row: (row[2], row[1], -row[3], row[0]),
            )[0]
            order.append(chosen)
            selected.add(chosen)
            remaining.remove(chosen)

        return order, charged_ops

    def generate_manifest(self, clauses: Iterable[Sequence[int]]) -> Manifest:
        cnf = canonical_cnf(clauses)
        groups, clause_to_group = clause_group_map(cnf)
        profiles = variable_profiles(cnf, clause_to_group)
        leaves = all_leaves(cnf)

        candidates: list[Candidate] = []
        candidates.append(
            Candidate(
                "LEXICAL_BASELINE",
                self._lexical(leaves),
                "deterministic lexical leaf order",
                len(leaves),
            )
        )
        candidates.append(
            Candidate(
                "EXACT_DUPLICATE_CLAUSE_BLOCKS",
                self._duplicate_blocks(cnf, groups),
                "exact clause fingerprints grouped before any probe",
                len(cnf) + len(leaves),
            )
        )
        candidates.append(
            Candidate(
                "SIGNED_INCIDENCE_PROFILE_BLOCKS",
                self._profile_blocks(cnf, groups, profiles),
                "variables grouped by exact signed profile over exact clause groups",
                sum(len(profile) for profile in profiles.values()) + len(leaves),
            )
        )
        slime_order, slime_ops = self._slime_pressure_order(
            cnf,
            clause_to_group,
            profiles,
        )
        candidates.append(
            Candidate(
                "SLIME_SEMANTIC_PRESSURE",
                slime_order,
                "trace rewards low incidence and certified-group frontier pressure",
                slime_ops,
            )
        )

        expected = sorted(leaves)
        for candidate in candidates:
            if (
                sorted(candidate.linear_leaf_order) != expected
                or len(candidate.linear_leaf_order) != len(expected)
            ):
                raise AssertionError("candidate is not an exact leaf permutation")

        feature_certificate = {
            "clause_groups": groups,
            "variable_profiles": {
                str(variable): [list(row) for row in profiles[variable]]
                for variable in sorted(profiles)
            },
            "feature_classes": [
                "CLAUSE_INCIDENCE",
                "EXACT_CLAUSE_FINGERPRINT",
                "SIGNED_INCIDENCE_PROFILE",
            ],
            "assignment_independent": True,
            "truth_table_free": True,
        }
        total_generation_ops = sum(c.charged_ops for c in candidates)
        return Manifest(
            artifact_id="JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V1",
            source_sha256=source_digest(cnf),
            source_variables=len(variables_of(cnf)),
            source_clauses=len(cnf),
            feature_certificate=feature_certificate,
            candidates=candidates,
            total_generation_ops=total_generation_ops,
        ).seal()


def selftest() -> dict:
    router = SlimeSemanticCandidateRouter()

    duplicate_family = tuple(tuple(range(1, 7)) for _ in range(6))
    first = router.generate_manifest(duplicate_family)
    second = router.generate_manifest(duplicate_family)
    assert first.manifest_sha256 == second.manifest_sha256
    assert len(first.candidates) == 4
    assert first.feature_certificate["clause_groups"][0]["members"] == list(range(6))
    assert first.frozen_before_probe is True
    assert first.exact_ps_width_computed_inside_generator is False
    assert first.sat_oracle_used is False

    mixed = (
        (1, 2, 3),
        (1, 2, 3),
        (-1, 2, 4),
        (-1, 2, 4),
        (3, -4, 5),
    )
    mixed_manifest = router.generate_manifest(mixed)
    assert all(
        candidate.role == "CANDIDATE_ONLY_NOT_WIDTH_CERTIFICATE"
        for candidate in mixed_manifest.candidates
    )

    return {
        "status": "PASS",
        "duplicate_manifest_sha256": first.manifest_sha256,
        "mixed_manifest_sha256": mixed_manifest.manifest_sha256,
        "candidate_count": len(first.candidates),
        "generator_truth_table_free": True,
        "generator_sat_oracle_free": True,
        "authority": "HEURISTIC_GENERATOR_EXACT_VERIFIER_SPLIT",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
