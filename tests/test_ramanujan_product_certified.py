from restored.ramanujan_product_certified import (
    CERTIFIED,
    NOT_CERTIFIED,
    certify_phi_product,
    certify_psi_product,
    certify_ramanujan_f_product,
)
from restored.ramanujan_theta_kernel import phi, psi, ramanujan_f


def test_phi_product_gets_rigorous_tail_interval():
    receipt = certify_phi_product(q="0.9", abs_error="1e-12", max_terms=512)
    assert receipt["status"] == CERTIFIED
    assert receipt["error_bound_le_requested"] is True
    assert receipt["true_value_interval"] is not None
    assert receipt["exact_arithmetic"] is True


def test_psi_product_gets_rigorous_tail_interval():
    receipt = certify_psi_product(q="0.9", abs_error="1e-12", max_terms=512)
    assert receipt["status"] == CERTIFIED
    assert receipt["error_bound_le_requested"] is True
    assert receipt["true_value_interval"] is not None


def test_general_ramanujan_product_gets_rigorous_tail_interval():
    receipt = certify_ramanujan_f_product(a="0.2", b="0.3", abs_error="1e-12", max_terms=128)
    assert receipt["status"] == CERTIFIED
    assert receipt["error_bound_le_requested"] is True
    assert receipt["true_value_interval"] is not None


def test_near_boundary_small_budget_fails_closed():
    receipt = certify_phi_product(
        q="0.999",
        abs_error="1e-12",
        start_terms=8,
        max_terms=64,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 64
    assert receipt["error_bound_le_requested"] is False


def test_product_certificate_bounds_agree_with_direct_series_regression():
    phi_receipt = certify_phi_product(q="0.5", abs_error="1e-12", max_terms=128)
    psi_receipt = certify_psi_product(q="0.5", abs_error="1e-12", max_terms=128)
    f_receipt = certify_ramanujan_f_product(a="0.2", b="0.3", abs_error="1e-12", max_terms=128)

    phi_err = float(phi_receipt["absolute_error_bound_decimal"])
    psi_err = float(psi_receipt["absolute_error_bound_decimal"])
    f_err = float(f_receipt["absolute_error_bound_decimal"])

    assert abs(phi_receipt["estimate"] - float(phi(0.5, 200))) <= phi_err * 1.000001
    assert abs(psi_receipt["estimate"] - float(psi(0.5, 200))) <= psi_err * 1.000001
    assert abs(f_receipt["estimate"] - float(ramanujan_f(0.2, 0.3, 200))) <= f_err * 1.000001


def test_product_certificates_have_zero_runtime_authority():
    receipts = [
        certify_phi_product(q="0.2", abs_error="1e-12", max_terms=128),
        certify_psi_product(q="0.2", abs_error="1e-12", max_terms=128),
        certify_ramanujan_f_product(a="0.2", b="0.3", abs_error="1e-12", max_terms=128),
    ]
    for receipt in receipts:
        assert all(value is False for value in receipt["authority"].values())
