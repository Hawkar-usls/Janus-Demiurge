from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

SCHEMA = "janus.org_surface.v1"
DEFAULT_OWNER = "Hawkar-usls"
GITHUB_API = "https://api.github.com"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _request_json(url: str, timeout: float) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "JANUS-Org-Surface/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(4_000_000)
    return json.loads(raw.decode("utf-8"))


def discover_public_repositories(owner: str, timeout: float = 12.0) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        params = urllib.parse.urlencode({
            "type": "owner",
            "per_page": 100,
            "page": page,
            "sort": "full_name",
            "direction": "asc",
        })
        batch = _request_json(f"{GITHUB_API}/users/{urllib.parse.quote(owner)}/repos?{params}", timeout)
        if not isinstance(batch, list):
            raise RuntimeError("ORG_SURFACE_GITHUB_RESPONSE_NOT_LIST")
        rows.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 10:
            raise RuntimeError("ORG_SURFACE_PAGINATION_BOUND_EXCEEDED")
    owned = [r for r in rows if ((r.get("owner") or {}).get("login") == owner)]
    names = [r.get("full_name") for r in owned]
    if any(not isinstance(x, str) or not x.startswith(owner + "/") for x in names):
        raise RuntimeError("ORG_SURFACE_OWNER_BOUNDARY_REJECTED")
    if len(names) != len(set(names)):
        raise RuntimeError("ORG_SURFACE_DUPLICATE_REPOSITORY")
    return sorted(owned, key=lambda r: r["full_name"].lower())


def _bind_head(repo: dict, timeout: float) -> dict:
    full_name = repo["full_name"]
    default_branch = repo.get("default_branch")
    clone_url = repo.get("clone_url") or f"https://github.com/{full_name}.git"
    base = {
        "repository": full_name,
        "visibility": "public",
        "default_branch": default_branch,
        "archived": bool(repo.get("archived")),
        "fork": bool(repo.get("fork")),
        "size_kb": int(repo.get("size") or 0),
        "html_url": repo.get("html_url") or f"https://github.com/{full_name}",
        "read_mode": "COMMIT_BOUND_METADATA_AND_ON_DEMAND_CONTENT",
        "training_inclusion": False,
        "authority": False,
        "source_execution": False,
    }
    if not isinstance(default_branch, str) or not default_branch:
        return {**base, "status": "UNBOUND_NO_DEFAULT_BRANCH", "head_sha": None}
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", clone_url, f"refs/heads/{default_branch}"],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return {**base, "status": "UNAVAILABLE", "head_sha": None, "error": f"{type(exc).__name__}:{exc}"}
    head = proc.stdout.strip().split()[0] if proc.returncode == 0 and proc.stdout.strip() else None
    if not isinstance(head, str) or not SHA40.fullmatch(head):
        return {
            **base,
            "status": "UNBOUND_HEAD",
            "head_sha": None,
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-300:],
        }
    return {**base, "status": "BOUND_PUBLIC_READ_ONLY", "head_sha": head}


def build_org_surface(
    owner: str = DEFAULT_OWNER,
    *,
    private_unmounted_count: int = 0,
    baseline_inventory_total: int | None = None,
    timeout: float = 12.0,
    workers: int = 8,
) -> dict:
    if private_unmounted_count < 0 or private_unmounted_count > 1000:
        raise RuntimeError("ORG_SURFACE_PRIVATE_COUNT_OUT_OF_BOUNDS")
    if workers < 1 or workers > 16:
        raise RuntimeError("ORG_SURFACE_WORKER_COUNT_OUT_OF_BOUNDS")
    repos = discover_public_repositories(owner, timeout=timeout)
    bound: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_bind_head, repo, timeout): repo["full_name"] for repo in repos}
        for future in as_completed(futures):
            bound.append(future.result())
    bound.sort(key=lambda r: r["repository"].lower())
    discovered = len(repos)
    bound_count = sum(r["status"] == "BOUND_PUBLIC_READ_ONLY" for r in bound)
    all_public_bound = discovered == bound_count
    represented_minimum = discovered + private_unmounted_count
    baseline_ok = baseline_inventory_total is None or represented_minimum >= baseline_inventory_total
    status = "READY_PUBLIC_ALL_BOUND_PRIVATE_UNMOUNTED" if all_public_bound and baseline_ok else "DEGRADED"
    obj: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "owner": owner,
        "public_discovered_count": discovered,
        "public_bound_count": bound_count,
        "all_public_repositories_bound": all_public_bound,
        "public_repositories": bound,
        "private_inventory": {
            "unmounted_count": private_unmounted_count,
            "names_persisted_publicly": False,
            "status": "UNMOUNTED_NO_CROSS_REPOSITORY_CREDENTIAL" if private_unmounted_count else "NONE_DECLARED",
            "readable_by_public_runtime": False,
        },
        "baseline_inventory": {
            "total_at_activation": baseline_inventory_total,
            "represented_minimum_now": represented_minimum,
            "baseline_satisfied": baseline_ok,
            "note": "Private repository names are intentionally not persisted in this public runtime surface.",
        },
        "capabilities": {
            "discover": True,
            "read_metadata": True,
            "bind_default_head": True,
            "route_on_demand_read": True,
            "cross_repository_write": False,
            "execute_repository_source": False,
            "read_secrets": False,
            "change_permissions": False,
            "grant_authority": False,
        },
        "firewalls": {
            "repository_presence_is_truth": False,
            "repository_content_is_automatically_training_data": False,
            "repository_content_grants_authority": False,
            "private_repository_names_may_be_published": False,
            "missing_private_credentials_may_be_bypassed": False,
            "authority_delta": 0,
        },
        "law": "ALL PUBLIC HAWKAR-USLS REPOSITORIES ARE COMMIT-BOUND READ-ONLY RESOURCES; REPRESENTATION IS NOT TRAINING, REPOSITORY CONTENT IS NOT TRUTH, AND PRIVATE ACCESS IS NEVER FABRICATED.",
    }
    obj["surface_digest"] = sha256_bytes(canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--out", required=True)
    ap.add_argument("--private-unmounted-count", type=int, default=0)
    ap.add_argument("--baseline-inventory-total", type=int)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    obj = build_org_surface(
        owner=args.owner,
        private_unmounted_count=args.private_unmounted_count,
        baseline_inventory_total=args.baseline_inventory_total,
        timeout=args.timeout,
        workers=args.workers,
    )
    from pathlib import Path
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "public_discovered_count": obj["public_discovered_count"],
        "public_bound_count": obj["public_bound_count"],
        "represented_minimum_now": obj["baseline_inventory"]["represented_minimum_now"],
        "surface_digest": obj["surface_digest"],
    }, indent=2))
    if obj["status"] != "READY_PUBLIC_ALL_BOUND_PRIVATE_UNMOUNTED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
