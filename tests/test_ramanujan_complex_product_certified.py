from restored.ramanujan_complex_product_certified import (
    CERTIFIED,
    NOT_CERTIFIED,
    OUTSIDE_BOUND_DOMAIN,
    certify_complex_phi_product,
    certify_complex_psi_product,
    certify_complex_ramanujan_f_product,
)
from restored.ramanujan_theta_kernel import phi_product, psi_product, ramanujan_f_product


def test_complex_phi_and_psi_products_get_rigorous_certificates():
    receipts = [
        certify_complex_phi_product(q=("0.3", "0.2"), abs_error="1e-12", max_terms=128),
        certify_complex_psi_product(q=("0.3", "0.2"), abs_error="1e-12", max_terms=128),
    ]
    for receipt in receipts:
        assert receipt["status"] == CERTIFIED
        assert receipt["error_bound_le_requested"] is True
        assert receipt["exact_arithmetic"] == "GAUSSIAN_RATIONAL_Q_I"


def test_complex_general_ramanujan_product_gets_rigorous_certificate():
    receipt = certify_complex_ramanujan_f_product(
        a=("0.2", "0.1"),
        b=("0.3", "-0.05"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["error_bound_le_requested"] is True
    assert receipt["input"]["interpretation"] == "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"


def test_complex_product_l1_domain_boundary_is_visible():
    receipt = certify_complex_phi_product(q=("0.8", "0.3"), abs_error="1e-12", max_terms=128)
    assert receipt["status"] == OUTSIDE_BOUND_DOMAIN
    assert receipt["terms_used"] == 0
    assert receipt["bound_geometry"] == "L1_MAJORANT_DIAMOND"


def test_complex_product_small_budget_fails_closed():
    receipt = certify_complex_phi_product(
        q=("0.9", "0.05"),
        abs_error="1e-12",
        start_terms=2,
        max_terms=8,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 8
    assert receipt.get("error_bound_le_requested", False) is False


def test_complex_product_bounds_cover_float_regression_values():
    q = 0.3 + 0.2j
    phi_receipt = certify_complex_phi_product(q=("0.3", "0.2"), abs_error="1e-12", max_terms=128)
    psi_receipt = certify_complex_psi_product(q=("0.3", "0.2"), abs_error="1e-12", max_terms=128)
    f_receipt = certify_complex_ramanujan_f_product(a=("0.2", "0.1"), b=("0.3", "-0.05"), abs_error="1e-12", max_terms=128)

    phi_est = complex(*phi_receipt["estimate"])
    psi_est = complex(*psi_receipt["estimate"])
    f_est = complex(*f_receipt["estimate"])
    phi_bound = float(phi_receipt["absolute_error_bound_decimal"])
    psi_bound = float(psi_receipt["absolute_error_bound_decimal"])
    f_bound = float(f_receipt["absolute_error_bound_decimal"])

    assert abs(phi_est - complex(phi_product(q, 200))) <= phi_bound * 1.00001 + 1e-15
    assert abs(psi_est - complex(psi_product(q, 200))) <= psi_bound * 1.00001 + 1e-15
    assert abs(f_est - complex(ramanujan_f_product(0.2 + 0.1j, 0.3 - 0.05j, 200))) <= f_bound * 1.00001 + 1e-15


def test_complex_product_certificates_have_zero_runtime_authority():
    receipts = [
        certify_complex_phi_product(q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
        certify_complex_psi_product(q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
        certify_complex_ramanujan_f_product(a=("0.2", "0.1"), b=("0.3", "-0.05"), abs_error="1e-12", max_terms=128),
    ]
    for receipt in receipts:
        assert all(value is False for value in receipt["authority"].values())
