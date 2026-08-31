from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

from trump_candidate import TrumpCandidateError
from trump_slime_open_only_swarm_r3 import (
    generate_fronts,
    pivot_priority_patch,
    solve_open_only_swarm,
)


def result(status: str, work: int = 1, nonce: int = 0):
    return {
        "status": status,
        "reason": "TEST",
        "nonce": nonce,
        "residual_units": 0,
        "ledger": {
            "proposal_work": work,
            "certificate_discovery_work": 0,
            "verification_work": 0,
            "elimination_pair_work": 0,
            "recompression_work": 0,
            "witness_recovery_work": 0,
            "bounded_width_resolution_work": 0,
            "two_sat_work": 0,
            "gf2_work": 0,
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


class FakeCandidate:
    def __init__(self, name, order, ops=5):
        self.name = name
        self.linear_leaf_order = order
        self.charged_ops = ops


class FakeManifest:
    artifact_id = "fake"
    source_sha256 = "0" * 64
    total_generation_ops = 80
    candidates = [
        FakeCandidate(f"front-{i:02d}", (["v:2", "v:1", "c:0"] if i == 0 else ["v:1", "v:2", "c:0"]))
        for i in range(16)
    ]


class FakeDonor:
    class SlimeSemanticCandidateSwarmV3Amortized:
        def generate_manifest(self, clauses):
            return FakeManifest()


class FakeSolver:
    def __init__(self, canonical_status="OPEN", mismatch=False):
        self.canonical_status = canonical_status
        self.mismatch = mismatch
        self.calls = 0

    @staticmethod
    def canonical_pivot_order(state, cnf=None):
        # Unit tests may pass an explicit live-variable list to exercise the
        # extension suffix contract. During fake solve execution cnf is a
        # tuple-of-clauses, so preserve the intended root canonical [1, 2].
        if isinstance(cnf, list) and all(isinstance(x, int) for x in cnf):
            return list(cnf)
        return [1, 2]

    def solve_fail_closed(self, clauses, **profile):
        self.calls += 1
        state = SimpleNamespace(residual=((1, 2), (-1, 2)), state_cap=100)
        order = self.canonical_pivot_order(state, state.residual)
        if self.canonical_status in {"SAT", "UNSAT"} and order == [1, 2]:
            return result(self.canonical_status, 3)
        if order == [1, 2]:
            return result("OPEN", 3)
        nonce = self.calls if self.mismatch else 0
        return result("SAT", 4, nonce=nonce)


def test_pivot_patch_preserves_exact_live_set_and_canonical_suffix():
    solver = FakeSolver()
    with pivot_priority_patch(solver, [2, 1, 999]) as telemetry:
        state = SimpleNamespace(residual=(), state_cap=100)
        assert solver.canonical_pivot_order(state, [1, 2, 7]) == [2, 1, 7]
    assert telemetry["pivot_order_calls"] == 1
    assert FakeSolver.canonical_pivot_order(None, [1, 2, 7]) == [1, 2, 7]


def test_canonical_decisive_never_generates_or_runs_swarm():
    solver = FakeSolver(canonical_status="UNSAT")
    out = solve_open_only_swarm(solver, [[1], [-1]], donor_module=object())
    assert out["winner"] == "CANONICAL"
    assert out["donor_generated"] is False
    assert out["fronts_attempted"] == 0
    # first pass + exact replay only
    assert solver.calls == 2


def test_open_invokes_swarm_and_first_decisive_replay_stops():
    solver = FakeSolver(canonical_status="OPEN")
    out = solve_open_only_swarm(solver, [[1, 2], [-1, 2]], donor_module=FakeDonor())
    assert out["baseline"]["status"] == "OPEN"
    assert out["final_result"]["status"] == "SAT"
    assert out["winner"] == "front-00"
    assert out["fronts_attempted"] == 1
    assert out["front_attempts"][0]["replay_match"] is True
    assert out["candidate_result_promoted"] is False
    assert out["same_theorem_face_learning"] is False


def test_decisive_replay_mismatch_fails_closed():
    solver = FakeSolver(canonical_status="OPEN", mismatch=True)
    with pytest.raises(TrumpCandidateError, match="R3_DECISIVE_REPLAY_MISMATCH"):
        solve_open_only_swarm(solver, [[1, 2], [-1, 2]], donor_module=FakeDonor())


def test_generated_fronts_are_full_root_permutations_and_projection_cost_is_charged():
    generated = generate_fronts([[1, 2], [-1, 2]], FakeDonor())
    assert len(generated["fronts"]) == 16
    assert all(set(front["pivot_priority"]) == {1, 2} for front in generated["fronts"])
    assert generated["pivot_projection_ops"] == 16 * 3
    assert generated["slime_generation_ops"] == 80
