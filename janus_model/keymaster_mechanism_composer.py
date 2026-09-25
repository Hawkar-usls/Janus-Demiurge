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


def _reachable(
    mechanisms: list[dict],
    start: str,
    goal: str,
    max_depth: int,
) -> bool:
    if start == goal:
        return True
    by_input: dict[str, list[str]] = {}
    for row in mechanisms:
        by_input.setdefault(row["input_type"], []).append(row["output_type"])
    q = deque([(start, 0)])
    seen = {start}
    while q:
        typ, depth = q.popleft()
        if depth >= max_depth:
            continue
        for out in by_input.get(typ, []):
            if out == goal:
                return True
            if out not in seen:
                seen.add(out)
                q.append((out, depth + 1))
    return False


def _barriers_for_gap(
    barriers: list[dict],
    src: str,
    dst: str,
    authoritative: list[dict],
    max_depth: int,
) -> list[dict]:
    hits = []
    seen: set[str] = set()
    for b in barriers:
        if b.get("status") not in PROVED_STATUSES:
            continue
        bf = b.get("from_type", "*")
        bt = b.get("to_type", "*")
        direct = (bf in ("*", src)) and (bt in ("*", dst))
        inherited = False
        if not direct and bf != "*" and bt != "*":
            # If a candidate src->dst edge plus already-authoritative exact
            # edges would complete a route that a proved barrier forbids, the
            # gap inherits that barrier. This is implication, not promotion:
            #
            #   barrier(bf -> bt)
            #   bf =>* src ; [candidate src -> dst] ; dst =>* bt
            #
            # therefore admitting the candidate would imply the blocked route.
            inherited = (
                _reachable(authoritative, bf, src, max_depth)
                and _reachable(authoritative, dst, bt, max_depth)
            )
        if not direct and not inherited:
            continue
        if b["id"] in seen:
            continue
        seen.add(b["id"])
        hits.append({
            "id": b["id"],
            "kind": b.get("kind", "SCOPED_BLOCKER"),
            "penalty": int(b.get("penalty", BARRIER_PENALTIES["SCOPED_BLOCKER"])),
            "scope": b.get("scope"),
            "authority": b.get("authority"),
            "inheritance": "DIRECT" if direct else "COMPOSITIONAL_IMPLICATION",
            "implied_blocked_route": {
                "from_type": bf,
                "to_type": bt,
            },
        })
    return sorted(hits, key=lambda x: (-x["penalty"], x["id"]))


def _progress_readout(authoritative_paths: list[list[str]], shadow_paths: list[list[str]], gaps: list[dict]) -> dict:
    best = gaps[0] if gaps else None
    if authoritative_paths:
        stage = 3
        label = "AUTHORITATIVE_COMPLETE_ROUTE_EXISTS"
        coverage = 100.0
    elif shadow_paths:
        stage = 2
        label = "COMPLETE_ROUTE_EXISTS_WITH_UNSEALED_CANDIDATE"
        coverage = 100.0
    elif best:
        stage = 2
        label = "ONE_INTERFACE_AWAY_ON_BEST_TYPED_ROUTE"
        denom = max(1, int(best.get("complete_path_edges_if_closed", 1)))
        coverage = round(100.0 * int(best.get("proved_context_edges", 0)) / denom, 1)
    else:
        stage = 0
        label = "NO_TYPED_ROUTE_CONTEXT"
        coverage = 0.0

    best_route = None
    if best:
        best_route = {
            "from_type": best["from_type"],
            "to_type": best["to_type"],
            "proved_prefix_edges": best["proved_prefix_edges"],
            "proved_suffix_edges": best["proved_suffix_edges"],
            "proved_context_edges": best["proved_context_edges"],
            "complete_path_edges_if_closed": best["complete_path_edges_if_closed"],
            "barrier_penalty": best["barrier_penalty"],
            "lockpick_score": best["lockpick_score"],
        }

    return {
        "schema": "janus.keymaster.progress_readout.v1",
        "metric_kind": "PROOF_OBLIGATION_COMPLETENESS_NOT_PROBABILITY",
        "stage": stage,
        "stage_max": 5,
        "stage_label": label,
        "stage_ladder": [
            "0_NO_TYPED_ROUTE_CONTEXT",
            "1_TYPED_FRAGMENTS_ONLY",
            "2_SINGLE_GAP_OR_UNSEALED_COMPLETE_ROUTE",
            "3_AUTHORITATIVE_COMPLETE_ROUTE",
            "4_INDEPENDENT_REPLAY_AND_RELEASE_GATES",
            "5_PROOF_AUTHORIZED_RELEASE",
        ],
        "best_route_coverage_percent": coverage,
        "best_route": best_route,
        "authoritative_complete_route_count": len(authoritative_paths),
        "shadow_complete_route_count": len(shadow_paths),
        "p_equals_np_probability": None,
        "p_vs_np": "OPEN",
        "proof_authorized": False,
        "laws": [
            "ROUTE_COVERAGE_PERCENT_IS_NOT_P_EQUALS_NP_PROBABILITY",
            "ONE_MISSING_INTERFACE_DOES_NOT_MEAN_ONE_EASY_LEMMA_REMAINS",
            "COMPLETE_ROUTE_IS_NOT_PROOF_UNTIL_INDEPENDENT_REPLAY_AND_RELEASE_GATES_PASS",
            "P_VS_NP_REMAINS_OPEN_UNTIL_PROOF_AUTHORIZED_RELEASE",
        ],
    }


def _proven_delta(
    previous: dict | None,
    *,
    authoritative_edge_count: int,
    proved_barrier_count: int,
    complete_route_count: int,
    progress: dict,
) -> dict:
    if not isinstance(previous, dict) or previous.get("schema") != SCHEMA:
        return {
            "schema": "janus.keymaster.proven_delta.v1",
            "baseline": "UNAVAILABLE",
            "baseline_report_sha256": None,
            "authoritative_edge_delta": 0,
            "proved_barrier_delta": 0,
            "complete_route_delta": 0,
            "stage_delta": 0,
            "route_coverage_delta_percent": 0.0,
            "mathematical_progress": "UNRESOLVED_BASELINE",
            "proven_advance_event_count": 0,
            "law": "ROUTE_COVERAGE_DELTA_IS_NOT_PROVEN_PROGRESS",
        }

    prev_progress = previous.get("progress_readout") or {}
    edge_delta = authoritative_edge_count - int(previous.get("authoritative_edge_count") or 0)
    barrier_delta = proved_barrier_count - int(previous.get("proved_barrier_count") or previous.get("typed_dynamic_barrier_count") or 0)
    route_delta = complete_route_count - len(previous.get("complete_universal_lifecycle_candidates") or [])
    stage_delta = int(progress.get("stage") or 0) - int(prev_progress.get("stage") or 0)
    coverage_delta = round(
        float(progress.get("best_route_coverage_percent") or 0.0)
        - float(prev_progress.get("best_route_coverage_percent") or 0.0),
        1,
    )
    advances = sum(
        1 for value in (edge_delta, barrier_delta, route_delta, stage_delta)
        if value > 0
    )
    regressions = sum(
        1 for value in (edge_delta, barrier_delta, route_delta, stage_delta)
        if value < 0
    )
    if advances > 0:
        status = "POSITIVE"
    elif regressions > 0:
        status = "REGRESSION_OR_RECLASSIFICATION"
    else:
        status = "ZERO"

    return {
        "schema": "janus.keymaster.proven_delta.v1",
        "baseline": "PREVIOUS_KEYMASTER_REPORT",
        "baseline_report_sha256": previous.get("report_sha256"),
        "authoritative_edge_delta": edge_delta,
        "proved_barrier_delta": barrier_delta,
        "complete_route_delta": route_delta,
        "stage_delta": stage_delta,
        "route_coverage_delta_percent": coverage_delta,
        "mathematical_progress": status,
        "proven_advance_event_count": advances,
        "law": "ROUTE_COVERAGE_DELTA_IS_NOT_PROVEN_PROGRESS",
    }


def load_autonomous_forge(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    obj = load_json(path)
    if obj.get("schema") != "janus.keymaster.autonomous_forge.v1":
        raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_SCHEMA_REJECTED")
    firewall = obj.get("firewall") or {}
    if firewall.get("branch_only_research") is not True:
        raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_BRANCH_BOUNDARY_REJECTED")
    for key in (
        "writes_fundamentum_main",
        "writes_user_research_branch",
        "automatic_merge",
        "automatic_theorem_promotion",
        "automatic_p_equals_np_claim",
        "model_output_is_proof",
        "candidate_algorithm_is_proof",
    ):
        if firewall.get(key) is not False:
            raise RuntimeError(f"KEYMASTER_AUTONOMOUS_FORGE_AUTHORITY_REJECTED:{key}")
    if firewall.get("P_VS_NP") != "OPEN" or firewall.get("D1") != "EMPTY":
        raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_SCIENTIFIC_BOUNDARY_REJECTED")
    if obj.get("keymaster_shadow_admission") is not False:
        raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_SHADOW_ADMISSION_REJECTED")
    candidate = obj.get("candidate")
    if candidate is not None:
        if not isinstance(candidate, dict):
            raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_CANDIDATE_REJECTED")
        if candidate.get("keymaster_shadow_admission") is not False:
            raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_CANDIDATE_SHADOW_REJECTED")
        authority = candidate.get("authority") or {}
        if authority.get("proof") is not False or authority.get("automatic_merge") is not False:
            raise RuntimeError("KEYMASTER_AUTONOMOUS_FORGE_CANDIDATE_AUTHORITY_REJECTED")
    return {
        "schema": obj.get("schema"),
        "status": obj.get("status"),
        "state_sha256": obj.get("state_sha256"),
        "cycle_count": int(obj.get("cycle_count") or 0),
        "candidate_proposal_count": int(obj.get("candidate_proposal_count") or 0),
        "distinct_candidate_count": int(obj.get("distinct_candidate_count") or 0),
        "duplicate_candidate_count": int(obj.get("duplicate_candidate_count") or 0),
        "target": obj.get("target"),
        "search_queries": obj.get("search_queries") or [],
        "selected_donor_count": len(obj.get("selected_donors") or []),
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "title": candidate.get("title"),
            "status": candidate.get("status"),
            "candidate_fingerprint": candidate.get("candidate_fingerprint"),
            "keymaster_shadow_admission": False,
        } if isinstance(candidate, dict) else None,
        "next_action": obj.get("next_action"),
        "keymaster_shadow_admission": False,
        "authority": {
            "proof": False,
            "scientific_claim_promotion": False,
            "automatic_merge": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }


def compose(
    registry: dict,
    scan: dict,
    contract: dict,
    autonomous_forge: dict | None = None,
    previous_report: dict | None = None,
) -> dict:
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
            gap_barriers = _barriers_for_gap(
                barriers,
                src,
                dst,
                authoritative,
                max_depth,
            )
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

    progress = _progress_readout(authoritative_paths, shadow_paths, gaps)
    proved_barrier_count = sum(1 for x in barriers if x.get("status") in PROVED_STATUSES)
    proven_delta = _proven_delta(
        previous_report,
        authoritative_edge_count=len(authoritative),
        proved_barrier_count=proved_barrier_count,
        complete_route_count=len(authoritative_paths),
        progress=progress,
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
        "proved_barrier_count": proved_barrier_count,
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
        "autonomous_forge": autonomous_forge or {
            "status": "NOT_CONNECTED",
            "cycle_count": 0,
            "candidate_proposal_count": 0,
            "distinct_candidate_count": 0,
            "duplicate_candidate_count": 0,
            "target": None,
            "candidate": None,
            "keymaster_shadow_admission": False,
            "authority": {
                "proof": False,
                "scientific_claim_promotion": False,
                "automatic_merge": False,
                "P_VS_NP": "OPEN",
                "D1": "EMPTY",
            },
        },
        "progress_readout": progress,
        "proven_delta": proven_delta,
        "runtime_adoption_policy": {
            "mode": "BEST_ADMITTED_EXECUTABLE_CANDIDATE_FOR_JANUS_INTERNAL_USE",
            "selection_authority": "KEYMASTER_TRUMP_BRIDGE",
            "candidate_use_allowed": True,
            "self_application_allowed": True,
            "self_application_scope": "CANDIDATE_INTERNAL_TASKS_ONLY",
            "proof_authority_granted": False,
            "scientific_claim_promotion_granted": False,
            "direct_main_writeback": False,
            "automatic_merge": False,
            "on_full_authoritative_route": "VERIFY_SOURCE_THEN_SELFTEST_THEN_INDEPENDENT_REPLAY_THEN_RELEASE_GATE",
        },
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
    ap.add_argument("--autonomous-forge")
    ap.add_argument("--previous-report")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load_registry(Path(args.registry))
    contract = load_contract(Path(args.contract))
    scan = scan_fundamentum(Path(args.fundamentum), contract)
    forge = load_autonomous_forge(Path(args.autonomous_forge)) if args.autonomous_forge else None
    previous = load_json(Path(args.previous_report)) if args.previous_report and Path(args.previous_report).exists() else None
    report = compose(registry, scan, contract, forge, previous)

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
        "progress_stage": report["progress_readout"]["stage"],
        "best_route_coverage_percent": report["progress_readout"]["best_route_coverage_percent"],
        "autonomous_forge_status": report["autonomous_forge"]["status"],
        "autonomous_forge_cycles": report["autonomous_forge"]["cycle_count"],
        "autonomous_forge_distinct_candidates": report["autonomous_forge"]["distinct_candidate_count"],
        "mathematical_progress": report["proven_delta"]["mathematical_progress"],
        "proven_advance_event_count": report["proven_delta"]["proven_advance_event_count"],
        "authoritative_edge_delta": report["proven_delta"]["authoritative_edge_delta"],
        "proved_barrier_delta": report["proven_delta"]["proved_barrier_delta"],
        "D1": report["firewall"]["D1"],
        "P_VS_NP": report["firewall"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
