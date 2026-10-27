#!/usr/bin/env python3
"""Deterministic JANUS HRAiN endurance study; disposable synthetic graph ONLY.

Intentionally does not import user state, use network, access remote devices,
start daemons or auto-authorize live memory operations. A successful cycle
is not proof of process-restart or real-memory production readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hrain_graph_engine import HrainGraphEngine
from restored.hrain_autonomy import HrainAutonomy

SCHEMA = "janus.hrain.synthetic_autonomy_endurance.v1"


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def simulate(cycles: int = 300, seed: int = 1408, capacity: int = 80) -> dict:
    if not (60 <= cycles <= 1500 and 16 <= capacity <= 500
            and type(seed) is int and 0 <= seed < 2 ** 32):
        raise ValueError("SYNTHETIC_SIMULATION_INPUT_BOUNDS_HOLD")
    random.seed(seed)
    graph = HrainGraphEngine({
        "max_nodes": capacity,
        "edge_decay": 0.99,
        "energy_decay": 0.997,
        "node_energy_threshold": 0.01,
        "similarity_threshold": 2.0,
        "exploration_prob": 0.01,
        "energy_flow_rate": 0.005,
        "compression_interval": 7
    })
    autonomy = HrainAutonomy(graph, synthetic_only=True)
    autonomy.enable_synthetic_sandbox()
    before_nodes: set[str] = set()
    before_edge_directions: dict[str, str] = {}
    outcomes: dict[str, int] = {}
    verified_roundtrips = 0
    for index in range(cycles):
        view, event = autonomy.cycle_once()
        kind = event.get("kind", "UNKNOWN")
        outcomes[kind] = outcomes.get(kind, 0) + 1
        current_nodes = set(graph.nodes)
        current_edges = {key: edge.get("direction") for key, edge in graph.edges.items()}
        if not before_nodes.issubset(current_nodes):
            raise AssertionError("AUTONOMOUS_NODE_ERASURE_HOLD")
        if not set(before_edge_directions).issubset(current_edges):
            raise AssertionError("AUTONOMOUS_EDGE_ERASURE_HOLD")
        if any(current_edges[key] != direction for key, direction in before_edge_directions.items()):
            raise AssertionError("AUTONOMOUS_EDGE_DIRECTION_CHANGED_HOLD")
        if view["meta"]["graph_nodes"] != len(graph.nodes) or view["meta"]["graph_edges"] != len(graph.edges):
            raise AssertionError("AUTONOMOUS_STATE_VIEW_DIVERGENCE_HOLD")
        if len(graph.nodes) > capacity:
            raise AssertionError("AUTONOMOUS_CAPACITY_EXCEEDED_HOLD")
        if autonomy.runtime["nodes_pruned"] != 0:
            raise AssertionError("AUTONOMOUS_PRUNE_CLAIM_HOLD")
        before_nodes, before_edge_directions = current_nodes, current_edges
        if index and index % 50 == 0:
            snapshot = graph.get_full_state()
            raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False)
            copy = json.loads(raw)
            fresh = HrainGraphEngine(graph.config)
            fresh.load_full_state(copy)
            if fingerprint(fresh.get_full_state()) != fingerprint(snapshot):
                raise AssertionError("AUTONOMOUS_RESTORE_BYTE_SEMANTICS_HOLD")
            verified_roundtrips += 1
    if not outcomes.get("foundation") or not outcomes.get("growth"):
        raise AssertionError("AUTONOMOUS_GROWTH_NOT_EXERCISED_HOLD")
    if verified_roundtrips < 1:
        raise AssertionError("AUTONOMOUS_REPLAY_NOT_EXERCISED_HOLD")
    return {
        "schema": SCHEMA, "status": "PASS_SYNTHETIC_LONG_RUN",
        "seed": seed, "cycles": cycles, "capacity": capacity,
        "nodes": len(graph.nodes), "edges": len(graph.edges),
        "outcomes": outcomes, "roundtripChecks": verified_roundtrips,
        "nodeLosses": 0, "edgeLosses": 0,
        "privateGraphUsed": False,
        "realProcessRestartTested": False,
        "productionAutonomyAuthorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1408)
    parser.add_argument("--capacity", type=int, default=80)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = simulate(args.cycles, args.seed, args.capacity)
    encoded = json.dumps(result, sort_keys=True, ensure_ascii=True) + "\\n"
    if args.report:
        if args.report.is_symlink() or args.report.exists():
            raise FileExistsError("SYNTHETIC_REPORT_REFUSES_OVERWRITE")
        with args.report.open("x", encoding="utf-8") as out:
            out.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
