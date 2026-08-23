#!/usr/bin/env python3
"""JANUS Scout CAUSAL_ACK / WORK_CLAIM ledger.

Closes the machine-readable provenance chain:

sender(s) -> message(s) -> coordinated WORK_CLAIM -> execution -> fetched source
-> round-2 observation -> CAUSAL_ACK -> recorded state change.

A COMPLETE_TRACE proves workflow provenance only. It does not prove scientific
truth or psychological causation. Duplicate instructions may coordinate into one
work claim, while every origin message, sender, Scout identity and observation is
preserved separately.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from spiral_evolution import SpiralLedger, fingerprint_payload
from swarm_genome_ledger import SwarmGenomeLedger


CAUSAL_ACK_LAWS = (
    "SCOUT_IDENTITIES_MUST_NOT_COLLAPSE",
    "OBSERVATIONS_MUST_NOT_COLLAPSE",
    "DUPLICATE_WORK_MAY_COORDINATE_WITHOUT_DELETING_ORIGIN_MESSAGES",
    "WORK_CLAIMS_ARE_APPEND_ONLY",
    "MESSAGES_ARE_ROUTING_CONTEXT_NOT_EMPIRICAL_EVIDENCE",
    "COMPLETE_TRACE_REQUIRES_MESSAGE_TO_WORK_TO_EXECUTION_TO_SOURCE_TO_OBSERVATION",
    "MULTI_ORIGIN_WORK_PRESERVES_ALL_ORIGINS_AND_DOES_NOT_INVENT_A_SINGLE_TRIGGER",
    "UNATTRIBUTED_OBSERVATIONS_MUST_REMAIN_IN_LINEAGE",
    "SAME_SOURCE_REPETITION_IS_NOT_INDEPENDENT_REPLICATION",
    "WORKFLOW_CAUSATION_IS_NOT_SCIENTIFIC_CAUSATION",
)

FETCH_OK = {"FETCHED", "FETCHED_NO_TEXT"}


def _read_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"expected object: {path}")
    return obj


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm_url(value: Any) -> str:
    text = str(value or "").strip()
    return text.split("#", 1)[0]


def _uniq(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        value = str(value)
        if value and value not in out:
            out.append(value)
    return out


def _work_claim_id(scout_id: str, kind: str, target: str) -> str:
    return "WORK::" + fingerprint_payload({
        "scout_id": scout_id,
        "kind": kind,
        "target": target,
    })[:28]


def _execution_id(claim_id: str, payload: Mapping[str, Any]) -> str:
    return "EXEC::" + fingerprint_payload({"claim_id": claim_id, "payload": payload})[:28]


def _ack_id(scout_id: str, observation_id: str, candidate_claim_ids: Sequence[str]) -> str:
    return "ACK::" + fingerprint_payload({
        "scout_id": scout_id,
        "observation_id": observation_id,
        "candidate_claim_ids": list(candidate_claim_ids),
    })[:28]


def _state_change_id(scout_id: str, observation_id: str, fact_id: str) -> str:
    return "CHANGE::" + fingerprint_payload({
        "scout_id": scout_id,
        "observation_id": observation_id,
        "fact_id": fact_id,
    })[:28]


def _message_urls(message: Mapping[str, Any]) -> List[str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    urls: List[str] = []
    for url in payload.get("source_urls", []) or []:
        urls.append(_norm_url(url))
    for fact in payload.get("facts", []) or []:
        if not isinstance(fact, dict):
            continue
        for url in fact.get("source_urls", []) or []:
            urls.append(_norm_url(url))
    return _uniq(urls)


def _message_queries(message: Mapping[str, Any]) -> List[str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    return _uniq(_norm_text(q) for q in (payload.get("suggested_queries", []) or []))


def build_work_claims(
    scout_id: str,
    inbox: Mapping[str, Any],
    peer_report: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Coordinate duplicate work while preserving every origin message.

    One recipient Scout gets at most one WORK_CLAIM for the same normalized
    QUERY or SOURCE_POINTER target. If several messages requested the same work,
    all origin message IDs and senders remain attached to that work claim.
    """
    peer_context = peer_report.get("peer_context") if isinstance(peer_report.get("peer_context"), dict) else {}
    admitted_queries = {_norm_text(q) for q in (peer_context.get("peer_queries_admitted", []) or [])}
    admitted_urls = {_norm_url(u) for u in (peer_context.get("peer_seed_urls_admitted", []) or [])}
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def admit(kind: str, target: str, message: Mapping[str, Any]) -> None:
        key = (kind, target)
        claim = grouped.setdefault(key, {
            "work_claim_id": _work_claim_id(scout_id, kind, target),
            "scout_id": scout_id,
            "kind": kind,
            "target": target,
            "origin_message_ids": [],
            "origin_sender_ids": [],
            "admission": "ADMITTED_FROM_PEER_MESSAGE",
            "coordination": "DUPLICATE_WORK_CLUSTERED__ORIGINS_PRESERVED",
            "append_only": True,
        })
        mid = str(message.get("message_id") or "")
        sender = str(message.get("sender_id") or "")
        if mid and mid not in claim["origin_message_ids"]:
            claim["origin_message_ids"].append(mid)
        if sender and sender not in claim["origin_sender_ids"]:
            claim["origin_sender_ids"].append(sender)

    for message in inbox.get("messages", []) or []:
        if not isinstance(message, dict) or not message.get("message_id"):
            continue
        for query in _message_queries(message):
            if query in admitted_queries:
                admit("QUERY", query, message)
        for url in _message_urls(message):
            if url in admitted_urls:
                admit("SOURCE_POINTER", url, message)

    return [grouped[key] for key in sorted(grouped)]


def _source_aliases(source: Mapping[str, Any]) -> List[str]:
    return _uniq(_norm_url(source.get(k)) for k in ("url", "final_url") if source.get(k))


def attach_execution_trace(
    claims: List[Dict[str, Any]],
    peer_report: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    discovery = peer_report.get("discovery") if isinstance(peer_report.get("discovery"), dict) else {}
    search_events = [e for e in (discovery.get("search_events", []) or []) if isinstance(e, dict)]
    sources = [s for s in (discovery.get("sources", []) or []) if isinstance(s, dict)]

    for claim in claims:
        target = claim["target"]
        if claim["kind"] == "QUERY":
            event = next((e for e in search_events if _norm_text(e.get("query")) == target), None)
            result_urls = _uniq(_norm_url(u) for u in ((event or {}).get("urls", []) or []))
            fetched: List[Dict[str, Any]] = []
            for source in sources:
                aliases = _source_aliases(source)
                if any(url in result_urls for url in aliases):
                    fetched.append({
                        "source_urls": aliases,
                        "status": source.get("status"),
                        "text_sha256": source.get("text_sha256"),
                    })
            execution: Dict[str, Any] = {
                "executed": event is not None,
                "query": target,
                "result_urls": result_urls,
                "result_count": int((event or {}).get("result_count") or len(result_urls)),
                "fetched_sources": fetched,
            }
        else:
            source = next((s for s in sources if target in _source_aliases(s)), None)
            execution = {
                "executed": source is not None,
                "source_pointer": target,
                "fetched_source": ({
                    "source_urls": _source_aliases(source),
                    "status": source.get("status"),
                    "text_sha256": source.get("text_sha256"),
                } if source else None),
            }
        execution["execution_id"] = _execution_id(claim["work_claim_id"], execution)
        claim["execution"] = execution
    return claims


def _claim_fetched_urls(claim: Mapping[str, Any]) -> List[str]:
    execution = claim.get("execution") if isinstance(claim.get("execution"), dict) else {}
    urls: List[str] = []
    if claim.get("kind") == "QUERY":
        for item in execution.get("fetched_sources", []) or []:
            if not isinstance(item, dict) or str(item.get("status")) not in FETCH_OK:
                continue
            urls.extend(_norm_url(u) for u in (item.get("source_urls", []) or []))
    else:
        item = execution.get("fetched_source")
        if isinstance(item, dict) and str(item.get("status")) in FETCH_OK:
            urls.extend(_norm_url(u) for u in (item.get("source_urls", []) or []))
    return _uniq(urls)


def build_causal_acks(
    scout_id: str,
    claims: Sequence[Mapping[str, Any]],
    round2_observations: Sequence[Mapping[str, Any]],
    new_fact_ids: Iterable[str],
) -> List[Dict[str, Any]]:
    new_fact_ids = {str(x) for x in new_fact_ids}
    acks: List[Dict[str, Any]] = []
    for obs in round2_observations:
        observation_id = str(obs.get("observation_id") or "")
        if not observation_id:
            continue
        obs_urls = {_norm_url(u) for u in (obs.get("source_urls", []) or [])}
        routes: List[Dict[str, Any]] = []
        for claim in claims:
            matched = sorted(obs_urls & set(_claim_fetched_urls(claim)))
            if not matched:
                continue
            execution = claim.get("execution") if isinstance(claim.get("execution"), dict) else {}
            routes.append({
                "work_claim_id": claim.get("work_claim_id"),
                "origin_message_ids": list(claim.get("origin_message_ids") or []),
                "origin_sender_ids": list(claim.get("origin_sender_ids") or []),
                "execution_id": execution.get("execution_id"),
                "kind": claim.get("kind"),
                "target": claim.get("target"),
                "matched_source_urls": matched,
            })

        candidate_ids = _uniq(str(r.get("work_claim_id")) for r in routes if r.get("work_claim_id"))
        if len(candidate_ids) == 1:
            status = "COMPLETE_TRACE"
            work_route_proven = True
            origin_ids = _uniq(str(x) for x in (routes[0].get("origin_message_ids") or []))
            single_origin = len(origin_ids) == 1
        elif len(candidate_ids) > 1:
            status = "AMBIGUOUS_MULTI_WORK_TRACE"
            work_route_proven = False
            single_origin = False
        else:
            status = "UNATTRIBUTED_OBSERVATION"
            work_route_proven = False
            single_origin = False

        fact_id = str(obs.get("fact_id") or "")
        acks.append({
            "causal_ack_id": _ack_id(scout_id, observation_id, candidate_ids),
            "scout_id": scout_id,
            "observation_id": observation_id,
            "fact_id": fact_id,
            "interaction_birth": fact_id in new_fact_ids,
            "status": status,
            "candidate_routes": routes,
            "work_route_proven": work_route_proven,
            "single_origin_message_proven": single_origin,
            "exact_workflow_trigger_claimed": single_origin,
            "workflow_causation_only": True,
            "scientific_causation_claimed": False,
            "peer_message_is_empirical_evidence": False,
            "append_only": True,
        })
    return acks


def build_state_changes(acks: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    for ack in acks:
        if not ack.get("interaction_birth"):
            continue
        changes.append({
            "state_change_id": _state_change_id(
                str(ack.get("scout_id") or ""),
                str(ack.get("observation_id") or ""),
                str(ack.get("fact_id") or ""),
            ),
            "scout_id": ack.get("scout_id"),
            "fact_id": ack.get("fact_id"),
            "observation_id": ack.get("observation_id"),
            "change_kind": "FACT_FIRST_OBSERVED_BY_SCOUT_AFTER_PEER_ROUND",
            "causal_ack_id": ack.get("causal_ack_id"),
            "trace_status": ack.get("status"),
            "work_route_proven": ack.get("work_route_proven"),
            "single_origin_message_proven": ack.get("single_origin_message_proven"),
            "scientific_causation_claimed": False,
            "append_only": True,
        })
    return changes


class _GenomeProjection:
    def __init__(self, mission_id: str, run_id: str):
        self.genome = SwarmGenomeLedger(f"JANUS_CAUSAL_ACK_GENOME::{mission_id}::{run_id}")
        self.spirals: Dict[str, SpiralLedger] = {}
        self.typed_edges: List[Dict[str, Any]] = []
        self.node_by_key: Dict[str, str] = {}

    def add(
        self,
        key: str,
        state: Dict[str, Any],
        evidence: Dict[str, Any],
        parents: Optional[Sequence[Tuple[str, str]]] = None,
        relation: str = "CAUSAL_ACK_EVENT",
    ) -> str:
        ledger = self.spirals.setdefault(key, SpiralLedger(key))
        before = ledger.turns[-1].active_state_after if ledger.turns else None
        turn = ledger.ascend(
            state_before=before,
            candidate_state=state,
            active_state_after=state,
            promoted=True,
            outcome=relation,
            constraints=list(CAUSAL_ACK_LAWS),
        )
        parent_pairs = list(parents or [])
        node = self.genome.register_spiral_turn(
            turn,
            identity_strand=state,
            evidence_strand=evidence,
            extra_parent_ids=[pid for pid, _ in parent_pairs],
            relation=relation,
        )
        for parent_id, edge_relation in parent_pairs:
            body = {
                "parent_genome_id": parent_id,
                "child_genome_id": node.genome_id,
                "relation": edge_relation,
            }
            self.typed_edges.append({
                "edge_id": "EDGE::" + fingerprint_payload(body)[:28],
                **body,
                "append_only": True,
                "deletable": False,
            })
        self.node_by_key[key] = node.genome_id
        return node.genome_id


def project_genome(
    result: Mapping[str, Any],
    work_claims: Sequence[Mapping[str, Any]],
    acks: Sequence[Mapping[str, Any]],
    state_changes: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    p = _GenomeProjection(
        str(result.get("mission_id") or "UNKNOWN_MISSION"),
        str(result.get("run_id") or "UNKNOWN_RUN"),
    )

    scout_ids = sorted({str(x.get("scout_id")) for x in [*work_claims, *acks] if x.get("scout_id")})
    for sid in scout_ids:
        p.add(
            f"SCOUT_ROUND2::{sid}",
            {"scout_id": sid, "round": 2, "role": "CAUSAL_ACK_RECIPIENT"},
            {"identity_preserved": True},
            relation="SCOUT_ROUND2_CAUSAL_ANCHOR",
        )

    message_meta: Dict[str, Dict[str, Any]] = {}
    for claim in work_claims:
        senders = list(claim.get("origin_sender_ids") or [])
        for index, mid in enumerate(claim.get("origin_message_ids") or []):
            mid = str(mid)
            meta = message_meta.setdefault(mid, {"message_id": mid, "sender_ids": []})
            if index < len(senders) and senders[index] not in meta["sender_ids"]:
                meta["sender_ids"].append(senders[index])
    message_nodes = {
        mid: p.add(
            f"MESSAGE::{mid}",
            {"message_id": mid, "sender_ids": meta.get("sender_ids", [])},
            {"peer_message_is_empirical_evidence": False},
            relation="MESSAGE_ANCHOR",
        )
        for mid, meta in sorted(message_meta.items())
    }

    claim_nodes: Dict[str, str] = {}
    exec_nodes: Dict[str, str] = {}
    source_nodes: Dict[Tuple[str, str], str] = {}
    for claim in work_claims:
        cid = str(claim.get("work_claim_id"))
        sid = str(claim.get("scout_id"))
        parents: List[Tuple[str, str]] = []
        for mid in claim.get("origin_message_ids") or []:
            mid = str(mid)
            if mid in message_nodes:
                parents.append((message_nodes[mid], "MESSAGE_CONTRIBUTED_TO_WORK_CLAIM"))
        anchor = p.node_by_key.get(f"SCOUT_ROUND2::{sid}")
        if anchor:
            parents.append((anchor, "WORK_CLAIM_ASSIGNED_TO_SCOUT"))
        cnode = p.add(
            f"WORK_CLAIM::{cid}",
            {
                "work_claim_id": cid,
                "scout_id": sid,
                "kind": claim.get("kind"),
                "target": claim.get("target"),
                "origin_message_ids": list(claim.get("origin_message_ids") or []),
            },
            {
                "admission": claim.get("admission"),
                "coordination": claim.get("coordination"),
                "append_only": True,
            },
            parents=list(dict.fromkeys(parents)),
            relation="WORK_CLAIM",
        )
        claim_nodes[cid] = cnode

        execution = claim.get("execution") if isinstance(claim.get("execution"), dict) else {}
        eid = str(execution.get("execution_id") or "")
        if not eid:
            continue
        enode = p.add(
            f"EXECUTION::{eid}",
            {"execution_id": eid, "executed": execution.get("executed")},
            {"execution": execution},
            parents=[(cnode, "EXECUTES_WORK_CLAIM")],
            relation="WORK_EXECUTION",
        )
        exec_nodes[eid] = enode
        for url in _claim_fetched_urls(claim):
            skey = (eid, url)
            source_nodes[skey] = p.add(
                f"SOURCE::{fingerprint_payload({'execution_id': eid, 'url': url})[:28]}",
                {"url": url, "execution_id": eid},
                {"fetched": True},
                parents=[(enode, "EXECUTION_FETCHED_SOURCE")],
                relation="FETCHED_SOURCE",
            )

    observation_nodes: Dict[str, str] = {}
    for ack in acks:
        oid = str(ack.get("observation_id"))
        sid = str(ack.get("scout_id"))
        parents: List[Tuple[str, str]] = []
        anchor = p.node_by_key.get(f"SCOUT_ROUND2::{sid}")
        if anchor:
            parents.append((anchor, "OBSERVED_BY_SCOUT"))
        for route in ack.get("candidate_routes", []) or []:
            if not isinstance(route, dict):
                continue
            eid = str(route.get("execution_id") or "")
            for url in route.get("matched_source_urls", []) or []:
                node = source_nodes.get((eid, _norm_url(url)))
                if node:
                    parents.append((node, "SOURCE_CITED_BY_OBSERVATION"))
        onode = p.add(
            f"OBSERVATION::{oid}",
            {
                "observation_id": oid,
                "scout_id": sid,
                "fact_id": ack.get("fact_id"),
                "interaction_birth": ack.get("interaction_birth"),
            },
            {"causal_ack_status": ack.get("status")},
            parents=list(dict.fromkeys(parents)),
            relation="ROUND2_OBSERVATION",
        )
        observation_nodes[oid] = onode

    ack_nodes: Dict[str, str] = {}
    for ack in acks:
        aid = str(ack.get("causal_ack_id"))
        oid = str(ack.get("observation_id"))
        parents: List[Tuple[str, str]] = []
        if oid in observation_nodes:
            parents.append((observation_nodes[oid], "ACKNOWLEDGES_OBSERVATION_PROVENANCE"))
        for route in ack.get("candidate_routes", []) or []:
            if not isinstance(route, dict):
                continue
            cid = str(route.get("work_claim_id") or "")
            eid = str(route.get("execution_id") or "")
            if cid in claim_nodes:
                parents.append((claim_nodes[cid], "ACKNOWLEDGES_WORK_CLAIM"))
            if eid in exec_nodes:
                parents.append((exec_nodes[eid], "ACKNOWLEDGES_EXECUTION"))
            for mid in route.get("origin_message_ids", []) or []:
                mid = str(mid)
                if mid in message_nodes:
                    parents.append((message_nodes[mid], "ACKNOWLEDGES_ORIGIN_MESSAGE"))
        anode = p.add(
            f"CAUSAL_ACK::{aid}",
            {
                "causal_ack_id": aid,
                "status": ack.get("status"),
                "interaction_birth": ack.get("interaction_birth"),
            },
            {
                "work_route_proven": ack.get("work_route_proven"),
                "single_origin_message_proven": ack.get("single_origin_message_proven"),
                "workflow_causation_only": True,
                "scientific_causation_claimed": False,
            },
            parents=list(dict.fromkeys(parents)),
            relation="CAUSAL_ACK",
        )
        ack_nodes[aid] = anode

    for change in state_changes:
        cid = str(change.get("state_change_id"))
        aid = str(change.get("causal_ack_id"))
        parents: List[Tuple[str, str]] = []
        if aid in ack_nodes:
            parents.append((ack_nodes[aid], "CAUSAL_ACK_RECORDS_STATE_CHANGE"))
        oid = str(change.get("observation_id"))
        if oid in observation_nodes:
            parents.append((observation_nodes[oid], "OBSERVATION_BECAME_INTERACTION_BIRTH"))
        p.add(
            f"STATE_CHANGE::{cid}",
            {
                "state_change_id": cid,
                "scout_id": change.get("scout_id"),
                "fact_id": change.get("fact_id"),
                "change_kind": change.get("change_kind"),
            },
            {
                "trace_status": change.get("trace_status"),
                "work_route_proven": change.get("work_route_proven"),
                "single_origin_message_proven": change.get("single_origin_message_proven"),
                "scientific_causation_claimed": False,
            },
            parents=list(dict.fromkeys(parents)),
            relation="INTERACTION_BIRTH_STATE_CHANGE",
        )

    return {"genome": p.genome.to_dict(), "typed_edges": p.typed_edges}


def build_bundle_from_objects(
    result: Mapping[str, Any],
    peer_reports: Mapping[str, Mapping[str, Any]],
    inboxes: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    observations = [o for o in (result.get("observations", []) or []) if isinstance(o, dict)]
    identity_rounds = result.get("identity_rounds") if isinstance(result.get("identity_rounds"), dict) else {}
    all_claims: List[Dict[str, Any]] = []
    all_acks: List[Dict[str, Any]] = []

    for scout_id, peer_report in sorted(peer_reports.items()):
        claims = attach_execution_trace(
            build_work_claims(scout_id, inboxes.get(scout_id) or {"messages": []}, peer_report),
            peer_report,
        )
        round2_obs = [
            o for o in observations
            if str(o.get("scout_id")) == scout_id and int(o.get("round") or 0) == 2
        ]
        meta = identity_rounds.get(scout_id) if isinstance(identity_rounds.get(scout_id), dict) else {}
        all_claims.extend(claims)
        all_acks.extend(build_causal_acks(
            scout_id,
            claims,
            round2_obs,
            meta.get("new_fact_ids_after_peer_round", []) or [],
        ))

    state_changes = build_state_changes(all_acks)
    projection = project_genome(result, all_claims, all_acks, state_changes)
    counts = {
        "COMPLETE_TRACE": sum(a.get("status") == "COMPLETE_TRACE" for a in all_acks),
        "AMBIGUOUS_MULTI_WORK_TRACE": sum(a.get("status") == "AMBIGUOUS_MULTI_WORK_TRACE" for a in all_acks),
        "UNATTRIBUTED_OBSERVATION": sum(a.get("status") == "UNATTRIBUTED_OBSERVATION" for a in all_acks),
    }
    bundle: Dict[str, Any] = {
        "schema": "janus.swarm.causal_ack_ledger.v1",
        "mission_id": result.get("mission_id"),
        "run_id": result.get("run_id"),
        "parent_orchestrator_result_sha256": result.get("result_sha256"),
        "model": "MESSAGE_TO_WORK_TO_EXECUTION_TO_SOURCE_TO_OBSERVATION_TO_CHANGE_PROVENANCE",
        "laws": list(CAUSAL_ACK_LAWS),
        "work_claims": all_claims,
        "causal_acks": all_acks,
        "state_changes": state_changes,
        "genome": projection["genome"],
        "typed_edges": projection["typed_edges"],
        "stats": {
            "scout_count": len(peer_reports),
            "work_claim_count": len(all_claims),
            "causal_ack_count": len(all_acks),
            "state_change_count": len(state_changes),
            "status_counts": counts,
            "complete_trace_interaction_birth_count": sum(
                a.get("interaction_birth") and a.get("status") == "COMPLETE_TRACE" for a in all_acks
            ),
            "single_origin_interaction_birth_count": sum(
                a.get("interaction_birth") and a.get("single_origin_message_proven") for a in all_acks
            ),
            "genome_node_count": len(projection["genome"].get("nodes", {})),
            "typed_edge_count": len(projection["typed_edges"]),
        },
        "epistemic_boundary": {
            "complete_trace_proves_workflow_provenance": True,
            "complete_trace_proves_scientific_truth": False,
            "complete_trace_proves_psychological_causation": False,
            "multi_origin_complete_trace_proves_single_message_trigger": False,
            "peer_message_is_empirical_evidence": False,
            "same_source_multi_scout_is_independent_replication": False,
        },
    }
    body = dict(bundle)
    bundle["bundle_sha256"] = fingerprint_payload(body)
    return bundle


def build_from_run_dir(run_dir: Path) -> Dict[str, Any]:
    result = _read_json(run_dir / "ORCHESTRATOR_RESULT.json")
    peer_reports: Dict[str, Dict[str, Any]] = {}
    inboxes: Dict[str, Dict[str, Any]] = {}
    for path in sorted((run_dir / "agents").glob("*/round2.json")):
        report = _read_json(path)
        peer_reports[str(report.get("scout_id") or path.parent.name)] = report
    for path in sorted((run_dir / "inboxes").glob("*.json")):
        inbox = _read_json(path)
        inboxes[str(inbox.get("scout_id") or path.stem)] = inbox
    return build_bundle_from_objects(result, peer_reports, inboxes)


def write_bundle(run_dir: Path, output: Path) -> Path:
    bundle = build_from_run_dir(run_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _synthetic() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    url = "https://example.org/source"
    result = {
        "mission_id": "TEST",
        "run_id": "1",
        "result_sha256": "parent",
        "identity_rounds": {"SCOUT_B": {"new_fact_ids_after_peer_round": ["FACT_NEW"]}},
        "observations": [{
            "observation_id": "OBS1",
            "scout_id": "SCOUT_B",
            "round": 2,
            "fact_id": "FACT_NEW",
            "source_urls": [url],
        }],
    }
    peer = {
        "scout_id": "SCOUT_B",
        "peer_context": {"peer_queries_admitted": ["find exact source"], "peer_seed_urls_admitted": []},
        "discovery": {
            "search_events": [{"query": "find exact source", "urls": [url], "result_count": 1}],
            "sources": [{"url": url, "final_url": url, "status": "FETCHED", "text_sha256": "abc"}],
        },
    }
    inbox = {
        "scout_id": "SCOUT_B",
        "messages": [{
            "message_id": "MSG::one",
            "sender_id": "SCOUT_A",
            "kind": "REQUEST_HELP",
            "payload": {"suggested_queries": ["find exact source"]},
        }],
    }
    return result, {"SCOUT_B": peer}, {"SCOUT_B": inbox}


def self_test() -> None:
    result, peers, inboxes = _synthetic()
    bundle = build_bundle_from_objects(result, peers, inboxes)
    assert bundle["stats"]["work_claim_count"] == 1
    assert bundle["stats"]["status_counts"]["COMPLETE_TRACE"] == 1
    assert bundle["stats"]["complete_trace_interaction_birth_count"] == 1
    assert bundle["stats"]["state_change_count"] == 1
    ack = bundle["causal_acks"][0]
    assert ack["work_route_proven"] is True
    assert ack["single_origin_message_proven"] is True
    assert ack["scientific_causation_claimed"] is False
    assert ack["candidate_routes"][0]["origin_message_ids"] == ["MSG::one"]

    # Same task arriving from two messages coordinates into one WORK_CLAIM.
    # Both origins remain preserved, so the work route is complete while no
    # single origin message is invented as the unique cause.
    inboxes2 = json.loads(json.dumps(inboxes))
    inboxes2["SCOUT_B"]["messages"].append({
        "message_id": "MSG::two",
        "sender_id": "SCOUT_C",
        "kind": "REQUEST_HELP",
        "payload": {"suggested_queries": ["find exact source"]},
    })
    bundle2 = build_bundle_from_objects(result, peers, inboxes2)
    assert bundle2["stats"]["work_claim_count"] == 1
    assert bundle2["stats"]["status_counts"]["COMPLETE_TRACE"] == 1
    ack2 = bundle2["causal_acks"][0]
    assert ack2["work_route_proven"] is True
    assert ack2["single_origin_message_proven"] is False
    assert len(ack2["candidate_routes"][0]["origin_message_ids"]) == 2
    print("JANUS_CAUSAL_ACK_LEDGER_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.run_dir or not args.output:
        parser.error("--run-dir and --output are required")
    print(write_bundle(Path(args.run_dir), Path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
