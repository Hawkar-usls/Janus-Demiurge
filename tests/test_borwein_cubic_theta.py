from restored.borwein_cubic_theta import convergence_probe, cubic_a, cubic_b, cubic_c, identity_residual


def test_cubic_theta_identity_at_small_q():
    for q in (0.01, 0.05, 0.1, 0.2):
        assert identity_residual(q, 12) < 1e-11


def test_cubic_theta_convergence_at_q_0_4():
    probe = convergence_probe(0.4, (3, 5, 8, 12, 16))
    assert probe["rows"][0]["identity_residual"] > probe["rows"][-1]["identity_residual"]
    assert probe["final_residual"] < 1e-10
    assert all(value is False for value in probe["authority"].values())


def test_cubic_components_are_stable():
    a8 = cubic_a(0.2, 8)
    a12 = cubic_a(0.2, 12)
    b = complex(cubic_b(0.2, 12))
    c = cubic_c(0.2, 12)
    assert abs(a8 - a12) < 1e-13
    assert abs(b.imag) < 1e-12
    assert a12 > 0.0 and c > 0.0


def test_real_q_domain_gate():
    for bad in (0.0, 1.0, -0.1):
        try:
            cubic_a(bad, 8)
        except ValueError:
            pass
        else:
            raise AssertionError("cubic theta implementation must require real 0 < q < 1")
