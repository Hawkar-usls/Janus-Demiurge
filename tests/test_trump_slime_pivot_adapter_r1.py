from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

from trump_slime_pivot_adapter_r1 import SlimePivotAdapterError, pivot_priority_patch


class FakeSolver:
    @staticmethod
    def canonical_pivot_order(state, cnf=None):
        return list(cnf if cnf is not None else state)


def test_patch_reorders_only_same_live_set_and_appends_extensions_canonically():
    solver = FakeSolver()
    with pivot_priority_patch(solver, [3, 1, 2]) as stats:
        assert solver.canonical_pivot_order(None, [1, 2, 3]) == [3, 1, 2]
        # Extension 9 was absent from frozen root priority and stays in the
        # canonical suffix after the proposed live roots.
        assert solver.canonical_pivot_order(None, [1, 2, 3, 9]) == [3, 1, 2, 9]
        # If only a subset remains, no dead variable is reintroduced.
        assert solver.canonical_pivot_order(None, [2, 9]) == [2, 9]
    assert stats["pivot_order_calls"] == 3
    assert stats["pivot_order_reorders"] == 2
    assert FakeSolver.canonical_pivot_order(None, [1, 2, 3]) == [1, 2, 3]


def test_duplicate_priority_fails_before_patch():
    solver = FakeSolver()
    with pytest.raises(SlimePivotAdapterError, match="DUPLICATE_PIVOT_PRIORITY"):
        with pivot_priority_patch(solver, [1, 1, 2]):
            pass


def test_unknown_priority_variables_cannot_expand_live_set():
    solver = FakeSolver()
    with pivot_priority_patch(solver, [999, 3, 1, 2]):
        observed = solver.canonical_pivot_order(None, [1, 2, 3])
    assert observed == [3, 1, 2]
    assert set(observed) == {1, 2, 3}
