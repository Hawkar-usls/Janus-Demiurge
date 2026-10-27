"""HRAiN power-loss recovery contract: never overwrite unreadable graph data."""
from __future__ import annotations
import ast
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.calls = 0

    def load_full_state(self, state):
        self.calls += 1
        self.nodes = state['nodes']
        self.edges = state['edges']


class Log:
    def critical(self, *args):
        pass

    def info(self, *args):
        pass


def isolated_loader(state_path, graph):
    tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
    handlers = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "load_graph_state"]
    if len(handlers) != 1:
        raise AssertionError("MISSING_SAFE_BOOT_LOADER")
    module = ast.fix_missing_locations(ast.Module(body=handlers, type_ignores=[]))
    namespace = dict(os=os, json=json, logger=Log(), graph_engine=graph,
                     HRAIN_STATE_FILE=str(state_path))
    exec(compile(module, "<synthetic-safe-loader>", "exec"), namespace)
    return namespace["load_graph_state"]


class NonDestructiveBoot(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.snapshot = Path(self.temp.name) / "hrain_graph_state.json"
        self.graph = Graph()

    def boot(self):
        return asyncio.run(isolated_loader(self.snapshot, self.graph)())

    def test_missing_file_allows_first_start_without_writes(self):
        self.assertFalse(self.boot())
        self.assertFalse(self.snapshot.exists())
        self.assertEqual(self.graph.calls, 0)

    def test_valid_state_loads_once(self):
        state = {"nodes": {"a": {"id": "a", "data": {}}},
                 "edges": {"a->a": {"weight": 0.5}},
                 "tick": 4, "node_counter": 2}
        self.snapshot.write_text(json.dumps(state), encoding="utf-8")
        self.assertTrue(self.boot())
        self.assertEqual(self.graph.nodes, state["nodes"])
        self.assertEqual(self.graph.edges, state["edges"])
        self.assertEqual(self.graph.calls, 1)

    def test_truncated_empty_and_partial_json_hold_exact_bytes(self):
        for bad in (b"", b"{", b"{}",
                    b'{"nodes":{},"edges":{},"tick":1}',
                    b'{"nodes":[],"edges":{},"tick":1,"node_counter":1}',
                    b'{"nodes":{},"edges":{},"tick":true,"node_counter":1}',
                    b'{"nodes":{},"edges":{},"tick":NaN,"node_counter":1}'):
            with self.subTest(payload=bad[:24]):
                self.snapshot.write_bytes(bad)
                before = self.snapshot.read_bytes()
                self.graph = Graph()
                with self.assertRaisesRegex(RuntimeError, "HRAIN_STATE_CORRUPT_BOOT_HOLD"):
                    self.boot()
                self.assertEqual(self.snapshot.read_bytes(), before)
                self.assertEqual(self.graph.calls, 0)

    def test_oversized_source_stays_untouched(self):
        with self.snapshot.open("wb") as out:
            out.seek(32_000_000)
            out.write(b"x")
        initial_size = self.snapshot.stat().st_size
        with self.assertRaisesRegex(RuntimeError, "HRAIN_STATE_CORRUPT_BOOT_HOLD"):
            self.boot()
        self.assertEqual(self.snapshot.stat().st_size, initial_size)
        self.assertEqual(self.graph.calls, 0)

    def test_startup_does_not_schedule_writer_before_restore(self):
        source = (ROOT / "server.py").read_text(encoding="utf-8")
        start = source.index("async def run_server():")
        pos_read = source.index("await load_graph_state()", start)
        pos_write = source.index("asyncio.create_task(save_graph_state())", start)
        self.assertLess(pos_read, pos_write)

if __name__ == "__main__":
    unittest.main()
