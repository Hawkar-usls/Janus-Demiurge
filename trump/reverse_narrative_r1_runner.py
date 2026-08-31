#!/usr/bin/env python3
"""Frozen R1 hard-scope tournament for TRUMP reverse narrative scheduling.

The preregistration is commit-bound before execution. This runner implements the
frozen witness constructors, one-profile budget, substantive no-name tie rule,
and ORIGIN_PRIME receipt. It never mutates witness/formula/verifier/theorem face.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from looking_for_something_policy import DEFAULT_PROFILES
from looking_for_something_runner import run_portfolio
from reverse_narrative_transform import MODES, canonical_bytes, schedule, transform_receipt
from reverse_narrative_origin_prime import build_origin_prime

EXPERIMENT_ID = "TRUMP_REVERSE_NARRATIVE_R1_ORIGIN_PRIME"
PREREG_COMMIT = "5a83dd495fcc8f6939cd8b94d4cd38e2c26ccb3f"
BUDGET_PROFILES = 1

BASE_HARDISH = (
    (1,2,3,4),(-1,-2,3,4),(1,-2,-3,4),(-1,2,-3,4),
    (1,2,-3,-4),(-1,-2,-3,-4),(1,-2,3,-4),(-1,2,3,-4),
)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _offset_clause(clause: tuple[int, ...], offset: int) -> list[int]:
    return [((abs(x) + offset) if x > 0 else -(abs(x) + offset)) for x in clause]


def _hardish_base() -> list[list[int]]:
    return [list(c) for c in BASE_HARDISH]


def _hardish_double() -> list[list[int]]:
    return [_offset_clause(c, off) for off in (0, 4) for c in BASE_HARDISH]


def _php_4_into_3() -> list[list[int]]:
    # var(p,h) = p*3+h+1 for p in 0..3, h in 0..2
    clauses: list[list[int]] = []
    for p in range(4):
        clauses.append([p * 3 + h + 1 for h in range(3)])
    for h in range(3):
        for p in range(4):
            for q in range(p + 1, 4):
                clauses.append([-(p * 3 + h + 1), -(q * 3 + h + 1)])
    return clauses


def _full_cube_5_unsat() -> list[list[int]]:
    clauses: list[list[int]] = []
    for mask in range(1 << 5):
        clause = []
        for i in range(5):
            # Clause is false exactly on assignment bit pattern mask.
            bit = (mask >> i) & 1
            v = i + 1
            clause.append(-v if bit else v)
        clauses.append(clause)
    return clauses


def _random_3cnf_12v_48c() -> list[list[int]]:
    state = 20260831

    def nxt() -> int:
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return state

    out: list[list[int]] = []
    for _ in range(48):
        vs: list[int] = []
        while len(vs) < 3:
            v = nxt() % 12 + 1
            if v not in vs:
                vs.append(v)
        clause = []
        for v in vs:
            clause.append(v if (nxt() & 1) else -v)
        out.append(clause)
    return out


FROZEN_WITNESSES = (
    {"id": "C025_HARDISH_BASE", "clauses": _hardish_base()},
    {"id": "C025_HARDISH_DOUBLE_DISJOINT", "clauses": _hardish_double()},
    {"id": "PHP_4_INTO_3", "clauses": _php_4_into_3()},
    {"id": "FULL_CUBE_5_UNSAT", "clauses": _full_cube_5_unsat()},
    {"id": "DETERMINISTIC_RANDOM_3CNF_12V_48C", "clauses": _random_3cnf_12v_48c()},
)


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
        receipt = run_portfolio(witness["clauses"], profiles=attempted, replay=True)
        policy = receipt["policy_report"]
        ranked = policy["ranked_candidates"]
        total_paid_work += sum(int(r["FAST_paid_work"]) for r in ranked)
        replay_failures += sum(1 for r in ranked if not r["WARM_replay_match"])
        statuses = [r["status"] for r in ranked]
        if any(s in {"SAT", "UNSAT"} for s in statuses):
            decisive += 1
        if statuses and all(s == "OPEN" for s in statuses):
            open_count += 1
        rows.append({
            "witness_id": witness["id"],
            "witness_digest": digest(witness["clauses"]),
            "attempted_profiles": [_profile_key(p) for p in attempted],
            "candidate_statuses": statuses,
            "candidate_reasons": [r.get("reason") for r in ranked],
            "advisory_choice": policy.get("advisory_choice"),
            "portfolio_receipt_hash": receipt["receipt_hash"],
            "P_VS_NP": receipt["scientific_boundary"]["P_VS_NP"],
        })

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


def _substantive_key(row: dict) -> tuple[int, int, int, int]:
    return (
        -int(row["decisive_witnesses"]),
        int(row["all_open_witnesses"]),
        int(row["replay_failures"]),
        int(row["total_paid_work"]),
    )


def _champion(mode_rows: list[dict]) -> tuple[str, str]:
    ranked = sorted(mode_rows, key=_substantive_key)
    best = _substantive_key(ranked[0])
    tied = [r for r in ranked if _substantive_key(r) == best]
    if len(tied) != 1:
        return "NO_UNIQUE_CHAMPION", "substantive comparator tie; mode-name tie-break forbidden"
    return tied[0]["mode"], "unique finite frozen substantive comparator winner"


def frozen_r1() -> dict:
    mode_rows = [_mode_run(mode) for mode in MODES]
    champion, champion_reason = _champion(mode_rows)
    witness_digest = digest(FROZEN_WITNESSES)
    universe_digest = digest(DEFAULT_PROFILES)
    origin_prime = build_origin_prime(
        mode_rows,
        witness_digest=witness_digest,
        operator_universe_digest=universe_digest,
        prereg_commit=PREREG_COMMIT,
    )

    body = {
        "schema": "janus.trump.reverse_narrative.r1_origin_prime.receipt.v0.1",
        "experiment_id": EXPERIMENT_ID,
        "prereg_commit": PREREG_COMMIT,
        "frozen_contract": {
            "witness_digest": witness_digest,
            "operator_universe_digest": universe_digest,
            "modes": list(MODES),
            "profile_attempt_budget": BUDGET_PROFILES,
            "same_witness_bytes": True,
            "same_profile_universe": True,
            "same_underlying_candidate": True,
            "same_verifier": True,
            "same_replay_requirement": True,
            "formula_semantics_mutable": False,
            "theorem_face_mutable": False,
            "mode_name_scientific_tiebreak_allowed": False,
        },
        "results": mode_rows,
        "certified_search_champion": champion,
        "champion_reason": champion_reason,
        "origin_prime": origin_prime,
        "laws": [
            "WINNER_WITHOUT_RECEIPT = NO_WINNER",
            "SCORE != TRUTH",
            "SCHEDULE != PROOF",
            "REVERSE_READING != SEMANTIC_MUTATION",
            "HINDSIGHT != CAUSAL_EVIDENCE",
            "RETURN != RESET",
            "ORIGIN_PRIME_ASCENT_REQUIRES_NEW_CERTIFIED_INFORMATION",
            "FINITE_SEARCH_WIN != POLYNOMIAL_THEOREM",
        ],
        "authority": {
            "candidate_search_only": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
        },
        "scientific_boundary": {
            "scientific_claim": "FINITE_FROZEN_HARD_SCOPE_SEARCH_ORDER_COMPARISON_ONLY",
            "polynomial_time_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    body["receipt_hash"] = digest(body)
    return body


def selftest() -> None:
    assert BUDGET_PROFILES == 1
    assert BUDGET_PROFILES < len(DEFAULT_PROFILES)
    assert len(FROZEN_WITNESSES) == 5
    assert len(_php_4_into_3()) == 22
    assert len(_full_cube_5_unsat()) == 32
    assert len(_random_3cnf_12v_48c()) == 48
    # With a one-profile budget, FORWARD and BIDIRECTIONAL intentionally share
    # the same first profile; this is an internal control for schedule plumbing.
    assert schedule(DEFAULT_PROFILES, "FORWARD")[0] == schedule(DEFAULT_PROFILES, "BIDIRECTIONAL")[0]
    assert schedule(DEFAULT_PROFILES, "REVERSE")[0] != schedule(DEFAULT_PROFILES, "FORWARD")[0]


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    sub.add_parser("frozen-r1")
    args = p.parse_args()
    if args.command == "selftest":
        selftest()
        out = {"terminal": "TRUMP_REVERSE_NARRATIVE_R1_SELFTEST_PASS", "proof_authority": False, "P_VS_NP": "OPEN"}
    else:
        out = frozen_r1()
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
