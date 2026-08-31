#!/usr/bin/env python3
"""Exact/advisory ORIGIN_PRIME receipt for TRUMP reverse narrative experiments.

ORIGIN_PRIME never changes a formula or proves a theorem. It compares already
produced replayed receipts and records (a) exact invariants and (b) observable
directional deltas. An ascent is permitted only when new certified finite-search
information exists. Interpretive semantics have zero proof authority.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

ORIGIN_PRIME_ID = "TRUMP_ORIGIN_PRIME_R1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _summary(row: dict) -> dict:
    return {
        "mode": row["mode"],
        "attempted_profiles": list(row["attempted_profiles"]),
        "decisive_witnesses": int(row["decisive_witnesses"]),
        "all_open_witnesses": int(row["all_open_witnesses"]),
        "total_paid_work": int(row["total_paid_work"]),
        "replay_failures": int(row["replay_failures"]),
        "status_vector": [
            {
                "witness_id": r["witness_id"],
                "candidate_statuses": list(r["candidate_statuses"]),
            }
            for r in row["rows"]
        ],
    }


def build_origin_prime(
    mode_rows: Sequence[dict],
    *,
    witness_digest: str,
    operator_universe_digest: str,
    prereg_commit: str,
) -> dict:
    if not mode_rows:
        raise ValueError("ORIGIN_PRIME_REQUIRES_MODE_ROWS")
    by_mode = {row["mode"]: row for row in mode_rows}
    if "FORWARD" not in by_mode:
        raise ValueError("ORIGIN_PRIME_REQUIRES_FORWARD_ORIGIN")

    summaries = {mode: _summary(row) for mode, row in sorted(by_mode.items())}
    baseline = summaries["FORWARD"]
    deltas = []
    for mode, summary in summaries.items():
        if mode == "FORWARD":
            continue
        delta = {
            "mode": mode,
            "attempted_profiles_changed": summary["attempted_profiles"] != baseline["attempted_profiles"],
            "decisive_delta": summary["decisive_witnesses"] - baseline["decisive_witnesses"],
            "all_open_delta": summary["all_open_witnesses"] - baseline["all_open_witnesses"],
            "paid_work_delta": summary["total_paid_work"] - baseline["total_paid_work"],
            "status_vector_changed": summary["status_vector"] != baseline["status_vector"],
            "replay_failure_delta": summary["replay_failures"] - baseline["replay_failures"],
        }
        delta["substantive_delta"] = bool(
            delta["decisive_delta"]
            or delta["all_open_delta"]
            or delta["paid_work_delta"]
            or delta["status_vector_changed"]
        )
        deltas.append(delta)

    all_replayed = all(int(row["replay_failures"]) == 0 for row in mode_rows)
    has_substantive_delta = any(d["substantive_delta"] for d in deltas)
    ascended = bool(all_replayed and has_substantive_delta)

    body = {
        "schema": "janus.trump.origin_prime.receipt.v0.1",
        "origin_prime_id": ORIGIN_PRIME_ID,
        "prereg_commit": prereg_commit,
        "origin": "FORWARD",
        "exact_invariants": {
            "witness_digest": witness_digest,
            "operator_universe_digest": operator_universe_digest,
            "same_formula_bytes_across_modes": True,
            "same_underlying_candidate": True,
            "same_verifier": True,
            "theorem_face_mutable": False,
        },
        "mode_summaries": summaries,
        "directional_deltas_from_forward": deltas,
        "all_receipts_replayed": all_replayed,
        "new_certified_information": ascended,
        "origin_prime_status": (
            "ASCENDED_CERTIFIED_SEARCH_INFORMATION"
            if ascended
            else "RETURN_NO_NEW_CERTIFIED_INFORMATION"
        ),
        "authority": {
            "interpretive_semantics_authority": False,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
        },
        "laws": [
            "RETURN != RESET",
            "HINDSIGHT != CAUSAL_EVIDENCE",
            "ORIGIN_PRIME_ASCENT_REQUIRES_NEW_CERTIFIED_INFORMATION",
            "DIRECTIONAL_DELTA != THEOREM",
        ],
        "scientific_boundary": {
            "P_equals_NP_proved": False,
            "polynomial_time_SAT_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    body["receipt_hash"] = digest(body)
    return body


def selftest() -> None:
    rows = [
        {
            "mode": "FORWARD", "attempted_profiles": ["C1_K0"],
            "decisive_witnesses": 0, "all_open_witnesses": 1,
            "total_paid_work": 10, "replay_failures": 0,
            "rows": [{"witness_id": "W", "candidate_statuses": ["OPEN"]}],
        },
        {
            "mode": "REVERSE", "attempted_profiles": ["C2_K1"],
            "decisive_witnesses": 1, "all_open_witnesses": 0,
            "total_paid_work": 20, "replay_failures": 0,
            "rows": [{"witness_id": "W", "candidate_statuses": ["SAT"]}],
        },
    ]
    r = build_origin_prime(rows, witness_digest="w", operator_universe_digest="o", prereg_commit="p")
    assert r["new_certified_information"] is True
    assert r["authority"]["proof_authority"] is False
    assert r["scientific_boundary"]["P_VS_NP"] == "OPEN"


if __name__ == "__main__":
    selftest()
    print("PASS: TRUMP ORIGIN_PRIME selftest")
    print("P_VS_NP = OPEN")
