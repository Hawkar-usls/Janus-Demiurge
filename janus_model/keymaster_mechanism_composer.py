from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

SCHEMA = "janus.keymaster.mechanism_composition_report.v1"
REGISTRY_SCHEMA = "janus.keymaster.mechanism_registry.v1"
CONTRACT_SCHEMA = "janus.keymaster.mechanism_composition_contract.v1"

PROVED_STATUSES = {"PASS", "PROVED", "SOURCE_PROVED", "FROZEN_PASS"}
CANDIDATE_STATUSES = {"CANDIDATE", "AUDIT_PASS", "CANDIDATE_AUDIT_PASS", "FORMAL_PROOF_REQUIRED"}
TEXT_EXTENSIONS = {".json", ".md", ".markdown", ".txt", ".yml", ".yaml"}

BARRIER_PENALTIES = {
    "FULL_BLOCKER": 100,
    "SCOPED_BLOCKER": 4,
    "REPACKAGING": 12,
    "ANTI_LOOP": 8,
    "REPRESENTATION_LOWER_BOUND": 6,
    "DISCOVERY_HARDNESS": 5,
    "CAUTION": 2,
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 180) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[-1200:]
        raise RuntimeError(f"KEYMASTER_MECHANISM_COMMAND_FAILED:{cmd[0]}:{proc.returncode}:{detail}")
    return proc.stdout


def load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"KEYMASTER_MECHANISM_JSON_OBJECT_REQUIRED:{path}")
    return obj


def _validate_mechanism(row: dict) -> dict:
    required = [
        "id", "input_type", "output_type", "status", "semantics",
        "construction_poly", "state_poly", "reconstruction_poly", "verification_poly",
        "universal_scope", "roles", "authority",
    ]
    missing = [k for k in required if k not in row]
    if missing:
        raise RuntimeError(f"KEYMASTER_MECHANISM_FIELDS_MISSING:{row.get('id')}:{','.join(missing)}")
    if row["semantics"] != "EXACT":
        raise RuntimeError(f"KEYMASTER_MECHANISM_NONEXACT_REJECTED:{row['id']}")
    if not isinstance(row["roles"], list) or not row["roles"]:
        raise RuntimeError(f"KEYMASTER_MECHANISM_ROLES_REJECTED:{row['id']}")
    return row


def _validate_barrier(row: dict) -> dict:
    required = ["id", "from_type", "to_type", "status", "kind", "scope", "authority"]
    missing = [k for k in required if k not in row]
    if missing:
        raise RuntimeError(f"KEYMASTER_BARRIER_FIELDS_MISSING:{row.get('id')}:{','.join(missing)}")
    if row["kind"] not in BARRIER_PENALTIES:
        raise RuntimeError(f"KEYMASTER_BARRIER_KIND_REJECTED:{row['id']}:{row['kind']}")
    row["penalty"] = int(row.get("penalty", BARRIER_PENALTIES[row["kind"]]))
    if row["penalty"] < 0:
        raise RuntimeError(f"KEYMASTER_BARRIER_PENALTY_REJECTED:{row['id']}")
    return row


def load_registry(path: Path) -> dict:
    reg = load_json(path)
    if reg.get("schema") != REGISTRY_SCHEMA:
        raise RuntimeError("KEYMASTER_MECHANISM_REGISTRY_SCHEMA_REJECTED")
    mechanisms = [_validate_mechanism(dict(x)) for x in reg.get("mechanisms", [])]
    ids = [x["id"] for x in mechanisms]
    if len(ids) != len(set(ids)):
        raise RuntimeError("KEYMASTER_MECHANISM_DUPLICATE_ID")
    barriers = []
    for raw in reg.get("barriers") or []:
        if not isinstance(raw, dict) or "id" not in raw:
            raise RuntimeError("KEYMASTER_BARRIER_ROW_REJECTED")
        row = dict(raw)
        row.setdefault("from_type", "*")
        row.setdefault("to_type", "*")
        row.setdefault("status", "PROVED")
        row.setdefault("kind", "SCOPED_BLOCKER")
        row.setdefault("scope", "UNSPECIFIED_SCOPED_BARRIER")
        row.setdefault("authority", "SEED_REGISTRY")
        barriers.append(_validate_barrier(row))
    reg["mechanisms"] = mechanisms
    reg["barriers"] = barriers
    return reg


def load_contract(path: Path) -> dict:
    cfg = load_json(path)
    if cfg.get("schema") != CONTRACT_SCHEMA:
        raise RuntimeError("KEYMASTER_MECHANISM_CONTRACT_SCHEMA_REJECTED")
    firewalls = cfg.get("firewalls") or {}
    required_false = [
        "automatic_theorem_promotion",
        "automatic_d1_promotion",
        "automatic_p_equals_np_claim",
        "training_signal_is_evidence",
    ]
    if any(firewalls.get(k) is not False for k in required_false):
        raise RuntimeError("KEYMASTER_MECHANISM_FIREWALL_REJECTED")
    if firewalls.get("fundamentum_is_scientific_authority") is not True:
        raise RuntimeError("KEYMASTER_FUNDAMENTUM_AUTHORITY_REQUIRED")
    return cfg


def discover_refs(repo: Path, patterns: list[str], max_refs: int) -> list[dict]:
    raw = run(
        [
            "git", "for-each-ref",
            "--format=%(refname:short)%09%(objectname)%09%(committerdate:unix)",
            "refs/heads", "refs/remotes/origin",
        ],
        cwd=repo,
    )
    by_branch: dict[str, dict] = {}
    for line in raw.splitlines():
        parts = line.rstrip().split("\t")
        if len(parts) != 3:
            continue
        ref, sha, ts = parts
        if ref == "origin/HEAD":
            continue
        branch = ref[len("origin/"):] if ref.startswith("origin/") else ref
        if not any(fnmatch.fnmatch(branch, pattern) for pattern in patterns):
            continue
        try:
            commit_ts = int(ts)
        except ValueError:
            commit_ts = 0
        current = by_branch.get(branch)
        row = {"branch": branch, "sha": sha, "commit_ts": commit_ts}
        if current is None or (commit_ts, sha) > (current["commit_ts"], current["sha"]):
            by_branch[branch] = row
    rows = list(by_branch.values())
    rows.sort(key=lambda row: (row["commit_ts"], row["branch"]), reverse=True)
    if len(rows) > max_refs:
        kept = rows[:max_refs]
        main = next((row for row in rows if row["branch"] == "main"), None)
        if main is not None and all(row["branch"] != "main" for row in kept):
            kept[-1] = main
        rows = kept
    return sorted(rows, key=lambda row: row["branch"])


def _git_tree(repo: Path, ref: str, roots: list[str]) -> list[tuple[str, str]]:
    args = ["git", "ls-tree", "-r", ref, "--", *roots]
    out = run(args, cwd=repo)
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        try:
            left, path = line.split("\t", 1)
            _, typ, blob_sha = left.split()
        except ValueError:
            continue
        if typ != "blob":
            continue
        if Path(path).suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rows.append((path, blob_sha))
    return rows


def _status_token(obj: dict) -> str | None:
    """Extract only an explicit scalar scientific status.

    Fundamentum receipts are intentionally heterogeneous. A mapping-valued
    status is metadata, not a permission to promote an artifact. We accept a
    nested token only from a small allow-list and otherwise fail closed.
    """
    status = obj.get("status")
    if isinstance(status, str):
        return status
    verdict = obj.get("verdict")
    if isinstance(verdict, str):
        return verdict
    if isinstance(status, dict):
        for key in ("status", "verdict", "state"):
            value = status.get(key)
            if isinstance(value, str):
                return value
    return None


def _ref_exists(repo: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(repo),
        text=True,
        capture_output=True,
    )
    return proc.returncode == 0


def _scan_ref(repo: Path, branch: str) -> str:
    remote = f"origin/{branch}"
    return remote if _ref_exists(repo, remote) else branch


def _git_delta_tree(repo: Path, base_ref: str, ref: str, roots: list[str]) -> list[tuple[str, str]]:
    try:
        out = run(
            ["git", "diff", "--name-only", "--diff-filter=AM", f"{base_ref}...{ref}", "--", *roots],
            cwd=repo,
        )
    except RuntimeError:
        return _git_tree(repo, ref, roots)
    rows: list[tuple[str, str]] = []
    for path in out.splitlines():
        path = path.strip()
        if not path or Path(path).suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            blob_sha = run(["git", "rev-parse", f"{ref}:{path}"], cwd=repo).strip()
        except RuntimeError:
            continue
        rows.append((path, blob_sha))
    return rows


def _artifact_summary(obj: dict, *, branch: str, path: str, blob_sha: str) -> dict:
    boundary = obj.get("scientific_boundary") or obj.get("scientific_state") or {}
    return {
        "branch": branch,
        "path": path,
        "blob_sha": blob_sha,
        "artifact_id": obj.get("artifact_id"),
        "schema": obj.get("schema"),
        "status": _status_token(obj),
        "P_VS_NP": boundary.get("P_VS_NP") if isinstance(boundary, dict) else None,
        "D1": boundary.get("D1") if isinstance(boundary, dict) else None,
        "current_target": obj.get("current_target") or obj.get("next") or obj.get("next_action"),
    }


def _dynamic_mechanisms(obj: dict, *, branch: str, path: str, blob_sha: str) -> list[dict]:
    rows = []
    payloads: list[dict] = []
    if obj.get("schema") == "janus.keymaster.mechanism.v1":
        payloads.append(obj)
    km = obj.get("keymaster_mechanism")
    if isinstance(km, dict):
        payloads.append(km)
    if isinstance(km, list):
        payloads.extend(x for x in km if isinstance(x, dict))
    for payload in payloads:
        row = dict(payload)
        row.setdefault("authority", {})
        row["authority"] = {
            **row["authority"],
            "repository": "Hawkar-usls/Janus-Fundamentum",
            "branch": branch,
            "path": path,
            "blob_sha": blob_sha,
        }
        rows.append(_validate_mechanism(row))
    return rows


def _dynamic_barriers(obj: dict, *, branch: str, path: str, blob_sha: str) -> list[dict]:
    rows = []
    payloads: list[dict] = []
    if obj.get("schema") == "janus.keymaster.barrier.v1":
        payloads.append(obj)
    kb = obj.get("keymaster_barrier")
    if isinstance(kb, dict):
        payloads.append(kb)
    if isinstance(kb, list):
        payloads.extend(x for x in kb if isinstance(x, dict))
    for payload in payloads:
        row = dict(payload)
        row.setdefault("authority", {})
        authority = row["authority"] if isinstance(row["authority"], dict) else {"source": row["authority"]}
        row["authority"] = {
            **authority,
            "repository": "Hawkar-usls/Janus-Fundamentum",
            "branch": branch,
            "path": path,
            "blob_sha": blob_sha,
        }
        rows.append(_validate_barrier(row))
    return rows


def scan_fundamentum(repo: Path, contract: dict) -> dict:
    scan = contract["fundamentum_scan"]
    refs = discover_refs(repo, scan["branch_patterns"], int(scan["max_branches"]))
    artifacts_by_key: dict[tuple[str, str], dict] = {}
    dynamic = []
    dynamic_barriers = []
    normalization_by_key: dict[tuple[str, str], dict] = {}
    blob_cache: dict[str, dict | None] = {}
    max_json_bytes = int(scan.get("max_json_bytes", 500000))
    main_ref = _scan_ref(repo, "main")
    for row in refs:
        branch = row["branch"]
        ref = _scan_ref(repo, branch)
        if branch == "main":
            tree = _git_tree(repo, ref, scan["roots"])
        else:
            tree = _git_delta_tree(repo, main_ref, ref, scan["roots"])
        row["scan_mode"] = "FULL_MAIN" if branch == "main" else "DELTA_FROM_MAIN"
        row["scanned_file_count"] = len(tree)
        branch_artifacts = 0
        for path, blob_sha in tree:
            if not path.endswith(".json"):
                continue
            if blob_sha in blob_cache:
                obj = blob_cache[blob_sha]
                if obj is None:
                    continue
            else:
                size = int(run(["git", "cat-file", "-s", blob_sha], cwd=repo).strip())
                if size > max_json_bytes:
                    blob_cache[blob_sha] = None
                    continue
                raw = run(["git", "show", f"{ref}:{path}"], cwd=repo)
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    blob_cache[blob_sha] = None
                    continue
                if not isinstance(parsed, dict):
                    blob_cache[blob_sha] = None
                    continue
                blob_cache[blob_sha] = parsed
                obj = parsed
            summary = _artifact_summary(obj, branch=branch, path=path, blob_sha=blob_sha)
            if any(summary.get(k) is not None for k in ("artifact_id", "status", "P_VS_NP", "D1")):
                key = (path, blob_sha)
                if key not in artifacts_by_key:
                    artifacts_by_key[key] = {**summary, "branches": [branch]}
                elif branch not in artifacts_by_key[key]["branches"]:
                    artifacts_by_key[key]["branches"].append(branch)
                branch_artifacts += 1
            dyn = _dynamic_mechanisms(obj, branch=branch, path=path, blob_sha=blob_sha)
            if dyn:
                dynamic.extend(dyn)
            dyn_barriers = _dynamic_barriers(obj, branch=branch, path=path, blob_sha=blob_sha)
            dynamic_barriers.extend(dyn_barriers)
            evidence_only = obj.get("keymaster_evidence_only") is True
            if not dyn and not dyn_barriers and not evidence_only and summary.get("status") in PROVED_STATUSES | CANDIDATE_STATUSES:
                key = (path, blob_sha)
                if key not in normalization_by_key:
                    normalization_by_key[key] = {
                        "path": path,
                        "blob_sha": blob_sha,
                        "branches": [branch],
                        "artifact_id": summary.get("artifact_id"),
                        "status": summary.get("status"),
                        "reason": "AUTHORITY_LIKE_ARTIFACT_HAS_NO_TYPED_KEYMASTER_MECHANISM_CONTRACT",
                    }
                elif branch not in normalization_by_key[key]["branches"]:
                    normalization_by_key[key]["branches"].append(branch)
        row["authority_artifact_count"] = branch_artifacts
    artifacts = sorted(artifacts_by_key.values(), key=lambda x: (x["path"], x["blob_sha"]))
    normalization_queue = sorted(normalization_by_key.values(), key=lambda x: (x["path"], x["blob_sha"]))
    digest = sha256_bytes(canonical_bytes({
        "refs": refs,
        "artifacts": artifacts,
        "dynamic_mechanisms": sorted({x["id"] for x in dynamic}),
        "dynamic_barriers": sorted({x["id"] for x in dynamic_barriers}),
    }))
    return {
        "repository": "Hawkar-usls/Janus-Fundamentum",
        "refs": refs,
        "artifacts": artifacts,
        "dynamic_mechanisms": dynamic,
        "dynamic_barriers": dynamic_barriers,
        "normalization_queue": normalization_queue,
        "snapshot_sha256": digest,
    }


def eligible_edge(row: dict, *, allow_candidates: bool = False) -> bool:
    allowed = set(PROVED_STATUSES)
    if allow_candidates:
        allowed |= CANDIDATE_STATUSES
    return (
        row.get("status") in allowed
        and row.get("semantics") == "EXACT"
        and row.get("construction_poly") is True
        and row.get("state_poly") is True
        and row.get("reconstruction_poly") is True
        and row.get("verification_poly") is True
        and row.get("universal_scope") is True
    )


def _bfs_paths(mechanisms: list[dict], start: str, goal: str, max_depth: int) -> list[list[str]]:
    by_input: dict[str, list[dict]] = {}
    for row in mechanisms:
        by_input.setdefault(row["input_type"], []).append(row)
    q = deque([(start, [])])
    seen_depth = {start: 0}
    paths = []
    while q:
        typ, path = q.popleft()
        if len(path) >= max_depth:
            continue
        for edge in sorted(by_input.get(typ, []), key=lambda x: x["id"]):
            new_path = path + [edge["id"]]
            out = edge["output_type"]
            if out == goal:
                paths.append(new_path)
                continue
            depth = len(new_path)
            if depth < seen_depth.get(out, 10**9):
                seen_depth[out] = depth
                q.append((out, new_path))
    return paths


def _forward_depth(mechanisms: list[dict], start: str, max_depth: int) -> dict[str, int]:
    by_input: dict[str, list[dict]] = {}
    for row in mechanisms:
        by_input.setdefault(row["input_type"], []).append(row)
    depth = {start: 0}
    q = deque([start])
    while q:
        typ = q.popleft()
        if depth[typ] >= max_depth:
            continue
        for edge in by_input.get(typ, []):
            out = edge["output_type"]
            if out not in depth:
                depth[out] = depth[typ] + 1
                q.append(out)
    return depth


def _backward_depth(mechanisms: list[dict], goal: str, max_depth: int) -> dict[str, int]:
    by_output: dict[str, list[dict]] = {}
    for row in mechanisms:
        by_output.setdefault(row["output_type"], []).append(row)
    depth = {goal: 0}
    q = deque([goal])
    while q:
        typ = q.popleft()
        if depth[typ] >= max_depth:
            continue
        for edge in by_output.get(typ, []):
            inp = edge["input_type"]
            if inp not in depth:
                depth[inp] = depth[typ] + 1
                q.append(inp)
    return depth


def _barriers_for_gap(barriers: list[dict], src: str, dst: str) -> list[dict]:
    hits = []
    for b in barriers:
        if b.get("status") not in PROVED_STATUSES:
            continue
        bf = b.get("from_type", "*")
        bt = b.get("to_type", "*")
        if (bf in ("*", src)) and (bt in ("*", dst)):
            hits.append({
                "id": b["id"],
                "kind": b.get("kind", "SCOPED_BLOCKER"),
                "penalty": int(b.get("penalty", BARRIER_PENALTIES["SCOPED_BLOCKER"])),
                "scope": b.get("scope"),
                "authority": b.get("authority"),
            })
    return sorted(hits, key=lambda x: (-x["penalty"], x["id"]))


def compose(registry: dict, scan: dict, contract: dict) -> dict:
    merged = list(registry["mechanisms"]) + list(scan.get("dynamic_mechanisms", []))
    by_id: dict[str, dict] = {}
    for row in merged:
        by_id[row["id"]] = row
    merged = list(by_id.values())

    barrier_by_id: dict[str, dict] = {}
    for row in list(registry.get("barriers", [])) + list(scan.get("dynamic_barriers", [])):
        barrier_by_id[row["id"]] = row
    barriers = list(barrier_by_id.values())

    authoritative = [x for x in merged if eligible_edge(x, allow_candidates=False)]
    shadow = [x for x in merged if eligible_edge(x, allow_candidates=True)]
    start = contract["search"]["start_type"]
    goal = contract["search"]["goal_type"]
    max_depth = int(contract["search"].get("max_depth", 8))

    authoritative_paths = _bfs_paths(authoritative, start, goal, max_depth)
    shadow_paths = _bfs_paths(shadow, start, goal, max_depth)
    fwd = _forward_depth(authoritative, start, max_depth)
    back = _backward_depth(authoritative, goal, max_depth)
    existing_pairs = {(x["input_type"], x["output_type"]) for x in authoritative}

    gaps = []
    for src, fd in sorted(fwd.items(), key=lambda x: (x[1], x[0])):
        for dst, bd in sorted(back.items(), key=lambda x: (x[1], x[0])):
            if src == dst or (src, dst) in existing_pairs:
                continue
            gap_barriers = _barriers_for_gap(barriers, src, dst)
            barrier_penalty = sum(x["penalty"] for x in gap_barriers)
            gaps.append({
                "from_type": src,
                "to_type": dst,
                "proved_prefix_edges": fd,
                "proved_suffix_edges": bd,
                "proved_context_edges": fd + bd,
                "complete_path_edges_if_closed": fd + 1 + bd,
                "barriers": gap_barriers,
                "barrier_penalty": barrier_penalty,
                "lockpick_score": (fd + bd) * 10 - barrier_penalty,
                "required_contract": {
                    "semantics": "EXACT",
                    "construction_poly": True,
                    "state_poly": True,
                    "reconstruction_poly": True,
                    "verification_poly": True,
                    "universal_scope": True,
                },
            })
    gaps.sort(
        key=lambda x: (
            -x["lockpick_score"],
            -x["proved_context_edges"],
            -min(x["proved_prefix_edges"], x["proved_suffix_edges"]),
            x["from_type"],
            x["to_type"],
        )
    )

    candidate_only = sorted(
        [
            {
                "id": x["id"],
                "input_type": x["input_type"],
                "output_type": x["output_type"],
                "status": x["status"],
                "authority": x["authority"],
            }
            for x in merged
            if x.get("status") in CANDIDATE_STATUSES
        ],
        key=lambda x: x["id"],
    )

    report = {
        "schema": SCHEMA,
        "status": "COMPLETE",
        "mode": "PROOF_CARRYING_MECHANISM_COMPOSITION",
        "fundamentum_snapshot_sha256": scan["snapshot_sha256"],
        "fundamentum_refs": scan["refs"],
        "authority_artifact_count": len(scan["artifacts"]),
        "typed_dynamic_mechanism_count": len(scan.get("dynamic_mechanisms", [])),
        "typed_dynamic_barrier_count": len(scan.get("dynamic_barriers", [])),
        "normalization_queue": scan["normalization_queue"],
        "registry_mechanism_count": len(registry["mechanisms"]),
        "authoritative_edge_count": len(authoritative),
        "candidate_edge_count": len(candidate_only),
        "start_type": start,
        "goal_type": goal,
        "complete_universal_lifecycle_candidates": authoritative_paths,
        "shadow_paths_including_unsealed_candidates": shadow_paths,
        "missing_interface_queue": gaps[: int(contract["search"].get("max_gap_results", 50))],
        "candidate_only_mechanisms": candidate_only,
        "firewall": {
            "fundamentum_is_scientific_authority": True,
            "automatic_theorem_promotion": False,
            "automatic_d1_promotion": False,
            "automatic_p_equals_np_claim": False,
            "training_signal_is_evidence": False,
            "complete_path_is_proof": False,
            "path_requires_independent_replay": True,
            "D1": "EMPTY",
            "P_VS_NP": "OPEN",
        },
    }
    report["report_sha256"] = sha256_bytes(canonical_bytes(report))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--contract", required=True)
    ap.add_argument("--fundamentum", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load_registry(Path(args.registry))
    contract = load_contract(Path(args.contract))
    scan = scan_fundamentum(Path(args.fundamentum), contract)
    report = compose(registry, scan, contract)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "report_sha256": report["report_sha256"],
        "fundamentum_snapshot_sha256": report["fundamentum_snapshot_sha256"],
        "fundamentum_branch_count": len(report["fundamentum_refs"]),
        "complete_universal_lifecycle_candidates": len(report["complete_universal_lifecycle_candidates"]),
        "shadow_paths": len(report["shadow_paths_including_unsealed_candidates"]),
        "missing_interfaces": len(report["missing_interface_queue"]),
        "normalization_queue": len(report["normalization_queue"]),
        "D1": report["firewall"]["D1"],
        "P_VS_NP": report["firewall"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
