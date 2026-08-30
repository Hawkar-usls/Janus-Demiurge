from pathlib import Path
import importlib.util
import sys


MODULE = Path(__file__).resolve().parents[1] / "trump" / "janus_soul_hindsight.py"
SPEC = importlib.util.spec_from_file_location("janus_soul_hindsight", MODULE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def test_exact_failure_is_rejected_but_neighbor_is_not_promoted():
    soul = MOD.HindsightSoul(max_work=100, max_bytes=1000)
    state = {"state": 7}
    bad = {"op": "expand", "pivot": 3}
    neighbor = {"op": "factor", "pivot": 3}

    soul.record_exact_failure(
        state=state,
        action=bad,
        axis="POLY_FIND",
        mechanism="KNOWN_DEAD_ROUTE",
        trace_digest="trace-demo",
        verifier_digest="verifier-demo",
    )

    assert soul.classify(state=state, action=bad) is MOD.Decision.REJECT_KNOWN_BAD
    assert soul.classify(state=state, action=neighbor) is MOD.Decision.NOT_KNOWN_BAD


def test_freeze_forbids_post_hoc_learning():
    soul = MOD.HindsightSoul(max_work=100, max_bytes=1000)
    soul.freeze()

    try:
        soul.record_exact_failure(
            state={"s": 1},
            action={"a": 1},
            axis="POLY_HOLD",
            mechanism="POST_HOC",
            trace_digest="t",
            verifier_digest="v",
        )
    except RuntimeError as exc:
        assert "post-hoc" in str(exc)
    else:
        raise AssertionError("Frozen theorem face accepted post-hoc learning")


def test_hotel_california_gate_requires_strict_bounded_descent():
    gate = MOD.HindsightSoul.hotel_california_gate
    assert gate(before_rank=5, after_rank=4, polynomial_rank_cap=9) is MOD.Decision.PASS_PROGRESS
    assert gate(before_rank=5, after_rank=5, polynomial_rank_cap=9) is MOD.Decision.REJECT_NO_PROGRESS
    assert gate(before_rank=5, after_rank=6, polynomial_rank_cap=9) is MOD.Decision.REJECT_NO_PROGRESS
    assert gate(before_rank=10, after_rank=9, polynomial_rank_cap=9) is MOD.Decision.REJECT_NO_PROGRESS


def test_debt_is_charged_and_fails_closed():
    soul = MOD.HindsightSoul(max_work=2, max_bytes=10)
    assert soul.ledger.charge(work=2, bytes_used=10) is MOD.Decision.PASS_DEBT_BOUND
    assert soul.ledger.charge(work=1) is MOD.Decision.REJECT_DEBT_BOUND
    assert soul.ledger.work == 2
    assert soul.ledger.bytes_used == 10


def test_selftest_preserves_scientific_boundary():
    result = MOD.selftest()
    assert result["status"] == "PASS"
    assert result["scientific_boundary"] == "P_VS_NP_OPEN"
