from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any

SCHEMA = "janus.memory_graph.query.v1"
HISTORICAL_SOURCE_SHA256 = "d82e290efffa38deee103705756e315cffc587bc4f9c6a3c2ae35467a3a7dbb3"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _snapshot(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, list[str]], list[dict[str, Any]]]:
    if not isinstance(graph, dict):
        raise ValueError("graph must be a mapping")
    nodes: dict[str, dict[str, Any]] = {}
    for raw in graph.get("nodes", []):
        if not isinstance(raw, dict) or "id" not in raw:
            raise ValueError("each node must be a mapping with id")
        nid = str(raw["id"])
        if nid in nodes:
            raise ValueError(f"duplicate node id: {nid}")
        nodes[nid] = dict(raw)

    outgoing = {nid: [] for nid in nodes}
    incoming = {nid: [] for nid in nodes}
    edges: list[dict[str, Any]] = []
    for raw in graph.get("edges", []):
        if not isinstance(raw, dict) or "source" not in raw or "target" not in raw:
            raise ValueError("each edge must contain source and target")
        s, t = str(raw["source"]), str(raw["target"])
        if s not in nodes or t not in nodes:
            raise ValueError(f"dangling edge: {s}->{t}")
        edge = {"source": s, "target": t, "weight": raw.get("weight", 1.0)}
        if "relation" in raw:
            edge["relation"] = raw["relation"]
        edges.append(edge)
        outgoing[s].append(t)
        incoming[t].append(s)

    for table in (outgoing, incoming):
        for nid in table:
            table[nid] = sorted(set(table[nid]))
    edges.sort(key=lambda e: (e["source"], e["target"], repr(e.get("weight")), repr(e.get("relation"))))
    return nodes, outgoing, incoming, edges


def shortest_path(graph: dict[str, Any], start_id: str, end_id: str, *, max_edges: int = 6) -> dict[str, Any]:
    if max_edges < 0:
        raise ValueError("max_edges must be non-negative")
    nodes, outgoing, _incoming, _edges = _snapshot(graph)
    start, end = str(start_id), str(end_id)
    path: list[str] = []
    if start in nodes and end in nodes:
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            current, current_path = queue.popleft()
            if current == end:
                path = current_path
                break
            if len(current_path) - 1 >= max_edges:
                continue
            for neighbor in outgoing.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_path + [neighbor]))

    body = {
        "schema": SCHEMA,
        "query": "SHORTEST_PATH",
        "start_id": start,
        "end_id": end,
        "max_edges": max_edges,
        "path": path,
        "found": bool(path),
        "historical_source_sha256": HISTORICAL_SOURCE_SHA256,
        "authority": {"mutates_graph": False, "loads_or_saves_graph": False, "declares_semantic_truth": False},
        "law": "PATH_EXISTS_IN_SNAPSHOT_NE_SEMANTIC_OR_CAUSAL_TRUTH",
    }
    body["receipt_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def related_subgraph(graph: dict[str, Any], center_id: str, *, depth: int = 2) -> dict[str, Any]:
    if depth < 0:
        raise ValueError("depth must be non-negative")
    nodes, outgoing, incoming, edges = _snapshot(graph)
    center = str(center_id)
    selected: set[str] = set()
    if center in nodes:
        selected = {center}
        frontier = {center}
        for _ in range(depth):
            nxt: set[str] = set()
            for nid in sorted(frontier):
                nxt.update(outgoing.get(nid, []))
                nxt.update(incoming.get(nid, []))
            nxt -= selected
            selected.update(nxt)
            frontier = nxt
            if not frontier:
                break

    sub_nodes = [nodes[nid] for nid in sorted(selected)]
    sub_edges = [e for e in edges if e["source"] in selected and e["target"] in selected]
    body = {
        "schema": SCHEMA,
        "query": "RELATED_SUBGRAPH",
        "center_id": center,
        "depth": depth,
        "found": center in nodes,
        "nodes": sub_nodes,
        "edges": sub_edges,
        "historical_source_sha256": HISTORICAL_SOURCE_SHA256,
        "authority": {"mutates_graph": False, "loads_or_saves_graph": False, "declares_semantic_truth": False},
        "laws": [
            "CONTEXT_NEIGHBORHOOD_NE_SEMANTIC_TRUTH",
            "QUERY_LAYER_NE_GRAPH_OWNERSHIP",
            "SECOND_MUTABLE_GRAPH_OWNER_FORBIDDEN_WITHOUT_EXPLICIT_OWNERSHIP_GATE",
        ],
    }
    body["receipt_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
