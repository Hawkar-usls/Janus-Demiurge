"""JANUS Nexus/Conductor legacy ABI adapter, explicit-callback probation only.

Historical evidence: E:/Janus_Titan/janus_core.py Nexus discovered modules
and called run(core); E:/Janus_Titan/modules/mod_conductor.py launched async
mod_*.py by PRIORITY. Neither historical source is imported here.
This adapter builds a stable dependency/priority plan and may run ONLY
previously constructed trusted callables after explicit operator approval.
It is NOT a process sandbox, code-admission authority or production actuator.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
from collections import defaultdict

SCHEMA = "janus.demiurge.legacy_nexus_conductor_plan.v1"
RECEIPT_SCHEMA = "janus.demiurge.legacy_nexus_conductor_probation.v1"
NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
CAPABILITIES = frozenset(("READ_GRAPH", "READ_MEMORY", "PURE_COMPUTE"))
MAX_MODULES = 64


def canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_plan(records, *, intent=""):
    """No filesystem search, code imports, runtime initialization, or writes."""
    if not isinstance(records, list) or len(records) > MAX_MODULES:
        return {"schema": SCHEMA, "status": "HOLD", "reasons": ["ROSTER_BOUND_HOLD"], "order": []}
    reasons = []
    by_name = {}
    for row in records:
        if not isinstance(row, dict):
            reasons.append("INVALID_ENTRY")
            continue
        name, source_sha = row.get("id"), row.get("source_sha256")
        deps = row.get("dependencies", [])
        caps = row.get("capabilities", [])
        mode = row.get("mode")
        priority = row.get("priority", 10)
        if (not isinstance(name, str) or not NAME.fullmatch(name)
                or name in by_name):
            reasons.append("INVALID_OR_DUPLICATE_ID")
            continue
        if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
            reasons.append("MISSING_OR_BAD_SOURCE_SHA:" + name)
            continue
        if mode not in ("PLUGIN", "SERVICE"):
            reasons.append("INVALID_MODULE_MODE:" + name)
            continue
        if type(priority) is not int or not 0 <= priority <= 100:
            reasons.append("INVALID_PRIORITY:" + name)
            continue
        if (not isinstance(deps, list) or len(deps) > MAX_MODULES
                or not all(isinstance(d, str) and NAME.fullmatch(d) for d in deps)
                or len(deps) != len(set(deps))):
            reasons.append("BAD_DEPENDENCIES:" + name)
            continue
        if (not isinstance(caps, list) or len(caps) != len(set(map(str, caps)))
                or not all(isinstance(c, str) and c in CAPABILITIES for c in caps)):
            reasons.append("CAPABILITY_FIREWALL:" + name)
            continue
        if row.get("reviewed") is not True or row.get("synthetic_only") is not True:
            reasons.append("NO_REVIEWED_PROBATION_ADMISSION:" + name)
            continue
        by_name[name] = {
            "id": name, "source_sha256": source_sha, "mode": mode,
            "priority": priority, "dependencies": sorted(deps),
            "capabilities": sorted(caps), "reviewed": True, "synthetic_only": True
        }

    if reasons:
        return {"schema": SCHEMA, "status": "HOLD", "reasons": sorted(set(reasons)), "order": []}
    child = defaultdict(list)
    degree = {name: 0 for name in by_name}
    for name, row in by_name.items():
        for dep in row["dependencies"]:
            if dep not in by_name:
                reasons.append("MISSING_DEPENDENCY:" + name)
            else:
                child[dep].append(name)
                degree[name] += 1
    if reasons:
        return {"schema": SCHEMA, "status": "HOLD", "reasons": sorted(set(reasons)), "order": []}
    order = []
    ready = [n for n, d in degree.items() if not d]
    while ready:
        ready.sort(key=lambda n: (by_name[n]["priority"], n))
        name = ready.pop(0)
        order.append(name)
        for next_name in child[name]:
            degree[next_name] -= 1
            if degree[next_name] == 0:
                ready.append(next_name)
    if len(order) != len(by_name):
        return {"schema": SCHEMA, "status": "HOLD", "reasons": ["DEPENDENCY_CYCLE"], "order": []}
    # Historical Nexus used a label/prophesy token match and random fallback.
    # Recreate the affinity, but make the fallback deterministic and auditable.
    words = set(re.findall(r"[a-z0-9]+", str(intent).lower()[:256]))
    plugins = [n for n in order if by_name[n]["mode"] == "PLUGIN"]
    selected = min(plugins, key=lambda n: (
        -len(words.intersection(n.split("_"))), by_name[n]["priority"], n
    )) if plugins else None
    manifest = {"modules": [by_name[n] for n in sorted(by_name)],
                "order": order, "selected_plugin": selected}
    return {
        "schema": SCHEMA, "status": "PLAN_ONLY",
        **manifest,
        "plan_sha256": hashlib.sha256(canonical_bytes(manifest)).hexdigest(),
        "authority": {
            "imports_legacy_files": False, "uses_exec": False,
            "auto_discovers_modules": False, "activates_services": False,
            "auto_installs_generated_code": False, "grants_runtime_admission": False
        }
    }


async def probation_run(plan, *, target, handlers, core_port,
                        operator_approved=False, timeout_seconds=1.0):
    """Explicitly run already-trusted async callbacks; NEVER import a .py file.

    The caller is responsible for constructing trusted handlers and a synthetic
    core_port. Not an operating-system security boundary.
    """
    if not operator_approved:
        raise PermissionError("OPERATOR_PROBATION_APPROVAL_REQUIRED")
    if plan.get("schema") != SCHEMA or plan.get("status") != "PLAN_ONLY":
        raise ValueError("VALID_PLAN_REQUIRED")
    if type(timeout_seconds) not in (int, float) or not 0.01 <= timeout_seconds <= 5.0:
        raise ValueError("TIMEOUT_BOUND_HOLD")
    rows = {r["id"]: r for r in plan["modules"]}
    if target not in rows:
        raise ValueError("TARGET_NOT_ADMITTED")
    if not isinstance(handlers, dict):
        raise ValueError("EXPLICIT_TRUSTED_HANDLERS_REQUIRED")
    visited = set()

    def require(name):
        if name in visited:
            return
        visited.add(name)
        for dep in rows[name]["dependencies"]:
            require(dep)

    require(target)
    ordered = [n for n in plan["order"] if n in visited]
    outcomes = {}
    for name in ordered:
        if any(outcomes.get(dep) != "PROBATION_CALLBACK_COMPLETED"
               for dep in rows[name]["dependencies"]):
            outcomes[name] = "HOLD_FAILED_DEPENDENCY"
            continue
        fn = handlers.get(name)
        if not inspect.iscoroutinefunction(fn):
            outcomes[name] = "HOLD_TRUSTED_ASYNC_HANDLER_MISSING"
            continue
        try:
            # Bounded single-step call. Services cannot detach tasks or persist
            # safely here; only a trusted, externally restricted mock core.
            await asyncio.wait_for(fn(core_port), timeout=timeout_seconds)
            outcomes[name] = "PROBATION_CALLBACK_COMPLETED"
        except asyncio.TimeoutError:
            outcomes[name] = "PROBATION_TIMEOUT"
        except Exception:
            outcomes[name] = "PROBATION_CALLBACK_ERROR"
    return {
        "schema": RECEIPT_SCHEMA, "status": "SYNTHETIC_PROBATION_ONLY",
        "source_plan_sha256": plan["plan_sha256"],
        "target": target, "order": ordered, "outcomes": outcomes,
        "authority": {
            "model_promoted": False, "production_service_started": False,
            "github_workflow_dispatched": False, "legacy_file_imported": False,
            "security_sandbox_proven": False, "scientific_success_claimed": False
        }
    }
