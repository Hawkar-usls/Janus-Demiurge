from restored.ramanujan_complex_certified import (
    CERTIFIED,
    NOT_CERTIFIED,
    OUTSIDE_BOUND_DOMAIN,
    as_empirical_complex,
    certify_complex_q_series,
    certify_complex_ramanujan_f,
)
from restored.ramanujan_theta_kernel import theta3, psi, ramanujan_f


def test_exact_complex_theta3_gets_analytic_certificate():
    receipt = certify_complex_q_series(
        "theta3",
        q=("0.3", "0.2"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["exact_arithmetic"] == "GAUSSIAN_RATIONAL_Q_I"
    assert receipt["bound_geometry"] == "L1_MAJORANT_DIAMOND"


def test_exact_complex_psi_and_mock_theta_functions_certify():
    receipts = [
        certify_complex_q_series("psi", q={"re": "0.2", "im": "0.1"}, abs_error="1e-12", max_terms=128),
        certify_complex_q_series("mock_theta_f", q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
        certify_complex_q_series("mock_theta_omega", q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
    ]
    for receipt in receipts:
        assert receipt["status"] == CERTIFIED
        assert receipt["tail_bound_le_requested"] is True


def test_exact_complex_general_ramanujan_f_certifies():
    receipt = certify_complex_ramanujan_f(
        a=("0.2", "0.1"),
        b=("0.3", "-0.05"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["input"]["interpretation"] == "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"


def test_l1_domain_is_conservative_and_visible():
    # Euclidean modulus is < 1, but the current exact proof uses rho=|Re|+|Im|.
    receipt = certify_complex_q_series(
        "theta3",
        q=("0.8", "0.3"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == OUTSIDE_BOUND_DOMAIN
    assert receipt["terms_used"] == 0
    assert "L1_MAJORANT" in receipt["bound_geometry"]


def test_complex_near_boundary_small_budget_fails_closed():
    receipt = certify_complex_q_series(
        "theta3",
        q=("0.9", "0.05"),
        abs_error="1e-12",
        start_terms=2,
        max_terms=8,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 8
    assert receipt["tail_bound_le_requested"] is False


def test_complex_certificate_regression_against_float_kernel():
    q_pair = ("0.3", "0.2")
    q = as_empirical_complex(q_pair)
    theta_receipt = certify_complex_q_series("theta3", q=q_pair, abs_error="1e-12", max_terms=128)
    psi_receipt = certify_complex_q_series("psi", q=q_pair, abs_error="1e-12", max_terms=128)
    f_receipt = certify_complex_ramanujan_f(a=("0.2", "0.1"), b=("0.3", "-0.05"), abs_error="1e-12", max_terms=128)

    theta_est = complex(*theta_receipt["estimate"])
    psi_est = complex(*psi_receipt["estimate"])
    f_est = complex(*f_receipt["estimate"])
    theta_bound = float(theta_receipt["tail_bound_decimal"])
    psi_bound = float(psi_receipt["tail_bound_decimal"])
    f_bound = float(f_receipt["tail_bound_decimal"])

    assert abs(theta_est - complex(theta3(q, 200))) <= theta_bound * 1.00001 + 1e-15
    assert abs(psi_est - complex(psi(q, 200))) <= psi_bound * 1.00001 + 1e-15
    assert abs(f_est - complex(ramanujan_f(0.2 + 0.1j, 0.3 - 0.05j, 200))) <= f_bound * 1.00001 + 1e-15


def test_complex_certificates_have_zero_runtime_authority():
    receipts = [
        certify_complex_q_series("theta4", q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
        certify_complex_ramanujan_f(a=("0.2", "0.1"), b=("0.3", "-0.05"), abs_error="1e-12", max_terms=128),
    ]
    for receipt in receipts:
        assert all(value is False for value in receipt["authority"].values())
