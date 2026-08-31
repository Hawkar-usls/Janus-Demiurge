from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r5a_collision_hash_cons_benchmark as r5a


def test_complete_blocker_has_all_eight_width3_clauses():
    rows = r5a.complete_blocker((2, 3, 4))
    assert len(rows) == 8
    assert len(set(rows)) == 8
    assert all(len(row) == 3 for row in rows)


def test_collision_formula_has_exact_frozen_shape():
    generated = r5a.collision_formula(8101)
    assert len(generated["base_child"]) == 32
    assert len(generated["root"]) == 64
    assert len(generated["triples"]) == 4
    flat = sorted(v for triple in generated["triples"] for v in triple)
    assert flat == list(range(2, 14))
    assert all(len(c) == 3 for c in generated["base_child"])
    assert all(len(c) == 4 for c in generated["root"])


def test_collision_root_is_exactly_unsat_by_independent_truth_oracle():
    generated = r5a.collision_formula(8101)
    truth = r5a.exact_truth_oracle_13var(generated["root"])
    assert truth == {"status": "UNSAT", "assignments_tested": 8192, "witness": None}


def test_frozen_seed_partitions_are_unique():
    spec = r5a.load_spec()
    roots = set()
    for seed in spec["holdout"]["seeds"]:
        generated = r5a.collision_formula(seed)
        roots.add(tuple(tuple(c) for c in generated["root"]))
    assert len(roots) == 24
