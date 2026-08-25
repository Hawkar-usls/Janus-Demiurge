from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable

SCHEMA = "janus.modules_live_migration_plan.v1"

HISTORICAL_EXODUS_ELITE = (
    "genesis.py",
    "blood_collapse.py",
    "hephaestus.py",
    "amor.py",
    "simulation_chamber.py",
    "lineage.py",
    "database_controller.py",
)


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _basename(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("module entry must be non-empty text")
    return os.path.basename(value.strip().replace("\\", "/"))


def classify_roster(entries: Iterable[str], elite_profile: Iterable[str] = HISTORICAL_EXODUS_ELITE) -> dict[str, Any]:
    elite = {_basename(name).lower() for name in elite_profile}
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    for raw in entries:
        name = _basename(raw)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        if not key.endswith(".py") or key.startswith("_"):
            classification = "IGNORE_NON_LIVE_SOURCE"
            reason = "not an ordinary public Python live-module candidate"
        elif key.startswith("gen_") or key.startswith("plugin_gen_"):
            classification = "GENERATED_QUARANTINE"
            reason = "generated module requires individual audit and promotion"
        elif key in elite:
            classification = "SELECT_FOR_PROBATION"
            reason = "selected by historical EXODUS elite profile; runtime success not implied"
        else:
            classification = "HOLD_REVIEW"
            reason = "not selected by historical EXODUS profile; preserve for review rather than delete"

        rows.append({"module": name, "classification": classification, "reason": reason})

    rows.sort(key=lambda row: row["module"].lower())
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "MIGRATION_CLASSIFICATION_PLAN_ONLY",
        "historical_profile": "EXODUS_ELITE_SQUAD",
        "historical_elite": list(HISTORICAL_EXODUS_ELITE),
        "entries": rows,
        "counts": counts,
        "authority": {
            "copies_files": False,
            "moves_files": False,
            "renames_directories": False,
            "deletes_files_or_directories": False,
            "loads_modules": False,
            "promotes_to_live": False,
        },
        "laws": [
            "MIGRATION_SELECTION_NE_RUNTIME_SUCCESS",
            "SELECT_FOR_PROBATION_NE_LIVE_AUTHORITY",
            "QUARANTINE_NE_DELETE",
            "HOLD_REVIEW_NE_GARBAGE",
            "PLAN_NE_FILESYSTEM_AUTHORITY",
            "GENERATED_MODULE_REQUIRES_INDIVIDUAL_PROMOTION",
        ],
    }
    body["plan_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
