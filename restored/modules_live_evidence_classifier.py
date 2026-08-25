from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable

SCHEMA = "janus.modules_live.evidence_roster.v1"

TIER = {
    "REGISTRY_LABEL": 0,
    "INDEX_OR_HASH_PRESENCE": 1,
    "MIGRATION_SELECTED": 2,
    "LIVE_DIRECTORY_FILE_PRESENCE": 3,
    "BOOT_ATTEMPTED": 4,
    "LIVE_MODULE_ONLINE": 5,
    "LIVE_MODULE_SUCCESS": 6,
}
FAILURE_KINDS = {"LIVE_MODULE_ERROR", "BOOT_ERROR", "IMPORT_ERROR"}


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _module_key(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("module name is required")
    name = raw.rsplit("/", 1)[-1]
    if name.casefold().endswith(".py"):
        name = name[:-3]
    if not name:
        raise ValueError("invalid module name")
    return name.casefold()


def build_roster(evidence: Iterable[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("evidence items must be mappings")
        key = _module_key(item.get("module"))
        kind = str(item.get("kind", "")).strip().upper()
        if kind not in TIER and kind not in FAILURE_KINDS:
            raise ValueError(f"unsupported evidence kind: {kind}")
        normalized = {
            "module": key,
            "kind": kind,
            "source": item.get("source"),
            "timestamp": item.get("timestamp"),
            "source_sha256": item.get("source_sha256"),
            "detail": item.get("detail"),
        }
        grouped.setdefault(key, []).append(normalized)

    modules = []
    for key in sorted(grouped):
        events = grouped[key]
        positive = [e for e in events if e["kind"] in TIER]
        highest_kind = max((e["kind"] for e in positive), key=lambda k: TIER[k], default=None)
        errors = [e for e in events if e["kind"] in FAILURE_KINDS]

        if highest_kind == "LIVE_MODULE_SUCCESS":
            state = "LIVE_SUCCESS_CONFIRMED"
        elif errors and highest_kind in {"BOOT_ATTEMPTED", "LIVE_MODULE_ONLINE"}:
            state = "RUNTIME_FAILURE_CONFIRMED"
        elif highest_kind == "LIVE_MODULE_ONLINE":
            state = "LIVE_ONLINE_CONFIRMED"
        elif highest_kind == "BOOT_ATTEMPTED":
            state = "BOOT_ATTEMPTED_ONLY"
        elif highest_kind == "LIVE_DIRECTORY_FILE_PRESENCE":
            state = "LIVE_DIRECTORY_FILE_ONLY"
        elif highest_kind == "MIGRATION_SELECTED":
            state = "MIGRATION_SELECTED_ONLY"
        elif highest_kind == "INDEX_OR_HASH_PRESENCE":
            state = "INDEX_OR_HASH_PRESENCE_ONLY"
        elif highest_kind == "REGISTRY_LABEL":
            state = "REGISTRY_ONLY"
        elif errors:
            state = "FAILURE_EVIDENCE_WITHOUT_POSITIVE_TIER"
        else:
            state = "NO_EVIDENCE"

        modules.append({
            "module": key,
            "state": state,
            "highest_positive_kind": highest_kind,
            "highest_positive_tier": None if highest_kind is None else TIER[highest_kind],
            "failure_evidence_count": len(errors),
            "evidence_kind_counts": dict(sorted(Counter(e["kind"] for e in events).items())),
            "events": events,
        })

    body = {
        "schema": SCHEMA,
        "status": "EVIDENCE_CLASSIFICATION_ONLY",
        "modules": modules,
        "module_count": len(modules),
        "authority": {
            "loads_modules": False,
            "executes_modules": False,
            "writes_modules_live": False,
            "promotes_modules": False,
            "deletes_or_quarantines_modules": False,
        },
        "laws": [
            "MIGRATION_SELECTION_NE_RUNTIME_SUCCESS",
            "LIVE_DIRECTORY_FILE_PRESENCE_NE_LIVE_MODULE_ONLINE",
            "LIVE_MODULE_ONLINE_NE_LIVE_MODULE_SUCCESS",
            "FAILURE_RECEIPT_MUST_NOT_BE_ERASED_BY_LATER_SUCCESS",
            "EVIDENCE_CLASSIFICATION_NE_RUNTIME_AUTHORITY",
        ],
    }
    body["roster_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
