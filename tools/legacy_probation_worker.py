#!/usr/bin/env python3
"""One-shot JANUS subprocess worker; only the pinned modern graph-query organ.

This is process separation, NOT an OS sandbox: do not supply untrusted code.
It reads a single bounded JSON request on stdin and writes one receipt on stdout.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import sys

SCHEMA = "janus.demiurge.legacy_subprocess_request.v1"
RECEIPT_SCHEMA = "janus.demiurge.legacy_subprocess_receipt.v1"
ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = {
    "nexus": "restored/legacy_nexus_conductor.py",
    "graph_port": "restored/legacy_core_graph_query_port.py",
    "graph_query": "restored/memory_graph_query.py",
    "worker": "tools/legacy_probation_worker.py",
}


def refuse(reason: str) -> None:
    print(json.dumps({"schema": RECEIPT_SCHEMA, "status": "HOLD", "reason": reason},
                     sort_keys=True), flush=True)


def _verify_hashes(expected: object) -> bool:
    if not isinstance(expected, dict) or set(expected) != set(FILES):
        return False
    for key, rel in FILES.items():
        name = expected[key]
        if not isinstance(name, str) or len(name) != 64 or any(c not in "0123456789abcdef" for c in name):
            return False
        path = ROOT / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 120000:
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != name:
            return False
    return True


async def _execute(request: dict) -> dict:
    if set(request) != {"schema", "target", "graph", "start_id", "end_id", "file_sha256", "artifact_sha256"}:
        raise ValueError("REQUEST_FIELDS_HOLD")
    if request["schema"] != SCHEMA or request["target"] != "legacy_graph_query":
        raise ValueError("REQUEST_SCHEMA_OR_TARGET_HOLD")
    if not _verify_hashes(request["file_sha256"]):
        raise ValueError("PINNED_CODE_SHA_MISMATCH")
    graph = request["graph"]
    if not isinstance(graph, dict):
        raise ValueError("GRAPH_OBJECT_HOLD")
    # The historical artifact is DATA, not an executable task specification.
    # Accept only the known Meta Registry archival projection fields.
    if not set(graph).issubset({
        "artifact_id", "schema", "status", "source", "projection",
        "interpretation", "security", "links"
    }):
        raise ValueError("GRAPH_TOP_LEVEL_FIELDS_HOLD")
    projection = graph.get("projection")
    if not isinstance(projection, dict) or set(projection) != {
        "node_count", "relation_count", "relations_with_both_endpoints_declared",
        "relations_with_unresolved_endpoint", "nodes", "historical_relations"
    }:
        raise ValueError("GRAPH_PROJECTION_FIELDS_HOLD")
    if not isinstance(projection["nodes"], list) or not isinstance(projection["historical_relations"], list):
        raise ValueError("GRAPH_LIST_FIELDS_HOLD")
    for node in projection["nodes"]:
        if not isinstance(node, dict) or set(node) != {"id", "kind"}:
            raise ValueError("GRAPH_NODE_FIELDS_HOLD")
    for edge in projection["historical_relations"]:
        if not isinstance(edge, dict) or set(edge) != {
            "from", "to", "historical_relation", "endpoints_declared_in_legacy_nodes"
        }:
            raise ValueError("GRAPH_EDGE_FIELDS_HOLD")
    identity = json.dumps(graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(identity) > 300000 or hashlib.sha256(identity).hexdigest() != request["artifact_sha256"]:
        raise ValueError("ARCHIVE_GRAPH_SHA_HOLD")
    sys.path.insert(0, str(ROOT))
    # These are fixed, Git-reviewed modern organ imports. Never import a legacy
    # filename, Python module path, pickle or user-generated source from stdin.
    from restored.legacy_nexus_conductor import build_plan, probation_run
    from restored.legacy_core_graph_query_port import LegacyGraphQueryPort, run_legacy_graph_query

    plan = build_plan([{
        "id": "legacy_graph_query", "mode": "PLUGIN",
        "source_sha256": request["file_sha256"]["graph_port"],
        "priority": 1, "dependencies": [], "capabilities": ["READ_GRAPH"],
        "reviewed": True, "synthetic_only": True,
    }], intent="read-only legacy graph")
    if plan["status"] != "PLAN_ONLY":
        raise ValueError("NEXUS_PLAN_HOLD")
    port = LegacyGraphQueryPort(graph, request["start_id"], request["end_id"])
    result = await probation_run(plan, target="legacy_graph_query",
                                handlers={"legacy_graph_query": run_legacy_graph_query},
                                core_port=port, operator_approved=True,
                                timeout_seconds=1.5)
    if result["outcomes"]["legacy_graph_query"] != "PROBATION_CALLBACK_COMPLETED":
        raise ValueError("MODERN_GRAPH_CALLBACK_HOLD")
    return {
        "schema": RECEIPT_SCHEMA, "status": "PASS_PROCESS_SEPARATED_SYNTHETIC_PROBATION",
        "source_plan_sha256": plan["plan_sha256"],
        "archive_artifact_sha256": request["artifact_sha256"],
        "organ_receipt": port.receipt,
        "authority": {
            "production_activation": False, "model_promoted": False,
            "graph_mutation": False, "legacy_source_executed": False,
            "os_security_sandbox_proven": False, "network_namespace_isolated": False,
        },
    }


def main() -> None:
    try:
        data = sys.stdin.buffer.read(300001)
        if not data or len(data) > 300000:
            refuse("INPUT_BOUND_HOLD")
            return
        try:
            request = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            refuse("REQUEST_JSON_HOLD")
            return
        if not isinstance(request, dict):
            refuse("REQUEST_OBJECT_HOLD")
            return
        try:
            result = asyncio.run(_execute(request))
        except (ValueError, KeyError, TypeError, AttributeError):
            refuse("VALIDATION_OR_PROBATION_HOLD")
            return
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    except Exception:
        # Never disclose the contents of private graph or unexpected stack traces.
        refuse("WORKER_INTERNAL_HOLD")


if __name__ == "__main__":
    main()
