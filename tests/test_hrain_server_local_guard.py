"""Synthetic v78 HRAiN API access boundary; never import live server."""
from __future__ import annotations
import ast
import asyncio
import hmac
import os
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]


class WebStub:
    @staticmethod
    def middleware(fn):
        return fn

    @staticmethod
    def json_response(body, *, status):
        return {"status": status, "body": body}


class RequestStub:
    def __init__(self, *, host="localhost:1138", remote="127.0.0.1",
                 path="/api/hrain/state", token=None, origin=None):
        self.path = path
        self.remote = remote
        self.headers = {"Host": host}
        if token is not None:
            self.headers["X-JANUS-Local-Token"] = token
        if origin is not None:
            self.headers["Origin"] = origin


def middleware():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "janus_local_access_guard"]
    if len(functions) != 1:
        raise AssertionError("HRAIN_LOCAL_ACCESS_GUARD_MISSING")
    copied = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    local = {"web": WebStub, "os": os, "hmac": hmac, "HRAIN_SERVER_PORT": 1138}
    exec(compile(copied, "<synthetic-guard>", "exec"), local)
    return local["janus_local_access_guard"]


async def harmless(_request):
    return {"status": 200, "body": {"status": "synthetic_read_only"}}


class LoopbackProtection(TestCase):
    good = "synthetic-local-test-token-value-1234567"

    def call(self, **overrides):
        request = RequestStub(**overrides)
        return asyncio.run(middleware()(request, harmless))

    def test_valid_token_allows_local_api(self):
        with mock.patch.dict(os.environ, {"JANUS_HRAIN_LOCAL_API_TOKEN": self.good}):
            response = self.call(token=self.good, origin="http://localhost:1138")
        self.assertEqual(response["status"], 200)

    def test_no_token_fails_closed_for_get_and_ws(self):
        with mock.patch.dict(os.environ, {"JANUS_HRAIN_LOCAL_API_TOKEN": self.good}):
            for path in ("/api/hrain/state", "/api/device/command/dev", "/ws"):
                with self.subTest(path=path):
                    self.assertEqual(self.call(path=path)["status"], 403)

    def test_empty_or_short_config_token_does_not_authorize_access(self):
        for token in ("", "test", "a" * 23):
            with self.subTest(token_length=len(token)):
                with mock.patch.dict(os.environ, {"JANUS_HRAIN_LOCAL_API_TOKEN": token}):
                    self.assertEqual(self.call(token=token)["status"], 403)

    def test_rejects_lan_and_host_header_spoofing(self):
        with mock.patch.dict(os.environ, {"JANUS_HRAIN_LOCAL_API_TOKEN": self.good}):
            for opts in (
                {"host": "evil.invalid:1138"},
                {"host": "192.0.2.1:1138"},
                {"remote": "192.0.2.50"},
                {"remote": "unknown"},
                {"origin": "https://evil.invalid"},
            ):
                with self.subTest(opts=opts):
                    self.assertEqual(self.call(token=self.good, **opts)["status"], 403)

    def test_safe_loopback_health_ping_remains_available(self):
        with mock.patch.dict(os.environ, {"JANUS_HRAIN_LOCAL_API_TOKEN": ""}):
            self.assertEqual(self.call(path="/", token=None)["status"], 200)
            self.assertEqual(self.call(path="/ping", token=None)["status"], 200)

    def test_server_actually_binds_loopback_and_registers_guard(self):
        tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "TCPSite"]
        self.assertEqual(len(calls), 1)
        self.assertIn("HRAIN_LOCAL_BIND_HOST", ast.unparse(calls[0]))
        self.assertNotIn("'0.0.0.0'", ast.unparse(calls[0]))
        self.assertIn("janus_local_access_guard", ast.unparse(tree))

if __name__ == "__main__":
    import unittest
    unittest.main()
