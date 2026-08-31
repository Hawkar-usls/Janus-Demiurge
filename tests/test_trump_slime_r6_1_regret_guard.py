from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import trump_slime_r6_keymaster_m2r as base
import trump_slime_r6_1_regret_guard as guard


class FakeSolver:
    def __init__(self, fp: str):
        self.fp = fp
    @staticmethod
    def vars_of(cnf):
        return tuple(sorted({abs(lit) for clause in cnf for lit in clause}))
    @staticmethod
    def state_units(cnf):
        return 1 + len(cnf) + sum(len(c) for c in cnf)
    @classmethod
    def input_size_units(cls, cnf):
        return max(2, cls.state_units(cnf) + len(cls.vars_of(cnf)))
    def fingerprint(self, cnf):
        return self.fp


def sample_cnf():
    return (
        (1, 2, 3), (-1, 2, 4), (1, -3, 4), (-1, -2, 5),
        (2, 3, 5), (-2, 4, 5), (3, -4, 5), (-3, -4, -5),
    )


def make_memory(solver, cnf, *, alternate_mean: float):
    candidates, _, _ = base.build_candidate_views(solver, cnf)
    assert len(candidates) >= 2
    aggregates = {}
    for i, candidate in enumerate(candidates):
        aggregates[candidate["context_bucket"]] = {
            "count": 3,
            "mean": 100.0 if i == 0 else float(alternate_mean),
            "M2": 0.0,
            "sample_variance": 0.0,
            "OPEN_exposures": 0,
        }
    return {
        "source_identity": base.source_identity(),
        "episodes": [{"immutable": True}],
        "global_decisive_execution_work": {"count": 9, "mean": 100.0, "M2": 0.0, "sample_variance": 0.0},
        "aggregates": aggregates,
    }


def test_high_predicted_regret_is_shadow_rejected_on_trigger():
    solver = FakeSolver("00000000" + "0" * 56)
    cnf = sample_cnf()
    memory = make_memory(solver, cnf, alternate_mean=500.0)
    out = guard.select_root_route(solver, cnf, memory)
    assert out["exploration_trigger"] is True
    assert out["diversity_alternate"] is not None
    assert out["predicted_regret_ratio"] > 1.25
    assert out["regret_guard_shadow_reject"] is True
    assert out["exploration_alternate_exact_executed"] is False
    assert out["selected"]["pivot_id_local"] == out["memory_best"]["pivot_id_local"]


def test_low_predicted_regret_executes_diversity_alternate_on_trigger():
    solver = FakeSolver("00000000" + "0" * 56)
    cnf = sample_cnf()
    memory = make_memory(solver, cnf, alternate_mean=110.0)
    out = guard.select_root_route(solver, cnf, memory)
    assert out["exploration_trigger"] is True
    assert out["diversity_alternate"] is not None
    assert out["predicted_regret_ratio"] <= 1.25
    assert out["regret_guard_shadow_reject"] is False
    assert out["exploration_alternate_exact_executed"] is True
    assert out["selected"]["pivot_id_local"] == out["diversity_alternate"]["pivot_id_local"]


def test_no_trigger_keeps_memory_best_even_when_alternate_supported():
    solver = FakeSolver("10000000" + "0" * 56)
    cnf = sample_cnf()
    memory = make_memory(solver, cnf, alternate_mean=110.0)
    out = guard.select_root_route(solver, cnf, memory)
    assert out["exploration_trigger"] is False
    assert out["selected"]["pivot_id_local"] == out["memory_best"]["pivot_id_local"]
    assert out["exploration_alternate_exact_executed"] is False


def test_source_drift_still_cold_resets_to_r5_fallback():
    solver = FakeSolver("00000000" + "0" * 56)
    cnf = sample_cnf()
    memory = make_memory(solver, cnf, alternate_mean=110.0)
    drifted = dict(base.source_identity())
    drifted["R5_runtime_git_blob_sha"] = "drift"
    out = guard.select_root_route(solver, cnf, memory, identity=drifted)
    assert out["cold_reset"] is True
    assert out["selected"] is None
    assert out["top_k"] == ["R5_FALLBACK_SENTINEL"]


def test_threshold_is_frozen_at_1_25_and_not_runtime_mutable():
    spec = guard.load_frozen_spec()
    assert spec["single_successor_change"]["exact_execution_threshold"] == 1.25
    assert spec["single_successor_change"]["regret_guard_may_update_threshold_on_holdout"] is False
