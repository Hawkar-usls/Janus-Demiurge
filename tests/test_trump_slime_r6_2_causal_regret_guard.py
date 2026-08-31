from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r6_2_causal_regret_guard_benchmark as r62


def test_frozen_spec_requires_real_causal_exposure() -> None:
    spec = r62.load_frozen_spec()
    assert spec["gate"]["minimum_pre_result_selected_formulas"] == 16
    assert spec["gate"]["minimum_canonical_OPEN_causal_exposures"] == 12
    assert spec["counterfactual_lane"]["role"] == "MEASUREMENT_ONLY_NO_PROOF_OR_SELECTION_AUTHORITY"
    assert spec["fresh_pre_result_candidate_pool"]["formula_selection_uses_exact_solver_result"] is False
    assert spec["fresh_pre_result_candidate_pool"]["formula_selection_uses_holdout_truth"] is False
    assert spec["fresh_pre_result_candidate_pool"]["formula_selection_uses_exact_route_work"] is False


def test_preselection_is_structural_only(monkeypatch) -> None:
    class FakeSolver:
        def canon_cnf(self, clauses):
            return tuple(tuple(int(x) for x in c) for c in clauses)

        def fingerprint(self, cnf):
            # Every generated seed is a deterministic exploration trigger because
            # the first eight hex digits decode to a multiple of ten.
            seed = abs(int(cnf[0][0]))
            return f"00000000{seed:056x}"[-64:]

    spec = copy.deepcopy(r62.load_frozen_spec())
    spec["fresh_pre_result_candidate_pool"]["families"] = ["GT6_WRAPPED"]
    spec["fresh_pre_result_candidate_pool"]["GT6_WRAPPED_seed_scan"] = {"start": 1, "stop_inclusive": 3}
    spec["fresh_pre_result_candidate_pool"]["selection_target_per_family"] = 2

    monkeypatch.setattr(r62.base, "formula_for", lambda family, seed: [[int(seed)]])

    def fake_select(solver, root, memory):
        seed = abs(int(root[0][0]))
        return {
            "memory_best": {"view": "LOW_PAIR_RISK", "pivot_id_local": 1, "predicted_execution_work": 10.0, "vector": (0.0,)},
            "diversity_alternate": {"view": "STRUCTURAL_DIVERSITY", "pivot_id_local": 2, "predicted_execution_work": 20.0, "vector": (1.0,)},
            "selected": {"view": "LOW_PAIR_RISK", "pivot_id_local": 1, "predicted_execution_work": 10.0, "vector": (0.0,)},
            "supported": [{"pivot_id_local": 1}, {"pivot_id_local": 2}],
            "feature_inference_work": 7,
            "exploration_trigger": True,
            "predicted_regret_ratio": 2.0,
            "regret_threshold": 1.25,
            "regret_guard_shadow_reject": True,
            "exploration_alternate_exact_executed": False,
        }

    monkeypatch.setattr(r62.guard, "select_root_route", fake_select)
    rows = r62.preselect_subjects(FakeSolver(), {"frozen": True}, spec)
    assert [row["seed"] for row in rows] == [1, 2]
    assert all(row["selection"]["regret_guard_shadow_reject"] for row in rows)


def test_route_with_fallback_charges_same_baseline(monkeypatch) -> None:
    baseline = {
        "combined_fallback_work": 100,
        "replay_work": 20,
        "exact_result": {"status": "UNSAT", "reason": "BASE"},
    }

    monkeypatch.setattr(
        r62.base,
        "run_forced_root_route",
        lambda solver, clauses, pivot, profile: {
            "status": "OPEN",
            "reason": "FORCED_OPEN",
            "execution_work": 30,
            "replay_work": 0,
            "selected_split_verified": True,
        },
    )
    result = r62._route_with_fallback(object(), [], {}, 1, baseline)
    assert result["fallback_used"] is True
    assert result["final_status"] == "UNSAT"
    assert result["execution_work"] == 130
    assert result["replay_work"] == 20
    assert result["full_route_work"] == 150


def test_decisive_forced_route_does_not_add_fallback(monkeypatch) -> None:
    baseline = {
        "combined_fallback_work": 100,
        "replay_work": 20,
        "exact_result": {"status": "UNSAT", "reason": "BASE"},
    }
    monkeypatch.setattr(
        r62.base,
        "run_forced_root_route",
        lambda solver, clauses, pivot, profile: {
            "status": "UNSAT",
            "reason": "FORCED_UNSAT",
            "execution_work": 30,
            "replay_work": 7,
            "selected_split_verified": True,
        },
    )
    result = r62._route_with_fallback(object(), [], {}, 1, baseline)
    assert result["fallback_used"] is False
    assert result["execution_work"] == 30
    assert result["replay_work"] == 7
    assert result["full_route_work"] == 37


def test_selftest_keeps_counterfactual_non_authoritative() -> None:
    result = r62.selftest()
    assert result["status"] == "PASS"
    assert result["counterfactual_authority"] is False
    assert result["P_VS_NP"] == "OPEN"
