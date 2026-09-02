from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SEMANTIC_EXTENSIONS = {
    ".json", ".md", ".markdown", ".txt", ".py", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".csv", ".tsv", ".html", ".htm", ".js", ".ts", ".tsx",
    ".jsx", ".css", ".scss", ".sh", ".ps1", ".xml", ".jsonl", ".ndjson",
}
SECRETISH = re.compile(
    r"(?:^|[._/-])(env|secret|token|credential|password|private[_-]?key)(?:$|[._/-])",
    re.I,
)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
]
EXCLUDED_PARTS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", "runtime", "outbox", "receipts", "artifacts",
}
PRIORITY_NAMES = {
    "README.md", "PROJECT_STATUS.json", "AGENTS.md", "CONTRACT.md", "PROTOCOL.md",
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def scrub(text: str) -> str:
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 180) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = scrub((proc.stderr or proc.stdout or "")[-1200:])
        raise RuntimeError(f"KEYMASTER_COMMAND_FAILED:{cmd[0]}:{proc.returncode}:{detail}")
    return proc.stdout


def _score_path(rel: str) -> tuple[int, str]:
    path = Path(rel)
    score = 100 if path.name in PRIORITY_NAMES else 0
    low = rel.lower()
    for word in (
        "readme", "status", "manifest", "protocol", "contract", "architecture",
        "keymaster", "topa", "spider", "lapis", "observer", "io", "cat", "train",
        "learn", "verify", "test", "model", "engine",
    ):
        if word in low:
            score += 10
    return (-score, rel)


def eligible_tracked_files(repo: Path) -> list[str]:
    rows = []
    for rel in run(["git", "ls-files"], cwd=repo).splitlines():
        rel = rel.strip()
        if not rel:
            continue
        path = Path(rel)
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if SECRETISH.search(rel):
            continue
        if path.suffix.lower() not in SEMANTIC_EXTENSIONS:
            continue
        full = repo / rel
        if full.is_file():
            rows.append(rel)
    return sorted(rows, key=_score_path)


def collect_repository(contributor: dict, max_bytes: int, work_root: Path) -> tuple[dict, str]:
    repository = contributor["repository"]
    ref = contributor.get("ref") or "main"
    repo = work_root / contributor["id"].lower()
    clone_url = f"https://github.com/{repository}.git"
    run(["git", "clone", "--depth", "1", "--branch", ref, clone_url, str(repo)])
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise RuntimeError(f"KEYMASTER_HEAD_INVALID:{repository}:{head}")

    selected = []
    chunks = []
    used = 0
    for rel in eligible_tracked_files(repo):
        raw = (repo / rel).read_bytes()
        if not raw:
            continue
        file_sha = sha256_bytes(raw)
        text = scrub(raw.decode("utf-8", errors="replace"))
        envelope = (
            f"\n<JANUS_KEYMASTER_RECORD contributor={json.dumps(contributor['id'])} "
            f"repository={json.dumps(repository)} head={json.dumps(head)} "
            f"path={json.dumps(rel)} sha256={json.dumps(file_sha)} "
            f"provenance={json.dumps(contributor['provenance'])} "
            f"authority=\"TRAINING_MATERIAL_REQUIRES_VERIFICATION\">\n"
            f"{text}\n</JANUS_KEYMASTER_RECORD>\n"
        ).encode("utf-8")
        remain = max_bytes - used
        if remain <= 0:
            break
        bounded = envelope[:remain]
        decoded = bounded.decode("utf-8", errors="ignore")
        actual = len(decoded.encode("utf-8"))
        if actual <= 0:
            continue
        chunks.append(decoded)
        used += actual
        selected.append({
            "path": rel,
            "sha256": file_sha,
            "source_bytes": len(raw),
            "contributed_bytes": actual,
        })

    if used <= 0 or not selected:
        raise RuntimeError(f"KEYMASTER_ZERO_BYTE_CONTRIBUTOR:{repository}")

    identity = {
        "id": contributor["id"],
        "repository": repository,
        "ref": ref,
        "head_sha": head,
        "provenance": contributor["provenance"],
        "selected_files": selected,
        "selected_file_count": len(selected),
        "contributed_bytes": used,
    }
    identity["contribution_sha256"] = sha256_bytes(canonical_bytes(identity))
    return identity, "".join(chunks)


def collect(config_path: Path, out_dir: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "janus.keymaster.primary_learning_contributors.v1":
        raise RuntimeError("KEYMASTER_CONFIG_SCHEMA_REJECTED")
    contributors = config.get("contributors")
    expected_count = int(config.get("contributor_count", -1))
    if not isinstance(contributors, list) or len(contributors) != expected_count or expected_count != 5:
        raise RuntimeError("KEYMASTER_REQUIRED_5_OF_5_CONFIG_REJECTED")
    repositories = [row.get("repository") for row in contributors if isinstance(row, dict)]
    if len(set(repositories)) != 5 or any(not isinstance(x, str) or not x for x in repositories):
        raise RuntimeError("KEYMASTER_CONTRIBUTOR_REPOSITORIES_REJECTED")
    learning = config.get("learning") or {}
    firewalls = config.get("firewalls") or {}
    if learning.get("lane") != "TRAIN_ONLY" or learning.get("adaptive_holdout_inclusion") is not False:
        raise RuntimeError("KEYMASTER_TRAIN_ONLY_FIREWALL_REJECTED")
    if learning.get("frozen_anchor_inclusion") is not False:
        raise RuntimeError("KEYMASTER_ANCHOR_FIREWALL_REJECTED")
    if firewalls.get("cross_repository_write") is not False or firewalls.get("authority_delta") != 0:
        raise RuntimeError("KEYMASTER_AUTHORITY_FIREWALL_REJECTED")
    if firewalls.get("source_execution") is not False:
        raise RuntimeError("KEYMASTER_SOURCE_EXECUTION_FIREWALL_REJECTED")

    out_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(config.get("max_bytes_per_contributor", 120000))
    if not 1000 <= max_bytes <= 250000:
        raise RuntimeError("KEYMASTER_MAX_BYTES_REJECTED")

    records = []
    packs = []
    with tempfile.TemporaryDirectory(prefix="janus-keymaster-") as td:
        root = Path(td)
        for contributor in contributors:
            record, pack = collect_repository(contributor, max_bytes, root)
            records.append(record)
            packs.append(pack)

    identity = {
        "schema": "janus.keymaster.learning_contribution_manifest.v1",
        "status": "READY_5_OF_5",
        "contributor_count": len(records),
        "contributors": records,
        "training_only": True,
        "adaptive_holdout_inclusion": False,
        "frozen_anchor_inclusion": False,
        "training_material_is_truth": False,
        "contribution_grants_authority": False,
        "source_execution": False,
        "cross_repository_write": False,
        "authority_delta": 0,
    }
    identity["contribution_sha256"] = sha256_bytes(canonical_bytes(identity))
    training_text = "".join(packs)
    training_sha = sha256_bytes(training_text.encode("utf-8"))
    identity["training_pack_sha256"] = training_sha
    identity["training_bytes"] = len(training_text.encode("utf-8"))
    if identity["contributor_count"] != 5 or identity["training_bytes"] <= 0:
        raise RuntimeError("KEYMASTER_5_OF_5_NOT_READY")

    (out_dir / "training.txt").write_text(training_text, encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return identity


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = collect(Path(args.config), Path(args.out))
    print(json.dumps({
        "status": result["status"],
        "contributor_count": result["contributor_count"],
        "contribution_sha256": result["contribution_sha256"],
        "training_pack_sha256": result["training_pack_sha256"],
        "training_bytes": result["training_bytes"],
        "contributors": [
            {
                "id": row["id"],
                "repository": row["repository"],
                "head_sha": row["head_sha"],
                "contributed_bytes": row["contributed_bytes"],
                "provenance": row["provenance"],
            }
            for row in result["contributors"]
        ],
        "authority_delta": result["authority_delta"],
    }, indent=2))


if __name__ == "__main__":
    main()
