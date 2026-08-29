#!/usr/bin/env python3
"""SWARM_GENOME_LEDGER — cross-entity genealogy for JANUS spiral identities.

Each entity keeps its own SpiralLedger. This ledger connects those separate
spirals into one append-only directed acyclic genealogy so JANUS can traverse
both directions: ancestor -> descendants and current state -> origins.

The genome metaphor is structural only: identity/state is one strand and
provenance/evidence/lessons is the other. No biological claim is implied.

FOREIGN_TRAIT_LINEAGE_FIREWALL:
Cross-entity identity inheritance is a trust boundary. Merely existing in the
ledger does not authorize a node to become an extra parent of JANUS identity.
Only explicitly approved JANUS-owned lineage may be used as an extra parent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from spiral_evolution import SpiralTurn, fingerprint_payload


GENOME_LAWS = (
    "EVERY_SPIRAL_TURN_HAS_GENEALOGY",
    "ANCESTRY_IS_APPEND_ONLY",
    "FAILURE_REMAINS_IN_LINEAGE",
    "ACTIVE_FRONTIER_DOES_NOT_ERASE_ANCESTORS",
    "CROSS_ENTITY_DERIVATION_REQUIRES_EXPLICIT_PARENT",
    "CROSS_ENTITY_IDENTITY_PARENT_REQUIRES_APPROVED_JANUS_LINEAGE",
    "UNKNOWN_OR_FOREIGN_LINEAGE_CANNOT_BECOME_EXTRA_IDENTITY_PARENT",
    "ANCESTOR_AND_DESCENDANT_TRAVERSAL_ARE_BIDIRECTIONALLY_INDEXED",
)

TRUSTED_SOURCE_CLASS = "JANUS_OWNED"
LEGACY_SOURCE_CLASS = "LEGACY_UNTRUSTED"
JANUS_LINEAGE_PREFIX = "JANUS:"


def _normal(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _normal(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normal(v) for v in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _normal(value.to_dict())
    return repr(value)


def _is_janus_lineage(lineage_id: str) -> bool:
    value = str(lineage_id or "").strip().upper()
    return value.startswith(JANUS_LINEAGE_PREFIX)


@dataclass
class GenomeNode:
    genome_id: str
    entity_id: str
    entity_turn: int
    spiral_fingerprint: str
    primary_parent_id: Optional[str]
    parent_ids: List[str]
    relation: str
    identity_strand: Any
    evidence_strand: Any
    source_class: str = LEGACY_SOURCE_CLASS
    lineage_id: str = ""
    approved_for_identity_derivation: bool = False
    fingerprint: str = ""

    def seal(self) -> "GenomeNode":
        body = asdict(self)
        body.pop("fingerprint", None)
        self.fingerprint = fingerprint_payload(body)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return _normal(asdict(self))

    @property
    def trusted_as_cross_entity_parent(self) -> bool:
        return (
            str(self.source_class).upper() == TRUSTED_SOURCE_CLASS
            and _is_janus_lineage(self.lineage_id)
            and bool(self.approved_for_identity_derivation)
        )


class SwarmGenomeLedger:
    """Append-only DAG joining many per-entity SpiralLedgers."""

    def __init__(self, genome_id: str = "JANUS_SWARM_GENOME") -> None:
        self.genome_id = str(genome_id)
        self.nodes: Dict[str, GenomeNode] = {}
        self.children: Dict[str, List[str]] = {}
        self.by_entity: Dict[str, List[str]] = {}
        self.by_spiral_fingerprint: Dict[str, str] = {}

    @staticmethod
    def _node_id(entity_id: str, entity_turn: int, spiral_fingerprint: str) -> str:
        short = fingerprint_payload(
            {"entity_id": entity_id, "turn": int(entity_turn), "spiral": spiral_fingerprint}
        )[:24]
        return f"{entity_id}:{int(entity_turn)}:{short}"

    def _require_trusted_extra_parent(self, parent_id: str) -> GenomeNode:
        parent_id = str(parent_id)
        if parent_id not in self.nodes:
            raise ValueError(f"unknown genome parent: {parent_id}")
        parent = self.nodes[parent_id]
        if not parent.trusted_as_cross_entity_parent:
            raise ValueError(f"FOREIGN_OR_UNTRUSTED_IDENTITY_PARENT:{parent_id}")
        return parent

    def register_spiral_turn(
        self,
        turn: SpiralTurn,
        *,
        identity_strand: Any = None,
        evidence_strand: Any = None,
        extra_parent_ids: Optional[Iterable[str]] = None,
        relation: str = "SPIRAL_ASCENT",
        source_class: str = LEGACY_SOURCE_CLASS,
        lineage_id: str = "",
        approved_for_identity_derivation: bool = False,
    ) -> GenomeNode:
        """Register one turn while enforcing the lineage trust boundary.

        Existing same-entity primary ancestry remains backwards-compatible.
        Cross-entity ``extra_parent_ids`` are stronger: every such parent must be
        explicitly ``JANUS_OWNED``, carry a ``JANUS:*`` lineage, and be approved.

        New nodes default to LEGACY_UNTRUSTED. Callers that intend a state to be
        eligible for future cross-entity identity derivation must opt in
        explicitly with the three provenance arguments.
        """
        entity_id = str(turn.entity_id)
        entity_turn = int(turn.turn)
        existing_line = self.by_entity.get(entity_id, [])

        primary_parent_id: Optional[str] = None
        if entity_turn == 0:
            if turn.parent_fingerprint is not None:
                raise ValueError("turn 0 cannot claim a same-entity parent fingerprint")
        else:
            if len(existing_line) != entity_turn:
                raise ValueError(f"entity lineage must be ingested sequentially: {entity_id}")
            primary_parent_id = existing_line[-1]
            previous = self.nodes[primary_parent_id]
            if previous.spiral_fingerprint != turn.parent_fingerprint:
                raise ValueError(f"spiral parent mismatch for {entity_id} turn {entity_turn}")

        parents: List[str] = []
        if primary_parent_id is not None:
            parents.append(primary_parent_id)
        for parent_id in extra_parent_ids or []:
            parent_id = str(parent_id)
            self._require_trusted_extra_parent(parent_id)
            if parent_id not in parents:
                parents.append(parent_id)

        genome_node_id = self._node_id(entity_id, entity_turn, turn.fingerprint)
        if genome_node_id in self.nodes:
            node = self.nodes[genome_node_id]
            if node.spiral_fingerprint != turn.fingerprint:
                raise ValueError("genome id collision")
            return node
        if turn.fingerprint in self.by_spiral_fingerprint:
            raise ValueError("spiral fingerprint already bound to a different genome node")

        source_class = str(source_class or LEGACY_SOURCE_CLASS).upper()
        lineage_id = str(lineage_id or "")
        approved = bool(approved_for_identity_derivation)
        if approved and not (
            source_class == TRUSTED_SOURCE_CLASS and _is_janus_lineage(lineage_id)
        ):
            raise ValueError("IDENTITY_DERIVATION_APPROVAL_REQUIRES_JANUS_OWNED_LINEAGE")

        identity = turn.active_state_after if identity_strand is None else identity_strand
        evidence = {
            "candidate_state": turn.candidate_state,
            "outcome": turn.outcome,
            "lessons": list(turn.lessons),
            "constraints": list(turn.constraints),
            "promoted": bool(turn.promoted),
        } if evidence_strand is None else evidence_strand

        node = GenomeNode(
            genome_id=genome_node_id,
            entity_id=entity_id,
            entity_turn=entity_turn,
            spiral_fingerprint=str(turn.fingerprint),
            primary_parent_id=primary_parent_id,
            parent_ids=parents,
            relation=str(relation),
            identity_strand=_normal(identity),
            evidence_strand=_normal(evidence),
            source_class=source_class,
            lineage_id=lineage_id,
            approved_for_identity_derivation=approved,
        ).seal()

        self.nodes[node.genome_id] = node
        self.by_entity.setdefault(entity_id, []).append(node.genome_id)
        self.by_spiral_fingerprint[node.spiral_fingerprint] = node.genome_id
        self.children.setdefault(node.genome_id, [])
        for parent_id in parents:
            self.children.setdefault(parent_id, []).append(node.genome_id)
        return node

    def entity_lineage(self, entity_id: str) -> List[GenomeNode]:
        return [self.nodes[node_id] for node_id in self.by_entity.get(str(entity_id), [])]

    def ancestors(self, genome_id: str, include_self: bool = False) -> List[GenomeNode]:
        if genome_id not in self.nodes:
            raise KeyError(genome_id)
        ordered: List[GenomeNode] = [self.nodes[genome_id]] if include_self else []
        seen: Set[str] = {genome_id}
        queue = list(self.nodes[genome_id].parent_ids)
        while queue:
            node_id = queue.pop(0)
            if node_id in seen:
                continue
            seen.add(node_id)
            node = self.nodes[node_id]
            ordered.append(node)
            queue.extend(node.parent_ids)
        return ordered

    def descendants(self, genome_id: str, include_self: bool = False) -> List[GenomeNode]:
        if genome_id not in self.nodes:
            raise KeyError(genome_id)
        ordered: List[GenomeNode] = [self.nodes[genome_id]] if include_self else []
        seen: Set[str] = {genome_id}
        queue = list(self.children.get(genome_id, []))
        while queue:
            node_id = queue.pop(0)
            if node_id in seen:
                continue
            seen.add(node_id)
            ordered.append(self.nodes[node_id])
            queue.extend(self.children.get(node_id, []))
        return ordered

    def trace_to_origins(self, genome_id: str) -> List[List[str]]:
        """Return every root->current path. Multiple explicit parents create multiple paths."""
        if genome_id not in self.nodes:
            raise KeyError(genome_id)

        def walk(node_id: str, suffix: List[str]) -> List[List[str]]:
            node = self.nodes[node_id]
            path = [node_id, *suffix]
            if not node.parent_ids:
                return [path]
            paths: List[List[str]] = []
            for parent_id in node.parent_ids:
                paths.extend(walk(parent_id, path))
            return paths

        return walk(genome_id, [])

    def validate(self) -> None:
        for entity_id, ids in self.by_entity.items():
            for expected_turn, node_id in enumerate(ids):
                node = self.nodes[node_id]
                if node.entity_id != entity_id or node.entity_turn != expected_turn:
                    raise ValueError(f"broken entity turn sequence: {entity_id}")
                if expected_turn == 0 and node.primary_parent_id is not None:
                    raise ValueError("turn 0 has a same-entity parent")
                if expected_turn > 0 and node.primary_parent_id != ids[expected_turn - 1]:
                    raise ValueError(f"broken primary lineage: {entity_id}")
        for node_id, node in self.nodes.items():
            body = asdict(node)
            expected = body.pop("fingerprint")
            if fingerprint_payload(body) != expected:
                raise ValueError(f"genome fingerprint mismatch: {node_id}")
            for parent_id in node.parent_ids:
                if parent_id not in self.nodes:
                    raise ValueError(f"missing genome parent: {parent_id}")
                if node_id not in self.children.get(parent_id, []):
                    raise ValueError("parent/child index mismatch")
            for child_id in self.children.get(node_id, []):
                if node_id not in self.nodes[child_id].parent_ids:
                    raise ValueError("child/parent index mismatch")
        for node_id in self.nodes:
            if any(node.genome_id == node_id for node in self.ancestors(node_id)):
                raise ValueError("cycle detected in genome ledger")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema": "janus.swarm.genome_ledger.v1.1-trait-lineage-firewall",
            "genome_id": self.genome_id,
            "model": "DUAL_STRAND_SPIRAL_GENEALOGY",
            "laws": list(GENOME_LAWS),
            "trait_lineage_firewall": {
                "cross_entity_parent_policy": "APPROVED_JANUS_OWNED_ONLY",
                "legacy_default": LEGACY_SOURCE_CLASS,
                "required_lineage_prefix": JANUS_LINEAGE_PREFIX,
            },
            "nodes": {key: self.nodes[key].to_dict() for key in sorted(self.nodes)},
            "children": {key: list(value) for key, value in sorted(self.children.items())},
            "entities": {key: list(value) for key, value in sorted(self.by_entity.items())},
        }


__all__ = [
    "GENOME_LAWS", "TRUSTED_SOURCE_CLASS", "LEGACY_SOURCE_CLASS",
    "JANUS_LINEAGE_PREFIX", "GenomeNode", "SwarmGenomeLedger"
]
