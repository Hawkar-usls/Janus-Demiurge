from restored.ramanujan_certified_bounds import (
    CERTIFIED,
    NOT_CERTIFIED,
    canonical_certificate_suite,
    certify_q_series,
    certify_ramanujan_f,
)


def test_phi_gets_true_analytic_error_certificate():
    receipt = certify_q_series(
        "phi",
        q="0.9",
        abs_error="1e-12",
        start_terms=4,
        max_terms=256,
        growth=1.5,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["exact_arithmetic"] is True
    assert receipt["estimate_is_certified"] is False
    assert receipt["terms_used"] < 256


def test_theta4_and_psi_are_certified_by_absolute_majorants():
    theta4 = certify_q_series("theta4", q="-0.8", abs_error="1e-12", max_terms=256)
    psi = certify_q_series("psi", q="0.9", abs_error="1e-12", max_terms=256)
    assert theta4["status"] == CERTIFIED
    assert psi["status"] == CERTIFIED
    assert theta4["tail_bound_le_requested"] is True
    assert psi["tail_bound_le_requested"] is True


def test_tight_near_boundary_budget_fails_closed():
    receipt = certify_q_series(
        "phi",
        q="0.999",
        abs_error="1e-12",
        start_terms=8,
        max_terms=64,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 64
    assert receipt["tail_bound_le_requested"] is False


def test_general_ramanujan_f_has_two_sided_tail_certificate():
    receipt = certify_ramanujan_f(
        a="0.2",
        b="0.3",
        abs_error="1e-12",
        start_terms=2,
        max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["input"]["interpretation"] == "EXACT_REAL_RATIONAL_FROM_DECIMAL_SPELLING"


def test_mock_theta_functions_can_be_certified_on_safe_real_q():
    f_receipt = certify_q_series("mock_theta_f", q="0.2", abs_error="1e-12", max_terms=128)
    w_receipt = certify_q_series("mock_theta_omega", q="0.2", abs_error="1e-12", max_terms=128)
    assert f_receipt["status"] == CERTIFIED
    assert w_receipt["status"] == CERTIFIED
    assert f_receipt["denominator_infinite_product_lower_bound"] is not None
    assert w_receipt["denominator_infinite_product_lower_bound"] is not None


def test_certificate_suite_has_zero_runtime_authority():
    suite = canonical_certificate_suite()
    for key, receipt in suite.items():
        if key in {"schema", "authority"}:
            continue
        assert receipt["status"] == CERTIFIED
        assert all(value is False for value in receipt["authority"].values())
