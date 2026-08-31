from __future__ import annotations

import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r5b2_graph_tautology_benchmark as r5b2


def test_logical_gt6_gt7_schema_counts():
    for n in (6, 7):
        cnf, variables = r5b2.logical_graph_tautology(n)
        assert variables == comb(n, 2)
        assert len(cnf) == n + 2 * comb(n, 3)
        assert sum(len(c) == n - 1 for c in cnf) == n
        assert sum(len(c) == 3 for c in cnf) == 2 * comb(n, 3)


def test_tiny_graph_tautologies_bruteforce_unsat():
    assert r5b2.tiny_truth_regression() == {"GT3": "UNSAT", "GT4": "UNSAT"}


def test_every_frozen_renaming_inverse_reconstructs_exact_logical_formula():
    spec = r5b2.load_spec()
    fingerprints = set()
    for family in ("GT6", "GT7"):
        order = spec["holdout"][family]["order"]
        logical, count = r5b2.logical_graph_tautology(order)
        for seed in spec["holdout"][family]["seeds"]:
            mapping = r5b2.seeded_bijection(count, seed)
            assert any(mapping[v] != v for v in mapping)
            renamed = r5b2.rename_cnf(logical, mapping)
            assert r5b2.inverse_rename_cnf(renamed, mapping) == logical
            cert = r5b2.structural_certificate(order, seed)
            assert cert["structural_truth"] == "UNSAT"
            assert cert["inverse_renaming_reconstructs_logical_GT"] is True
            fingerprints.add(tuple(tuple(c) for c in renamed))
    assert len(fingerprints) == 24


def test_frozen_seed_sets_are_fresh_disjoint_and_exactly_24():
    spec = r5b2.load_spec()
    gt6 = spec["holdout"]["GT6"]["seeds"]
    gt7 = spec["holdout"]["GT7"]["seeds"]
    assert gt6 == list(range(9101, 9113))
    assert gt7 == list(range(9201, 9213))
    assert set(gt6).isdisjoint(gt7)
    assert len(gt6) + len(gt7) == 24
