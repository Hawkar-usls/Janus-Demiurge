"""Trusted read-only historical organ graph adapter for JANUS Demiurge.

Converts the archival 74-node registry projection to a valid graph by excluding
relations with unresolved endpoints. Feeds the existing modern graph-query
organ without importing any historical module or writing HRAiN state.
"""
from __future__ import annotations

import copy
import re
from restored.memory_graph_query import shortest_path

SOURCE_SCHEMA = "janus.legacy_core.module_relationships_non_authoritative.v1"
MAX_NODES = 512
MAX_EDGES = 2048
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$")


class GraphProjectionHold(ValueError):
    pass


def project_readonly_legacy_graph(artifact: dict) -> dict:
    if not isinstance(artifact, dict) or artifact.get("schema") != SOURCE_SCHEMA:
        raise GraphProjectionHold("LEGACY_REGISTRY_SCHEMA_HOLD")
    if artifact.get("status") != "ARCHIVAL_RELATIONSHIP_PROJECTION_ONLY":
        raise GraphProjectionHold("UNTRUSTED_SOURCE_AUTHORITY_HOLD")
    spec = artifact.get("projection")
    if not isinstance(spec, dict):
        raise GraphProjectionHold("PROJECTION_MISSING_HOLD")
    nodes, relations = spec.get("nodes"), spec.get("historical_relations")
    if (not isinstance(nodes, list) or not isinstance(relations, list)
            or len(nodes) > MAX_NODES or len(relations) > MAX_EDGES):
        raise GraphProjectionHold("PROJECTION_BOUNDS_HOLD")
    graph_nodes = []
    seen = set()
    for row in nodes:
        if not isinstance(row, dict):
            raise GraphProjectionHold("INVALID_NODE_HOLD")
        name, kind = row.get("id"), row.get("kind")
        if not isinstance(name, str) or not SAFE_ID.fullmatch(name) or name in seen:
            raise GraphProjectionHold("NODE_ID_OR_DUPLICATE_HOLD")
        if not isinstance(kind, str) or not SAFE_ID.fullmatch(kind):
            raise GraphProjectionHold("NODE_KIND_HOLD")
        seen.add(name)
        graph_nodes.append({"id": name, "kind": kind, "archive_only": True})
    edges = []
    excluded = 0
    for row in relations:
        if not isinstance(row, dict):
            raise GraphProjectionHold("INVALID_RELATION_HOLD")
        src, dst, rel = row.get("from"), row.get("to"), row.get("historical_relation")
        if not all(isinstance(n, str) and SAFE_ID.fullmatch(n) for n in (src,dst,rel)):
            raise GraphProjectionHold("RELATION_ID_HOLD")
        present = src in seen and dst in seen
        if row.get("endpoints_declared_in_legacy_nodes") is not present:
            raise GraphProjectionHold("DECLARED_ENDPOINT_FLAG_MISMATCH")
        if present:
            edges.append({"source": src, "target": dst, "relation": rel})
        else:
            excluded += 1
    if (spec.get("node_count") != len(nodes)
            or spec.get("relation_count") != len(relations)
            or spec.get("relations_with_unresolved_endpoint") != excluded
            or spec.get("relations_with_both_endpoints_declared") != len(edges)):
        raise GraphProjectionHold("SOURCE_COUNT_CONTRACT_HOLD")
    return {
        "nodes": sorted(graph_nodes, key=lambda r:r["id"]),
        "edges": sorted(edges,key=lambda r:(r["source"],r["target"],r["relation"])),
        "read_only": True,
        "excluded_unresolved_relations": excluded,
        "raw_relation_count": len(relations),
        "scientific_authority": False,
    }


class LegacyGraphQueryPort:
    """An explicitly supplied, detached snapshot plus bounded query coordinates."""
    __slots__ = ("_graph", "_start", "_end", "_receipt")

    def __init__(self, archival_projection: dict, start_id: str, end_id: str):
        self._graph = project_readonly_legacy_graph(copy.deepcopy(archival_projection))
        if start_id not in {n["id"] for n in self._graph["nodes"]}:
            raise GraphProjectionHold("QUERY_START_NOT_A_DECLARED_NODE")
        if end_id not in {n["id"] for n in self._graph["nodes"]}:
            raise GraphProjectionHold("QUERY_END_NOT_A_DECLARED_NODE")
        self._start = start_id
        self._end = end_id
        self._receipt = None

    @property
    def receipt(self):
        return copy.deepcopy(self._receipt)


async def run_legacy_graph_query(core_port):
    """Modern trusted async run(core_port) organ for Nexus probation.

    No await on external services; no filesystem or network, writes only its
    caller-owned isolated port. The existing memory_graph_query does the work.
    """
    if type(core_port) is not LegacyGraphQueryPort:
        raise GraphProjectionHold("TRUSTED_GRAPH_PORT_REQUIRED")
    result = shortest_path(core_port._graph, core_port._start, core_port._end, max_edges=8)
    core_port._receipt = {
        "schema": "janus.demiurge.legacy_graph_query_evidence.v1",
        "status": "READ_ONLY_PATH_IN_ARCHIVAL_GRAPH",
        "found": result["found"],
        "path": list(result["path"]),
        "excluded_unresolved_relations": core_port._graph["excluded_unresolved_relations"],
        "source_archive_only": True,
        "scientific_authority": False,
        "mutation_authority": False,
    }
