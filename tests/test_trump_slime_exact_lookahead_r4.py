from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import trump_slime_exact_lookahead_r4 as r4
from trump_candidate import TrumpCandidateError


class FakeLedger:
    def __init__(self):
        self.proposal_work = 0
        self.certificate_discovery_work = 0
        self.verification_work = 0
        self.elimination_pair_work = 0


class FakeState:
    def __init__(self):
        self.residual = ((1, 2, 3), (-1, 2, 4), (1, -3, 4))
        self.root_vars = (1, 2, 3, 4)
        self.state_cap = 100
        self.ledger = FakeLedger()

    def progress_phi(self, cnf=None, ext_count=None):
        f = self.residual if cnf is None else cnf
        return sum(len(c) for c in f)


class FakeSelectorSolver:
    def __init__(self, verifier_ok=True):
        self.verifier_ok = verifier_ok
        self.first_capped_elimination = lambda *a, **k: None

    @staticmethod
    def canonical_pivot_order(state, cnf=None):
        return [1, 2, 3, 4]

    @staticmethod
    def state_units(cnf):
        return 1 + len(cnf) + sum(len(c) for c in cnf)

    def eliminate_var_capped(self, cnf, var, cap):
        if var == 1:
            return ((8, 9, 10),), {"pairs": 3, "raw_units": 6}
        if var == 2:
            return ((8, 9), (10,)), {"pairs": 4, "raw_units": 8}
        return None, {"pairs": 5, "raw_units": 101}

    def verify_elimination_transition(self, before, var, out, cap):
        return self.verifier_ok


class FakeFeatureSolver:
    @staticmethod
    def state_units(cnf):
        return 1 + len(cnf) + sum(len(c) for c in cnf)


def fake_result(status: str, work: int = 1, nonce: int = 0):
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


def test_shortlist_is_bounded_contains_canonical_and_never_expands_live_set():
    solver = FakeFeatureSolver()
    cnf = ((1, 2, 3), (-1, 2, 4), (1, -3, 4), (-2, -3, 4))
    pivots = [1, 2, 3, 4]
    shortlist, detail = r4.build_shortlist(solver, cnf, pivots)
    assert shortlist[0] == 1
    assert 1 <= len(shortlist) <= 4
    assert set(shortlist) <= set(pivots)
    assert detail["feature_work"] > 0
    assert set(detail["views"]) == {
        "canonical", "low_pair_risk", "conflict_cancellation", "structural_diversity", "diversity_anchor"
    }


def test_numeric_pivot_label_is_not_a_structural_feature_axis():
    solver = FakeFeatureSolver()
    rows, _ = r4.structural_feature_rows(solver, ((1, 2), (-1, 3)), [1, 2, 3])
    transferable_keys = set(rows[0]) - {"var", "canonical_index"}
    assert "pivot_id" not in transferable_keys
    assert "var" not in transferable_keys


def test_exact_selector_prefers_verified_two_sat_ready_candidate(monkeypatch):
    solver = FakeSelectorSolver()
    state = FakeState()
    monkeypatch.setattr(
        r4,
        "build_shortlist",
        lambda solver_module, cnf, pivots: ([1, 2], {"feature_work": 17, "rows": [], "views": {}, "shortlist": [1, 2]}),
    )
    with r4.exact_lookahead_patch(solver) as telemetry:
        chosen = solver.first_capped_elimination(state)
    assert chosen is not None
    assert chosen[0] == 2  # certificate-readiness tier beats smaller raw/state candidate
    assert telemetry["lookahead_candidates_attempted"] == 2
    assert telemetry["verified_candidates"] == 2
    assert telemetry["selected_noncanonical"] == 1
    assert telemetry["selected_certificate_ready"] == 1
    assert telemetry["feature_work"] == 17
    assert state.ledger.proposal_work == 2
    assert state.ledger.elimination_pair_work == 7
    assert state.ledger.certificate_discovery_work == (1 + 3) + (1 + 4)
    assert state.ledger.verification_work == (1 + 3) + (1 + 4)


def test_verifier_mismatch_fails_closed(monkeypatch):
    solver = FakeSelectorSolver(verifier_ok=False)
    state = FakeState()
    monkeypatch.setattr(
        r4,
        "build_shortlist",
        lambda solver_module, cnf, pivots: ([1], {"feature_work": 1, "rows": [], "views": {}, "shortlist": [1]}),
    )
    with pytest.raises(AssertionError, match="R4 exact elimination replay mismatch"):
        with r4.exact_lookahead_patch(solver):
            solver.first_capped_elimination(state)


def test_all_shortlisted_cap_failures_return_none_without_fake_transition(monkeypatch):
    solver = FakeSelectorSolver()
    state = FakeState()
    monkeypatch.setattr(
        r4,
        "build_shortlist",
        lambda solver_module, cnf, pivots: ([3, 4], {"feature_work": 5, "rows": [], "views": {}, "shortlist": [3, 4]}),
    )
    with r4.exact_lookahead_patch(solver) as telemetry:
        chosen = solver.first_capped_elimination(state)
    assert chosen is None
    assert telemetry["failed_cap_candidates"] == 2
    assert telemetry["verified_candidates"] == 0
    assert state.ledger.verification_work == 0


def test_canonical_decisive_is_replayed_and_r4_never_invoked(monkeypatch):
    calls = {"solve": 0, "fallback": 0}

    class Solver:
        def solve_fail_closed(self, clauses, **profile):
            calls["solve"] += 1
            return fake_result("UNSAT", 3)

    def forbidden_fallback(*a, **k):
        calls["fallback"] += 1
        raise AssertionError("R4 must not run after canonical decisive")

    monkeypatch.setattr(r4, "solve_r4_fallback", forbidden_fallback)
    out = r4.solve_canonical_then_r4(Solver(), [[1], [-1]])
    assert out["winner"] == "CANONICAL"
    assert out["r4_invoked"] is False
    assert calls == {"solve": 2, "fallback": 0}


def test_canonical_open_runs_r4_twice_for_exact_and_telemetry_replay(monkeypatch):
    class Solver:
        def solve_fail_closed(self, clauses, **profile):
            return fake_result("OPEN", 3)

    calls = {"fallback": 0}

    def fallback(*a, **k):
        calls["fallback"] += 1
        return {
            "exact_result": fake_result("SAT", 7),
            "telemetry": {"shortlist_calls": 2, "feature_work": 11},
            "exact_paid_work": 7,
            "feature_work": 11,
            "combined_fallback_work": 18,
        }

    monkeypatch.setattr(r4, "solve_r4_fallback", fallback)
    out = r4.solve_canonical_then_r4(Solver(), [[1, 2, 3]])
    assert calls["fallback"] == 2
    assert out["winner"] == "R4"
    assert out["final_result"]["status"] == "SAT"
    assert out["r4_invoked"] is True
