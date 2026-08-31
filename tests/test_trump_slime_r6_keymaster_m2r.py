from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import trump_slime_r6_keymaster_m2r as r6


class FakeSolver:
    def __init__(self, fp: str = "10000000" + "0" * 56):
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


def memory_for_candidates(solver, cnf, *, open_exposures=0):
    candidates, _, _ = r6.build_candidate_views(solver, cnf)
    aggregates = {}
    for i, candidate in enumerate(candidates):
        aggregates[candidate["context_bucket"]] = {
            "count": 3,
            "mean": float(100 + i * 100),
            "M2": 0.0,
            "sample_variance": 0.0,
            "OPEN_exposures": int(open_exposures),
        }
    return {
        "source_identity": r6.source_identity(),
        "episodes": [{"immutable": True}],
        "global_decisive_execution_work": {"count": 9, "mean": 300.0, "M2": 0.0, "sample_variance": 0.0},
        "aggregates": aggregates,
    }, candidates


def test_transferable_features_exclude_numeric_pivot_id():
    solver = FakeSolver()
    rows, _ = r6.structural_feature_rows(solver, sample_cnf())
    assert rows
    for row in rows:
        features = r6.transferable_features(row)
        assert "var" not in features
        assert "pivot_id_local" not in features
        assert "canonical_index" not in features


def test_coarse_bucket_matches_structural_not_local_pivot_provenance():
    solver = FakeSolver()
    rows, _ = r6.structural_feature_rows(solver, sample_cnf())
    features = r6.transferable_features(rows[0])
    with_fake_pivot = dict(features)
    with_fake_pivot["pivot_id_local"] = 999999
    assert r6.coarse_bucket(features) == r6.coarse_bucket(with_fake_pivot)


def test_open_exposure_does_not_change_numeric_prediction():
    solver = FakeSolver(fp="10000000" + "0" * 56)  # no exploration trigger
    cnf = sample_cnf()
    memory0, _ = memory_for_candidates(solver, cnf, open_exposures=0)
    memory9, _ = memory_for_candidates(solver, cnf, open_exposures=999)
    selected0 = r6.select_root_route(solver, cnf, memory0)
    selected9 = r6.select_root_route(solver, cnf, memory9)
    assert selected0["selected"] is not None and selected9["selected"] is not None
    assert selected0["selected"]["view"] == selected9["selected"]["view"]
    assert selected0["selected"]["predicted_execution_work"] == selected9["selected"]["predicted_execution_work"]


def test_source_identity_drift_cold_resets_without_deleting_history():
    solver = FakeSolver()
    cnf = sample_cnf()
    memory, _ = memory_for_candidates(solver, cnf)
    drifted = dict(r6.source_identity())
    drifted["R5_runtime_git_blob_sha"] = "deadbeef"
    selected = r6.select_root_route(solver, cnf, memory, identity=drifted)
    assert selected["selected"] is None
    assert selected["cold_reset"] is True
    assert selected["memory_stale"] is True
    assert selected["history_retained"] is True
    assert selected["top_k"] == ["R5_FALLBACK_SENTINEL"]


def test_deterministic_exploration_uses_supported_diversity_alternate():
    solver = FakeSolver(fp="00000000" + "0" * 56)  # int(prefix,16) % 10 == 0
    cnf = sample_cnf()
    memory, candidates = memory_for_candidates(solver, cnf)
    if len(candidates) < 2:
        raise AssertionError("test fixture must produce at least two distinct candidate pivots")
    selected = r6.select_root_route(solver, cnf, memory)
    assert selected["exploration_trigger"] is True
    assert selected["diversity_alternate"] is not None
    assert selected["selected"] is not None
    assert selected["selected"]["pivot_id_local"] == selected["diversity_alternate"]["pivot_id_local"]


def test_unsupported_memory_falls_back_without_materializing_r5_baseline_pivot():
    solver = FakeSolver()
    cnf = sample_cnf()
    memory = {
        "source_identity": r6.source_identity(),
        "episodes": [{"immutable": True}],
        "global_decisive_execution_work": {"count": 1, "mean": 1.0, "M2": 0.0, "sample_variance": 0.0},
        "aggregates": {},
    }
    selected = r6.select_root_route(solver, cnf, memory)
    assert selected["selected"] is None
    assert selected["supported"] == []
    assert selected["top_k"][-1] == "R5_FALLBACK_SENTINEL"


def test_welford_matches_direct_mean_and_variance():
    w = r6.Welford()
    for value in (10.0, 20.0, 30.0):
        w.add(value)
    out = w.json()
    assert out["count"] == 3
    assert out["mean"] == 20.0
    assert out["sample_variance"] == 100.0


def test_frozen_holdout_does_not_overlap_calibration_seeds():
    spec = r6.load_frozen_spec()
    train = set()
    train.update(spec["finalized_calibration_sources"]["initial_R5_receipt"]["training_subjects"]["seeds"])
    for family in ("GT6", "GT7"):
        train.update(spec["finalized_calibration_sources"]["R5B2_receipt"]["training_subjects"][family])
    for family in ("GT6_WRAPPED", "GT7_WRAPPED"):
        train.update(spec["finalized_calibration_sources"]["R5A2_receipt"]["training_subjects"][family])
    holdout = set()
    for seeds in spec["fresh_holdout"].values():
        if isinstance(seeds, list):
            holdout.update(seeds)
    assert train.isdisjoint(holdout)
