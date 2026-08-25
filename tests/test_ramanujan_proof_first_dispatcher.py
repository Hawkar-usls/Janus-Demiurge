from restored.ramanujan_adaptive_precision import CONVERGED
from restored.ramanujan_certified_bounds import CERTIFIED, NOT_CERTIFIED
from restored.ramanujan_proof_first_dispatcher import (
    EMPIRICAL_ONLY,
    NO_NUMERICAL_ASSURANCE,
    proof_first_evaluate,
)


def test_proof_first_stops_after_true_certificate():
    receipt = proof_first_evaluate("phi", q="0.9", precision="1e-12")
    assert receipt["status"] == CERTIFIED
    assert receipt["assurance_class"] == "ANALYTIC_CERTIFIED_ERROR_BOUND"
    assert receipt["proof_route"]["attempted"] is True
    assert receipt["proof_route"]["status"] == CERTIFIED
    assert receipt["empirical_route"]["attempted"] is False
    assert receipt["proof_receipt"]["tail_bound_le_requested"] is True


def test_theta2_is_now_promoted_to_certified_symbolic_lane():
    receipt = proof_first_evaluate(
        "theta2",
        q="0.2",
        precision="1e-12",
        proof_max_terms=128,
    )
    assert receipt["status"] == CERTIFIED
    assert receipt["assurance_class"] == "ANALYTIC_CERTIFIED_ERROR_BOUND"
    assert receipt["proof_route"]["available"] is True
    assert receipt["proof_route"]["eligible"] is True
    assert receipt["empirical_route"]["attempted"] is False
    assert receipt["proof_receipt"]["certified_object"] == "EXACT_SYMBOLIC_ALGEBRAIC_PARTIAL_SUM_PLUS_RATIONAL_ANALYTIC_TAIL_BOUND"


def test_function_without_proof_lane_falls_back_but_stays_empirical():
    receipt = proof_first_evaluate(
        "phi_product",
        q=0.2,
        precision="1e-12",
        empirical_start_terms=4,
        empirical_max_terms=128,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY
    assert receipt["proof_route"]["available"] is False
    assert receipt["empirical_route"]["attempted"] is True
    assert receipt["proof_receipt"] is None


def test_complex_q_cannot_enter_real_certificate_lane():
    q = 0.6 + 0.1j
    receipt = proof_first_evaluate(
        "theta3",
        q=q,
        precision="1e-12",
        empirical_start_terms=8,
        empirical_max_terms=256,
    )
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY
    assert receipt["proof_route"]["available"] is True
    assert receipt["proof_route"]["eligible"] is False
    assert "COMPLEX_INPUT" in receipt["proof_route"]["reason"]
    assert receipt["empirical_route"]["attempted"] is True


def test_failed_proof_budget_can_fall_back_without_claim_upgrade():
    receipt = proof_first_evaluate(
        "phi",
        q="0.2",
        precision="1e-12",
        proof_start_terms=0,
        proof_max_terms=0,
        empirical_start_terms=4,
        empirical_max_terms=128,
    )
    assert receipt["proof_receipt"]["status"] == NOT_CERTIFIED
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY
    assert receipt["empirical_route"]["attempted"] is True
    assert receipt["proof_route"]["status"] == NOT_CERTIFIED


def test_failed_proof_with_fallback_disabled_fails_closed():
    receipt = proof_first_evaluate(
        "phi",
        q="0.2",
        precision="1e-12",
        proof_start_terms=0,
        proof_max_terms=0,
        allow_empirical_fallback=False,
    )
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["assurance_class"] == NO_NUMERICAL_ASSURANCE
    assert receipt["empirical_route"]["attempted"] is False


def test_dispatcher_never_grants_runtime_authority():
    certified = proof_first_evaluate("psi", q="0.5", precision="1e-12")
    empirical = proof_first_evaluate("phi_product", q=0.2, precision="1e-12", empirical_max_terms=128)
    assert all(value is False for value in certified["authority"].values())
    assert all(value is False for value in empirical["authority"].values())
