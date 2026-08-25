from __future__ import annotations

"""Independent convergence/cross-identity probe for the restored Ramanujan theta kernel.

The probe is pure mathematics only. It never controls a scheduler, network,
mining path, proof gate, runtime admission, filesystem mutation or model state.

The purpose is to make truncation error visible, especially for complex q and
for |q| close to 1 where finite q-products converge much more slowly than the
direct theta sums.
"""

import cmath
from typing import Any, Iterable

from restored.ramanujan_theta_kernel import (
    phi,
    phi_product,
    psi,
    psi_product,
    ramanujan_f,
    ramanujan_f_product,
    theta2,
    theta3,
    theta4,
)

SCHEMA = "janus.ramanujan_theta_precision_probe.v1"
DEFAULT_SCHEDULE = (16, 32, 64, 128, 256, 512, 1024, 2048)


def _schedule(values: Iterable[int]) -> tuple[int, ...]:
    out = tuple(sorted({int(v) for v in values if int(v) > 0}))
    if not out:
        raise ValueError("term schedule must contain at least one positive integer")
    if out[-1] > 4096:
        raise ValueError("term schedule exceeds kernel MAX_TERMS=4096")
    return out


def _finite_complex(z: complex) -> bool:
    return all(x == x and abs(x) != float("inf") for x in (z.real, z.imag))


def general_theta_crosscheck(a: complex, b: complex, schedule: Iterable[int] = DEFAULT_SCHEDULE) -> dict[str, Any]:
    schedule = _schedule(schedule)
    rows = []
    previous = None
    for terms in schedule:
        direct = complex(ramanujan_f(a, b, terms))
        product = complex(ramanujan_f_product(a, b, terms))
        if not (_finite_complex(direct) and _finite_complex(product)):
            raise ArithmeticError("non-finite general-theta value")
        rows.append({
            "terms": terms,
            "direct": [direct.real, direct.imag],
            "product": [product.real, product.imag],
            "identity_residual": abs(direct - product),
            "direct_step_delta": None if previous is None else abs(direct - previous),
        })
        previous = direct
    return {
        "schema": SCHEMA,
        "kind": "RAMANUJAN_GENERAL_THETA",
        "a": [complex(a).real, complex(a).imag],
        "b": [complex(b).real, complex(b).imag],
        "abs_ab": abs(complex(a) * complex(b)),
        "rows": rows,
        "final_residual": rows[-1]["identity_residual"],
        "authority": "MATHEMATICS_ONLY",
    }


def theta_constant_crosscheck(q: complex, schedule: Iterable[int] = DEFAULT_SCHEDULE) -> dict[str, Any]:
    schedule = _schedule(schedule)
    q = complex(q)
    rows = []
    previous_theta3 = None
    for terms in schedule:
        ph = complex(phi(q, terms))
        ph_prod = complex(phi_product(q, terms))
        ps = complex(psi(q, terms))
        ps_prod = complex(psi_product(q, terms))
        t2 = complex(theta2(q, terms))
        t3 = complex(theta3(q, terms))
        t4 = complex(theta4(q, terms))
        rows.append({
            "terms": terms,
            "phi_vs_theta3": abs(ph - t3),
            "phi_product_residual": abs(ph - ph_prod),
            "psi_product_residual": abs(ps - ps_prod),
            "jacobi_quartic_residual": abs(t3**4 - t2**4 - t4**4),
            "theta3_step_delta": None if previous_theta3 is None else abs(t3 - previous_theta3),
        })
        previous_theta3 = t3
    return {
        "schema": SCHEMA,
        "kind": "THETA_CONSTANTS",
        "q": [q.real, q.imag],
        "abs_q": abs(q),
        "rows": rows,
        "final": rows[-1],
        "warning": "finite q-products can require far more terms than direct theta sums as |q| approaches 1",
        "authority": "MATHEMATICS_ONLY",
    }


def canonical_probe_suite() -> dict[str, Any]:
    cases = {
        "real_q_0_2": theta_constant_crosscheck(0.2, (16, 32, 64, 128)),
        "real_q_0_9": theta_constant_crosscheck(0.9, (32, 64, 128, 256, 512)),
        "real_q_0_99": theta_constant_crosscheck(0.99, (128, 256, 512, 1024, 2048)),
        "complex_q": theta_constant_crosscheck(0.6 * cmath.exp(0.3j), (32, 64, 128, 256)),
        "complex_general_theta": general_theta_crosscheck(0.2 + 0.1j, 0.3 - 0.05j, (32, 64, 128, 256)),
    }
    return {
        "schema": SCHEMA,
        "cases": cases,
        "authority": {
            "network": False,
            "scheduler": False,
            "runtime_admission": False,
            "mining_or_submit": False,
            "proof_acceptance": False,
            "filesystem_mutation": False,
        },
        "laws": [
            "TRUNCATION_RESIDUAL_MUST_BE_VISIBLE",
            "NEAR_UNIT_CIRCLE_REQUIRES_CONVERGENCE_EVIDENCE",
            "COMPLEX_Q_SUPPORT_REQUIRES_IDENTITY_CROSSCHECK",
            "NUMERICAL_AGREEMENT_NE_PHYSICAL_INTERPRETATION",
        ],
    }
