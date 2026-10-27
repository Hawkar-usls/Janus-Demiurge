"""Verify authoritative HRAiN graph cannot be wholesale overwritten from UI."""
from __future__ import annotations

import ast
import asyncio
import copy
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def inspect_handler(path: pathlib.Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    handler = next((n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "handle_save_state"), None)
    if handler is None:
        raise AssertionError("HRAIN_SAVE_HANDLER_MISSING")
    calls = {n.func.attr for n in ast.walk(handler)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    written = {
        ast.unparse(target) for node in ast.walk(handler)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
    }
    return source, handler, calls, written


class _FakeWeb:
    @staticmethod
    def json_response(data, *, status):
        return {"payload": data, "http_status": status}


class LegacyFullSaveFirewall(unittest.TestCase):
    def test_no_authoritative_graph_write_in_handler(self):
        _, h, calls, targets = inspect_handler(ROOT / "server.py")
        self.assertFalse(any("graph_engine." in x for x in targets))
        self.assertFalse({"replace", "persist_state", "load_full_state",
                          "add_node", "add_edge", "json"} & calls)
        self.assertFalse(any("graph_engine" in ast.unparse(node) for node in h.body))

    def test_handler_rejects_post_without_reading_body(self):
        _, handler, _, _ = inspect_handler(ROOT / "server.py")
        unit = ast.fix_missing_locations(ast.Module(body=[handler], type_ignores=[]))
        fake_global = {"web": _FakeWeb()}
        exec(compile(unit, "<synthetic-extracted-handler>", "exec"), fake_global)
        class Request:
            async def json(self):
                raise AssertionError("REQUEST_BODY_MUST_NOT_BE_READ")
        result = asyncio.run(fake_global["handle_save_state"](Request()))
        self.assertEqual(result["http_status"], 409)
        self.assertEqual(result["payload"]["status"], "HOLD_LEGACY_GRAPH_REPLACEMENT")
        self.assertFalse(result["payload"]["source_graph_modified"])

    def test_historical_get_state_path_is_preserved(self):
        source, _, _, _ = inspect_handler(ROOT / "server.py")
        self.assertIn("async def handle_get_state(", source)
        self.assertIn("'/api/hrain/state'", source)
        self.assertIn("'/api/hrain/save'", source)
        self.assertIn("async def handle_janus_action(", source)

    def test_full_save_cannot_be_bypassed_by_env_or_config(self):
        _, h, _, _ = inspect_handler(ROOT / "server.py")
        rendered = ast.unparse(h)
        self.assertNotIn("os.environ", rendered)
        self.assertNotIn("config", rendered)
        self.assertNotIn("request.json", rendered)
        self.assertNotIn("get_full_state", rendered)
        self.assertNotIn("load_full_state", rendered)

if __name__ == "__main__":
    unittest.main()
