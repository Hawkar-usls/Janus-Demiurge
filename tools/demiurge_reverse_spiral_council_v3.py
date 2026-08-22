#!/usr/bin/env python3
"""JANUS HA10 reverse council v3: monotonic evidence-progress guard.

Historical v1/v2 implementations remain byte-preserved. V3 consumes explicit
nonrepeatable gate IDs from the current council input so a later successful or
bounded provenance pass cannot accidentally re-select an older gate whose access
condition is still known to be unchanged. Suppression is advisory routing only;
it creates no scientific evidence and never changes frozen results.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

V2_PATH = Path(__file__).with_name("demiurge_reverse_spiral_council_v2.py")
_SPEC = importlib.util.spec_from_file_location("demiurge_reverse_spiral_council_v2_frozen", V2_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("CANNOT_LOAD_COUNCIL_V2")
v2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2)
v1 = v2.v1


def explicit_nonrepeatable(payload: dict[str, Any]) -> list[str]:
    guard = payload.get("progress_guard") if isinstance(payload.get("progress_guard"), dict) else {}
    raw = guard.get("nonrepeatable_gate_ids") or []
    if not isinstance(raw, list):
        raise ValueError("NONREPEATABLE_GATE_IDS_MUST_BE_LIST")
    candidate_ids = {
        str(row["gate_id"])
        for row in v1.load_mission().get("candidate_gates", [])
        if isinstance(row, dict) and row.get("gate_id")
    }
    out: list[str] = []
    for item in raw:
        gate = str(item)
        if gate not in candidate_ids:
            raise ValueError(f"UNKNOWN_NONREPEATABLE_GATE:{gate}")
        if gate not in out:
            out.append(gate)
    return out


def suppression_reason(payload: dict[str, Any], gate_id: str) -> str:
    guard = payload.get("progress_guard") if isinstance(payload.get("progress_guard"), dict) else {}
    reasons = guard.get("reasons") if isinstance(guard.get("reasons"), dict) else {}
    reason = str(reasons.get(gate_id) or "No changed evidence/access condition is declared for this already-consumed gate.")
    return reason[:1200]


def run_role(role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    vote = v2.run_role(role_id, payload)
    suppressed = explicit_nonrepeatable(payload)
    applied: list[str] = []
    for gate in suppressed:
        row = next((r for r in vote["ranked_candidates"] if r.get("gate_id") == gate), None)
        if row is None:
            continue
        row["score"] = -850.0
        row["reason"] = (
            "iNAIHR v3 progress guard: do not immediately revisit this already-consumed "
            "gate without a declared evidence/access change. " + suppression_reason(payload, gate)
        )
        applied.append(gate)
    # 119-Hz veto remains absolute and lower than all progress-routing suppressions.
    target = next(r for r in vote["ranked_candidates"] if r["gate_id"] == "COUSTEAU_HA10_119HZ_REINTERPRETATION")
    target["score"] = -1000.0
    vote["ranked_candidates"].sort(key=lambda r: (-float(r["score"]), str(r["gate_id"])))
    for idx, row in enumerate(vote["ranked_candidates"], start=1):
        row["rank"] = idx
    vote["selector_version"] = "V3_MONOTONIC_EVIDENCE_PROGRESS"
    inherited = vote.get("nonrepeatable_due_to_data_boundary") or []
    vote["nonrepeatable_due_to_data_boundary"] = sorted(set(str(x) for x in inherited) | set(applied))
    return vote


def aggregate(votes: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    # V1 aggregation is intentionally used over V3-ranked exact votes; V2's aggregate
    # may apply only the immediate blocked-gate rule and is not needed for explicit V3 routing.
    result = v1.aggregate(votes, payload)
    suppressed = explicit_nonrepeatable(payload)
    if result["selected_next_gate"] in suppressed:
        raise RuntimeError("V3_SELECTED_EXPLICIT_NONREPEATABLE_GATE")
    result["schema"] = "janus.demiurge.reverse_spiral_council_result.v3"
    result["selector_version"] = "V3_MONOTONIC_EVIDENCE_PROGRESS"
    result["nonrepeatable_due_to_data_boundary"] = suppressed
    result["contradiction_resolution"] = {
        "rule": "NO_CHANGED_EVIDENCE_OR_ACCESS -> ALREADY_CONSUMED_GATE_NOT_IMMEDIATELY_REPEATABLE",
        "applied": bool(suppressed),
        "suppressed_gates": suppressed,
    }
    result["canonical_answer"] = (
        f"Run {result['selected_next_gate']} next. Do not repeat {', '.join(suppressed) if suppressed else 'no guarded gates'} "
        "until their evidence/access condition changes; preserve frozen results, keep bathymetry independent, and keep 119 Hz vetoed."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--role")
    parser.add_argument("--votes-dir")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = v1.load_json(Path(args.input))
    if args.role:
        result = run_role(args.role, payload)
    elif args.votes_dir:
        votes = [v1.load_json(p) for p in sorted(Path(args.votes_dir).glob("*.json"))]
        result = aggregate(votes, payload)
    else:
        raise SystemExit("REQUIRE_ROLE_OR_VOTES_DIR")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS_APPEND_ONLY_REQUIRED")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result.get("status", "ROLE_VOTE"),
        "selected_next_gate": result.get("selected_next_gate"),
        "selector_version": result.get("selector_version"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
