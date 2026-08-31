from __future__ import annotations

import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r5a2_wrapped_gt_hash_cons_benchmark as r5a2


def test_logical_graph_tautology_schema_counts():
    for n in (6, 7):
        cnf, count = r5a2.logical_graph_tautology(n)
        assert count == comb(n, 2)
        assert len(cnf) == n + 2 * comb(n, 3)


def test_wrapped_gt3_bruteforce_unsat_regression():
    assert r5a2.tiny_wrapped_truth_regression() == "UNSAT"


def test_every_frozen_subject_has_exact_selector_collision_by_construction():
    spec = r5a2.load_spec()
    roots = set()
    for family in ("GT6_WRAPPED", "GT7_WRAPPED"):
        order = spec["holdout"][family]["order"]
        logical, count = r5a2.logical_graph_tautology(order)
        for seed in spec["holdout"][family]["seeds"]:
            mapping = r5a2.seeded_base_mapping(count, seed)
            base = r5a2.rename_cnf(logical, mapping)
            assert r5a2.inverse_rename_cnf(base, mapping) == logical
            root = r5a2.selector_wrap(base)
            # Independent Boolean restriction by literal filtering; do not call C025.
            def restrict_selector(bit):
                true_lit = 1 if bit else -1
                false_lit = -true_lit
                rows = []
                for clause in root:
                    if true_lit in clause:
                        continue
                    rows.append(tuple(lit for lit in clause if lit != false_lit))
                return r5a2.local_canon_cnf(rows)
            assert restrict_selector(0) == base
            assert restrict_selector(1) == base
            roots.add(root)
    assert len(roots) == 24


def test_no_hit_dict_preserves_writes_but_disables_membership_retrieval():
    memo = r5a2.NoHitDict()
    memo["x"] = {"status": "UNSAT"}
    assert memo["x"]["status"] == "UNSAT"
    assert "x" not in memo


def test_frozen_seed_sets_are_exact_and_disjoint():
    spec = r5a2.load_spec()
    gt6 = spec["holdout"]["GT6_WRAPPED"]["seeds"]
    gt7 = spec["holdout"]["GT7_WRAPPED"]["seeds"]
    assert gt6 == list(range(11101, 11113))
    assert gt7 == list(range(11201, 11213))
    assert set(gt6).isdisjoint(gt7)
    assert len(gt6) + len(gt7) == 24
