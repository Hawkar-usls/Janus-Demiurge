from __future__ import annotations

"""Borwein cubic theta extension for the JANUS Ramanujan mathematics branch.

Attribution boundary
--------------------
These cubic theta functions are included because they belong to the modern
Ramanujan-theta legacy, but this implementation does NOT attribute the cubic
system itself to Srinivasa Ramanujan. The a,b,c formulation and identity used
here are associated with Jonathan and Peter Borwein's cubic-theta theory.

This module is pure mathematics only. It has no scheduler, network, mining,
proof-acceptance, runtime-admission, or filesystem-mutation authority.

For real 0 < q < 1:
    a(q) = sum_{m,n in Z} q^(m^2 + mn + n^2)
    b(q) = sum_{m,n in Z} omega^(m-n) q^(m^2 + mn + n^2)
    c(q) = sum_{m,n in Z} q^((m+1/3)^2 + (m+1/3)(n+1/3) + (n+1/3)^2)
where omega = exp(2*pi*i/3), and
    a(q)^3 = b(q)^3 + c(q)^3.
"""

import cmath
import math
from typing import Any

SCHEMA = "janus.borwein_cubic_theta.v1"
OMEGA = cmath.exp(2j * math.pi / 3.0)
MAX_RADIUS = 256


def _q(q: float) -> float:
    if isinstance(q, bool) or not isinstance(q, (int, float)):
        raise ValueError("q must be a real number")
    q = float(q)
    if not math.isfinite(q) or not (0.0 < q < 1.0):
        raise ValueError("this implementation requires real 0 < q < 1")
    return q


def _radius(radius: int) -> int:
    if isinstance(radius, bool):
        raise ValueError("radius must be an integer")
    radius = int(radius)
    if radius < 1 or radius > MAX_RADIUS:
        raise ValueError(f"radius must be in [1,{MAX_RADIUS}]")
    return radius


def _real_if_close(z: complex, tol: float = 1e-14) -> complex | float:
    return float(z.real) if abs(z.imag) <= tol else z


def cubic_a(q: float, radius: int = 12) -> float:
    q = _q(q)
    radius = _radius(radius)
    total = 0.0
    for m in range(-radius, radius + 1):
        for n in range(-radius, radius + 1):
            exponent = m * m + m * n + n * n
            total += q ** exponent
    return total


def cubic_b(q: float, radius: int = 12) -> complex | float:
    q = _q(q)
    radius = _radius(radius)
    total = 0.0 + 0.0j
    for m in range(-radius, radius + 1):
        for n in range(-radius, radius + 1):
            exponent = m * m + m * n + n * n
            total += (OMEGA ** (m - n)) * (q ** exponent)
    return _real_if_close(total)


def cubic_c(q: float, radius: int = 12) -> float:
    q = _q(q)
    radius = _radius(radius)
    total = 0.0
    shift = 1.0 / 3.0
    for m in range(-radius, radius + 1):
        x = m + shift
        for n in range(-radius, radius + 1):
            y = n + shift
            exponent = x * x + x * y + y * y
            total += q ** exponent
    return total


def identity_residual(q: float, radius: int = 12) -> float:
    a = complex(cubic_a(q, radius))
    b = complex(cubic_b(q, radius))
    c = complex(cubic_c(q, radius))
    return abs(a**3 - b**3 - c**3)


def convergence_probe(q: float, radii: tuple[int, ...] = (3, 5, 8, 12, 16)) -> dict[str, Any]:
    q = _q(q)
    clean = tuple(sorted({_radius(r) for r in radii}))
    if not clean:
        raise ValueError("at least one radius is required")
    rows = []
    previous = None
    for radius in clean:
        a = cubic_a(q, radius)
        b = complex(cubic_b(q, radius))
        c = cubic_c(q, radius)
        row = {
            "radius": radius,
            "a": a,
            "b": [b.real, b.imag],
            "c": c,
            "identity_residual": abs(complex(a) ** 3 - b**3 - complex(c) ** 3),
            "a_step_delta": None if previous is None else abs(a - previous),
        }
        rows.append(row)
        previous = a
    return {
        "schema": SCHEMA,
        "q": q,
        "rows": rows,
        "final_residual": rows[-1]["identity_residual"],
        "attribution": "BORWEIN_CUBIC_THETA_IN_RAMANUJAN_LEGACY_CONTEXT__NOT_DIRECT_RAMANUJAN_AUTHORSHIP",
        "authority": {
            "network": False,
            "scheduler": False,
            "runtime_admission": False,
            "mining_or_submit": False,
            "proof_acceptance": False,
            "filesystem_mutation": False,
        },
        "laws": [
            "RAMANUJAN_LEGACY_NE_DIRECT_AUTHORSHIP",
            "CUBIC_THETA_IDENTITY_NE_PHYSICAL_CONSERVATION_LAW",
            "NUMERICAL_RESIDUAL_MUST_REMAIN_VISIBLE",
        ],
    }
