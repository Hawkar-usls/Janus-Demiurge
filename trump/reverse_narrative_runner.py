#!/usr/bin/env python3
"""Frozen R0 tournament for TRUMP REVERSE NARRATIVE TRANSFORM.

The experiment compares FORWARD, REVERSE and BIDIRECTIONAL scheduling under the
same frozen witness set, profile universe, verifier and profile-attempt budget.
The operator may only reorder the frozen profiles. It cannot alter formulas,
solver semantics, receipts or theorem authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from looking_for_something_policy import DEFAULT_PROFILES
from looking_for_something_runner import run_portfolio
from reverse_narrative_transform import MODES, canonical_bytes, schedule, transform_receipt

EXPERIMENT_ID = "TRUMP_REVERSE_NARRATIVE_FROZEN_R0"
BUDGET_PROFILES = 2

FROZEN_WITNESSES = (
    {
        "id": "UNIT_UNSAT",
        "clauses": [[1], [-1]],
    },
    {
        "id": "FOUR_CLAUSE_2SAT_UNSAT",
        "clauses": [[1, 2], [-1, 2], [1, -2], [-1, -2]],
    },
    {
        "id": "SMALL_3CNF_SAT",
        "clauses": [[1, 2, 3], [-1, 2, 3], [1, -2, 3], [1, 2, -3]],
    },
)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _profile_key(profile: dict) -> str:
    return f"C{int(profile['cap_exponent'])}_K{int(profile['extension_exponent'])}"


def _mode_run(mode: str) -> dict:
    ordered = schedule(DEFAULT_PROFILES, mode)
    attempted = tuple(ordered[:BUDGET_PROFILES])
    rows = []
    decisive = 0
    open_count = 0
    total_paid_work = 0
    replay_failures = 0

    for witness in FROZEN_WITNESSES:
        receipt = run_portfolio(
            witness["clauses"],
            profiles=attempted,
            replay=True,
        )
        policy = receipt["policy_report"]
        ranked = policy["ranked_candidates"]
        total_paid_work += sum(int(r["FAST_paid_work"]) for r in ranked)
        replay_failures += sum(1 for r in ranked if not r["WARM_replay_match"])
        statuses = [r["status"] for r in ranked]
        if any(s in {"SAT", "UNSAT"} for s in statuses):
            decisive += 1
        if all(s == "OPEN" for s in statuses):
            open_count += 1
        rows.append(
            {
                "witness_id": witness["id"],
                "witness_digest": digest(witness["clauses"]),
                "attempted_profiles": [_profile_key(p) for p in attempted],
                "candidate_statuses": statuses,
                "advisory_choice": policy.get("advisory_choice"),
                "portfolio_receipt_hash": receipt["receipt_hash"],
                "P_VS_NP": receipt["scientific_boundary"]["P_VS_NP"],
            }
        )

    return {
        "mode": mode,
        "transform_receipt": transform_receipt(DEFAULT_PROFILES, mode),
        "attempted_profiles": [_profile_key(p) for p in attempted],
        "witness_count": len(FROZEN_WITNESSES),
        "decisive_witnesses": decisive,
        "all_open_witnesses": open_count,
        "total_paid_work": total_paid_work,
        "replay_failures": replay_failures,
        "rows": rows,
    }


def _comparator(row: dict) -> tuple:
    # Finite certified-search comparator only. It has no theorem semantics.
    return (
        -int(row["decisive_witnesses"]),
        int(row["all_open_witnesses"]),
        int(row["replay_failures"]),
        int(row["total_paid_work"]),
        row["mode"],
    )


def frozen_r0() -> dict:
    mode_rows = [_mode_run(mode) for mode in MODES]
    ranked = sorted(mode_rows, key=_comparator)
    champion = ranked[0]

    body = {
        "schema": "janus.trump.reverse_narrative.frozen_r0.receipt.v0.1",
        "experiment_id": EXPERIMENT_ID,
        "frozen_contract": {
            "witness_digest": digest(FROZEN_WITNESSES),
            "operator_universe_digest": digest(DEFAULT_PROFILES),
            "modes": list(MODES),
            "profile_attempt_budget": BUDGET_PROFILES,
            "same_witness_bytes": True,
            "same_profile_universe": True,
            "same_underlying_candidate": True,
            "same_verifier": True,
            "same_replay_requirement": True,
            "formula_semantics_mutable": False,
            "theorem_face_mutable": False,
        },
        "results": mode_rows,
        "certified_search_champion": champion["mode"],
        "champion_reason": "finite frozen comparator only",
        "laws": [
            "WINNER_WITHOUT_RECEIPT = NO_WINNER",
            "SCORE != TRUTH",
            "SCHEDULE != PROOF",
            "REVERSE_READING != SEMANTIC_MUTATION",
            "FINITE_SEARCH_WIN != POLYNOMIAL_THEOREM",
        ],
        "authority": {
            "candidate_search_only": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
        },
        "scientific_boundary": {
            "scientific_claim": "FINITE_FROZEN_SEARCH_ORDER_COMPARISON_ONLY",
            "polynomial_time_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    body["receipt_hash"] = digest(body)
    return body


def selftest() -> None:
    assert BUDGET_PROFILES < len(DEFAULT_PROFILES)
    assert len(FROZEN_WITNESSES) >= 3
    for mode in MODES:
        ordered = schedule(DEFAULT_PROFILES, mode)
        assert len(ordered) == len(DEFAULT_PROFILES)
    assert digest(FROZEN_WITNESSES) == digest(FROZEN_WITNESSES)


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    sub.add_parser("frozen-r0")
    args = p.parse_args()

    if args.command == "selftest":
        selftest()
        out = {
            "terminal": "TRUMP_REVERSE_NARRATIVE_SELFTEST_PASS",
            "proof_authority": False,
            "P_VS_NP": "OPEN",
        }
    else:
        out = frozen_r0()
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
