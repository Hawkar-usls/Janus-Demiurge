#!/usr/bin/env python3
"""Normalize JANUS Scout runtime health without confusing snapshot truth with model synthesis.

The Scout engine deliberately fails closed when Copilot synthesis is unavailable.
A deterministic Git repository snapshot can still have succeeded. This module
keeps those two planes separate instead of reporting successful snapshots as
"0 observed" merely because the model plane degraded.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scout_swarm" / "SCOUT_SWARM_MANIFEST-v1.json"
STATUS = ROOT / "scout_swarm" / "state" / "SCOUT_SWARM_STATUS-v1.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def snapshot_observed(report: Dict[str, Any]) -> bool:
    snapshot = report.get("repository_snapshot")
    return (
        isinstance(snapshot, dict)
        and bool(str(snapshot.get("target_commit") or "").strip())
        and not snapshot.get("snapshot_error")
    )


def model_synthesis_ok(report: Dict[str, Any]) -> bool:
    return report.get("status") == "OBSERVED_REPOSITORY_STATE" and not report.get("model_error")


def classify_reports(reports: Dict[str, Dict[str, Any]], expected: Iterable[str]) -> Dict[str, Any]:
    expected_ids = list(expected)
    received = [aid for aid in expected_ids if aid in reports]
    missing = [aid for aid in expected_ids if aid not in reports]
    snapshot_ok = [aid for aid in received if snapshot_observed(reports[aid])]
    model_ok = [aid for aid in received if model_synthesis_ok(reports[aid])]
    model_degraded = [aid for aid in snapshot_ok if aid not in model_ok]
    target_unavailable = [aid for aid in received if aid not in snapshot_ok]
    any_degraded = [aid for aid in expected_ids if aid in set(model_degraded + target_unavailable)]

    if not received:
        status = "FAILED_NO_REPORTS"
    elif len(received) == len(expected_ids) and len(snapshot_ok) == len(expected_ids):
        status = "LIVE_17_OF_17" if len(model_ok) == len(expected_ids) else "LIVE_17_OF_17_SNAPSHOTS__MODEL_SYNTHESIS_DEGRADED"
    else:
        status = "DEGRADED_PARTIAL"

    return {
        "status": status,
        "agents_expected": len(expected_ids),
        "agents_received": len(received),
        "agents_observed": len(snapshot_ok),
        "agents_observed_semantics": "SUCCESSFUL_DETERMINISTIC_REPOSITORY_SNAPSHOT",
        "agents_snapshot_observed": len(snapshot_ok),
        "agents_snapshot_observed_ids": snapshot_ok,
        "agents_model_synthesis_ok": len(model_ok),
        "agents_model_synthesis_ok_ids": model_ok,
        "agents_model_synthesis_degraded": model_degraded,
        "agents_target_unavailable": target_unavailable,
        "agents_missing": missing,
        "agents_degraded": any_degraded,
        "agents_degraded_semantics": "DEGRADED_IN_ANY_RUNTIME_PLANE",
        "runtime_planes": {
            "repository_snapshot": {
                "observed": len(snapshot_ok),
                "expected": len(expected_ids),
                "empirical_scope": "READ_ONLY_GIT_REPOSITORY_STATE"
            },
            "model_synthesis": {
                "ok": len(model_ok),
                "degraded": len(model_degraded),
                "model_failure_does_not_erase_snapshot": True
            },
            "target_transport": {
                "unavailable": len(target_unavailable)
            }
        },
        "world_truth": False,
        "model_output_is_independent_evidence": False
    }


def load_run_reports(run_id: str) -> Dict[str, Dict[str, Any]]:
    run_dir = ROOT / "scout_swarm" / "outbox" / "runs" / str(run_id)
    reports: Dict[str, Dict[str, Any]] = {}
    if not run_dir.exists():
        return reports
    for path in run_dir.glob("SCOUT_*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        aid = obj.get("agent_id") if isinstance(obj, dict) else None
        if isinstance(aid, str):
            reports[aid] = obj
    return reports


def patch_json(path: Path, health: Dict[str, Any], run_id: str) -> None:
    if not path.exists():
        return
    obj = json.loads(path.read_text(encoding="utf-8"))
    if str(obj.get("run_id") or run_id) != str(run_id):
        raise ValueError(f"RUN_ID_MISMATCH:{path}")
    preserved = {
        key: obj.get(key)
        for key in ("schema", "run_id", "control_sha", "updated_at_utc", "agent_spiral_turns", "agent_ascent_status", "aura_oracle_agent", "response_repository", "evolution_model", "write_authority_over_targets")
        if key in obj
    }
    obj.update(health)
    obj.update({k: v for k, v in preserved.items() if v is not None})
    obj["health_schema"] = "janus.demiurge.scout_runtime_health_planes.v1"
    obj["health_normalized_at_utc"] = utc_now()
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_run(run_id: str) -> Dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = [a["id"] for a in manifest["agents"]]
    reports = load_run_reports(run_id)
    health = classify_reports(reports, expected)
    patch_json(STATUS, health, run_id)
    patch_json(ROOT / "scout_swarm" / "outbox" / "runs" / str(run_id) / "SWARM_SUMMARY.json", health, run_id)
    return health


def self_test() -> None:
    expected = [f"SCOUT_{i:02d}" for i in range(17)]
    reports = {
        aid: {
            "agent_id": aid,
            "status": "DEGRADED_MODEL_UNAVAILABLE",
            "repository_snapshot": {"target_commit": f"sha-{i}"},
            "model_error": "RuntimeError:model unavailable"
        }
        for i, aid in enumerate(expected)
    }
    health = classify_reports(reports, expected)
    assert health["agents_observed"] == 17
    assert health["agents_model_synthesis_ok"] == 0
    assert len(health["agents_model_synthesis_degraded"]) == 17
    assert health["status"] == "LIVE_17_OF_17_SNAPSHOTS__MODEL_SYNTHESIS_DEGRADED"

    reports[expected[-1]] = {
        "agent_id": expected[-1],
        "status": "DEGRADED_TARGET_UNAVAILABLE",
        "repository_snapshot": {"snapshot_error": "clone failed"}
    }
    health = classify_reports(reports, expected)
    assert health["agents_observed"] == 16
    assert health["agents_target_unavailable"] == [expected[-1]]
    assert health["status"] == "DEGRADED_PARTIAL"
    print("JANUS_SCOUT_OBSERVATION_HEALTH_PLANES_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.run_id:
        parser.error("--run-id is required unless --self-test is used")
    health = normalize_run(args.run_id)
    print(json.dumps(health, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
