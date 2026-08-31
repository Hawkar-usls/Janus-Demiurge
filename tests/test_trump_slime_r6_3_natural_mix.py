from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r6_3_natural_mix_benchmark as r63


def test_frozen_holdout_is_fixed_and_unenriched() -> None:
    spec = r63.load_frozen_spec()
    raw = spec["fresh_fixed_unenriched_holdout"]
    assert raw["formula_count"] == 60
    assert raw["selection_by_exploration_trigger_forbidden"] is True
    assert raw["selection_by_memory_support_forbidden"] is True
    assert raw["selection_by_predicted_regret_forbidden"] is True
    assert raw["selection_by_exact_truth_result_or_work_forbidden"] is True
    rows = r63.holdout_subjects(spec)
    assert len(rows) == 60
    assert len(set(rows)) == 60


def test_route_with_fallback_charges_baseline(monkeypatch) -> None:
    baseline = {
        "combined_fallback_work": 100,
        "replay_work": 20,
        "exact_result": {"status": "UNSAT", "reason": "BASE"},
    }
    monkeypatch.setattr(
        r63.base,
        "run_forced_root_route",
        lambda solver, clauses, pivot, profile: {
            "status": "OPEN",
            "reason": "OPEN",
            "execution_work": 30,
            "replay_work": 5,
            "selected_split_verified": True,
        },
    )
    out = r63._route_with_fallback(object(), [], {}, 1, baseline)
    assert out["fallback_used"] is True
    assert out["execution_work"] == 130
    assert out["replay_work"] == 25
    assert out["full_route_work"] == 155
    assert out["final_status"] == "UNSAT"


def test_decisive_forced_route_avoids_fallback(monkeypatch) -> None:
    baseline = {
        "combined_fallback_work": 100,
        "replay_work": 20,
        "exact_result": {"status": "UNSAT", "reason": "BASE"},
    }
    monkeypatch.setattr(
        r63.base,
        "run_forced_root_route",
        lambda solver, clauses, pivot, profile: {
            "status": "UNSAT",
            "reason": "DONE",
            "execution_work": 30,
            "replay_work": 5,
            "selected_split_verified": True,
        },
    )
    out = r63._route_with_fallback(object(), [], {}, 1, baseline)
    assert out["fallback_used"] is False
    assert out["full_route_work"] == 35


def test_selftest_preserves_natural_mix_boundary() -> None:
    out = r63.selftest()
    assert out["status"] == "PASS"
    assert out["enrichment"] is False
    assert out["formula_count"] == 60
    assert out["P_VS_NP"] == "OPEN"
