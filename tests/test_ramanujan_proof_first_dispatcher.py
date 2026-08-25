from restored.ramanujan_adaptive_precision import CONVERGED
from restored.ramanujan_certified_bounds import CERTIFIED, NOT_CERTIFIED
from restored.ramanujan_proof_first_dispatcher import EMPIRICAL_ONLY, NO_NUMERICAL_ASSURANCE, proof_first_evaluate


def test_proof_first_stops_after_true_real_certificate():
    receipt = proof_first_evaluate("phi", q="0.9", precision="1e-12")
    assert receipt["status"] == CERTIFIED
    assert receipt["assurance_class"] == "ANALYTIC_CERTIFIED_ERROR_BOUND"
    assert receipt["proof_route"]["mode"] == "EXACT_REAL_RATIONAL"
    assert receipt["empirical_route"]["attempted"] is False


def test_theta2_and_real_products_are_certified_first():
    receipts = [
        proof_first_evaluate("theta2", q="0.2", precision="1e-12", proof_max_terms=128),
        proof_first_evaluate("phi_product", q="0.5", precision="1e-12", proof_max_terms=128),
        proof_first_evaluate("psi_product", q="0.5", precision="1e-12", proof_max_terms=128),
        proof_first_evaluate("ramanujan_f_product", a="0.2", b="0.3", precision="1e-12", proof_max_terms=128),
    ]
    assert all(r["status"] == CERTIFIED for r in receipts)
    assert all(r["empirical_route"]["attempted"] is False for r in receipts)


def test_old_l1_hole_is_now_certified_in_exact_complex_dispatch():
    receipt = proof_first_evaluate("theta3", q=("0.8", "0.3"), precision="1e-12", proof_max_terms=128)
    assert receipt["status"] == CERTIFIED
    assert receipt["assurance_class"] == "ANALYTIC_CERTIFIED_ERROR_BOUND"
    assert receipt["proof_route"]["mode"] == "EXACT_GAUSSIAN_RATIONAL_UNIT_DISK_Q"
    assert "FULL_EXACT_OPEN_UNIT_DISK" in receipt["proof_receipt"]["bound_geometry"]
    assert receipt["proof_receipt"]["tail_bound_le_requested"] is True
    assert receipt["empirical_route"]["attempted"] is False


def test_exact_complex_products_are_certified_across_old_l1_hole():
    receipts = [
        proof_first_evaluate("phi_product", q=("0.8", "0.3"), precision="1e-12", proof_max_terms=256),
        proof_first_evaluate("psi_product", q=("0.8", "0.3"), precision="1e-12", proof_max_terms=256),
        proof_first_evaluate("ramanujan_f_product", a=("0.8", "0.6"), b=("0.5", "-0.4"), precision="1e-12", proof_max_terms=256),
    ]
    for receipt in receipts:
        assert receipt["status"] == CERTIFIED
        assert receipt["assurance_class"] == "ANALYTIC_CERTIFIED_ERROR_BOUND"
        assert receipt["proof_receipt"]["error_bound_le_requested"] is True
        assert receipt["empirical_route"]["attempted"] is False


def test_exact_complex_general_f_uses_ab_unit_disk_not_product_of_l1_bounds():
    receipt = proof_first_evaluate("ramanujan_f", a=("0.8", "0.6"), b={"re": "0.5", "im": "-0.4"}, precision="1e-12", proof_max_terms=256)
    assert receipt["status"] == CERTIFIED
    assert receipt["proof_route"]["mode"] == "EXACT_GAUSSIAN_RATIONAL_UNIT_DISK_GENERAL"
    assert receipt["proof_receipt"]["tail_bound_le_requested"] is True


def test_python_complex_float_is_not_silently_promoted_to_exact_input():
    receipt = proof_first_evaluate("theta3", q=0.3 + 0.2j, precision="1e-12", empirical_start_terms=8, empirical_max_terms=256)
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY
    assert receipt["proof_route"]["eligible"] is False
    assert "PYTHON_COMPLEX_FLOAT" in receipt["proof_route"]["reason"]


def test_exact_complex_outside_true_unit_disk_keeps_proof_failure_visible():
    receipt = proof_first_evaluate("theta3", q=("0.8", "0.7"), precision="1e-12", proof_max_terms=128, empirical_start_terms=16, empirical_max_terms=128)
    assert receipt["proof_route"]["attempted"] is True
    assert receipt["proof_receipt"]["status"].startswith("NOT_CERTIFIED_OUTSIDE")
    assert receipt["proof_receipt"]["input"]["majorant_profile"]["inside_open_unit_disk"] is False
    assert receipt["assurance_class"] in {EMPIRICAL_ONLY, NO_NUMERICAL_ASSURANCE}


def test_exact_complex_theta2_is_still_empirical_only():
    receipt = proof_first_evaluate("theta2", q=("0.2", "0.1"), precision="1e-12", empirical_start_terms=8, empirical_max_terms=256)
    assert receipt["proof_route"]["available"] is True
    assert receipt["proof_route"]["eligible"] is False
    assert "NO_EXACT_COMPLEX_CERTIFICATE" in receipt["proof_route"]["reason"]
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY


def test_failed_real_proof_budget_can_fall_back_without_claim_upgrade():
    receipt = proof_first_evaluate("phi", q="0.2", precision="1e-12", proof_start_terms=0, proof_max_terms=0, empirical_start_terms=4, empirical_max_terms=128)
    assert receipt["proof_receipt"]["status"] == NOT_CERTIFIED
    assert receipt["status"] == CONVERGED
    assert receipt["assurance_class"] == EMPIRICAL_ONLY


def test_failed_proof_with_fallback_disabled_fails_closed():
    receipt = proof_first_evaluate("phi", q="0.2", precision="1e-12", proof_start_terms=0, proof_max_terms=0, allow_empirical_fallback=False)
    assert receipt["status"] == NOT_CERTIFIED
    assert receipt["assurance_class"] == NO_NUMERICAL_ASSURANCE
    assert receipt["empirical_route"]["attempted"] is False


def test_dispatcher_never_grants_runtime_authority():
    certified = proof_first_evaluate("phi_product", q=("0.8", "0.3"), precision="1e-12", proof_max_terms=256)
    empirical = proof_first_evaluate("theta3", q=0.3 + 0.2j, precision="1e-12", empirical_max_terms=256)
    assert all(value is False for value in certified["authority"].values())
    assert all(value is False for value in empirical["authority"].values())
