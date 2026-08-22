#!/usr/bin/env python3
"""Bind JANUS Scout communication into the canonical SWARM_GENOME_LEDGER.

This layer does not replace the canonical genome ledger. It projects
orchestrator rounds, observations, messages, handoffs and fact clusters into
that append-only genealogy and adds typed interaction edges beside the
canonical parent DAG.

Important epistemic boundary: peer messages are routing context, not evidence.
The bridge may record that a new observation appeared after a peer-directed
round, but it does not claim that a specific message caused the finding unless
the source artifact explicitly carries that causal mapping.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from spiral_evolution import SpiralLedger, fingerprint_payload
from swarm_genome_ledger import SwarmGenomeLedger


NERVOUS_SYSTEM_LAWS = (
    "SCOUT_IDENTITY_PERSISTS_ACROSS_COMMUNICATION",
    "MESSAGES_ARE_APPEND_ONLY_GENOME_EVENTS",
    "OBSERVATIONS_REMAIN_SEPARATE_EVEN_WHEN_FACTS_CLUSTER",
    "HANDOFFS_CREATE_TYPED_GENEALOGY_EDGES",
    "PEER_CONTEXT_IS_NOT_EMPIRICAL_EVIDENCE",
    "SAME_SOURCE_REPETITION_IS_NOT_INDEPENDENT_REPLICATION",
    "CONFLICTS_AND_REFUTATIONS_REMAIN_IN_LINEAGE",
    "ROUND2_NOVELTY_IS_CONTEXTUAL_ASSOCIATION_NOT_PROVEN_CAUSATION",
)

POSITIVE_STATUSES = {"FOUND", "OBSERVED", "VERIFIED", "CONFIRMED", "PASS", "SUCCESS"}
NEGATIVE_STATUSES = {"REFUTED", "NOT_FOUND", "FAIL", "FAILED", "REJECTED", "NEGATIVE"}


def _clean(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    return repr(value)


def _status_class(status: Any) -> str:
    token = str(status or "").strip().upper()
    if token in POSITIVE_STATUSES:
        return "POSITIVE"
    if token in NEGATIVE_STATUSES:
        return "NEGATIVE"
    return "UNCERTAIN"


class NervousGenomeBuilder:
    """Project an orchestrator result into an append-only genome + typed edges."""

    def __init__(self, result: Dict[str, Any]) -> None:
        self.result = result
        mission_id = str(result.get("mission_id") or "UNKNOWN_MISSION")
        run_id = str(result.get("run_id") or "UNKNOWN_RUN")
        self.genome = SwarmGenomeLedger(
            genome_id=f"JANUS_SWARM_GENOME::{mission_id}::{run_id}"
        )
        self.spirals: Dict[str, SpiralLedger] = {}
        self.edges: List[Dict[str, Any]] = []
        self.scout_round_nodes: Dict[Tuple[str, int], str] = {}
        self.observation_nodes: Dict[str, str] = {}
        self.message_nodes: Dict[str, str] = {}
        self.fact_nodes: Dict[str, str] = {}
        self.birth_records: List[Dict[str, Any]] = []
        self._observations = [
            o for o in result.get("observations", []) if isinstance(o, dict)
        ]
        self._obs_by_id = {
            str(o.get("observation_id")): o
            for o in self._observations
            if o.get("observation_id")
        }

    def _append(
        self,
        entity_id: str,
        *,
        state: Dict[str, Any],
        evidence: Dict[str, Any],
        extra_parents: Optional[Iterable[str]] = None,
        relation: str,
        parent_relations: Optional[Dict[str, str]] = None,
    ) -> str:
        entity_id = str(entity_id)
        ledger = self.spirals.setdefault(entity_id, SpiralLedger(entity_id))
        before = ledger.turns[-1].active_state_after if ledger.turns else None
        turn = ledger.ascend(
            state_before=before,
            candidate_state=_clean(state),
            active_state_after=_clean(state),
            promoted=True,
            outcome=relation,
            lessons=[],
            constraints=list(NERVOUS_SYSTEM_LAWS),
        )
        node = self.genome.register_spiral_turn(
            turn,
            identity_strand=_clean(state),
            evidence_strand=_clean(evidence),
            extra_parent_ids=list(extra_parents or []),
            relation=relation,
        )
        relmap = dict(parent_relations or {})
        for parent_id in node.parent_ids:
            edge_relation = relmap.get(parent_id)
            if edge_relation is None:
                edge_relation = (
                    "SAME_ENTITY_ASCENT"
                    if parent_id == node.primary_parent_id
                    else relation
                )
            edge_body = {
                "parent_genome_id": parent_id,
                "child_genome_id": node.genome_id,
                "relation": edge_relation,
            }
            self.edges.append(
                {
                    "edge_id": "EDGE::" + fingerprint_payload(edge_body)[:28],
                    **edge_body,
                    "append_only": True,
                    "deletable": False,
                }
            )
        return node.genome_id

    def _orchestrator_anchor(self) -> str:
        orch = str(self.result.get("orchestrator") or "JANUS_SWARM_ORCHESTRATOR_01")
        return self._append(
            orch,
            state={
                "role": "SWARM_ORCHESTRATOR",
                "mission_id": self.result.get("mission_id"),
                "run_id": self.result.get("run_id"),
            },
            evidence={
                "controller_sha": self.result.get("controller_sha"),
                "identity_count": self.result.get("identity_count"),
                "identity_collapses": self.result.get("identity_collapses"),
            },
            relation="ORCHESTRATOR_RUN_ANCHOR",
        )

    def _build_round1_anchors(self) -> None:
        for scout_id, meta in sorted((self.result.get("identity_rounds") or {}).items()):
            if not isinstance(meta, dict) or not meta.get("round1_present"):
                continue
            node_id = self._append(
                scout_id,
                state={
                    "scout_id": scout_id,
                    "lineage_id": meta.get("lineage_id"),
                    "mission_id": self.result.get("mission_id"),
                    "run_id": self.result.get("run_id"),
                    "round": 1,
                    "phase": "INDEPENDENT_COLLECTION_COMPLETE",
                },
                evidence={
                    "report_sha256": meta.get("round1_report_sha256"),
                    "identity_preserved": meta.get("identity_preserved"),
                },
                relation="SCOUT_ROUND_1",
            )
            self.scout_round_nodes[(scout_id, 1)] = node_id

    def _build_observations_for_round(self, round_no: int) -> None:
        for obs in sorted(
            (o for o in self._observations if int(o.get("round") or 0) == round_no),
            key=lambda x: str(x.get("observation_id")),
        ):
            obs_id = str(obs.get("observation_id") or "")
            scout_id = str(obs.get("scout_id") or "")
            if not obs_id or not scout_id:
                continue
            anchor = self.scout_round_nodes.get((scout_id, round_no))
            if not anchor:
                raise ValueError(f"missing scout round anchor for observation {obs_id}")
            fact_id = str(obs.get("fact_id") or "")
            meta = (self.result.get("identity_rounds") or {}).get(scout_id, {})
            new_after_peer = (
                round_no == 2
                and fact_id in set(meta.get("new_fact_ids_after_peer_round") or [])
            )
            relation = (
                "PEER_ROUND_OBSERVATION"
                if round_no == 2
                else "INDEPENDENT_OBSERVATION"
            )
            node_id = self._append(
                f"OBS::{obs_id}",
                state={
                    "observation_id": obs_id,
                    "scout_id": scout_id,
                    "round": round_no,
                    "fact_id": fact_id,
                    "status": obs.get("status"),
                },
                evidence={
                    "claim": obs.get("claim"),
                    "source_urls": list(obs.get("source_urls") or []),
                    "confidence": obs.get("confidence"),
                    "status_class": _status_class(obs.get("status")),
                    "new_after_peer_round": new_after_peer,
                    "causal_status": (
                        "PEER_ROUND_CONTEXT_ASSOCIATION_NOT_PROVEN_CAUSATION"
                        if new_after_peer
                        else "NOT_APPLICABLE"
                    ),
                },
                extra_parents=[anchor],
                relation=relation,
                parent_relations={anchor: "OBSERVED_BY_SCOUT"},
            )
            self.observation_nodes[obs_id] = node_id

    def _message_source_observations(self, message: Dict[str, Any], round_no: int) -> List[str]:
        sender = str(message.get("sender_id") or "")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        out: List[str] = []

        for obs_id in payload.get("observation_ids") or []:
            node_id = self.observation_nodes.get(str(obs_id))
            if node_id and node_id not in out:
                out.append(node_id)

        fact_ids = {
            str(f.get("fact_id"))
            for f in (payload.get("facts") or [])
            if isinstance(f, dict) and f.get("fact_id")
        }
        for obs in self._observations:
            if (
                str(obs.get("scout_id") or "") == sender
                and int(obs.get("round") or 0) == round_no
                and str(obs.get("fact_id") or "") in fact_ids
            ):
                node_id = self.observation_nodes.get(str(obs.get("observation_id")))
                if node_id and node_id not in out:
                    out.append(node_id)
        return out

    def _build_round1_messages(self, orchestrator_anchor: str) -> None:
        for message in sorted(
            (
                m
                for m in self.result.get("message_log", [])
                if isinstance(m, dict) and m.get("kind") != "PEER_ROUND_RESPONSE"
            ),
            key=lambda x: int(x.get("sequence") or 0),
        ):
            message_id = str(message.get("message_id") or "")
            if not message_id:
                continue
            sender = str(message.get("sender_id") or "")
            parents: List[str] = []
            rels: Dict[str, str] = {}
            sender_anchor = self.scout_round_nodes.get((sender, 1))
            if sender_anchor:
                parents.append(sender_anchor)
                rels[sender_anchor] = "SENT_BY_SCOUT"
            elif sender == "JANUS_ORCHESTRATOR" or sender == str(self.result.get("orchestrator")):
                parents.append(orchestrator_anchor)
                rels[orchestrator_anchor] = "ISSUED_BY_ORCHESTRATOR"

            for obs_node in self._message_source_observations(message, 1):
                if obs_node not in parents:
                    parents.append(obs_node)
                    rels[obs_node] = "CARRIES_OBSERVATION"

            node_id = self._append(
                f"MSG::{message_id}",
                state={
                    "message_id": message_id,
                    "kind": message.get("kind"),
                    "topic": message.get("topic"),
                    "sender_id": sender,
                    "recipient_ids": list(message.get("recipient_ids") or []),
                    "sequence": message.get("sequence"),
                },
                evidence={
                    "payload": message.get("payload"),
                    "peer_message_is_evidence": False,
                    "append_only": message.get("append_only", True),
                    "deletable": message.get("deletable", False),
                },
                extra_parents=parents,
                relation="COMMUNICATION_EVENT",
                parent_relations=rels,
            )
            self.message_nodes[message_id] = node_id

    def _build_round2_anchors(self) -> None:
        for scout_id, meta in sorted((self.result.get("identity_rounds") or {}).items()):
            if not isinstance(meta, dict) or not meta.get("round2_present"):
                continue
            if (scout_id, 1) not in self.scout_round_nodes:
                raise ValueError(f"round2 scout has no round1 anchor: {scout_id}")
            inbound_ids = [str(x) for x in meta.get("inbound_message_ids") or []]
            message_parents: List[str] = []
            rels: Dict[str, str] = {}
            missing: List[str] = []
            for mid in inbound_ids:
                node_id = self.message_nodes.get(mid)
                if not node_id:
                    missing.append(mid)
                    continue
                message_parents.append(node_id)
                rels[node_id] = "PEER_CONTEXT_FOR"
            if missing:
                raise ValueError(
                    f"missing inbound message genome nodes for {scout_id}: {missing[:3]}"
                )

            node_id = self._append(
                scout_id,
                state={
                    "scout_id": scout_id,
                    "lineage_id": meta.get("lineage_id"),
                    "mission_id": self.result.get("mission_id"),
                    "run_id": self.result.get("run_id"),
                    "round": 2,
                    "phase": "PEER_DIRECTED_COLLECTION_COMPLETE",
                    "inbound_message_ids": inbound_ids,
                },
                evidence={
                    "report_sha256": meta.get("round2_report_sha256"),
                    "new_fact_ids_after_peer_round": list(
                        meta.get("new_fact_ids_after_peer_round") or []
                    ),
                    "identity_preserved": meta.get("identity_preserved"),
                    "causal_status": "PEER_CONTEXT_USED__EXACT_MESSAGE_CAUSATION_NOT_ASSERTED",
                },
                extra_parents=message_parents,
                relation="PEER_DIRECTED_ASCENT",
                parent_relations=rels,
            )
            self.scout_round_nodes[(scout_id, 2)] = node_id

    def _build_response_messages(self) -> None:
        for message in sorted(
            (
                m
                for m in self.result.get("message_log", [])
                if isinstance(m, dict) and m.get("kind") == "PEER_ROUND_RESPONSE"
            ),
            key=lambda x: int(x.get("sequence") or 0),
        ):
            message_id = str(message.get("message_id") or "")
            sender = str(message.get("sender_id") or "")
            if not message_id or not sender:
                continue
            payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
            parents: List[str] = []
            rels: Dict[str, str] = {}

            anchor = self.scout_round_nodes.get((sender, 2))
            if anchor:
                parents.append(anchor)
                rels[anchor] = "SENT_BY_SCOUT"

            for mid in payload.get("in_reply_to") or []:
                parent = self.message_nodes.get(str(mid))
                if parent and parent not in parents:
                    parents.append(parent)
                    rels[parent] = "REPLIES_TO"

            new_fact_ids = {str(x) for x in payload.get("new_fact_ids") or []}
            for obs in self._observations:
                if (
                    str(obs.get("scout_id") or "") == sender
                    and int(obs.get("round") or 0) == 2
                    and str(obs.get("fact_id") or "") in new_fact_ids
                ):
                    parent = self.observation_nodes.get(str(obs.get("observation_id")))
                    if parent and parent not in parents:
                        parents.append(parent)
                        rels[parent] = "REPORTS_NEW_OBSERVATION"

            node_id = self._append(
                f"MSG::{message_id}",
                state={
                    "message_id": message_id,
                    "kind": "PEER_ROUND_RESPONSE",
                    "topic": message.get("topic"),
                    "sender_id": sender,
                    "recipient_ids": list(message.get("recipient_ids") or []),
                    "sequence": message.get("sequence"),
                },
                evidence={
                    "payload": payload,
                    "peer_message_is_evidence": False,
                    "causal_status": "RESPONSE_TO_PEER_CONTEXT__NOT_PROOF_OF_EXACT_CAUSATION",
                },
                extra_parents=parents,
                relation="PEER_ROUND_RESPONSE",
                parent_relations=rels,
            )
            self.message_nodes[message_id] = node_id

    def _build_fact_nodes(self) -> None:
        for fact_id, cluster in sorted((self.result.get("fact_clusters") or {}).items()):
            if not isinstance(cluster, dict):
                continue
            obs_ids = [str(x) for x in cluster.get("observations") or []]
            parents = [
                self.observation_nodes[oid]
                for oid in obs_ids
                if oid in self.observation_nodes
            ]
            if not parents:
                continue
            statuses = [
                self._obs_by_id[oid].get("status")
                for oid in obs_ids
                if oid in self._obs_by_id
            ]
            classes = Counter(_status_class(s) for s in statuses)
            scouts = sorted(
                {
                    str(self._obs_by_id[oid].get("scout_id"))
                    for oid in obs_ids
                    if oid in self._obs_by_id
                }
            )
            rels: Dict[str, str] = {}
            for oid in obs_ids:
                node = self.observation_nodes.get(oid)
                obs = self._obs_by_id.get(oid)
                if not node or not obs:
                    continue
                cls = _status_class(obs.get("status"))
                rels[node] = {
                    "POSITIVE": "SUPPORTS_FACT_CLUSTER",
                    "NEGATIVE": "CHALLENGES_FACT_CLUSTER",
                    "UNCERTAIN": "QUALIFIES_FACT_CLUSTER",
                }[cls]

            node_id = self._append(
                f"FACT::{fact_id}",
                state={
                    "fact_id": fact_id,
                    "claim_variants": list(cluster.get("claim_variants") or []),
                    "source_urls": list(cluster.get("source_urls") or []),
                },
                evidence={
                    "observation_ids": obs_ids,
                    "distinct_scout_ids": scouts,
                    "observation_count": len(obs_ids),
                    "status_class_counts": dict(classes),
                    "independent_replication_claimed": bool(
                        cluster.get("independent_replication_claimed", False)
                    ),
                    "same_source_multi_scout_is_independent_replication": False,
                },
                extra_parents=parents,
                relation="FACT_CLUSTER_SYNTHESIS",
                parent_relations=rels,
            )
            self.fact_nodes[str(fact_id)] = node_id

    def _build_birth_records(self) -> None:
        responses = [
            m
            for m in self.result.get("message_log", [])
            if isinstance(m, dict) and m.get("kind") == "PEER_ROUND_RESPONSE"
        ]
        for scout_id, meta in sorted((self.result.get("identity_rounds") or {}).items()):
            if not isinstance(meta, dict):
                continue
            inbound = [str(x) for x in meta.get("inbound_message_ids") or []]
            for fact_id in meta.get("new_fact_ids_after_peer_round") or []:
                fact_id = str(fact_id)
                obs_ids = sorted(
                    str(o.get("observation_id"))
                    for o in self._observations
                    if str(o.get("scout_id") or "") == scout_id
                    and int(o.get("round") or 0) == 2
                    and str(o.get("fact_id") or "") == fact_id
                )
                response_ids = sorted(
                    str(m.get("message_id"))
                    for m in responses
                    if str(m.get("sender_id") or "") == scout_id
                    and fact_id
                    in {
                        str(x)
                        for x in (
                            (m.get("payload") or {}).get("new_fact_ids", [])
                            if isinstance(m.get("payload"), dict)
                            else []
                        )
                    }
                )
                self.birth_records.append(
                    {
                        "birth_id": "BIRTH::"
                        + fingerprint_payload(
                            {
                                "scout_id": scout_id,
                                "fact_id": fact_id,
                                "obs_ids": obs_ids,
                                "inbound": inbound,
                                "responses": response_ids,
                            }
                        )[:28],
                        "scout_id": scout_id,
                        "fact_id": fact_id,
                        "round2_observation_ids": obs_ids,
                        "inbound_message_ids": inbound,
                        "response_message_ids": response_ids,
                        "association": "NEW_AFTER_PEER_DIRECTED_ROUND",
                        "causal_claim": "CONTEXTUAL_ASSOCIATION_ONLY__EXACT_TRIGGER_NOT_PROVEN",
                    }
                )

    def build(self) -> Dict[str, Any]:
        if int(self.result.get("identity_collapses") or 0) != 0:
            raise ValueError("cannot bind an orchestrator result with identity collapse")

        orchestrator_anchor = self._orchestrator_anchor()
        self._build_round1_anchors()
        self._build_observations_for_round(1)
        self._build_round1_messages(orchestrator_anchor)
        self._build_round2_anchors()
        self._build_observations_for_round(2)
        self._build_response_messages()
        self._build_fact_nodes()
        self._build_birth_records()

        self.genome.validate()
        edge_ids = [e["edge_id"] for e in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("typed interaction edge collision")

        return {
            "schema": "janus.swarm.genome_nervous_system.v1",
            "mission_id": self.result.get("mission_id"),
            "run_id": self.result.get("run_id"),
            "controller_sha": self.result.get("controller_sha"),
            "status": "COMPLETE",
            "model": "SWARM_GENOME_LEDGER_PLUS_TYPED_NERVOUS_SYSTEM",
            "laws": list(NERVOUS_SYSTEM_LAWS),
            "evidence_boundary": {
                "peer_message_is_evidence": False,
                "same_source_multi_scout_is_independent_replication": False,
                "round2_new_fact_means_exact_message_caused_fact": False,
                "exact_causal_mapping_requires_explicit_source_artifact": True,
            },
            "indexes": {
                "scout_round_nodes": {
                    f"{sid}::R{round_no}": node_id
                    for (sid, round_no), node_id in sorted(self.scout_round_nodes.items())
                },
                "observation_nodes": dict(sorted(self.observation_nodes.items())),
                "message_nodes": dict(sorted(self.message_nodes.items())),
                "fact_nodes": dict(sorted(self.fact_nodes.items())),
            },
            "typed_interaction_edges": self.edges,
            "interaction_birth_records": self.birth_records,
            "stats": {
                "genome_node_count": len(self.genome.nodes),
                "typed_edge_count": len(self.edges),
                "scout_round_node_count": len(self.scout_round_nodes),
                "observation_node_count": len(self.observation_nodes),
                "message_node_count": len(self.message_nodes),
                "fact_node_count": len(self.fact_nodes),
                "interaction_birth_count": len(self.birth_records),
            },
            "swarm_genome_ledger": self.genome.to_dict(),
        }


def build_nervous_system(result: Dict[str, Any]) -> Dict[str, Any]:
    return NervousGenomeBuilder(result).build()


def write_nervous_system(input_path: Path, output_path: Path) -> Path:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    nervous = build_nervous_system(result)
    nervous["binding_sha256"] = fingerprint_payload(nervous)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(nervous, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def self_test() -> None:
    a_obs = {
        "observation_id": "obs-a-r1",
        "scout_id": "SCOUT_A",
        "round": 1,
        "fact_id": "FACT_X",
        "status": "FOUND",
        "claim": "x",
        "source_urls": ["https://example.test/x"],
        "confidence": "HIGH",
    }
    b_obs = {
        "observation_id": "obs-b-r1",
        "scout_id": "SCOUT_B",
        "round": 1,
        "fact_id": "FACT_X",
        "status": "FOUND",
        "claim": "x",
        "source_urls": ["https://example.test/x"],
        "confidence": "HIGH",
    }
    b_new = {
        "observation_id": "obs-b-r2",
        "scout_id": "SCOUT_B",
        "round": 2,
        "fact_id": "FACT_Y",
        "status": "FOUND",
        "claim": "y",
        "source_urls": ["https://example.test/y"],
        "confidence": "HIGH",
    }
    msg = {
        "message_id": "MSG::1",
        "sender_id": "SCOUT_A",
        "recipient_ids": ["SCOUT_B"],
        "kind": "OBSERVATION_BUNDLE",
        "topic": "TEST",
        "payload": {"facts": [{"fact_id": "FACT_X"}]},
        "sequence": 1,
        "append_only": True,
        "deletable": False,
    }
    response = {
        "message_id": "MSG::2",
        "sender_id": "SCOUT_B",
        "recipient_ids": ["JANUS_ORCHESTRATOR"],
        "kind": "PEER_ROUND_RESPONSE",
        "topic": "TEST",
        "payload": {"in_reply_to": ["MSG::1"], "new_fact_ids": ["FACT_Y"]},
        "sequence": 2,
        "append_only": True,
        "deletable": False,
    }
    result = {
        "mission_id": "TEST",
        "run_id": "1",
        "controller_sha": "abc",
        "orchestrator": "JANUS_SWARM_ORCHESTRATOR_01",
        "identity_count": 2,
        "identity_collapses": 0,
        "identity_rounds": {
            "SCOUT_A": {
                "lineage_id": "JANUS_SCOUT_LINEAGE::SCOUT_A",
                "round1_present": True,
                "round2_present": True,
                "round1_report_sha256": "a1",
                "round2_report_sha256": "a2",
                "inbound_message_ids": [],
                "new_fact_ids_after_peer_round": [],
                "identity_preserved": True,
            },
            "SCOUT_B": {
                "lineage_id": "JANUS_SCOUT_LINEAGE::SCOUT_B",
                "round1_present": True,
                "round2_present": True,
                "round1_report_sha256": "b1",
                "round2_report_sha256": "b2",
                "inbound_message_ids": ["MSG::1"],
                "new_fact_ids_after_peer_round": ["FACT_Y"],
                "identity_preserved": True,
            },
        },
        "observations": [a_obs, b_obs, b_new],
        "message_log": [msg, response],
        "fact_clusters": {
            "FACT_X": {
                "claim_variants": ["x"],
                "source_urls": ["https://example.test/x"],
                "observations": ["obs-a-r1", "obs-b-r1"],
                "independent_replication_claimed": False,
            },
            "FACT_Y": {
                "claim_variants": ["y"],
                "source_urls": ["https://example.test/y"],
                "observations": ["obs-b-r2"],
                "independent_replication_claimed": False,
            },
        },
    }
    out = build_nervous_system(result)
    assert out["stats"]["observation_node_count"] == 3
    assert out["stats"]["message_node_count"] == 2
    assert out["stats"]["fact_node_count"] == 2
    assert out["stats"]["interaction_birth_count"] == 1
    assert out["interaction_birth_records"][0]["causal_claim"].startswith(
        "CONTEXTUAL_ASSOCIATION_ONLY"
    )
    fact_x = out["indexes"]["fact_nodes"]["FACT_X"]
    parents = out["swarm_genome_ledger"]["nodes"][fact_x]["parent_ids"]
    assert len(parents) == 2
    assert out["evidence_boundary"]["same_source_multi_scout_is_independent_replication"] is False
    assert "SCOUT_A::R2" in out["indexes"]["scout_round_nodes"]
    assert "SCOUT_B::R2" in out["indexes"]["scout_round_nodes"]
    print("JANUS_SWARM_GENOME_NERVOUS_SYSTEM_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.input or not args.output:
        parser.error("--input and --output are required")
    print(write_nervous_system(Path(args.input), Path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
