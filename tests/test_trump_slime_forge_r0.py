from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

from trump_candidate import TrumpCandidateError
from trump_slime_forge_r0 import (
    AUTHORITY,
    SlimeForgeError,
    SlimeForgeMemory,
    digest,
    profile_key,
    source_identity_from_receipt,
)
from trump_slime_forge_runner_r0 import execute_order, normalized_source_identity


PROFILES = [
    {"cap_exponent": 1, "extension_exponent": 0},
    {"cap_exponent": 2, "extension_exponent": 0},
    {"cap_exponent": 2, "extension_exponent": 1},
]
SOURCE_RECEIPT = {
    "repository": "Hawkar-usls/Janus-Fundamentum",
    "commit": "1" * 40,
    "path": "candidate.py",
    "git_blob_sha": "2" * 40,
}
SOURCE_MANIFEST = {
    "repository": SOURCE_RECEIPT["repository"],
    "pinned_commit": SOURCE_RECEIPT["commit"],
    "path": SOURCE_RECEIPT["path"],
    "git_blob_sha": SOURCE_RECEIPT["git_blob_sha"],
}


def seal(body: dict) -> dict:
    out = copy.deepcopy(body)
    out["receipt_hash"] = digest(body)
    return out


def finalized(attempts: list[tuple[dict, str, int, bool]], *, input_byte: str = "a", source=None) -> dict:
    body = {
        "schema": "janus.trump.candidate_runtime_receipt.v0.1",
        "component": "TRUMP",
        "mode": "CANDIDATE_RUNTIME_TISSUE",
        "source": copy.deepcopy(source or SOURCE_RECEIPT),
        "authority": dict(AUTHORITY),
        "scientific_boundary": {
            "TRUMP_finished": False,
            "polynomial_time_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
        "terminal": "TRUMP_SLIME_FORGE_BOUNDED_SOLVE_COMPLETE",
        "candidate_result_promoted": False,
        "input_digest": input_byte * 64,
        "attempts": [
            {
                "profile": profile,
                "result": {"status": status},
                "paid_work": work,
                "real_boundary": True,
                "replay_match": replay,
            }
            for profile, status, work, replay in attempts
        ],
    }
    return seal(body)


def fake_result(status: str, work: int = 1, *, nonce: int = 0) -> dict:
    return {
        "status": status,
        "reason": "TEST",
        "residual_units": 0 if status != "OPEN" else 10,
        "nonce": nonce,
        "ledger": {"proposal_work": work},
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "claims_p_eq_np": False,
            "claims_p_neq_np": False,
            "heuristic_promotion": False,
            "general_sat_oracle": False,
            "semantic_equivalence_oracle": False,
        },
    }


def test_source_identity_is_canonical_across_manifest_and_receipt_names():
    receipt = finalized([(PROFILES[0], "OPEN", 5, False)])
    assert source_identity_from_receipt(receipt) == normalized_source_identity(SOURCE_MANIFEST)


def test_tampered_receipt_is_rejected_before_learning():
    mem = SlimeForgeMemory()
    receipt = finalized([(PROFILES[0], "SAT", 5, True)])
    receipt["attempts"][0]["paid_work"] = 999
    with pytest.raises(SlimeForgeError, match="RECEIPT_HASH_MISMATCH"):
        mem.learn_finalized_receipt(receipt)
    assert mem.snapshot()["episodes"] == {}


def test_replay_is_not_new_evidence():
    mem = SlimeForgeMemory()
    receipt = finalized([(PROFILES[0], "SAT", 5, True)])
    assert mem.learn_finalized_receipt(receipt)["status"] == "LEARNED"
    assert mem.learn_finalized_receipt(receipt)["status"] == "REPLAY_IGNORED"
    sid = source_identity_from_receipt(receipt)
    stats = mem.snapshot()["sources"][sid]["profiles"]["C1_K0"]
    assert stats["episodes"] == 1


def test_open_is_preserved_as_neutral_not_failure():
    mem = SlimeForgeMemory()
    receipt = finalized([(PROFILES[0], "OPEN", 500, False)])
    mem.learn_finalized_receipt(receipt)
    sid = source_identity_from_receipt(receipt)
    advice = mem.rank_profiles(PROFILES, source_identity=sid)
    row = next(r for r in advice["ranking"] if r["profile_key"] == "C1_K0")
    assert row["stats"]["open"] == 1
    assert row["stats"]["decisive"] == 0
    assert row["verified_route_score"] == 0.0


def test_small_n_lucky_profile_does_not_monopolize_mature_profile():
    mem = SlimeForgeMemory()
    r_a = finalized([(PROFILES[0], "SAT", 1, True)], input_byte="a")
    mem.learn_finalized_receipt(r_a)
    for i, b in enumerate("bcdef"):
        r_b = finalized([(PROFILES[1], "SAT", 20, True)], input_byte=b)
        mem.learn_finalized_receipt(r_b)
    sid = source_identity_from_receipt(r_a)
    advice = mem.rank_profiles(PROFILES, source_identity=sid)
    assert profile_key(advice["ordered_profiles"][0]) == "C2_K0"
    scores = {r["profile_key"]: r["rank_score"] for r in advice["ranking"]}
    assert scores["C2_K0"] > scores["C1_K0"]


def test_declared_profile_set_is_never_dropped_or_added():
    mem = SlimeForgeMemory()
    advice = mem.rank_profiles(PROFILES, source_identity="f" * 64)
    assert advice["candidate_set_changed"] is False
    assert len(advice["ordered_profiles"]) == len(PROFILES)
    assert {profile_key(p) for p in advice["ordered_profiles"]} == {profile_key(p) for p in PROFILES}
    assert advice["authority"]["proof_authority"] is False


def test_source_change_cold_resets_advice_without_deleting_history():
    mem = SlimeForgeMemory()
    receipt = finalized([(PROFILES[1], "SAT", 2, True)])
    mem.learn_finalized_receipt(receipt)
    old_sid = source_identity_from_receipt(receipt)
    assert mem.rank_profiles(PROFILES, source_identity=old_sid)["cold_context"] is False
    cold = mem.rank_profiles(PROFILES, source_identity="e" * 64)
    assert cold["cold_context"] is True
    assert all(r["verified_route_score"] == 0.0 for r in cold["ranking"])
    assert len(mem.snapshot()["episodes"]) == 1


def test_decisive_exact_result_stops_only_after_matching_replay():
    calls = []
    def solve(_clauses, *, cap_exponent, extension_exponent):
        calls.append((cap_exponent, extension_exponent))
        return fake_result("SAT", 7)
    attempts, status, stopped = execute_order([], ordered_profiles=PROFILES, solve=solve)
    assert status == "SAT"
    assert stopped is True
    assert len(attempts) == 1
    assert attempts[0]["replay_match"] is True
    assert calls == [(1, 0), (1, 0)]


def test_open_continues_and_is_not_treated_as_negative():
    calls = []
    def solve(_clauses, *, cap_exponent, extension_exponent):
        calls.append((cap_exponent, extension_exponent))
        if (cap_exponent, extension_exponent) == (1, 0):
            return fake_result("OPEN", 3)
        return fake_result("UNSAT", 9)
    attempts, status, stopped = execute_order([], ordered_profiles=PROFILES, solve=solve)
    assert status == "UNSAT"
    assert stopped is True
    assert [a["result"]["status"] for a in attempts] == ["OPEN", "UNSAT"]
    assert calls == [(1, 0), (2, 0), (2, 0)]


def test_decisive_replay_mismatch_fails_closed():
    calls = 0
    def solve(_clauses, *, cap_exponent, extension_exponent):
        nonlocal calls
        calls += 1
        return fake_result("SAT", 4, nonce=calls)
    with pytest.raises(TrumpCandidateError, match="DECISIVE_REPLAY_MISMATCH"):
        execute_order([], ordered_profiles=PROFILES, solve=solve)


def test_contradictory_decisive_terminals_are_rejected():
    mem = SlimeForgeMemory()
    receipt = finalized([
        (PROFILES[0], "SAT", 5, True),
        (PROFILES[1], "UNSAT", 5, True),
    ])
    with pytest.raises(SlimeForgeError, match="CONTRADICTORY_EXACT_TERMINALS"):
        mem.learn_finalized_receipt(receipt)
