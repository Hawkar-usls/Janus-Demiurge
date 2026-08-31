#!/usr/bin/env python3
"""TRUMP LOOKING FOR SOMETHING candidate-portfolio policy R0.

Semantic seed:
    LOOK -> NEW -> GOOD -> FAST -> EXCITING -> WARM -> REAL -> STRONG
    -> CHERISH -> FEEL/FEEDBACK

This module does not solve SAT and has no theorem authority. It only ranks
already-produced exact/fail-closed candidate receipts and retains a Pareto
frontier. Every metric is derived from explicit receipts and all solver work
remains charged to the underlying TRUMP candidate ledger.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

POLICY_ID = "TRUMP_LOOKING_FOR_SOMETHING_POLICY_R0"
DEFAULT_PROFILES = (
    {"cap_exponent": 1, "extension_exponent": 0},
    {"cap_exponent": 2, "extension_exponent": 0},
    {"cap_exponent": 2, "extension_exponent": 1},
)

WORK_FIELDS = (
    "proposal_work",
    "certificate_discovery_work",
    "verification_work",
    "elimination_pair_work",
    "recompression_work",
    "witness_recovery_work",
    "bounded_width_resolution_work",
    "two_sat_work",
    "gf2_work",
)


class LookingForSomethingPolicyError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def profile_key(profile: dict) -> tuple[int, int]:
    c = int(profile["cap_exponent"])
    k = int(profile["extension_exponent"])
    if c < 1 or k < 0:
        raise LookingForSomethingPolicyError("INVALID_FIXED_EXPONENT_PROFILE")
    return c, k


def _boundary_is_real(result: dict) -> bool:
    sb = result.get("scientific_boundary", {})
    return (
        result.get("status") in {"SAT", "UNSAT", "OPEN"}
        and sb.get("P_VS_NP") == "OPEN"
        and sb.get("claims_p_eq_np") is False
        and sb.get("claims_p_neq_np") is False
        and sb.get("heuristic_promotion") is False
        and sb.get("general_sat_oracle") is False
        and sb.get("semantic_equivalence_oracle") is False
    )


def paid_work(result: dict) -> int:
    ledger = result.get("ledger", {})
    return sum(max(0, int(ledger.get(name, 0))) for name in WORK_FIELDS)


def features(candidate: dict) -> dict:
    profile = candidate["profile"]
    result = candidate["result"]
    key = profile_key(profile)
    ledger = result.get("ledger", {})
    status = result.get("status")
    real = _boundary_is_real(result)
    good = bool(real)
    warm = candidate.get("replay_match") is True
    residual_units = max(0, int(result.get("residual_units", 0)))
    questions = max(0, int(ledger.get("question_count", 0)))
    extensions = max(0, int(ledger.get("extension_count", 0)))
    decisive = status in {"SAT", "UNSAT"}
    work = paid_work(result)

    # "EXCITING" is observable structural progress, never evidence by itself.
    exciting = questions + extensions + int(decisive)

    return {
        "profile": {
            "cap_exponent": key[0],
            "extension_exponent": key[1],
        },
        "profile_key": f"C{key[0]}_K{key[1]}",
        "result_digest": digest(result),
        "status": status,
        "reason": result.get("reason"),
        "NEW": True,
        "GOOD": good,
        "FAST_paid_work": work,
        "EXCITING_progress_events": exciting,
        "WARM_replay_match": warm,
        "REAL_fail_closed_boundary": real,
        "STRONG_residual_units": residual_units,
        "decisive_exact_terminal": decisive,
    }


def _dominates(a: dict, b: dict) -> bool:
    """Pareto dominance for advisory retention, not theorem promotion."""
    av = (
        int(a["REAL_fail_closed_boundary"]),
        int(a["GOOD"]),
        int(a["WARM_replay_match"]),
        int(a["decisive_exact_terminal"]),
        -a["STRONG_residual_units"],
        -a["FAST_paid_work"],
        a["EXCITING_progress_events"],
    )
    bv = (
        int(b["REAL_fail_closed_boundary"]),
        int(b["GOOD"]),
        int(b["WARM_replay_match"]),
        int(b["decisive_exact_terminal"]),
        -b["STRONG_residual_units"],
        -b["FAST_paid_work"],
        b["EXCITING_progress_events"],
    )
    return all(x >= y for x, y in zip(av, bv)) and any(
        x > y for x, y in zip(av, bv)
    )


def _advisory_sort_key(row: dict) -> tuple:
    return (
        -int(row["REAL_fail_closed_boundary"]),
        -int(row["GOOD"]),
        -int(row["WARM_replay_match"]),
        -int(row["decisive_exact_terminal"]),
        row["STRONG_residual_units"],
        row["FAST_paid_work"],
        -row["EXCITING_progress_events"],
        row["profile_key"],
    )


def evaluate_portfolio(candidates: Iterable[dict]) -> dict:
    # LOOK + NEW: bounded enumeration and exact profile deduplication.
    unique: dict[tuple[int, int], dict] = {}
    duplicates: list[str] = []
    for candidate in candidates:
        key = profile_key(candidate["profile"])
        if key in unique:
            duplicates.append(f"C{key[0]}_K{key[1]}")
            continue
        unique[key] = candidate

    rows = [features(candidate) for candidate in unique.values()]
    rows.sort(key=_advisory_sort_key)

    frontier = [
        row
        for row in rows
        if not any(_dominates(other, row) for other in rows if other is not row)
    ]
    frontier.sort(key=_advisory_sort_key)

    chosen = frontier[0] if frontier else None
    return {
        "schema": "janus.trump.looking_for_something.portfolio.v0.1",
        "policy_id": POLICY_ID,
        "semantic_sequence": [
            "LOOK",
            "NEW",
            "GOOD",
            "FAST",
            "EXCITING",
            "WARM",
            "REAL",
            "STRONG",
            "CHERISH",
            "FEEL_FEEDBACK",
        ],
        "candidate_count": len(rows),
        "duplicate_profiles_ignored": duplicates,
        "ranked_candidates": rows,
        "CHERISH_pareto_frontier": frontier,
        "advisory_choice": chosen,
        "authority": {
            "advisory_only": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "formula_semantics_changed": False,
            "solver_oracle": False,
        },
        "scientific_boundary": {
            "P_equals_NP_proved": False,
            "SAT_IN_P": "NOT_PROVED",
            "TRUMP_finished": False,
            "P_VS_NP": "OPEN",
        },
        "law": "SEMANTIC_INSPIRATION != ALGORITHM_CORRECTNESS != COMPLEXITY_PROOF",
    }


def selftest() -> None:
    def fake(status: str, residual: int, work: int) -> dict:
        return {
            "status": status,
            "reason": "SELFTEST",
            "residual_units": residual,
            "ledger": {
                "proposal_work": work,
                "question_count": 1,
                "extension_count": 0,
            },
            "scientific_boundary": {
                "P_VS_NP": "OPEN",
                "claims_p_eq_np": False,
                "claims_p_neq_np": False,
                "heuristic_promotion": False,
                "general_sat_oracle": False,
                "semantic_equivalence_oracle": False,
            },
        }

    report = evaluate_portfolio(
        [
            {
                "profile": {"cap_exponent": 1, "extension_exponent": 0},
                "result": fake("OPEN", 20, 5),
                "replay_match": True,
            },
            {
                "profile": {"cap_exponent": 2, "extension_exponent": 1},
                "result": fake("SAT", 0, 12),
                "replay_match": True,
            },
        ]
    )
    assert report["candidate_count"] == 2
    assert report["advisory_choice"] is not None
    assert report["scientific_boundary"]["P_VS_NP"] == "OPEN"
    assert report["authority"]["proof_authority"] is False


if __name__ == "__main__":
    selftest()
    print("PASS: TRUMP LOOKING FOR SOMETHING policy selftest")
    print("P_VS_NP = OPEN")
