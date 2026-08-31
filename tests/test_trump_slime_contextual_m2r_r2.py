from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

from trump_slime_contextual_m2r_r2 import contextual_features, rank_contextual_pivots


def test_rank_never_changes_pivot_set():
    cnf = ((1, 2, 3), (-1, 2, 4), (1, -3, 4), (-2, -3, 4))
    canonical = [1, 2, 3, 4]
    ordered, detail = rank_contextual_pivots(cnf, canonical, state_cap=100)
    assert len(ordered) == len(canonical)
    assert set(ordered) == set(canonical)
    assert detail["feature_work"] > 0


def test_unknown_or_dead_variables_are_not_invented():
    cnf = ((1, 2), (-1, 3))
    ordered, _ = rank_contextual_pivots(cnf, [1, 2, 3], state_cap=100)
    assert set(ordered) == {1, 2, 3}
    assert 999 not in ordered


def test_pure_pivot_gets_zero_parent_pairs_and_certified_bound_is_retained_only():
    cnf = ((1, 2, 3), (1, -2, 4), (2, 3, 4))
    rows, _ = contextual_features(cnf, [1, 2, 3, 4], state_cap=10**9)
    row = next(r for r in rows if r["var"] == 1)
    assert row["negative"] == 0
    assert row["parent_pairs"] == 0
    assert row["certified_raw_upper_units"] == row["retained_units"]


def test_safe_upper_is_one_sided_certificate_not_negative_when_false():
    cnf = ((1, 2, 3), (-1, 2, 4), (1, -3, 4), (-1, -2, -4))
    rows, _ = contextual_features(cnf, [1, 2, 3, 4], state_cap=1)
    assert all(r["certified_cap_safe"] is False for r in rows)
    # False means only "not certified by this bound"; rows remain rankable.
    ordered, _ = rank_contextual_pivots(cnf, [1, 2, 3, 4], state_cap=1)
    assert set(ordered) == {1, 2, 3, 4}


def test_ties_preserve_canonical_order():
    # v1 and v2 have symmetric occurrence geometry.
    cnf = ((1, 2, 3), (-1, -2, 4), (1, 2, -4), (-1, -2, -3))
    ordered, detail = rank_contextual_pivots(cnf, [2, 1, 3, 4], state_cap=10**9)
    by_var = {r["var"]: r for r in detail["rows"]}
    if by_var[1]["rank_tuple"][:-1] == by_var[2]["rank_tuple"][:-1]:
        assert ordered.index(2) < ordered.index(1)
