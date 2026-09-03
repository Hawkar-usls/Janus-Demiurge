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
    "experiment_manifest.json",
}
SUPPORTED_CONFIGS = {
    "janus.keymaster.primary_learning_contributors.v1": 5,
    "janus.keymaster.primary_learning_contributors.v2": 8,
}
TRUMP_REF_STRATEGY = "TRUMP_LATEST_RESEARCH_FRONTIER"
TRUMP_REPOSITORY = "Hawkar-usls/Janus-Fundamentum"
TRUMP_BRANCH_RE = re.compile(
    r"^research/janus-trump-r(?P<round>\d+)(?P<suffix>[a-z]?)(?P<variant>\d*)-",
    re.I,
)
TRUMP_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


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


def _trump_branch_sort_key(ref: str) -> tuple[int, int, int, str, str] | None:
    match = TRUMP_BRANCH_RE.match(ref)
    if match is None:
        return None
    suffix = (match.group("suffix") or "").lower()
    suffix_rank = (ord(suffix) - ord("a") + 1) if suffix else 0
    variant = int(match.group("variant") or "0")
    dates = TRUMP_DATE_RE.findall(ref)
    date = dates[-1] if dates else ""
    return (int(match.group("round")), suffix_rank, variant, date, ref.lower())


def resolve_contributor_ref(contributor: dict) -> tuple[str, dict]:
    configured_ref = contributor.get("ref") or "main"
    strategy = contributor.get("ref_strategy")
    if not strategy:
        return configured_ref, {
            "configured_ref": configured_ref,
            "resolved_ref": configured_ref,
            "ref_strategy": "FIXED",
            "resolver_failure_policy": "NOT_APPLICABLE",
        }
    if strategy != TRUMP_REF_STRATEGY:
        raise RuntimeError(f"KEYMASTER_REF_STRATEGY_REJECTED:{strategy}")
    if contributor.get("repository") != TRUMP_REPOSITORY:
        raise RuntimeError("KEYMASTER_TRUMP_STRATEGY_REPOSITORY_REJECTED")
    if contributor.get("resolver_failure_policy") != "FAIL_CLOSED":
        raise RuntimeError("KEYMASTER_TRUMP_RESOLVER_MUST_FAIL_CLOSED")

    branch_prefix = contributor.get("branch_prefix") or "research/janus-trump-r"
    if not isinstance(branch_prefix, str) or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch_prefix):
        raise RuntimeError("KEYMASTER_TRUMP_BRANCH_PREFIX_REJECTED")

    clone_url = f"https://github.com/{contributor['repository']}.git"
    refs = run([
        "git", "ls-remote", "--heads", clone_url, f"refs/heads/{branch_prefix}*",
    ])
    candidates: list[tuple[tuple[int, int, int, str, str], str, str]] = []
    for line in refs.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        head_sha, full_ref = parts
        if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
            continue
        prefix = "refs/heads/"
        if not full_ref.startswith(prefix):
            continue
        ref = full_ref[len(prefix):]
        if not ref.startswith(branch_prefix):
            continue
        key = _trump_branch_sort_key(ref)
        if key is not None:
            candidates.append((key, ref, head_sha))

    if not candidates:
        raise RuntimeError("KEYMASTER_TRUMP_FRONTIER_NOT_FOUND_FAIL_CLOSED")

    key, resolved_ref, selected_head = max(candidates, key=lambda row: row[0])
    return resolved_ref, {
        "configured_ref": configured_ref,
        "resolved_ref": resolved_ref,
        "ref_strategy": strategy,
        "resolver_failure_policy": "FAIL_CLOSED",
        "selected_head_at_resolution": selected_head,
        "natural_version": {
            "round": key[0],
            "suffix_rank": key[1],
            "variant": key[2],
            "date": key[3],
        },
    }


def _score_path(rel: str, extra_priority_terms: tuple[str, ...] = ()) -> tuple[int, str]:
    path = Path(rel)
    score = 100 if path.name in PRIORITY_NAMES else 0
    low = rel.lower()
    for word in (
        "readme", "status", "manifest", "protocol", "contract", "architecture",
        "keymaster", "topa", "spider", "lapis", "observer", "io", "cat", "train",
        "learn", "verify", "test", "model", "engine", "fundamentum", "proof",
        "demi", "arbiter", "aura", "oracle", "hypothesis", "evidence",
    ):
        if word in low:
            score += 10
    for word in extra_priority_terms:
        word = word.strip().lower()
        if word and word in low:
            score += 40
    return (-score, rel)


def eligible_tracked_files(repo: Path, extra_priority_terms: tuple[str, ...] = ()) -> list[str]:
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
    return sorted(rows, key=lambda rel: _score_path(rel, extra_priority_terms))


def collect_repository(contributor: dict, max_bytes: int, work_root: Path) -> tuple[dict, str]:
    repository = contributor["repository"]
    ref, ref_resolution = resolve_contributor_ref(contributor)
    repo = work_root / contributor["id"].lower()
    clone_url = f"https://github.com/{repository}.git"
    run(["git", "clone", "--depth", "1", "--branch", ref, clone_url, str(repo)])
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise RuntimeError(f"KEYMASTER_HEAD_INVALID:{repository}:{head}")

    extra_priority_terms = tuple(contributor.get("priority_terms") or ())
    frontier_match = TRUMP_BRANCH_RE.match(ref) if ref_resolution["ref_strategy"] == TRUMP_REF_STRATEGY else None
    if frontier_match is not None:
        frontier_token = (
            f"r{frontier_match.group('round')}"
            f"{(frontier_match.group('suffix') or '').lower()}"
            f"{frontier_match.group('variant') or ''}"
        )
        extra_priority_terms = extra_priority_terms + (frontier_token,)

    selected = []
    chunks = []
    used = 0
    for rel in eligible_tracked_files(repo, extra_priority_terms):
        raw = (repo / rel).read_bytes()
        if not raw:
            continue
        file_sha = sha256_bytes(raw)
        text = scrub(raw.decode("utf-8", errors="replace"))
        envelope = (
            f"\n<JANUS_KEYMASTER_RECORD contributor={json.dumps(contributor['id'])} "
            f"repository={json.dumps(repository)} ref={json.dumps(ref)} "
            f"ref_strategy={json.dumps(ref_resolution['ref_strategy'])} "
            f"head={json.dumps(head)} "
            f"path={json.dumps(rel)} sha256={json.dumps(file_sha)} "
            f"provenance={json.dumps(contributor['provenance'])} "
            f"cohort={json.dumps(contributor.get('cohort', 'LEGACY_5'))} "
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

    pack = "".join(chunks)
    identity = {
        "id": contributor["id"],
        "repository": repository,
        "configured_ref": ref_resolution["configured_ref"],
        "ref": ref,
        "ref_strategy": ref_resolution["ref_strategy"],
        "ref_resolution": ref_resolution,
        "head_sha": head,
        "provenance": contributor["provenance"],
        "cohort": contributor.get("cohort", "LEGACY_5"),
        "selected_files": selected,
        "selected_file_count": len(selected),
        "contributed_bytes": used,
        "training_pack_sha256": sha256_bytes(pack.encode("utf-8")),
    }
    identity["contribution_sha256"] = sha256_bytes(canonical_bytes(identity))
    return identity, pack


def _validate_config(config: dict) -> tuple[list[dict], int]:
    schema = config.get("schema")
    required_count = SUPPORTED_CONFIGS.get(schema)
    if required_count is None:
        raise RuntimeError("KEYMASTER_CONFIG_SCHEMA_REJECTED")
    contributors = config.get("contributors")
    expected_count = int(config.get("contributor_count", -1))
    if not isinstance(contributors, list) or len(contributors) != expected_count or expected_count != required_count:
        raise RuntimeError(f"KEYMASTER_REQUIRED_{required_count}_OF_{required_count}_CONFIG_REJECTED")
    if any(not isinstance(row, dict) for row in contributors):
        raise RuntimeError("KEYMASTER_CONTRIBUTOR_ROW_REJECTED")
    repositories = [row.get("repository") for row in contributors]
    ids = [row.get("id") for row in contributors]
    if len(set(repositories)) != required_count or len(set(ids)) != required_count:
        raise RuntimeError("KEYMASTER_CONTRIBUTOR_IDENTITY_DUPLICATE")
    if any(not isinstance(x, str) or not x for x in repositories + ids):
        raise RuntimeError("KEYMASTER_CONTRIBUTOR_IDENTITIES_REJECTED")

    for row in contributors:
        strategy = row.get("ref_strategy")
        if strategy is None:
            continue
        if strategy != TRUMP_REF_STRATEGY:
            raise RuntimeError(f"KEYMASTER_REF_STRATEGY_REJECTED:{strategy}")
        if row.get("repository") != TRUMP_REPOSITORY:
            raise RuntimeError("KEYMASTER_TRUMP_STRATEGY_REPOSITORY_REJECTED")
        if row.get("resolver_failure_policy") != "FAIL_CLOSED":
            raise RuntimeError("KEYMASTER_TRUMP_RESOLVER_MUST_FAIL_CLOSED")
        priority_terms = row.get("priority_terms") or []
        if not isinstance(priority_terms, list) or any(not isinstance(term, str) or not term for term in priority_terms):
            raise RuntimeError("KEYMASTER_PRIORITY_TERMS_REJECTED")

    if schema.endswith(".v2"):
        cohorts = [row.get("cohort") for row in contributors]
        if cohorts.count("CORE_5") != 5 or cohorts.count("EXTENDED_3") != 3:
            raise RuntimeError("KEYMASTER_V2_COHORT_PARTITION_REJECTED")
        attribution = config.get("attribution") or {}
        if attribution.get("enabled") is not True:
            raise RuntimeError("KEYMASTER_ATTRIBUTION_MUST_BE_ENABLED")
        if attribution.get("single_run_establishes_causality") is not False:
            raise RuntimeError("KEYMASTER_ATTRIBUTION_CAUSALITY_FIREWALL_REJECTED")
        if attribution.get("automatic_contributor_removal") is not False:
            raise RuntimeError("KEYMASTER_ATTRIBUTION_REMOVAL_FIREWALL_REJECTED")

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
    return contributors, required_count


def collect(config_path: Path, out_dir: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    contributors, required_count = _validate_config(config)

    out_dir.mkdir(parents=True, exist_ok=True)
    packs_dir = out_dir / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
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
            (packs_dir / f"{contributor['id']}.txt").write_text(pack, encoding="utf-8")

    training_text = "".join(packs)
    training_sha = sha256_bytes(training_text.encode("utf-8"))
    version = "v2" if required_count == 8 else "v1"
    identity = {
        "schema": f"janus.keymaster.learning_contribution_manifest.{version}",
        "config_schema": config["schema"],
        "status": f"READY_{required_count}_OF_{required_count}",
        "required_contributor_count": required_count,
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
        "training_pack_sha256": training_sha,
        "training_bytes": len(training_text.encode("utf-8")),
        "individual_pack_files_emitted": True,
        "attribution_enabled": bool((config.get("attribution") or {}).get("enabled", False)),
    }
    identity["contribution_sha256"] = sha256_bytes(canonical_bytes(identity))
    if identity["contributor_count"] != required_count or identity["training_bytes"] <= 0:
        raise RuntimeError(f"KEYMASTER_{required_count}_OF_{required_count}_NOT_READY")

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
                "configured_ref": row["configured_ref"],
                "ref": row["ref"],
                "ref_strategy": row["ref_strategy"],
                "head_sha": row["head_sha"],
                "contributed_bytes": row["contributed_bytes"],
                "provenance": row["provenance"],
                "cohort": row["cohort"],
            }
            for row in result["contributors"]
        ],
        "authority_delta": result["authority_delta"],
    }, indent=2))


if __name__ == "__main__":
    main()
