"""JANUS Cooling Tower: bounded, read-only asynchronous ecosystem observer.

A circuit that circulates *evidence*, not arbitrary downloaded Python modules.
Use existing authenticated conductor/activator gates for any real dispatch.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

OWNER = "Hawkar-usls"
ROOT = "https://api.github.com"
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "JANUS-Cooling-Tower/1.0",
    "X-GitHub-Api-Version": "2022-11-28",
}
CRITICAL = {
    "Janus_Genesis": "janus-g1-g20-causal-one-run-r0.yml",
    "Janus-Demiurge": "janus-demiurge-conductor.yml",
    "janus-meta-registry": "janus-autonomous-coder.yml",
    "Hrain": "hrain-topa-continuous-semantic-flywheel.yml",
    "TOPA": "spider-github-actions-scheduler-s3.yml",
    "janus-lapis": "universal-beetle-hourly.yml",
    "janus-distributed-ai-swarm": "validate-brain-five-face-bus.yml",
    "Janus-Fundamentum": "validate-registry.yml",
    "Demi_Head": "unified-memory-v2-e2e.yml",
    "AIFC": "validate-aifc-internal-terminal-handoff-v1.yml",
    "SCOBY-D0": "invariants.yml",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def get_json(path, *, token="", opener=urllib.request.urlopen):
    if not path.startswith("/repos/" + OWNER + "/") and not path.startswith("/users/" + OWNER + "/repos"):
        raise ValueError("GITHUB_OWNER_BOUNDARY")
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(ROOT + path, headers=headers)
    try:
        with opener(request, timeout=12) as response:
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError("GITHUB_RESPONSE_TOO_LARGE")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP_{exc.code}"}
    except (OSError, TimeoutError, ValueError) as exc:
        return {"error": type(exc).__name__}


def discover(token):
    items = []
    for page in (1, 2):
        result = get_json(f"/users/{OWNER}/repos?per_page=100&page={page}&type=owner", token=token)
        if not isinstance(result, list):
            raise RuntimeError("INVENTORY_FETCH_FAILED")
        items.extend(result)
        if len(result) < 100:
            break
    names = sorted({r["name"] for r in items if
                    r.get("owner", {}).get("login", "").lower() == OWNER.lower()
                    and r.get("private") is False and r.get("archived") is False
                    and NAME.fullmatch(r.get("name", ""))})
    if len(names) < 30:
        raise RuntimeError("INVENTORY_INCOMPLETE_FAIL_CLOSED")
    return names


def check_one(name, token, workflow=None):
    if not NAME.fullmatch(name):
        raise ValueError("UNTRUSTED_REPOSITORY_NAME")
    if workflow is not None and not re.fullmatch(r"[A-Za-z0-9_.-]+\.ya?ml", workflow):
        raise ValueError("UNTRUSTED_WORKFLOW_NAME")
    if workflow:
        path = f"/repos/{OWNER}/{name}/actions/workflows/{workflow}/runs?per_page=1"
    else:
        path = f"/repos/{OWNER}/{name}/actions/runs?per_page=8"
    payload = get_json(path, token=token)
    if not isinstance(payload, dict) or payload.get("error"):
        return {"repo": name, "workflow": workflow, "health": "UNKNOWN",
                "error": payload.get("error", "MALFORMED") if isinstance(payload, dict) else "MALFORMED"}
    runs = payload.get("workflow_runs", [])
    if not isinstance(runs, list):
        return {"repo": name, "workflow": workflow, "health": "UNKNOWN", "error": "MALFORMED_RUNS"}
    latest = next((x for x in runs if workflow or x.get("event") != "dynamic"), None)
    if latest is None:
        return {"repo": name, "workflow": workflow, "health": "UNKNOWN", "error": "NO_WORKFLOW_RUN"}
    status = latest.get("status")
    conclusion = latest.get("conclusion")
    health = "PASS" if status == "completed" and conclusion == "success" else (
        "FAIL" if status == "completed" and conclusion == "failure" else "UNKNOWN")
    return {"repo": name, "workflow": workflow, "health": health,
            "run_id": latest.get("id"), "head_sha": latest.get("head_sha"),
            "event": latest.get("event"), "status": status,
            "conclusion": conclusion, "created_at": latest.get("created_at")}


async def circulation(organs, probe, *, rounds=2, concurrency=6):
    """Isolate every organ failure; no unbounded recursion, dispatch, or global abort."""
    if not 1 <= rounds <= 2 or not 1 <= concurrency <= 8:
        raise ValueError("BOUNDED_CIRCULATION_ONLY")
    if len(organs) != len(set(organs)) or len(organs) > 100:
        raise ValueError("DUPLICATE_OR_OVERBROAD_ORGANS")
    sem = asyncio.Semaphore(concurrency)
    snapshots = []
    for cycle in range(1, rounds + 1):
        async def visit(organ):
            async with sem:
                try:
                    result = await asyncio.wait_for(probe(organ), timeout=18)
                    if not isinstance(result, dict) or result.get("health") not in ("PASS", "FAIL", "UNKNOWN"):
                        raise ValueError("UNTRUSTED_PROBE_RECEIPT")
                    return {"organ": organ, **result}
                except Exception as exc:
                    # A dead organ must not take down the sibling modules.
                    return {"organ": organ, "health": "UNKNOWN",
                            "error": type(exc).__name__, "isolated": True}
        rows = await asyncio.gather(*(visit(item) for item in organs))
        snapshots.append({"cycle": cycle, "observed_at": now(), "records": rows,
                          "passed": sum(r["health"] == "PASS" for r in rows),
                          "failed": sum(r["health"] == "FAIL" for r in rows),
                          "unknown": sum(r["health"] == "UNKNOWN" for r in rows)})
    return snapshots


async def live(output, *, token="", expected_min=30):
    names = await asyncio.to_thread(discover, token)
    organs = [(name, None) for name in names]
    for name, workflow in CRITICAL.items():
        if name in names:
            organs.append((name, workflow))

    async def probe(organ):
        return await asyncio.to_thread(check_one, organ[0], token, organ[1])

    shots = await circulation(organs, probe)
    important = [record for shot in shots for record in shot["records"] if record["organ"][1] is not None]
    blockers = [record for record in important if record["health"] != "PASS"]
    isolated = [record for shot in shots for record in shot["records"] if record.get("isolated")]
    count = len(names)
    gate = "HOLD" if count < expected_min or blockers or isolated else "PASS_OBSERVATION_ONLY"
    result = {
        "schema": "janus.cooling_tower.async_microkernel.v1",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "observed_at": now(),
        "public_repositories": count,
        "private_repositories_excluded": True,
        "bounded_rounds": 2,
        "max_concurrency": 6,
        "critical_workflows": len(CRITICAL),
        "observations": shots,
        "critical_blocker_count": len(blockers),
        "isolated_probe_failure_count": len(isolated),
        "gate": gate,
        "full_autonomy_accepted": False,
        "self_trigger_count": 0,
        "new_workflow_dispatches": 0,
        "new_module_executions": 0,
        "production_code_writes": 0,
        "external_effects": "DENIED",
        "safe_extension_path": "CURATED_SOURCE -> LICENSE -> STATIC_AUDIT -> ISOLATED_TEST -> INDEPENDENT_VERIFIER -> REVIEWED_PROMOTION",
        "proof_rule": "A successful probe does not imply a functioning model, independent ACK, or scientific truth.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                     ("public_repositories", "bounded_rounds", "critical_blocker_count",
                      "isolated_probe_failure_count", "gate")}, sort_keys=True))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    asyncio.run(live(args.out, token=os.environ.get("GH_TOKEN", "")))


if __name__ == "__main__":
    main()
