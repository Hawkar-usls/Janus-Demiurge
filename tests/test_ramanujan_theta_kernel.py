from restored.ramanujan_theta_kernel import audit_receipt, identity_residuals, partition_table, ramanujan_congruence_hits, ramanujan_f, ramanujan_f_product, tau_coefficients, theta3


def test_ramanujan_theta_identities():
    assert abs(complex(ramanujan_f(0.2, 0.3, 100)) - complex(ramanujan_f_product(0.2, 0.3, 100))) < 1e-13
    residuals = identity_residuals(0.2, 120)
    assert max(residuals.values()) < 1e-11


def test_ramanujan_partitions_and_tau():
    assert partition_table(10) == [1, 1, 2, 3, 5, 7, 11, 15, 22, 30, 42]
    assert tau_coefficients(10) == [1, -24, 252, -1472, 4830, -6048, -16744, 84480, -113643, -115920]
    for n in (4, 9, 14, 19, 24, 29):
        assert any(h["modulus"] == 5 and h["divisible"] for h in ramanujan_congruence_hits(n))


def test_ramanujan_authority_ceiling():
    receipt = audit_receipt(0.2, 100)
    assert receipt["partition_10"] == 42
    assert all(value is False for value in receipt["authority"].values())
    try:
        theta3(1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("theta3 must reject |q| >= 1")
