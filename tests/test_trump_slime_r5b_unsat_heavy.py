from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import run_trump_slime_r5b_unsat_heavy_benchmark as r5b


def test_exact_truth_oracle_rejects_a_simple_sat_formula():
    clauses = [[1]] + [[v, -v + 1 if v < 12 else -1] for v in range(2, 13)]
    # Use a cleaner explicit SAT 12-variable formula; all variables appear.
    clauses = [[v] for v in range(1, 13)]
    result = r5b.exact_truth_oracle_12var(clauses)
    assert result["status"] == "SAT"
    assert result["witness"] is not None


def test_all_frozen_php_variants_are_exactly_unsat():
    spec = r5b.load_spec()
    fps = set()
    for seed in spec["formula_families"]["PHP_4_INTO_3"]["seeds"]:
        clauses = r5b.php_4_into_3(seed)
        assert len(clauses) == 22
        truth = r5b.exact_truth_oracle_12var(clauses)
        assert truth == {"status": "UNSAT", "assignments_tested": 4096, "witness": None}
        fps.add(tuple(tuple(c) for c in clauses))
    assert len(fps) == 12


def test_all_frozen_k4_variants_are_exactly_unsat():
    spec = r5b.load_spec()
    fps = set()
    for seed in spec["formula_families"]["K4_THREE_COLOR"]["seeds"]:
        clauses = r5b.k4_three_color(seed)
        assert len(clauses) == 34
        truth = r5b.exact_truth_oracle_12var(clauses)
        assert truth == {"status": "UNSAT", "assignments_tested": 4096, "witness": None}
        fps.add(tuple(tuple(c) for c in clauses))
    assert len(fps) == 12


def test_family_generators_are_disjoint_and_total_holdout_is_24():
    spec = r5b.load_spec()
    rows = r5b.build_holdout(spec)
    assert len(rows) == 24
    assert sum(row["family"] == "PHP_4_INTO_3" for row in rows) == 12
    assert sum(row["family"] == "K4_THREE_COLOR" for row in rows) == 12
    serialized = {tuple(tuple(c) for c in row["clauses"]) for row in rows}
    assert len(serialized) == 24
    assert all(row["truth"]["status"] == "UNSAT" for row in rows)
