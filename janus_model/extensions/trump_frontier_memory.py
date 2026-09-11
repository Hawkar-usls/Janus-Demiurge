from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

INTAKE_SCHEMA = "janus.trump.frontier_intake.v1"
MEMORY_SCHEMA = "janus.trump.frontier_training_memory.v1"
EXPECTED_REPOSITORY = "Hawkar-usls/Janus-Fundamentum"
SEMANTIC_EXTENSIONS = {
    ".json", ".jsonl", ".ndjson", ".md", ".markdown", ".txt", ".py",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".csv", ".tsv", ".html",
    ".htm", ".js", ".ts", ".tsx", ".jsx", ".css", ".scss", ".sh", ".ps1",
    ".xml",
}
SECRETISH = re.compile(
    r"(?:^|[._/-])(env|secret|secrets|token|credential|credentials|password|private[_-]?key)(?:$|[._/-])",
    re.I,
)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
]
DEFAULT_MAX_BYTES = 240_000
DEFAULT_MAX_FILES = 24
DEFAULT_MAX_BYTES_PER_FILE = 48_000


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def scrub(text: str) -> str:
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub("[REDACTED_SECRET]", text)
    return text


def _safe_relpath(value: Any) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_PATH_REJECTED")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_PATH_REJECTED:{value}")
    return pure.as_posix()


def _verify_declared_intake_sha(obj: dict) -> str:
    declared = obj.get("intake_sha256")
    if not isinstance(declared, str) or not re.fullmatch(r"[0-9a-f]{64}", declared):
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_INTAKE_SHA_MISSING")
    unsigned = dict(obj)
    unsigned.pop("intake_sha256", None)
    actual = sha256_bytes(canonical_bytes(unsigned))
    if actual != declared:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_INTAKE_SHA_MISMATCH")
    return declared


def validate_intake(obj: dict) -> list[dict]:
    if obj.get("schema") != INTAKE_SCHEMA:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_INTAKE_SCHEMA_REJECTED")
    if obj.get("status") != "READ_ONLY_EXACT_COMMIT_INTAKE":
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_EXACT_INTAKE_REQUIRED")
    if obj.get("repository") != EXPECTED_REPOSITORY:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_REPOSITORY_REJECTED")
    if obj.get("P_VS_NP") != "OPEN":
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_P_VS_NP_MUST_REMAIN_OPEN")

    commit = obj.get("selected_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_COMMIT_REJECTED")

    authority = obj.get("authority") or {}
    if authority.get("read_only") is not True:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_READ_ONLY_REQUIRED")
    for key in (
        "source_repository_mutated",
        "active_lineage_changed",
        "proof_ladder_changed",
        "theorem_promoted",
        "runtime_promoted",
    ):
        if authority.get(key) is not False:
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_AUTHORITY_REJECTED:{key}")
    if authority.get("authority_delta") != 0:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_AUTHORITY_DELTA_REJECTED")

    _verify_declared_intake_sha(obj)

    rows = obj.get("relevant_files")
    if not isinstance(rows, list) or not rows or len(rows) > 64:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_FILES_REJECTED")

    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("TRUMP_FRONTIER_MEMORY_FILE_ROW_REJECTED")
        path = _safe_relpath(row.get("path"))
        if path in seen:
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_DUPLICATE_PATH:{path}")
        seen.add(path)
        blob = row.get("git_blob_sha")
        if not isinstance(blob, str) or not re.fullmatch(r"[0-9a-f]{40}", blob):
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_BLOB_REJECTED:{path}")
        size = row.get("size_bytes")
        if size is not None and (not isinstance(size, int) or size < 0):
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_SIZE_REJECTED:{path}")
        out.append({"path": path, "git_blob_sha": blob, "size_bytes": size})
    return out


def _priority(path: str) -> tuple[int, str]:
    lower = path.lower()
    score = 0
    for token, weight in (
        ("proof", 80), ("certificate", 75), ("receipt", 70), ("gate", 65),
        ("contract", 60), ("objective", 55), ("trump", 50), ("research", 45),
        ("experiment", 40), ("solver", 35), ("readme", 25),
    ):
        if token in lower:
            score += weight
    suffix = Path(path).suffix.lower()
    score += {".json": 18, ".py": 16, ".md": 12, ".txt": 8}.get(suffix, 0)
    return (-score, path)


def _repo_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def _repo_tree(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()


def build_memory(
    source_root: Path,
    intake_path: Path,
    out_text: Path,
    out_manifest: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes_per_file: int = DEFAULT_MAX_BYTES_PER_FILE,
) -> dict:
    if max_bytes <= 0 or max_files <= 0 or max_bytes_per_file <= 0:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_LIMIT_REJECTED")

    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_SOURCE_ROOT_MISSING")

    intake_raw = intake_path.read_bytes()
    intake = json.loads(intake_raw)
    rows = validate_intake(intake)
    selected_commit = intake["selected_commit"]
    if _repo_head(source_root) != selected_commit:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_SOURCE_COMMIT_MISMATCH")
    declared_tree = intake.get("tree_sha")
    if declared_tree and _repo_tree(source_root) != declared_tree:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_SOURCE_TREE_MISMATCH")

    chunks: list[bytes] = []
    included: list[dict] = []
    skipped: list[dict] = []
    used = 0

    for row in sorted(rows, key=lambda x: _priority(x["path"])):
        if len(included) >= max_files or used >= max_bytes:
            break
        rel = row["path"]
        suffix = Path(rel).suffix.lower()
        if suffix not in SEMANTIC_EXTENSIONS:
            skipped.append({"path": rel, "reason": "NON_SEMANTIC_EXTENSION"})
            continue
        if SECRETISH.search(rel):
            skipped.append({"path": rel, "reason": "SECRETISH_PATH"})
            continue

        path = source_root.joinpath(*PurePosixPath(rel).parts)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_FILE_MISSING:{rel}")
        if path.is_symlink() or not resolved.is_file() or source_root not in resolved.parents:
            skipped.append({"path": rel, "reason": "UNSAFE_FILE_TYPE_OR_ESCAPE"})
            continue

        raw = resolved.read_bytes()
        if row["size_bytes"] is not None and len(raw) != row["size_bytes"]:
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_SIZE_MISMATCH:{rel}")
        if git_blob_sha1(raw) != row["git_blob_sha"]:
            raise RuntimeError(f"TRUMP_FRONTIER_MEMORY_BLOB_MISMATCH:{rel}")

        body_raw = raw[:max_bytes_per_file]
        body = scrub(body_raw.decode("utf-8", errors="replace"))
        header = (
            f"\n<JANUS_TRUMP_FRONTIER_MEMORY repository={json.dumps(EXPECTED_REPOSITORY)} "
            f"commit={json.dumps(selected_commit)} path={json.dumps(rel)} "
            f"git_blob_sha={json.dumps(row['git_blob_sha'])} "
            'authority="UNVERIFIED_READ_ONLY_TRAINING_MEMORY">\n'
        )
        footer = "\n</JANUS_TRUMP_FRONTIER_MEMORY>\n"
        encoded = (header + body + footer).encode("utf-8")
        remain = max_bytes - used
        if len(encoded) > remain:
            fixed = (header + footer).encode("utf-8")
            body_budget = remain - len(fixed)
            if body_budget <= 0:
                break
            body_bytes = body.encode("utf-8")[:body_budget]
            body = body_bytes.decode("utf-8", errors="ignore")
            encoded = (header + body + footer).encode("utf-8")
        if not encoded:
            continue
        chunks.append(encoded)
        used += len(encoded)
        included.append({
            "path": rel,
            "git_blob_sha": row["git_blob_sha"],
            "source_bytes": len(raw),
            "included_source_bytes_capped": len(body_raw),
            "training_record_bytes": len(encoded),
            "source_truncated": len(raw) > len(body_raw),
        })

    if not included:
        raise RuntimeError("TRUMP_FRONTIER_MEMORY_EMPTY_AFTER_SAFETY_FILTERS")

    pack = b"".join(chunks)
    pack_sha = sha256_bytes(pack)
    out_text.parent.mkdir(parents=True, exist_ok=True)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    out_text.write_bytes(pack)

    manifest = {
        "schema": MEMORY_SCHEMA,
        "status": "READY_READ_ONLY_TRAINING_MEMORY",
        "source_repository": EXPECTED_REPOSITORY,
        "source_commit": selected_commit,
        "source_tree_sha": _repo_tree(source_root),
        "selected_ref": intake.get("selected_ref"),
        "intake_sha256": intake["intake_sha256"],
        "intake_file_sha256": sha256_bytes(intake_raw),
        "training_pack_sha256": pack_sha,
        "training_bytes": len(pack),
        "included_file_count": len(included),
        "included_files": included,
        "skipped_files": skipped[:64],
        "limits": {
            "max_training_bytes": max_bytes,
            "max_files": max_files,
            "max_source_bytes_per_file": max_bytes_per_file,
        },
        "training_only": True,
        "adaptive_holdout_inclusion": False,
        "frozen_anchor_inclusion": False,
        "training_material_is_truth": False,
        "contribution_grants_authority": False,
        "source_execution": False,
        "cross_repository_write": False,
        "P_VS_NP": "OPEN",
        "authority": {
            "read_only_source": True,
            "may_mutate_source_repository": False,
            "may_change_active_lineage": False,
            "may_change_proof_ladder": False,
            "may_promote_theorem": False,
            "may_promote_runtime": False,
            "authority_delta": 0,
        },
        "laws": [
            "SELECTED_FRONTIER_MEMORY != VERIFIED_RESULT",
            "TRAINING_MEMORY != TRUTH",
            "TRAINING_MEMORY != PROOF",
            "READ_ONLY_INTAKE != SOURCE_MUTATION",
            "EVALUATION_HOLDOUTS_EXCLUDE_FRONTIER_MEMORY",
            "PROMOTION_STILL_REQUIRES_FROZEN_EVALUATION_GATES",
            "P_VS_NP = OPEN",
        ],
    }
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--intake", required=True)
    ap.add_argument("--out-text", required=True)
    ap.add_argument("--out-manifest", required=True)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    ap.add_argument("--max-bytes-per-file", type=int, default=DEFAULT_MAX_BYTES_PER_FILE)
    args = ap.parse_args()
    manifest = build_memory(
        Path(args.source_root),
        Path(args.intake),
        Path(args.out_text),
        Path(args.out_manifest),
        max_bytes=args.max_bytes,
        max_files=args.max_files,
        max_bytes_per_file=args.max_bytes_per_file,
    )
    print(json.dumps({
        "status": manifest["status"],
        "source_commit": manifest["source_commit"],
        "training_pack_sha256": manifest["training_pack_sha256"],
        "training_bytes": manifest["training_bytes"],
        "included_file_count": manifest["included_file_count"],
        "P_VS_NP": manifest["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
