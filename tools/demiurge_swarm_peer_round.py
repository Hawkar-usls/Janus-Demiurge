#!/usr/bin/env python3
"""Execute a second Scout collection round from orchestrator peer messages.

When a Scout microkernel plan is supplied, the peer round consumes only the
admitted work claims from the sealed cohort. This keeps intake/admission/cohort
formation separate from execution and preserves deferred work for later turns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import demiurge_mail_research_swarm as base

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scout_microkernel

base.MISSION_PATH = ROOT / "scout_swarm" / "missions" / "JANUS_FULL_SYSTEM_SCOUT_DIRECTIONS-2026-08-22-v1.json"


def _read(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(path)
    return obj


def _uniq(values: List[str], cap: int) -> List[str]:
    out: List[str] = []
    for x in values:
        x = str(x).strip()
        if x and x not in out:
            out.append(x)
        if len(out) >= cap:
            break
    return out


def _legacy_peer_inputs(messages: List[Dict[str, Any]], agent: Dict[str, Any]) -> tuple[List[str], List[str]]:
    peer_urls: List[str] = []
    peer_queries: List[str] = []
    for msg in messages:
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        for url in payload.get("source_urls", []) or []:
            if base.host_allowed(str(url), agent.get("allowed_domains", [])):
                peer_urls.append(str(url))
        for fact in payload.get("facts", []) or []:
            if isinstance(fact, dict):
                for url in fact.get("source_urls", []) or []:
                    if base.host_allowed(str(url), agent.get("allowed_domains", [])):
                        peer_urls.append(str(url))
        for q in payload.get("suggested_queries", []) or []:
            peer_queries.append(str(q))
    return peer_urls, peer_queries


def run_peer(
    agent_id: str,
    original_path: Path,
    inbox_path: Path,
    output: Path,
    microkernel_plan_path: Path | None = None,
) -> None:
    mission = base.load_mission()
    agents = {a["id"]: a for a in mission["agents"]}
    if agent_id not in agents:
        raise SystemExit(f"UNKNOWN_AGENT:{agent_id}")
    original = _read(original_path)
    inbox = _read(inbox_path)
    if inbox.get("scout_id") != agent_id:
        raise ValueError("inbox identity mismatch")
    agent = dict(agents[agent_id])
    messages = [m for m in inbox.get("messages", []) if isinstance(m, dict)]

    microkernel_context: Dict[str, Any] = {
        "enabled": False,
        "fallback_legacy_message_intake": True,
    }
    if microkernel_plan_path is not None:
        plan = _read(microkernel_plan_path)
        if str(plan.get("scout_id") or "") != agent_id:
            raise ValueError("microkernel plan identity mismatch")
        inputs = scout_microkernel.execution_inputs(plan)
        peer_urls = [
            str(url)
            for url in inputs["source_urls"]
            if base.host_allowed(str(url), agent.get("allowed_domains", []))
        ]
        peer_queries = [str(q) for q in inputs["queries"]]
        microkernel_context = {
            "enabled": True,
            "fallback_legacy_message_intake": False,
            "plan_sha256": plan.get("plan_sha256"),
            "status": plan.get("status"),
            "admitted_work_claim_ids": [
                str(x.get("work_claim_id"))
                for x in plan.get("admitted_work_claims", [])
                if isinstance(x, dict) and x.get("work_claim_id")
            ],
            "deferred_work_claim_ids": [
                str(x.get("work_claim_id"))
                for x in plan.get("deferred_work_claims", [])
                if isinstance(x, dict) and x.get("work_claim_id")
            ],
            "cohort_ids": [
                str(x.get("cohort_id"))
                for x in plan.get("cohorts", [])
                if isinstance(x, dict) and x.get("cohort_id")
            ],
            "look_away_admission_barrier": plan.get("look_away_admission_barrier"),
        }
    else:
        peer_urls, peer_queries = _legacy_peer_inputs(messages, agent)

    already = {
        str(s.get("final_url") or s.get("url") or "")
        for s in original.get("discovery", {}).get("sources", [])
        if isinstance(s, dict)
    }
    peer_urls = [u for u in _uniq(peer_urls, 12) if u not in already]
    peer_queries = _uniq(peer_queries, 12)

    enriched = dict(agent)
    enriched["seed_urls"] = _uniq(list(agent.get("seed_urls", [])) + peer_urls, 18)
    enriched["queries"] = _uniq(list(agent.get("queries", [])) + peer_queries, 18)
    discovery = base.discover(enriched)
    analysis, model_error = base.model_analyze(enriched, discovery)
    parent_hash = base.canonical_hash(original)
    report = {
        "schema": "janus.demiurge.public_research_agent_report.v3.peer_round.microkernel_ready",
        "mission_id": mission["mission_id"],
        "scout_id": agent_id,
        "track": agent["track"],
        "focus": agent["focus"],
        "orchestrator_round": 2,
        "parent_report_sha256": parent_hash,
        "peer_context": {
            "inbound_message_ids": list(inbox.get("message_ids", [])),
            "peer_seed_urls_admitted": peer_urls,
            "peer_queries_admitted": peer_queries,
            "identity_preserved": True,
            "message_count": len(messages),
        },
        "microkernel_context": microkernel_context,
        "janus_agent_token": {
            "scope": "EPHEMERAL_GITHUB_RUN_AGENT",
            "fingerprint": hashlib.sha256((agent_id + parent_hash).encode()).hexdigest()[:16],
            "raw_persisted": False,
        },
        "discovery": discovery,
        "analysis": analysis,
        "model_error": model_error,
        "evidence_boundary": {
            "model_output_is_not_evidence": True,
            "positive_findings_require_fetched_source_url": True,
            "failed_fetch_is_not_proof_of_absence": True,
            "peer_message_is_routing_context_not_evidence": True,
            "identity_cannot_be_deduplicated": True,
            "microkernel_workflow_provenance_is_not_scientific_truth": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> None:
    mission = base.load_mission()
    assert len(mission["agents"]) == 17
    assert _uniq(["a", "a", "b"], 10) == ["a", "b"]
    scout_microkernel.self_test()
    print("JANUS_SWARM_PEER_ROUND_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--agent")
    p.add_argument("--original")
    p.add_argument("--inbox")
    p.add_argument("--output")
    p.add_argument("--microkernel-plan")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return 0
    if not all([a.agent, a.original, a.inbox, a.output]):
        p.error("--agent --original --inbox --output required")
    run_peer(
        a.agent,
        Path(a.original),
        Path(a.inbox),
        Path(a.output),
        Path(a.microkernel_plan) if a.microkernel_plan else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
