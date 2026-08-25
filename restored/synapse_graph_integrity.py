from __future__ import annotations
import hashlib, json
from collections import deque
from typing import Any

SCHEMA = "janus.synapse.graph_integrity.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _endpoint(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("id", "")
    return str(value or "").strip()


def analyze(graph: dict[str, Any], *, core_id: str = "CORE") -> dict[str, Any]:
    nodes = list(graph.get("nodes", []) or [])
    links = list(graph.get("links", graph.get("edges", [])) or [])
    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    ids: list[str] = []
    seen_ids: set[str] = set()
    for idx, node in enumerate(nodes):
        node_id = _endpoint(node)
        if not node_id:
            findings.append({"kind": "NODE_WITHOUT_ID", "index": idx})
            continue
        ids.append(node_id)
        if node_id in seen_ids:
            findings.append({"kind": "DUPLICATE_NODE_ID", "node_id": node_id})
        else:
            seen_ids.add(node_id)

    if core_id not in seen_ids:
        findings.append({"kind": "MISSING_CORE", "core_id": core_id})
        proposals.append({"kind": "ADD_CORE_NODE", "node": {"id": core_id, "label": "JANUS CORE"}})

    adjacency: dict[str, set[str]] = {node_id: set() for node_id in seen_ids}
    undirected_seen: set[tuple[str, str]] = set()
    for idx, link in enumerate(links):
        if not isinstance(link, dict):
            findings.append({"kind": "INVALID_LINK_RECORD", "index": idx})
            continue
        source = _endpoint(link.get("source"))
        target = _endpoint(link.get("target"))
        if not source or not target:
            findings.append({"kind": "LINK_WITHOUT_ENDPOINT", "index": idx})
            continue
        missing = [x for x in (source, target) if x not in seen_ids]
        if missing:
            findings.append({"kind": "LINK_TO_MISSING_NODE", "index": idx, "missing": missing, "source": source, "target": target})
            continue
        if source == target:
            findings.append({"kind": "SELF_LOOP", "index": idx, "node_id": source})
        key = tuple(sorted((source, target)))
        if key in undirected_seen:
            findings.append({"kind": "DUPLICATE_UNDIRECTED_LINK", "index": idx, "source": source, "target": target})
        else:
            undirected_seen.add(key)
        adjacency[source].add(target)
        adjacency[target].add(source)

    reachable: set[str] = set()
    if core_id in adjacency:
        q = deque([core_id]); reachable.add(core_id)
        while q:
            cur = q.popleft()
            for nxt in sorted(adjacency[cur]):
                if nxt not in reachable:
                    reachable.add(nxt); q.append(nxt)

    unreachable = sorted(seen_ids - reachable) if core_id in seen_ids else sorted(seen_ids)
    for node_id in unreachable:
        findings.append({"kind": "UNREACHABLE_FROM_CORE", "node_id": node_id})
        if core_id in seen_ids:
            proposals.append({"kind": "CONNECT_COMPONENT_TO_CORE", "source": core_id, "target": node_id, "reason": "proposal_only"})

    direct_core_neighbors = sorted(adjacency.get(core_id, set()))
    identity = {
        "core_id": core_id,
        "node_ids": sorted(seen_ids),
        "links": sorted([list(x) for x in undirected_seen]),
        "findings": findings,
        "proposals": proposals,
    }
    return {
        "schema": SCHEMA,
        "status": "CLEAN" if not findings else "REPAIR_PROPOSAL",
        "core_id": core_id,
        "node_count": len(nodes),
        "unique_node_count": len(seen_ids),
        "link_count": len(links),
        "reachable_from_core": sorted(reachable),
        "unreachable_from_core": unreachable,
        "direct_core_neighbors": direct_core_neighbors,
        "findings": findings,
        "repair_proposals": proposals,
        "analysis_sha256": hashlib.sha256(_canon(identity)).hexdigest(),
        "authority": {"mutates_graph": False, "saves_graph": False, "starts_loop": False},
        "laws": [
            "GRAPH_REACHABILITY_NE_DIRECT_STAR_TOPOLOGY",
            "INTEGRITY_ANALYSIS_NE_AUTOMATIC_REPAIR",
            "REGISTRY_ACTIVE_NE_EXECUTABLE_PROOF"
        ]
    }
