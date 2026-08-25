import cmath

from restored.ramanujan_adaptive_precision import (
    CONVERGED,
    NOT_CONVERGED,
    adaptive_evaluate,
    adaptive_identity_gate,
)


def test_adaptive_single_theta3_converges_without_fixed_term_assumption():
    receipt = adaptive_evaluate(
        "theta3",
        q=0.2,
        abs_tol=1e-12,
        rel_tol=1e-12,
        start_terms=4,
        max_terms=128,
        stable_steps=2,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["terms_used"] <= 128
    assert receipt["error_proxy"] <= receipt["threshold"]
    assert receipt["formal_error_bound"] is False


def test_adaptive_complex_q_theta3_converges():
    q = 0.6 * cmath.exp(0.3j)
    receipt = adaptive_evaluate(
        "theta3",
        q=q,
        abs_tol=1e-12,
        rel_tol=1e-12,
        start_terms=8,
        max_terms=256,
        stable_steps=2,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["terms_used"] <= 256


def test_adaptive_phi_identity_near_unit_circle_reaches_requested_tolerance():
    receipt = adaptive_identity_gate(
        "phi",
        q=0.99,
        abs_tol=1e-12,
        rel_tol=1e-12,
        start_terms=64,
        max_terms=4096,
        growth=1.5,
        stable_steps=2,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["identity_residual"] <= receipt["identity_threshold"]
    assert receipt["terms_used"] > 64


def test_tight_near_boundary_budget_fails_closed_instead_of_claiming_precision():
    receipt = adaptive_identity_gate(
        "phi",
        q=0.999,
        abs_tol=1e-14,
        rel_tol=0.0,
        start_terms=16,
        max_terms=256,
        growth=2.0,
        stable_steps=2,
    )
    assert receipt["status"] == NOT_CONVERGED
    assert receipt["terms_used"] == 256
    assert receipt["identity_residual"] > receipt["identity_threshold"]


def test_general_ramanujan_theta_direct_and_product_adapt_together():
    receipt = adaptive_identity_gate(
        "ramanujan_f",
        a=0.2 + 0.1j,
        b=0.3 - 0.05j,
        abs_tol=1e-12,
        rel_tol=1e-12,
        start_terms=8,
        max_terms=256,
        stable_steps=2,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["identity_residual"] <= receipt["identity_threshold"]


def test_precision_receipt_has_no_runtime_authority():
    receipt = adaptive_evaluate("mock_theta_f", q=0.2, start_terms=8, max_terms=128)
    assert receipt["status"] == CONVERGED
    assert all(value is False for value in receipt["authority"].values())
