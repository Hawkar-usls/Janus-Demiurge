#!/usr/bin/env python3
"""JANUS Scout microkernel / Wave Rider controller.

Applies the older JANUS A18 microkernel and Wave Rider architecture to Scout
coordination without importing mining-specific semantics. The controller keeps
narrow, replaceable kernels for intake, admission, cohort formation, drain,
utility classification, budget/health, evidence and policy/memory.

The important epistemic adaptation is a Look-Away admission barrier: work is
admitted from routing metadata before result quality is inspected. This reduces
adaptive confirmation pressure. Results are revealed/classified only after the
cohort is sealed and the execution drain completes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tools.demiurge_mail_research_swarm import canonical_hash

ROOT = Path(__file__).resolve().parent
PROTOCOL_PATH = ROOT / "scout_swarm" / "orchestrator" / "SCOUT_MICROKERNEL_PROTOCOL-v1.json"

KERNEL_ORDER = [
    "JOB_INTAKE_KERNEL",
    "ADMISSION_KERNEL",
    "COHORT_KERNEL",
    "DRAIN_KERNEL",
    "UTILITY_CLASSIFICATION_KERNEL",
    "BUDGET_HEALTH_KERNEL",
    "EVIDENCE_KERNEL",
    "POLICY_MEMORY_KERNEL",
]

PRIORITY = {
    "CONFLICT_REVIEW": 0,
    "REQUEST_HELP": 1,
    "OBSERVATION_BUNDLE": 2,
    "PEER_ROUND_RESPONSE": 3,
}


def _read(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(path)
    return obj


def load_protocol() -> Dict[str, Any]:
    protocol = _read(PROTOCOL_PATH)
    if protocol.get("status") != "ACTIVE":
        raise ValueError("Scout microkernel protocol is not ACTIVE")
    return protocol


def _uniq(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        token = str(value).strip()
        if token and token not in out:
            out.append(token)
    return out


def _task_key(task_type: str, payload: str) -> str:
    normalized = " ".join(str(payload).strip().split())
    if task_type == "QUERY":
        normalized = normalized.lower()
    return canonical_hash({"type": task_type, "payload": normalized})[:28]


def _origin(message: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message_id": str(message.get("message_id") or ""),
        "sender_id": str(message.get("sender_id") or ""),
        "kind": str(message.get("kind") or ""),
        "topic": str(message.get("topic") or ""),
        "sequence": message.get("sequence"),
    }


def extract_task_atoms(inbox: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Translate peer messages into narrow executable/context work atoms."""
    atoms: List[Dict[str, Any]] = []
    for message in inbox.get("messages", []):
        if not isinstance(message, dict):
            continue
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        origin = _origin(message)

        urls: List[str] = []
        urls.extend(str(x) for x in (payload.get("source_urls") or []))
        for fact in payload.get("facts") or []:
            if isinstance(fact, dict):
                urls.extend(str(x) for x in (fact.get("source_urls") or []))
        for url in _uniq(urls):
            atoms.append({
                "task_type": "SOURCE_POINTER",
                "payload": url,
                "origin": origin,
            })

        for query in _uniq(str(x) for x in (payload.get("suggested_queries") or [])):
            atoms.append({
                "task_type": "QUERY",
                "payload": query,
                "origin": origin,
            })

        if str(message.get("kind") or "") == "CONFLICT_REVIEW":
            fact_id = str(payload.get("fact_id") or "").strip()
            if fact_id:
                atoms.append({
                    "task_type": "CONTEXT_REVIEW",
                    "payload": fact_id,
                    "origin": origin,
                })
    return atoms


def coordinate_work(atoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Coalesce identical work, never identities or origin messages."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for atom in atoms:
        task_type = str(atom.get("task_type") or "")
        payload = str(atom.get("payload") or "")
        key = _task_key(task_type, payload)
        item = grouped.setdefault(key, {
            "work_claim_id": f"WORK::{key}",
            "task_type": task_type,
            "payload": payload,
            "origins": [],
            "origin_message_ids": [],
            "origin_scout_ids": [],
            "identity_collapses": 0,
            "coordinated_duplicate_work": False,
        })
        origin = dict(atom.get("origin") or {})
        msg_id = str(origin.get("message_id") or "")
        sender = str(origin.get("sender_id") or "")
        if msg_id and msg_id not in item["origin_message_ids"]:
            item["origins"].append(origin)
            item["origin_message_ids"].append(msg_id)
        if sender and sender not in item["origin_scout_ids"]:
            item["origin_scout_ids"].append(sender)
        item["coordinated_duplicate_work"] = len(item["origin_message_ids"]) > 1
        item["priority"] = min(
            [PRIORITY.get(str(x.get("kind") or ""), 9) for x in item["origins"]] or [9]
        )
    return sorted(grouped.values(), key=lambda x: (int(x.get("priority", 9)), x["work_claim_id"]))


def build_plan(agent_id: str, inbox: Dict[str, Any], protocol: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    protocol = protocol or load_protocol()
    if str(inbox.get("scout_id") or "") != agent_id:
        raise ValueError("inbox identity mismatch")

    atoms = extract_task_atoms(inbox)
    claims = coordinate_work(atoms)
    limits = protocol.get("wave_policy", {})
    width = int(limits.get("admission_width", 12))
    max_cohorts = int(limits.get("max_cohorts_per_peer_round", 2))
    capacity = max(1, width) * max(1, max_cohorts)
    admitted = claims[:capacity]
    deferred = claims[capacity:]

    cohorts: List[Dict[str, Any]] = []
    for idx in range(0, len(admitted), max(1, width)):
        members = admitted[idx: idx + max(1, width)]
        cohorts.append({
            "cohort_id": f"COHORT::{agent_id}::{idx // max(1, width) + 1}",
            "ordinal": idx // max(1, width) + 1,
            "work_claim_ids": [x["work_claim_id"] for x in members],
            "state_sequence": [
                "ADMISSION_OPEN",
                "COHORT_SEALED",
                "ADMISSION_CLOSED",
                "DRAIN_PENDING",
            ],
        })

    plan = {
        "schema": "janus.demiurge.scout_microkernel_plan.v1",
        "status": "SEALED_FOR_EXECUTION",
        "scout_id": agent_id,
        "lineage_id": inbox.get("lineage_id"),
        "mission_id": inbox.get("mission_id"),
        "kernel_order": list(KERNEL_ORDER),
        "source_architecture_lineage": protocol.get("source_architecture_lineage", []),
        "look_away_admission_barrier": {
            "enabled": True,
            "admission_may_read": ["message_kind", "task_type", "stable_work_fingerprint", "capacity"],
            "admission_must_not_read": ["future_result_quality", "future_claim_confidence", "future_positive_or_negative_outcome"],
            "meaning": "Seal work before looking at the result quality; reveal evidence after drain.",
        },
        "intake": {
            "inbound_message_count": int(inbox.get("message_count") or len(inbox.get("messages", []))),
            "task_atom_count": len(atoms),
        },
        "admission": {
            "width": width,
            "max_cohorts": max_cohorts,
            "capacity": capacity,
            "coordinated_work_claim_count": len(claims),
            "admitted_work_claim_count": len(admitted),
            "deferred_work_claim_count": len(deferred),
            "admission_closed_after_seal": True,
        },
        "admitted_work_claims": admitted,
        "deferred_work_claims": deferred,
        "cohorts": cohorts,
        "identity_protection": {
            "scout_identity_deduplication_allowed": False,
            "message_identity_deduplication_allowed": False,
            "observation_identity_deduplication_allowed": False,
            "identical_work_coordination_allowed": True,
            "all_origins_preserved": True,
        },
        "memory_rule": "DEFERRED_WORK_IS_CARRYOVER_NOT_DELETION",
        "plan_sha256": None,
    }
    copy = dict(plan)
    copy.pop("plan_sha256", None)
    plan["plan_sha256"] = canonical_hash(copy)
    return plan


def execution_inputs(plan: Dict[str, Any]) -> Dict[str, Any]:
    queries: List[str] = []
    source_urls: List[str] = []
    claim_map: Dict[str, Dict[str, Any]] = {}
    for claim in plan.get("admitted_work_claims", []):
        if not isinstance(claim, dict):
            continue
        cid = str(claim.get("work_claim_id") or "")
        ctype = str(claim.get("task_type") or "")
        payload = str(claim.get("payload") or "")
        claim_map[cid] = claim
        if ctype == "QUERY" and payload and payload not in queries:
            queries.append(payload)
        elif ctype == "SOURCE_POINTER" and payload and payload not in source_urls:
            source_urls.append(payload)
    return {"queries": queries, "source_urls": source_urls, "claim_map": claim_map}


def _source_index(report: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    index: Dict[str, Dict[str, Any]] = {}
    records: List[Dict[str, Any]] = []
    for src in report.get("discovery", {}).get("sources", []):
        if not isinstance(src, dict):
            continue
        records.append(src)
        for key in [str(src.get("url") or ""), str(src.get("final_url") or "")]:
            if key:
                index[key] = src
    return index, records


def finalize_trace(plan: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    if str(plan.get("scout_id") or "") != str(report.get("scout_id") or ""):
        raise ValueError("plan/report Scout mismatch")

    src_index, all_sources = _source_index(report)
    search_events = [x for x in report.get("discovery", {}).get("search_events", []) if isinstance(x, dict)]
    executions: List[Dict[str, Any]] = []

    for claim in plan.get("admitted_work_claims", []):
        if not isinstance(claim, dict):
            continue
        cid = str(claim.get("work_claim_id") or "")
        ctype = str(claim.get("task_type") or "")
        payload = str(claim.get("payload") or "")
        executed_urls: List[str] = []
        source_records: List[Dict[str, Any]] = []
        execution_status = "CONTEXT_RECORDED"

        if ctype == "QUERY":
            events = [x for x in search_events if str(x.get("query") or "") == payload]
            execution_status = "QUERY_EXECUTED" if events else "QUERY_NOT_OBSERVED_IN_REPORT"
            for event in events:
                executed_urls.extend(str(u) for u in (event.get("urls") or []))
            for url in _uniq(executed_urls):
                if url in src_index:
                    source_records.append(src_index[url])
        elif ctype == "SOURCE_POINTER":
            execution_status = "SOURCE_FETCH_ATTEMPTED" if payload in src_index else "SOURCE_POINTER_NOT_OBSERVED_IN_REPORT"
            if payload in src_index:
                source_records.append(src_index[payload])
                executed_urls.append(payload)
        elif ctype == "CONTEXT_REVIEW":
            execution_status = "CONTEXT_RECORDED"

        source_summaries = []
        for src in source_records:
            source_summaries.append({
                "url": src.get("final_url") or src.get("url"),
                "status": src.get("status"),
                "text_sha256": src.get("text_sha256"),
            })
        executions.append({
            "execution_id": "EXEC::" + canonical_hash({"claim": cid, "payload": payload, "sources": source_summaries})[:28],
            "work_claim_id": cid,
            "task_type": ctype,
            "payload": payload,
            "status": execution_status,
            "source_records": source_summaries,
            "origin_message_ids": list(claim.get("origin_message_ids") or []),
            "origin_scout_ids": list(claim.get("origin_scout_ids") or []),
        })

    claim_urls: Dict[str, set[str]] = {}
    for execution in executions:
        urls = {
            str(x.get("url"))
            for x in execution.get("source_records", [])
            if isinstance(x, dict) and x.get("url")
        }
        claim_urls[str(execution.get("work_claim_id"))] = urls

    observation_routes: List[Dict[str, Any]] = []
    findings = [x for x in report.get("analysis", {}).get("findings", []) if isinstance(x, dict)]
    for item in findings:
        f_urls = {str(u) for u in (item.get("source_urls") or []) if str(u)}
        matching = sorted(cid for cid, urls in claim_urls.items() if f_urls and urls.intersection(f_urls))
        if len(matching) == 1:
            route_status = "EXACT_WORK_ROUTE"
        elif len(matching) > 1:
            route_status = "MULTI_WORK_ROUTE"
        else:
            route_status = "UNATTRIBUTED_OBSERVATION"
        observation_routes.append({
            "observation_route_id": "ROUTE::" + canonical_hash({"finding": item, "matching": matching})[:28],
            "fact_id": item.get("fact_id"),
            "claim": item.get("claim"),
            "status": item.get("status"),
            "source_urls": sorted(f_urls),
            "work_claim_ids": matching,
            "route_status": route_status,
        })

    failed = sum(1 for src in all_sources if str(src.get("status") or "") == "FETCH_FAILED")
    fetched = sum(1 for src in all_sources if str(src.get("status") or "") in {"FETCHED", "FETCHED_NO_TEXT"})
    health = "HEALTHY"
    if failed and failed > fetched:
        health = "DEGRADED_FETCH_HEALTH"

    trace = {
        "schema": "janus.demiurge.scout_microkernel_trace.v1",
        "status": "DRAIN_COMPLETE__EVIDENCE_REVEALED__MEMORY_COMMIT_READY",
        "scout_id": plan.get("scout_id"),
        "mission_id": plan.get("mission_id"),
        "plan_sha256": plan.get("plan_sha256"),
        "kernel_order": list(KERNEL_ORDER),
        "cohorts": plan.get("cohorts", []),
        "executions": executions,
        "observation_routes": observation_routes,
        "budget_health": {
            "source_record_count": len(all_sources),
            "fetched_or_no_text_count": fetched,
            "fetch_failed_count": failed,
            "health": health,
            "failures_are_preserved_as_experience": True,
        },
        "drain": {
            "admission_closed_before_result_reveal": True,
            "in_flight_work_count": len(plan.get("admitted_work_claims", [])),
            "completed_execution_records": len(executions),
            "deferred_work_count": len(plan.get("deferred_work_claims", [])),
            "deferred_work_deleted": False,
        },
        "epistemic_boundary": {
            "microkernel_trace_proves_scientific_truth": False,
            "routing_context_is_empirical_evidence": False,
            "same_source_multi_scout_is_independent_replication": False,
            "admission_uses_future_result_quality": False,
        },
        "state_sequence": [
            "INTAKE_OPEN",
            "ADMISSION_OPEN",
            "COHORT_SEALED",
            "ADMISSION_CLOSED",
            "DRAIN_COMPLETE",
            "EVIDENCE_REVEAL",
            "MEMORY_COMMIT_READY",
        ],
    }
    trace["trace_sha256"] = canonical_hash(trace)
    return trace


def aggregate_traces(root: Path) -> Dict[str, Any]:
    traces: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("MICROKERNEL_TRACE.json")):
        try:
            obj = _read(path)
        except Exception:
            continue
        traces.append(obj)
    scouts = sorted({str(x.get("scout_id")) for x in traces if x.get("scout_id")})
    route_counts: Dict[str, int] = {}
    for trace in traces:
        for route in trace.get("observation_routes", []):
            if isinstance(route, dict):
                key = str(route.get("route_status") or "UNKNOWN")
                route_counts[key] = route_counts.get(key, 0) + 1
    result = {
        "schema": "janus.demiurge.scout_microkernel_swarm_trace.v1",
        "status": "COMPLETE" if traces else "NO_TRACES",
        "scout_count": len(scouts),
        "scout_ids": scouts,
        "kernel_order": list(KERNEL_ORDER),
        "trace_count": len(traces),
        "admitted_work_claim_count": sum(len(x.get("executions", [])) for x in traces),
        "deferred_work_claim_count": sum(int(x.get("drain", {}).get("deferred_work_count") or 0) for x in traces),
        "route_status_counts": route_counts,
        "identity_collapses": 0,
        "laws": [
            "FACTS_MAY_CLUSTER__SCOUTS_MUST_NOT",
            "DEFERRED_WORK_IS_CARRYOVER_NOT_DELETION",
            "ADMISSION_CLOSES_BEFORE_RESULT_REVEAL",
            "FAILURE_IS_EXPERIENCE_NOT_ERASURE",
            "NARROW_KERNELS_MUST_REMAIN_REPLACEABLE",
        ],
        "traces": [
            {
                "scout_id": x.get("scout_id"),
                "plan_sha256": x.get("plan_sha256"),
                "trace_sha256": x.get("trace_sha256"),
                "status": x.get("status"),
                "health": x.get("budget_health", {}).get("health"),
            }
            for x in traces
        ],
    }
    result["swarm_trace_sha256"] = canonical_hash(result)
    return result


def self_test() -> None:
    protocol = {
        "status": "ACTIVE",
        "source_architecture_lineage": ["old-a18.json"],
        "wave_policy": {"admission_width": 2, "max_cohorts_per_peer_round": 1},
    }
    inbox = {
        "scout_id": "SCOUT_TEST",
        "mission_id": "M",
        "lineage_id": "L",
        "messages": [
            {"message_id": "M1", "sender_id": "A", "kind": "REQUEST_HELP", "payload": {"suggested_queries": ["Find X"]}},
            {"message_id": "M2", "sender_id": "B", "kind": "REQUEST_HELP", "payload": {"suggested_queries": ["Find X"], "source_urls": ["https://example.org/x"]}},
        ],
    }
    plan = build_plan("SCOUT_TEST", inbox, protocol)
    assert plan["admission"]["coordinated_work_claim_count"] == 2
    query_claim = next(x for x in plan["admitted_work_claims"] if x["task_type"] == "QUERY")
    assert sorted(query_claim["origin_scout_ids"]) == ["A", "B"]
    assert query_claim["coordinated_duplicate_work"] is True
    assert plan["identity_protection"]["all_origins_preserved"] is True
    report = {
        "scout_id": "SCOUT_TEST",
        "discovery": {
            "search_events": [{"query": "Find X", "urls": ["https://example.org/x"]}],
            "sources": [{"url": "https://example.org/x", "final_url": "https://example.org/x", "status": "FETCHED", "text_sha256": "abc"}],
        },
        "analysis": {"findings": [{"claim": "X", "status": "FOUND", "source_urls": ["https://example.org/x"]}]},
    }
    trace = finalize_trace(plan, report)
    assert trace["state_sequence"][-1] == "MEMORY_COMMIT_READY"
    assert trace["epistemic_boundary"]["admission_uses_future_result_quality"] is False
    assert trace["observation_routes"][0]["route_status"] in {"EXACT_WORK_ROUTE", "MULTI_WORK_ROUTE"}
    print("JANUS_SCOUT_MICROKERNEL_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--aggregate", action="store_true")
    p.add_argument("--agent")
    p.add_argument("--inbox")
    p.add_argument("--plan-file")
    p.add_argument("--report")
    p.add_argument("--root")
    p.add_argument("--output")
    p.add_argument("--embed", action="store_true")
    a = p.parse_args()

    if a.self_test:
        self_test()
        return 0
    if a.plan:
        if not all([a.agent, a.inbox, a.output]):
            p.error("--plan requires --agent --inbox --output")
        plan = build_plan(str(a.agent), _read(Path(a.inbox)))
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(out)
        return 0
    if a.finalize:
        if not all([a.plan_file, a.report, a.output]):
            p.error("--finalize requires --plan-file --report --output")
        plan = _read(Path(a.plan_file))
        report_path = Path(a.report)
        report = _read(report_path)
        trace = finalize_trace(plan, report)
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if a.embed:
            report["microkernel_trace"] = trace
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(out)
        return 0
    if a.aggregate:
        if not all([a.root, a.output]):
            p.error("--aggregate requires --root --output")
        result = aggregate_traces(Path(a.root))
        out = Path(a.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(out)
        return 0
    p.error("choose --self-test, --plan, --finalize or --aggregate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
