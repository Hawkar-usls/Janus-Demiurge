#!/usr/bin/env python3
"""JANUS HA10 reverse council v2: monotonic blocked-gate escape.

V1 remains byte-preserved for historical council receipts. V2 adds one rule:
when the exact previously executed candidate gate returned a stable data/archive
boundary, that same gate is ineligible for immediate re-selection unless the input
explicitly records that the access condition changed. This prevents a deterministic
council from converting BLOCKED into an infinite retry loop without new evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools import demiurge_reverse_spiral_council as v1


def blocked_exact_repeat(payload: dict[str, Any]) -> str | None:
    new_result = payload.get("new_result") if isinstance(payload.get("new_result"), dict) else {}
    previous = payload.get("previous_council") if isinstance(payload.get("previous_council"), dict) else {}
    verdict = str(new_result.get("verdict") or "")
    executed = str(previous.get("executed_gate") or "")
    data_boundary = new_result.get("data_boundary") is True
    access_changed = new_result.get("access_condition_changed") is True
    candidate_ids = {
        str(row["gate_id"])
        for row in v1.load_mission().get("candidate_gates", [])
        if isinstance(row, dict) and row.get("gate_id")
    }
    if (
        verdict.startswith("BLOCKED")
        and data_boundary
        and executed in candidate_ids
        and not access_changed
    ):
        return executed
    return None


def run_role(role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    vote = v1.run_role(role_id, payload)
    suppressed = blocked_exact_repeat(payload)
    if not suppressed:
        vote["selector_version"] = "V2_MONOTONIC_BLOCKED_GATE_ESCAPE"
        vote["nonrepeatable_due_to_data_boundary"] = []
        return vote

    found = False
    for row in vote["ranked_candidates"]:
        if row["gate_id"] == suppressed:
            row["score"] = -900.0
            row["reason"] = (
                "iNAIHR monotonicity guard: this exact gate already returned a stable "
                "archive/data boundary and the input reports no changed access condition; "
                "an immediate identical retry cannot add evidence."
            )
            found = True
            break
    if not found:
        raise ValueError(f"SUPPRESSED_GATE_NOT_IN_CANDIDATES:{suppressed}")

    vote["ranked_candidates"].sort(key=lambda r: (-float(r["score"]), str(r["gate_id"])))
    for idx, row in enumerate(vote["ranked_candidates"], start=1):
        row["rank"] = idx
    vote["selector_version"] = "V2_MONOTONIC_BLOCKED_GATE_ESCAPE"
    vote["nonrepeatable_due_to_data_boundary"] = [suppressed]
    return vote


def aggregate(votes: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    result = v1.aggregate(votes, payload)
    suppressed = blocked_exact_repeat(payload)
    if suppressed and result["selected_next_gate"] == suppressed:
        raise RuntimeError("V2_SELECTED_NONREPEATABLE_BLOCKED_GATE")
    result["schema"] = "janus.demiurge.reverse_spiral_council_result.v2"
    result["selector_version"] = "V2_MONOTONIC_BLOCKED_GATE_ESCAPE"
    result["nonrepeatable_due_to_data_boundary"] = [suppressed] if suppressed else []
    result["contradiction_resolution"] = {
        "rule": "BLOCKED_BY_STABLE_DATA_BOUNDARY -> EXACT_IMMEDIATE_REPEAT_FORBIDDEN_UNLESS_ACCESS_CONDITION_CHANGED",
        "applied": suppressed is not None,
        "suppressed_gate": suppressed,
    }
    if suppressed:
        result["canonical_answer"] = (
            f"Do not immediately repeat {suppressed}: its access condition is unchanged. "
            f"Run {result['selected_next_gate']} next; preserve frozen results and keep "
            "bathymetry as an independent evidence lane."
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
