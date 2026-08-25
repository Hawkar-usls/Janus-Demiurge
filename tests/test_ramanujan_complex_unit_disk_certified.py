from fractions import Fraction

from restored.ramanujan_complex_certified import GaussianRational
from restored.ramanujan_complex_unit_disk_certified import (
    BOUND_GEOMETRY,
    CERTIFIED,
    NOT_CERTIFIED,
    OUTSIDE_BOUND_DOMAIN,
    certify_complex_phi_product_disk,
    certify_complex_psi_product_disk,
    certify_complex_q_series_disk,
    certify_complex_ramanujan_f_disk,
    certify_complex_ramanujan_f_product_disk,
    exact_squared_modulus,
    rational_euclidean_majorant,
    selected_modulus_majorant,
)


def test_rational_amgm_majorant_is_exact_and_closes_old_l1_hole():
    q = GaussianRational(Fraction(4, 5), Fraction(3, 10))
    assert exact_squared_modulus(q) == Fraction(73, 100)
    assert rational_euclidean_majorant(q) == Fraction(173, 200)
    assert q.l1() == Fraction(11, 10)
    assert selected_modulus_majorant(q) == Fraction(173, 200)


def test_point_inside_unit_disk_but_outside_old_l1_diamond_now_certifies():
    receipt = certify_complex_q_series_disk(
        "theta3",
        q=("0.8", "0.3"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["tail_bound_le_requested"] is True
    assert receipt["bound_geometry"] == BOUND_GEOMETRY
    assert receipt["input"]["majorant_profile"]["inside_open_unit_disk"] is True


def test_product_side_same_old_l1_hole_now_certifies():
    receipts = [
        certify_complex_phi_product_disk(q=("0.8", "0.3"), abs_error="1e-12", max_terms=256),
        certify_complex_psi_product_disk(q=("0.8", "0.3"), abs_error="1e-12", max_terms=256),
    ]
    for receipt in receipts:
        assert receipt["status"] == CERTIFIED
        assert receipt["error_bound_le_requested"] is True
        assert receipt["bound_geometry"] == BOUND_GEOMETRY


def test_general_f_uses_exact_ab_domain_not_product_of_l1_bounds():
    # Old L1 gate: rho(a)=1.4 and rho(b)=0.9, product=1.26 -> rejected.
    # Exact product is 0.64-0.02i, so |ab|^2=0.4100 < 1.
    direct = certify_complex_ramanujan_f_disk(
        a=("0.8", "0.6"),
        b=("0.5", "-0.4"),
        abs_error="1e-12",
        max_terms=256,
    )
    product = certify_complex_ramanujan_f_product_disk(
        a=("0.8", "0.6"),
        b=("0.5", "-0.4"),
        abs_error="1e-12",
        max_terms=256,
    )
    assert direct["status"] == CERTIFIED
    assert direct["tail_bound_le_requested"] is True
    assert product["status"] == CERTIFIED
    assert product["error_bound_le_requested"] is True


def test_outside_true_unit_disk_still_fails_closed():
    receipt = certify_complex_q_series_disk(
        "theta3",
        q=("0.8", "0.7"),
        abs_error="1e-12",
        max_terms=128,
    )
    assert receipt["status"] == OUTSIDE_BOUND_DOMAIN
    assert receipt["terms_used"] == 0
    assert receipt["input"]["majorant_profile"]["inside_open_unit_disk"] is False


def test_near_boundary_tight_budget_can_still_refuse_certificate():
    receipt = certify_complex_q_series_disk(
        "theta3",
        q=("0.99", "0.01"),
        abs_error="1e-14",
        start_terms=2,
        max_terms=8,
        growth=2.0,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["terms_used"] == 8
    assert receipt["tail_bound_le_requested"] is False


def test_new_complex_disk_certificates_never_grant_runtime_authority():
    receipts = [
        certify_complex_q_series_disk("mock_theta_f", q=("0.2", "0.1"), abs_error="1e-12", max_terms=128),
        certify_complex_phi_product_disk(q=("0.3", "0.2"), abs_error="1e-12", max_terms=128),
        certify_complex_ramanujan_f_disk(a=("0.8", "0.6"), b=("0.5", "-0.4"), abs_error="1e-12", max_terms=256),
    ]
    for receipt in receipts:
        assert all(value is False for value in receipt["authority"].values())
