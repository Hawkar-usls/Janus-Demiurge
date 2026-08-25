from restored.ramanujan_theta2_certified import (
    CERTIFIED,
    NOT_CERTIFIED,
    certify_theta2,
)


def test_theta2_positive_rational_gets_analytic_certificate():
    receipt = certify_theta2(q="0.9", abs_error="1e-12", max_terms=256)
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["certified_object"] == "EXACT_SYMBOLIC_ALGEBRAIC_PARTIAL_SUM_PLUS_RATIONAL_ANALYTIC_TAIL_BOUND"
    assert receipt["estimate_is_certified"] is False
    assert receipt["exact_symbolic_partial_sum"]["common_algebraic_factor"] == "q^(1/4)"


def test_theta2_near_boundary_small_budget_fails_closed():
    receipt = certify_theta2(
        q="0.999",
        abs_error="1e-12",
        start_terms=8,
        max_terms=64,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 64
    assert receipt["tail_bound_le_requested"] is False


def test_theta2_symbolic_coefficient_is_exact_and_authority_zero():
    receipt = certify_theta2(q="0.2", abs_error="1e-12", max_terms=128)
    coeff = receipt["exact_symbolic_partial_sum"]["C_N"]
    assert "numerator_sha256" in coeff
    assert "denominator_sha256" in coeff
    assert all(value is False for value in receipt["authority"].values())


def test_theta2_certified_lane_rejects_nonpositive_real_q():
    for q in ("0", "-0.2", "1"):
        try:
            certify_theta2(q=q)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for q={q}")
