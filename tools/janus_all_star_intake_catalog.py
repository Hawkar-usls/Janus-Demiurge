#!/usr/bin/env python3
"""Owner-local, read-only JANUS All Star source intake inventory.

Does not copy files, upload data, launch agents, create reports or access any
private graphs. Output includes only vetted root-level source names, hashes,
sizes and broad audit flags. Never claims automatic production readiness.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

SCHEMA = "janus.all_star.public_source_intake_inventory.v1"
MAX_SOURCE_BYTES = 256_000
ALLOWED_ROOT_MODULES = (
    "all_star_launcher.py", "ecosystem_bridges.py", "experimental_sat_profile.py",
    "genesis_protocol.py", "hrain_autonomy.py", "hrain_decision_core.py",
    "hrain_graph_engine.py", "janus_cli.py", "janus_cognitive_loop.py",
    "janus_control_ui.py", "janus_db.py", "janus_log_ingest.py",
    "janus_nas_sync.py", "memory.py", "project_paths.py",
    "server.py", "wormhole_reader.py",
)
RISK_IMPORTS = ("subprocess", "socket", "requests", "urllib", "http", "ftplib")
RISK_CALLS = ("remove_node", "unlink", "rmtree", "remove", "system", "popen",
              "urlopen", "post", "put", "write_text", "write_bytes", "mkdir", "open")
RISK_TOKENS = ("api_key", "secret", "token", "password", "authorization", "private_key")


def _flags(source: str) -> list[str]:
    tree = ast.parse(source)
    flags = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            if any(name.name.split(".")[0] in RISK_IMPORTS for name in item.names):
                flags.add("EXTERNAL_IO_IMPORT_REVIEW")
        if isinstance(item, ast.ImportFrom):
            if (item.module or "").split(".")[0] in RISK_IMPORTS:
                flags.add("EXTERNAL_IO_IMPORT_REVIEW")
        if isinstance(item, ast.Call):
            target = item.func
            name = target.attr if isinstance(target, ast.Attribute) else (
                target.id if isinstance(target, ast.Name) else "")
            if name.lower() in RISK_CALLS:
                flags.add("MUTATION_OR_IO_REVIEW")
    lowered = source.lower()
    if any(token in lowered for token in RISK_TOKENS):
        flags.add("CREDENTIAL_REVIEW")
    return sorted(flags)


def inventory(root: Path) -> dict:
    root = Path(root)
    if root.name != "All Star" or root.is_symlink() or not root.is_dir():
        raise ValueError("ONLY_EXPLICIT_ALL_STAR_ROOT_ALLOWED")
    files = []
    for name in ALLOWED_ROOT_MODULES:
        source = root / name
        if source.is_symlink():
            files.append({"name": name, "status": "SYMLINK_BLOCKED"})
            continue
        if not source.is_file():
            files.append({"name": name, "status": "ABSENT"})
            continue
        stat = source.stat()
        if stat.st_size > MAX_SOURCE_BYTES:
            files.append({"name": name, "status": "OVERSIZE_REVIEW"})
            continue
        body = source.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        try:
            if b"\x00" in body:
                raise ValueError("NUL")
            signals = _flags(body.decode("utf-8-sig"))
        except (ValueError, SyntaxError, UnicodeError):
            files.append({"name": name, "status": "INVALID_SOURCE_REVIEW", "sha256": digest})
            continue
        files.append({
            "name": name, "status": "STATIC_REVIEW_ONLY",
            "bytes": len(body), "sha256": digest,
            "signals": signals, "autonomousImportAllowed": False,
        })
    return {
        "schema": SCHEMA, "scope": "curated_public_source_files_only",
        "privateDirectoriesTraversed": False,
        "files": files, "productionUseAuthorized": False,
        "sourceMutationAllowed": False, "automaticGitPushAllowed": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(inventory(args.root), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
