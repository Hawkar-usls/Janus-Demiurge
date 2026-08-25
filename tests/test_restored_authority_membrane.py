from __future__ import annotations

import ast
from pathlib import Path

RESTORED = Path(__file__).resolve().parents[1] / "restored"

FORBIDDEN_IMPORT_ROOTS = {
    "socket",
    "requests",
    "urllib",
    "http",
    "subprocess",
    "paramiko",
    "ftplib",
    "telnetlib",
}

FORBIDDEN_CALLS = {
    "os.remove",
    "os.unlink",
    "os.rename",
    "os.replace",
    "os.system",
    "shutil.rmtree",
    "shutil.move",
    "Path.unlink",
    "Path.rename",
    "Path.replace",
}


def _call_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        parts = [fn.attr]
        value = fn.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
            return ".".join(reversed(parts))
    return None


def test_restored_tree_has_no_hidden_network_process_or_destructive_fs_actuators():
    violations: list[str] = []
    files = sorted(p for p in RESTORED.glob("*.py") if p.name != "__init__.py")
    assert files, "restored tree is unexpectedly empty"

    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(f"{path.name}:{node.lineno}: forbidden import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{path.name}:{node.lineno}: forbidden import-from {module}")
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path.name}:{node.lineno}: forbidden call {name}")

    assert violations == [], "restoration authority drift detected:\n" + "\n".join(violations)


def test_sender_membrane_remains_request_only_by_source_contract():
    source = (RESTORED / "sender_request_envelope.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "NETWORK_SEND_REQUEST_UNAUTHORIZED" in string_literals
    assert "REQUEST_ENVELOPE_NE_NETWORK_AUTHORITY" in string_literals
    assert "APPROVAL_MUST_BIND_TO_EXACT_ENVELOPE_HASH" in string_literals
