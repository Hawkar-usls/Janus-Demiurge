from restored.ramanujan_theta_precision_probe import canonical_probe_suite, general_theta_crosscheck, theta_constant_crosscheck


def test_complex_general_theta_sum_matches_triple_product():
    r = general_theta_crosscheck(0.2 + 0.1j, 0.3 - 0.05j, (32, 64, 128, 256))
    assert r["abs_ab"] < 1.0
    assert r["final_residual"] < 1e-12


def test_complex_theta_constants_crosscheck():
    q = 0.5732018934753635 + 0.1773121239968037j
    r = theta_constant_crosscheck(q, (32, 64, 128, 256))
    assert r["abs_q"] < 1.0
    assert r["final"]["phi_vs_theta3"] < 1e-13
    assert r["final"]["phi_product_residual"] < 1e-12
    assert r["final"]["jacobi_quartic_residual"] < 1e-11


def test_near_unit_circle_product_convergence_is_explicit():
    r = theta_constant_crosscheck(0.99, (128, 256, 512, 1024, 2048))
    rows = r["rows"]
    assert rows[0]["phi_product_residual"] > 1.0
    assert rows[-1]["phi_product_residual"] < 1e-10
    assert rows[-1]["phi_vs_theta3"] < 1e-13


def test_canonical_suite_has_no_authority():
    suite = canonical_probe_suite()
    assert set(suite["cases"]) == {"real_q_0_2", "real_q_0_9", "real_q_0_99", "complex_q", "complex_general_theta"}
    assert all(value is False for value in suite["authority"].values())
