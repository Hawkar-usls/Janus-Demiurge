#!/usr/bin/env python3
"""Bounded *synthetic-only* HRAiN hard-process-crash/restart proof.

Never reads owner graph, NAS, or private archives. Three separate Python
processes write, crash before promote, and recover a disposable graph. This
tests process death, not production activation or owner-data recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hrain_graph_engine import HrainGraphEngine
from restored.hrain_autonomy import HrainAutonomy

SCHEMA = "janus.hrain.synthetic_process_crash_restart.v1"
CONFIG = {
    "max_nodes": 64, "edge_decay": 1.0, "energy_decay": 1.0,
    "energy_flow_rate": 0.0, "exploration_prob": 0.0,
    "similarity_threshold": 2.0, "node_energy_threshold": 0.0,
    "compression_interval": 7,
}


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def validate_graph(state: dict) -> None:
    if not isinstance(state, dict):
        raise ValueError("SYNTHETIC_NOT_OBJECT")
    nodes, edges = state.get("nodes"), state.get("edges")
    if (not isinstance(nodes, dict) or len(nodes) < 4 or len(nodes) > 64
            or not isinstance(edges, dict) or not isinstance(state.get("tick"), int)
            or not isinstance(state.get("node_counter"), int)):
        raise ValueError("SYNTHETIC_GRAPH_SHAPE_HOLD")
    for key, node in nodes.items():
        if not isinstance(key, str) or not isinstance(node, dict):
            raise ValueError("SYNTHETIC_NODE_INVALID")
    for key, edge in edges.items():
        if not isinstance(key, str) or "->" not in key or not isinstance(edge, dict):
            raise ValueError("SYNTHETIC_EDGE_INVALID")
        src, dest = key.split("->", 1)
        if src not in nodes or dest not in nodes:
            raise ValueError("SYNTHETIC_DANGLING_EDGE_HOLD")


def stage(mode: str, directory: Path) -> None:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("DISPOSABLE_TEMP_DIR_ONLY")
    checkpoint = directory / "graph.json"
    temp = directory / "graph.pending"
    if mode == "prepare":
        if checkpoint.exists() or temp.exists():
            raise FileExistsError("SYNTHETIC_CREATE_ONLY")
        random.seed(1408)
        graph = HrainGraphEngine(dict(CONFIG))
        autonomy = HrainAutonomy(graph, synthetic_only=True)
        autonomy.enable_synthetic_sandbox()
        for _ in range(12):
            autonomy.cycle_once()
        state = graph.get_full_state()
        validate_graph(state)
        content = canonical(state)
        with checkpoint.open("xb") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        return
    if mode == "crash":
        if not checkpoint.is_file() or temp.exists():
            raise ValueError("SYNTHETIC_INVALID_CRASH_PRECONDITION")
        # Torn write sits in a separate pending file; authoritative committed
        # file must be unaffected even when the process is killed ungracefully.
        with temp.open("xb") as fp:
            fp.write(b'{"nodes":{"truncated":')
            fp.flush()
            os.fsync(fp.fileno())
        os.kill(os.getpid(), signal.SIGKILL)
        raise AssertionError("UNREACHABLE_AFTER_SIGKILL")
    if mode == "restore":
        state = json.loads(checkpoint.read_bytes())
        validate_graph(state)
        fresh = HrainGraphEngine(dict(CONFIG))
        fresh.load_full_state(state)
        loaded = fresh.get_full_state()
        validate_graph(loaded)
        if canonical(loaded) != canonical(state):
            raise ValueError("HRAIN_CROSS_PROCESS_RESTORE_MISMATCH")
        print(json.dumps({
            "status": "SYNTHETIC_RESTART_RESTORED",
            "source_sha256": sha(canonical(loaded)),
            "nodes": len(loaded["nodes"]), "edges": len(loaded["edges"]),
        }))
        return
    raise ValueError("SYNTHETIC_STAGE_NOT_PERMITTED")


def run_gate() -> dict:
    if os.name != "posix" or not hasattr(signal, "SIGKILL"):
        raise RuntimeError("HRAIN_HARD_KILL_GATE_REQUIRES_POSIX")
    with tempfile.TemporaryDirectory(prefix="janus-hrain-synthetic-crash-") as td:
        directory = Path(td)
        base = [sys.executable, str(Path(__file__).resolve()), "--dir", td]
        preparation = subprocess.run([*base, "--stage", "prepare"],
                                     capture_output=True, text=True, timeout=20)
        if preparation.returncode != 0:
            raise RuntimeError("HRAIN_SYNTHETIC_PREPARE_FAILED")
        checkpoint = directory / "graph.json"
        original = checkpoint.read_bytes()
        digest = sha(original)
        old = json.loads(original)
        validate_graph(old)
        crash = subprocess.run([*base, "--stage", "crash"],
                               capture_output=True, text=True, timeout=20)
        if crash.returncode != -signal.SIGKILL:
            raise AssertionError("HRAIN_REAL_CHILD_SIGKILL_NOT_OBSERVED")
        if checkpoint.read_bytes() != original:
            raise AssertionError("HRAIN_AUTHORITATIVE_CHECKPOINT_CHANGED_AFTER_KILL")
        if not (directory / "graph.pending").is_file():
            raise AssertionError("HRAIN_TORN_WRITE_NOT_PRESENT")
        restored = subprocess.run([*base, "--stage", "restore"],
                                  capture_output=True, text=True, timeout=20)
        if restored.returncode != 0:
            raise AssertionError("HRAIN_FRESH_PROCESS_RESTORE_FAILED:" + restored.stderr[-300:])
        record = json.loads(restored.stdout.strip())
        if record["source_sha256"] != digest:
            raise AssertionError("HRAIN_RESTORED_GRAPH_DIGEST_MISMATCH")
        # A damaged authoritative checkpoint must be rejected, never
        # silently overwritten or treated as valid owner data.
        checkpoint.write_bytes(b'{"nodes":')
        rejected = subprocess.run([*base, "--stage", "restore"],
                                  capture_output=True, text=True, timeout=20)
        if rejected.returncode == 0:
            raise AssertionError("HRAIN_CORRUPT_RESTART_NOT_REJECTED")
        return {
            "schema": SCHEMA,
            "status": "PASS_SYNTHETIC_HARD_CRASH_RESTART",
            "source_sha256": digest,
            "nodes": record["nodes"], "edges": record["edges"],
            "hard_kill_observed": True,
            "torn_pending_file_isolated": True,
            "authoritative_state_unchanged_after_crash": True,
            "separate_process_restore_verified": True,
            "corrupt_authoritative_file_rejected": True,
            "private_graph_used": False,
            "production_autonomy_authorized": False,
            "real_owner_process_restart_tested": False,
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("prepare", "crash", "restore"))
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    if args.stage:
        if args.dir is None or args.report is not None:
            ap.error("stages require --dir only")
        stage(args.stage, args.dir)
    else:
        if args.dir is not None or args.report is None:
            ap.error("gate requires --report only")
        result = run_gate()
        with args.report.open("xb") as fp:
            fp.write(canonical(result) + b"\n")
        print(json.dumps({"status": result["status"],
                          "private_graph_used": False,
                          "real_owner_process_restart_tested": False}))


if __name__ == "__main__":
    main()
