#!/usr/bin/env python3
"""JANUS Scout Swarm Orchestrator — identity-preserving coordination bus.

The orchestrator coordinates data collection without collapsing Scouts that reach
similar facts. Facts/sources may be clustered for epistemic accounting, but every
Scout identity, observation, message and round remains append-only and addressable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from demiurge_mail_research_swarm import canonical_hash
from demiurge_systemwide_scout_runner import base

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "scout_swarm" / "orchestrator" / "SWARM_ORCHESTRATOR_POLICY-v1.json"


def load_policy() -> Dict[str, Any]:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("status") != "ACTIVE":
        raise ValueError("orchestrator policy is not active")
    return policy


def load_mission() -> Dict[str, Any]:
    return base.load_mission()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def load_reports(root: Path) -> List[Dict[str, Any]]:
    mission_id = load_mission()["mission_id"]
    reports: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("report.json")):
        obj = _read_json(path)
        if obj and obj.get("mission_id") == mission_id and obj.get("scout_id"):
            obj = dict(obj)
            obj["_report_path"] = str(path)
            reports.append(obj)
    return reports


def identity_registry(mission: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        a["id"]: {
            "scout_id": a["id"],
            "lineage_id": f"JANUS_SCOUT_LINEAGE::{a['id']}",
            "track": a["track"],
            "focus": a.get("focus", ""),
            "identity_protected": True,
            "deduplication_allowed": False,
        }
        for a in mission["agents"]
    }


def fact_key(item: Dict[str, Any]) -> str:
    fid = str(item.get("fact_id") or "").strip()
    if fid:
        return fid
    payload = {
        "claim": str(item.get("claim") or "").strip(),
        "status": str(item.get("status") or "").strip(),
        "source_urls": sorted(str(u) for u in (item.get("source_urls") or [])),
    }
    return "DERIVED::" + canonical_hash(payload)[:24]


def _report_round(report: Dict[str, Any], default: int = 1) -> int:
    try:
        return int(report.get("orchestrator_round") or default)
    except Exception:
        return default


def cluster_reports(reports: Iterable[Dict[str, Any]], default_round: int = 1) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    facts: Dict[str, Dict[str, Any]] = {}
    sources: Dict[str, Dict[str, Any]] = {}
    observations: List[Dict[str, Any]] = []
    for report in reports:
        sid = str(report.get("scout_id"))
        round_no = _report_round(report, default_round)
        for src in report.get("discovery", {}).get("sources", []):
            if not isinstance(src, dict):
                continue
            url = str(src.get("final_url") or src.get("url") or "")
            if not url:
                continue
            entry = sources.setdefault(url, {
                "url": url,
                "title": src.get("title"),
                "text_sha256": src.get("text_sha256"),
                "observations": [],
            })
            entry["observations"].append({
                "scout_id": sid,
                "round": round_no,
                "status": src.get("status"),
                "text_sha256": src.get("text_sha256"),
            })
        for item in report.get("analysis", {}).get("findings", []):
            if not isinstance(item, dict):
                continue
            key = fact_key(item)
            obs = {
                "observation_id": canonical_hash({"scout": sid, "round": round_no, "fact": key, "item": item})[:32],
                "scout_id": sid,
                "round": round_no,
                "fact_id": key,
                "status": item.get("status"),
                "claim": item.get("claim"),
                "source_urls": list(item.get("source_urls") or []),
                "confidence": item.get("confidence"),
            }
            observations.append(obs)
            cluster = facts.setdefault(key, {
                "fact_id": key,
                "claim_variants": [],
                "source_urls": [],
                "observations": [],
                "observation_count": 0,
                "distinct_scout_count": 0,
                "independent_replication_claimed": False,
            })
            if obs["claim"] and obs["claim"] not in cluster["claim_variants"]:
                cluster["claim_variants"].append(obs["claim"])
            for url in obs["source_urls"]:
                if url not in cluster["source_urls"]:
                    cluster["source_urls"].append(url)
            cluster["observations"].append(obs["observation_id"])
    by_obs = {o["observation_id"]: o for o in observations}
    for cluster in facts.values():
        cluster["observation_count"] = len(cluster["observations"])
        cluster["distinct_scout_count"] = len({by_obs[x]["scout_id"] for x in cluster["observations"]})
    return facts, sources, observations


def _route_tracks(track: str, policy: Dict[str, Any]) -> List[str]:
    routes = policy.get("track_routes", {}).get(track, [])
    if "*" in routes:
        return ["*"]
    return [str(x) for x in routes]


def recipients_for(sender_id: str, track: str, registry: Dict[str, Dict[str, Any]], policy: Dict[str, Any]) -> List[str]:
    allowed_tracks = _route_tracks(track, policy)
    out: List[str] = []
    for sid, meta in registry.items():
        if sid == sender_id:
            continue
        if "*" in allowed_tracks or meta["track"] in allowed_tracks:
            out.append(sid)
    return sorted(out)


def _message(sender: str, recipients: List[str], kind: str, topic: str, payload: Dict[str, Any], seq: int) -> Dict[str, Any]:
    body = {
        "sender_id": sender,
        "recipient_ids": recipients,
        "kind": kind,
        "topic": topic,
        "payload": payload,
        "sequence": seq,
    }
    return {
        "message_id": "MSG::" + canonical_hash(body)[:28],
        **body,
        "append_only": True,
        "deletable": False,
    }


def build_coordination(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    mission = load_mission()
    policy = load_policy()
    registry = identity_registry(mission)
    facts, sources, observations = cluster_reports(reports, default_round=1)
    messages: List[Dict[str, Any]] = []
    seq = 0

    query_claims: Dict[str, Dict[str, Any]] = {}
    mission_agents = {a["id"]: a for a in mission["agents"]}
    for sid in sorted(registry):
        for query in mission_agents[sid].get("queries", []):
            fp = canonical_hash({"query": str(query).strip().lower()})[:24]
            item = query_claims.setdefault(fp, {"query": str(query), "claimants": []})
            item["claimants"].append(sid)
    for fp, item in query_claims.items():
        claimants = sorted(set(item["claimants"]))
        item["lead"] = claimants[0]
        item["witnesses"] = claimants[1:]
        item["rule"] = "LEAD_COORDINATES__WITNESSES_REMAIN_DISTINCT"

    for report in sorted(reports, key=lambda r: str(r.get("scout_id"))):
        sid = str(report["scout_id"])
        track = str(report.get("track") or registry[sid]["track"])
        recipients = recipients_for(sid, track, registry, policy)
        findings = [f for f in report.get("analysis", {}).get("findings", []) if isinstance(f, dict)]
        if findings and recipients:
            bundle = []
            source_urls: List[str] = []
            for f in findings[: policy.get("limits", {}).get("facts_per_message", 24)]:
                bundle.append({
                    "fact_id": fact_key(f),
                    "claim": str(f.get("claim") or "")[:900],
                    "status": f.get("status"),
                    "source_urls": list(f.get("source_urls") or [])[:6],
                })
                for u in f.get("source_urls") or []:
                    if u not in source_urls:
                        source_urls.append(u)
            seq += 1
            messages.append(_message(sid, recipients, "OBSERVATION_BUNDLE", track, {
                "facts": bundle,
                "source_urls": source_urls[: policy.get("limits", {}).get("source_urls_per_message", 12)],
                "request": "Cross-check only where your role/domain adds independent value; do not count duplicate source/model as replication.",
            }, seq))
        next_checks = [str(x) for x in report.get("analysis", {}).get("next_checks", []) if str(x).strip()]
        gaps = [str(x) for x in report.get("analysis", {}).get("gaps", []) if str(x).strip() and "MODEL_INTERPRETATION" not in str(x)]
        requested = (next_checks + gaps)[: policy.get("limits", {}).get("queries_per_request", 8)]
        if requested and recipients:
            seq += 1
            messages.append(_message(sid, recipients, "REQUEST_HELP", track, {
                "suggested_queries": requested,
                "reason": "Peer-directed follow-up from unresolved checks/gaps.",
            }, seq))

    verifier_ids = sorted(sid for sid, meta in registry.items() if meta["track"] == "VERIFY_SYNTHESIZE")
    obs_by_id = {o["observation_id"]: o for o in observations}
    for key, cluster in facts.items():
        obs = [obs_by_id[x] for x in cluster["observations"]]
        statuses = sorted({str(x.get("status")) for x in obs})
        claims = sorted({str(x.get("claim") or "") for x in obs})
        if len(statuses) > 1 or len(claims) > 1:
            senders = sorted({x["scout_id"] for x in obs})
            seq += 1
            messages.append(_message("JANUS_ORCHESTRATOR", verifier_ids, "CONFLICT_REVIEW", key, {
                "fact_id": key,
                "status_variants": statuses,
                "claim_variant_count": len(claims),
                "observers": senders,
                "observation_ids": cluster["observations"],
            }, seq))

    inboxes: Dict[str, Dict[str, Any]] = {}
    for sid in sorted(registry):
        inbound = [m for m in messages if sid in m["recipient_ids"]]
        inboxes[sid] = {
            "schema": "janus.demiurge.scout_inbox.v1",
            "mission_id": mission["mission_id"],
            "scout_id": sid,
            "lineage_id": registry[sid]["lineage_id"],
            "messages": inbound,
            "message_ids": [m["message_id"] for m in inbound],
            "identity_protected": True,
            "message_count": len(inbound),
        }

    board = {
        "schema": "janus.demiurge.swarm_orchestrator_blackboard.v1",
        "mission_id": mission["mission_id"],
        "orchestrator": policy["orchestrator_id"],
        "identity_registry": registry,
        "identity_count": len(registry),
        "identity_collapses": 0,
        "facts": facts,
        "sources": sources,
        "observations": observations,
        "messages": messages,
        "query_coordination": query_claims,
        "inboxes": {sid: {"message_ids": box["message_ids"], "message_count": box["message_count"]} for sid, box in inboxes.items()},
        "laws": policy["laws"],
        "stats": {
            "report_count": len(reports),
            "fact_cluster_count": len(facts),
            "observation_count": len(observations),
            "source_cluster_count": len(sources),
            "message_count": len(messages),
        },
    }
    board["blackboard_sha256"] = canonical_hash(board)
    return {"blackboard": board, "inboxes": inboxes}


def write_coordination(reports_root: Path, output_dir: Path) -> Path:
    reports = load_reports(reports_root)
    bundle = build_coordination(reports)
    output_dir.mkdir(parents=True, exist_ok=True)
    inbox_dir = output_dir / "inboxes"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for sid, box in bundle["inboxes"].items():
        (inbox_dir / f"{sid}.json").write_text(json.dumps(box, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    board_path = output_dir / "BLACKBOARD.json"
    board_path.write_text(json.dumps(bundle["blackboard"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return board_path


def _reports_by_id(reports: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in reports:
        out.setdefault(str(r.get("scout_id")), []).append(r)
    return out


def finalize(round1_root: Path, round2_root: Path, bus_dir: Path, run_id: str, sha: str) -> Path:
    mission = load_mission()
    policy = load_policy()
    r1 = load_reports(round1_root)
    r2 = load_reports(round2_root)
    board = _read_json(bus_dir / "BLACKBOARD.json") or {}
    all_reports = [*r1, *r2]
    facts, sources, observations = cluster_reports(all_reports)
    by1, by2 = _reports_by_id(r1), _reports_by_id(r2)
    registry = identity_registry(mission)
    identity_rounds: Dict[str, Any] = {}
    response_messages: List[Dict[str, Any]] = []
    seq = len(board.get("messages", []))

    for sid in sorted(registry):
        one = (by1.get(sid) or [None])[0]
        two = (by2.get(sid) or [None])[0]
        r1_facts = {fact_key(x) for x in (one or {}).get("analysis", {}).get("findings", []) if isinstance(x, dict)}
        r2_facts = {fact_key(x) for x in (two or {}).get("analysis", {}).get("findings", []) if isinstance(x, dict)}
        new_facts = sorted(r2_facts - r1_facts)
        inbound = list((two or {}).get("peer_context", {}).get("inbound_message_ids", []))
        identity_rounds[sid] = {
            "lineage_id": registry[sid]["lineage_id"],
            "round1_present": one is not None,
            "round2_present": two is not None,
            "round1_report_sha256": canonical_hash({k:v for k,v in (one or {}).items() if not k.startswith("_")}) if one else None,
            "round2_report_sha256": canonical_hash({k:v for k,v in (two or {}).items() if not k.startswith("_")}) if two else None,
            "inbound_message_ids": inbound,
            "new_fact_ids_after_peer_round": new_facts,
            "identity_preserved": True,
        }
        if two and inbound:
            seq += 1
            response_messages.append(_message(sid, ["JANUS_ORCHESTRATOR"], "PEER_ROUND_RESPONSE", str(two.get("track") or ""), {
                "in_reply_to": inbound,
                "new_fact_ids": new_facts,
                "new_source_urls": sorted({str(s.get("final_url") or s.get("url") or "") for s in two.get("discovery", {}).get("sources", []) if isinstance(s, dict) and str(s.get("final_url") or s.get("url") or "")}),
            }, seq))

    outdir = ROOT / "scout_swarm" / "orchestrator" / "outbox" / mission["mission_id"] / str(run_id)
    outdir.mkdir(parents=True, exist_ok=True)
    final = {
        "schema": "janus.demiurge.swarm_orchestrator_result.v1",
        "mission_id": mission["mission_id"],
        "run_id": str(run_id),
        "controller_sha": str(sha),
        "status": "COMPLETE" if len(by1) == 17 and len(by2) == 17 else "PARTIAL",
        "orchestrator": policy["orchestrator_id"],
        "identity_count": len(registry),
        "identity_collapses": 0,
        "round1_scouts": len(by1),
        "round2_scouts": len(by2),
        "identity_rounds": identity_rounds,
        "fact_clusters": facts,
        "source_clusters": sources,
        "observations": observations,
        "message_log": [*(board.get("messages") or []), *response_messages],
        "query_coordination": board.get("query_coordination", {}),
        "laws": policy["laws"],
        "stats": {
            "fact_cluster_count": len(facts),
            "observation_count": len(observations),
            "source_cluster_count": len(sources),
            "message_count": len(board.get("messages") or []) + len(response_messages),
            "round2_new_fact_observations": sum(len(x["new_fact_ids_after_peer_round"]) for x in identity_rounds.values()),
        },
    }
    final["result_sha256"] = canonical_hash(final)
    result_path = outdir / "ORCHESTRATOR_RESULT.json"
    result_path.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    agent_dir = outdir / "agents"
    for sid in sorted(registry):
        dst = agent_dir / sid
        dst.mkdir(parents=True, exist_ok=True)
        for round_name, report in (("round1", (by1.get(sid) or [None])[0]), ("round2", (by2.get(sid) or [None])[0])):
            if report:
                clean = {k: v for k, v in report.items() if not k.startswith("_")}
                (dst / f"{round_name}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if board:
        (outdir / "BLACKBOARD_ROUND1.json").write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    src_inboxes = bus_dir / "inboxes"
    if src_inboxes.exists():
        dst_inboxes = outdir / "inboxes"
        dst_inboxes.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_inboxes.glob("*.json")):
            obj = _read_json(src)
            if obj:
                (dst_inboxes / src.name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state_dir = ROOT / "scout_swarm" / "orchestrator" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{mission['mission_id']}.json"
    old = _read_json(state_path) or {}
    history = list(old.get("history", [])) if isinstance(old.get("history"), list) else []
    history.append({
        "run_id": str(run_id),
        "controller_sha": str(sha),
        "status": final["status"],
        "identity_count": len(registry),
        "identity_collapses": 0,
        "message_count": final["stats"]["message_count"],
        "result_sha256": final["result_sha256"],
    })
    state = {
        "schema": "janus.demiurge.swarm_orchestrator_state.v1",
        "mission_id": mission["mission_id"],
        "orchestrator": policy["orchestrator_id"],
        "latest": history[-1],
        "history": history,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result_path


def self_test() -> None:
    policy = load_policy()
    mission = load_mission()
    registry = identity_registry(mission)
    assert len(registry) == 17
    assert all(v["identity_protected"] and not v["deduplication_allowed"] for v in registry.values())
    a, b = mission["agents"][0], mission["agents"][1]
    same = {"fact_id":"SAME_FACT", "claim":"same", "status":"FOUND", "source_urls":["https://example.test/x"]}
    reports = [
        {"mission_id":mission["mission_id"], "scout_id":a["id"], "track":a["track"], "discovery":{"sources":[]}, "analysis":{"findings":[same], "next_checks":["q1"], "gaps":[]}},
        {"mission_id":mission["mission_id"], "scout_id":b["id"], "track":b["track"], "discovery":{"sources":[]}, "analysis":{"findings":[same], "next_checks":["q2"], "gaps":[]}},
    ]
    facts, _, observations = cluster_reports(reports)
    assert len(facts) == 1
    assert len(observations) == 2
    assert {o["scout_id"] for o in observations} == {a["id"], b["id"]}
    bundle = build_coordination(reports)
    assert bundle["blackboard"]["identity_count"] == 17
    assert bundle["blackboard"]["identity_collapses"] == 0
    assert all(m["append_only"] and not m["deletable"] for m in bundle["blackboard"]["messages"])
    assert "FACTS_MAY_CLUSTER__SCOUTS_MUST_NOT" in policy["laws"]
    print("JANUS_SWARM_ORCHESTRATOR_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build-round")
    p.add_argument("--output-dir")
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--round1")
    p.add_argument("--round2")
    p.add_argument("--bus-dir")
    p.add_argument("--run-id")
    p.add_argument("--sha")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test(); return 0
    if args.build_round:
        if not args.output_dir: p.error("--output-dir required")
        print(write_coordination(Path(args.build_round), Path(args.output_dir))); return 0
    if args.finalize:
        if not all([args.round1, args.round2, args.bus_dir, args.run_id, args.sha]): p.error("finalize requires --round1 --round2 --bus-dir --run-id --sha")
        print(finalize(Path(args.round1), Path(args.round2), Path(args.bus_dir), args.run_id, args.sha)); return 0
    p.error("choose --build-round, --finalize or --self-test")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
