#!/usr/bin/env python3
"""Cloud-runnable, read-only JANUS HRAiN autonomy safety gate.

Examines ONLY known public repo source files, never the owner's raw_logs,
credentials, NAS, private graph, or any connected service. The gate can
reject unsafe code; it never enables autonomy or merges changes.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

SCHEMA = "janus.hrain.unattended_integrity_gate.v1"
SOURCES = {
    "graph": "hrain_graph_engine.py",
    "server": "server.py",
    "autonomy": "restored/hrain_autonomy.py",
    "checkpoint": "tools/janus_hrain_private_checkpoint_ledger.py",
    "shadow": "tools/janus_hrain_lossless_shadow.py",
    "independent": "tools/janus_hrain_shadow_independent_verify.py",
}
MAX_SOURCE_BYTES = 120_000


def _class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    return next((x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == name), None)


def _method(cls: ast.ClassDef | None, name: str) -> ast.FunctionDef | None:
    if cls is None:
        return None
    return next((x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name), None)


def _calls(method: ast.AST | None) -> set[str]:
    if method is None:
        return set()
    return {
        x.func.attr if isinstance(x.func, ast.Attribute) else x.func.id
        for x in ast.walk(method) if isinstance(x, ast.Call)
        and isinstance(x.func, (ast.Attribute, ast.Name))
    }


def _mutates_graph(method: ast.AST | None, *, permit_growth: bool = False) -> bool:
    if method is None:
        return True
    prohibited = {"remove_node", "pop", "popitem", "clear", "setdefault"}
    if not permit_growth:
        prohibited.add("add_node")
    if prohibited & _calls(method):
        return True
    for node in ast.walk(method):
        if isinstance(node, (ast.Delete, ast.AugAssign)):
            if isinstance(node, ast.Delete):
                return True
            if any(_self_graph_target(target) for target in [node.target]):
                return True
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_self_graph_target(t) for t in targets):
                return True
    return False


def _self_graph_target(expr: ast.AST) -> bool:
    while isinstance(expr, (ast.Subscript, ast.Attribute)):
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == "self":
            return expr.attr in ("nodes", "edges", "clusters")
        expr = expr.value
    return False


def _returns_false(method: ast.AST | None) -> bool:
    return bool(method is not None and any(
        isinstance(x, ast.Return) and isinstance(x.value, ast.Constant) and x.value.value is False
        for x in ast.walk(method)
    ))


def _hold_strings(method: ast.AST | None, required: str) -> bool:
    return bool(method is not None and any(
        isinstance(x, ast.Constant) and isinstance(x.value, str) and required in x.value
        for x in ast.walk(method)
    ))


def _syntax(root: Path) -> dict[str, ast.Module]:
    trees = {}
    for name, rel in SOURCES.items():
        path = root / rel
        if path.is_symlink() or not path.is_file() or not (1 <= path.stat().st_size <= MAX_SOURCE_BYTES):
            raise ValueError("SAFE_GATE_SOURCE_MISSING_OR_UNSAFE")
        trees[name] = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    return trees


def assess(root: Path) -> dict:
    root = Path(root).resolve()
    trees = _syntax(root)
    graph = _class(trees["graph"], "HrainGraphEngine")
    server = trees["server"]
    autonomy = _class(trees["autonomy"], "HrainAutonomy")
    checks = {}
    save_handlers = [
        n for n in server.body if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "handle_save_state"
    ]
    save_endpoint = save_handlers[0] if len(save_handlers) == 1 else None
    if save_endpoint is None:
        checks["server_wholesale_save_hold"] = False
    else:
        # Exactly one return without parsing request, graph accesses, awaits,
        # persistence, or any other statements. Protect against guard bypass
        # via hidden branch or untrusted flags.
        server_response = ast.unparse(save_endpoint.body[1:]) if len(save_endpoint.body) > 1 else ""
        handler_dump = ast.dump(save_endpoint, include_attributes=False)
        checks["server_wholesale_save_hold"] = (
            len(save_endpoint.body) == 2
            and isinstance(save_endpoint.body[0], ast.Expr)
            and isinstance(save_endpoint.body[0].value, ast.Constant)
            and isinstance(save_endpoint.body[-1], ast.Return)
            and "HOLD_LEGACY_GRAPH_REPLACEMENT" in handler_dump
            and "409" in handler_dump
            and "json_response" in server_response
            and "graph_engine" not in handler_dump
            and "persist_state" not in handler_dump
            and "request.json" not in server_response
        )
    routes = [
        (n.func.attr, n.args)
        for n in ast.walk(server)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "web"
        and n.func.attr in ("get", "post")
        and len(n.args) >= 2
    ]
    def _route_for(verb: str, url: str, handler: str) -> bool:
        return sum(
            method == verb and isinstance(args[0], ast.Constant)
            and args[0].value == url
            and isinstance(args[1], ast.Name) and args[1].id == handler
            for method, args in routes
        ) == 1
    checks["server_ui_read_route_retained"] = (
        _route_for("get", "/api/hrain/state", "handle_get_state")
        and _route_for("post", "/api/hrain/save", "handle_save_state")
        and sum(
            method == "post" and isinstance(args[0], ast.Constant)
            and args[0].value == "/api/hrain/save"
            for method, args in routes
        ) == 1
    )
    # Reject a future network/public exposure of the historical server,
    # including a change that removes the token check while leaving the UI
    # full-write HOLD in place.
    guard_defs = [
        n for n in server.body if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "janus_local_access_guard"
    ]
    guard = guard_defs[0] if len(guard_defs) == 1 else None
    guard_ast = ast.unparse(guard) if guard else ""
    binds = [
        n.value for n in server.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "HRAIN_LOCAL_BIND_HOST" for t in n.targets)
    ]
    loopback_binding = (
        len(binds) == 1 and isinstance(binds[0], ast.Constant)
        and binds[0].value == "127.0.0.1"
    )
    sites = [
        n for n in ast.walk(server) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "TCPSite"
    ]
    applications = [
        n for n in ast.walk(server) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "Application"
    ]
    sites_use_loopback = (
        len(sites) == 1 and len(sites[0].args) >= 3
        and isinstance(sites[0].args[1], ast.Name)
        and sites[0].args[1].id == "HRAIN_LOCAL_BIND_HOST"
    )
    wired_guard = any(
        "janus_local_access_guard" in ast.unparse(k.value)
        for app in applications for k in app.keywords
        if k.arg == "middlewares"
    )
    checks["server_local_api_authority"] = (
        loopback_binding and sites_use_loopback and wired_guard
        and guard is not None
        and all(s in guard_ast for s in (
            "Host", "Origin", "request.remote", "X-JANUS-Local-Token",
            "JANUS_HRAIN_LOCAL_API_TOKEN", "hmac.compare_digest",
            "API_TOKEN_REQUIRED", "LOOPBACK_HOST_REQUIRED",
            "LOCAL_ORIGIN_REQUIRED", "/api/", "/ws"
        ))
    )
    compressor = _method(graph, "compress_clusters")
    checks["compression_hold"] = (
        compressor is not None
        and not _mutates_graph(compressor)
        and not ({"add_edge", "update", "exec", "eval"} & _calls(compressor))
        and _hold_strings(compressor, "HOLD_LEGACY_DESTRUCTIVE_COMPRESSION")
    )
    remover = _method(graph, "remove_node")
    checks["remove_node_hold"] = (
        remover is not None and not _mutates_graph(remover)
        and _returns_false(remover)
        and not ({"add_edge", "update", "exec", "eval"} & _calls(remover))
    )
    for method in ("decay_edges", "decay_nodes"):
        fn = _method(graph, method)
        checks[method + "_preserves_topology"] = (
            fn is not None and not _mutates_graph(fn)
            and not ({"remove_node", "add_edge", "delattr", "exec", "eval"} & _calls(fn))
        )
    update = _method(graph, "update")
    checks["capacity_atomic_hold"] = (
        update is not None and not _mutates_graph(update, permit_growth=True)
        and _hold_strings(update, "HRAIN_EVENT_BATCH_CAPACITY_HOLD")
        and "remove_node" not in _calls(update)
    )
    arm = _method(autonomy, "enable_synthetic_sandbox")
    arm_dump = ast.dump(arm, include_attributes=False) if arm else ""
    checks["clean_synthetic_only_arm"] = (
        bool(arm and "_synthetic_only" in arm_dump and "nodes" in arm_dump
             and "edges" in arm_dump and "PermissionError" in arm_dump)
    )
    cycle = _method(autonomy, "cycle_once")
    cycle_dump = ast.dump(cycle, include_attributes=False) if cycle else ""
    checks["cycle_disarmed_by_default"] = (
        bool(cycle and "_synthetic_only" in cycle_dump
             and "HOLD_NOT_ACTIVATED" in cycle_dump and "CAPACITY_HOLD" in cycle_dump)
    )
    maxwell = _method(autonomy, "_maxwell")
    checks["maxwell_no_deletion"] = (
        maxwell is not None and not _mutates_graph(maxwell)
        and not ({"remove_node", "exec", "eval"} & _calls(maxwell))
        and _hold_strings(maxwell, "retention_hold")
    )
    checkpoint_main = next((x for x in trees["checkpoint"].body
                           if isinstance(x, ast.FunctionDef) and x.name == "main"), None)
    ckpt_fn = next((x for x in trees["checkpoint"].body
                   if isinstance(x, ast.FunctionDef) and x.name == "checkpoint"), None)
    checks["checkpoint_opt_in_only"] = (
        checkpoint_main is not None and ckpt_fn is not None
        and _hold_strings(checkpoint_main, "--create")
        and _hold_strings(ckpt_fn, "OWNER_SOURCE_CHANGED_DURING_CHECKPOINT_HOLD")
        and not ({"subprocess", "system", "Popen", "urlopen", "requests"} &
                 _calls(trees["checkpoint"]))
    )
    checks["independent_shadow_verifier_present"] = (
        any(isinstance(x, ast.FunctionDef) and x.name == "verify"
            for x in trees["independent"].body)
        and any(isinstance(x, ast.FunctionDef) and x.name == "make_shadow"
                for x in trees["shadow"].body)
    )
    failed = sorted(k for k, v in checks.items() if not v)
    return {
        "schema": SCHEMA,
        "status": "PASS_PUBLIC_SOURCE_GATES" if not failed else "HOLD_UNSAFE_SOURCE",
        "checks": checks, "failed": failed,
        "privateGraphInspected": False,
        "workingMemoryModified": False,
        "productionAutonomyAuthorized": False,
        "action": "RUN_SYNTHETIC_TESTS" if not failed else "BLOCK_AND_INVESTIGATE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = assess(args.repo_root)
    serialized = json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError("SAFETY_REPORT_MUST_NOT_OVERWRITE")
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if not result["failed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
