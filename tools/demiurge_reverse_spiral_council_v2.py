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
import importlib.util
import json
from pathlib import Path
from typing import Any

V1_PATH = Path(__file__).with_name("demiurge_reverse_spiral_council.py")
_V1_SPEC = importlib.util.spec_from_file_location("demiurge_reverse_spiral_council_v1_frozen", V1_PATH)
if _V1_SPEC is None or _V1_SPEC.loader is None:
    raise RuntimeError("CANNOT_LOAD_FROZEN_COUNCIL_V1")
v1 = importlib.util.module_from_spec(_V1_SPEC)
_V1_SPEC.loader.exec_module(v1)


def blocked_exact_repeat(payload: dict[str, Any]) -> str | None:
    new_result = payload.get("new_result") if isinstance(payload.get("new_result"), dict) else {}
    previous = payload.get("previous_council") if isinstance(payload.get("previous_council"), dict) else {}
    verdict = str(new_result.get("verdict") or "")
    executed = str(previous.get("executed_gate") or "")
    data_boundary = new_result.get("data_boundary") is True
    access_changed = new_result.get("access_condition_changed") is True
    rankable_ids = set(
        v1.BASE_BY_VERDICT.get(
            verdict,
            v1.BASE_BY_VERDICT["MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING"],
        )
    )
    if (
        verdict.startswith("BLOCKED")
        and data_boundary
        and executed in rankable_ids
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
