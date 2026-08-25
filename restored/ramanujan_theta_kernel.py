from __future__ import annotations

"""Source-backed Ramanujan theta/q-series mathematics for JANUS restoration.

This module is deliberately pure and read-only. It restores mathematical
definitions and deterministic numerical checks only; it has no scheduler,
network, filesystem-mutation, mining, proof, or runtime-admission authority.

Conventions
-----------
q-Pochhammer:
    (a;q)_N = product_{k=0}^{N-1} (1-a q^k)

Ramanujan general theta:
    f(a,b) = sum_{n=-infinity}^{infinity}
             a^{n(n+1)/2} b^{n(n-1)/2},  |ab| < 1

Jacobi triple product in Ramanujan notation:
    f(a,b) = (-a;ab)_infinity (-b;ab)_infinity (ab;ab)_infinity

Special cases:
    phi(q) = f(q,q) = sum_{n in Z} q^{n^2}
    psi(q) = f(q,q^3) = sum_{n>=0} q^{n(n+1)/2}

Third-order mock theta functions restored from the historical JANUS notebooks:
    f_mock(q) = sum_{n>=0} q^{n^2} / (-q;q)_n^2
    omega(q)  = sum_{n>=0} q^{2n(n+1)} / (q;q^2)_{n+1}^2
"""

import math
from typing import Any

SCHEMA = "janus.ramanujan_theta_kernel.v1"
DEFAULT_TERMS = 80
MAX_TERMS = 4096


def _terms(value: int) -> int:
    if isinstance(value, bool):
        raise ValueError("terms must be an integer")
    value = int(value)
    if value < 1 or value > MAX_TERMS:
        raise ValueError(f"terms must be in [1,{MAX_TERMS}]")
    return value


def _unit_disk(name: str, value: complex | float | int) -> complex:
    z = complex(value)
    if not (math.isfinite(z.real) and math.isfinite(z.imag)):
        raise ValueError(f"{name} must be finite")
    if abs(z) >= 1.0:
        raise ValueError(f"{name} must satisfy |{name}| < 1")
    return z


def _real_if_close(z: complex, tol: float = 1e-15) -> complex | float:
    if abs(z.imag) <= tol:
        return float(z.real)
    return z


def q_pochhammer(a: complex | float, q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Finite approximation to (a;q)_infinity using ``terms`` factors."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    a = complex(a)
    if not (math.isfinite(a.real) and math.isfinite(a.imag)):
        raise ValueError("a must be finite")
    out = 1.0 + 0.0j
    power = 1.0 + 0.0j
    for _ in range(terms):
        out *= 1.0 - a * power
        power *= q
    return _real_if_close(out)


def ramanujan_f(a: complex | float, b: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Symmetric truncation of Ramanujan's general theta f(a,b)."""
    terms = _terms(terms)
    a = complex(a)
    b = complex(b)
    ab = a * b
    if not all(math.isfinite(x) for x in (a.real, a.imag, b.real, b.imag)):
        raise ValueError("a and b must be finite")
    if abs(ab) >= 1.0:
        raise ValueError("Ramanujan f(a,b) requires |a*b| < 1")
    total = 0.0 + 0.0j
    for n in range(-terms, terms + 1):
        e_a = n * (n + 1) // 2
        e_b = n * (n - 1) // 2
        total += (a ** e_a) * (b ** e_b)
    return _real_if_close(total)


def ramanujan_f_product(a: complex | float, b: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Finite Jacobi-triple-product side for Ramanujan f(a,b)."""
    terms = _terms(terms)
    a = complex(a)
    b = complex(b)
    ab = a * b
    if abs(ab) >= 1.0:
        raise ValueError("Ramanujan f(a,b) product requires |a*b| < 1")
    value = (
        complex(q_pochhammer(-a, ab, terms))
        * complex(q_pochhammer(-b, ab, terms))
        * complex(q_pochhammer(ab, ab, terms))
    )
    return _real_if_close(value)


def phi(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Ramanujan phi(q) = f(q,q) = sum_{n in Z} q^(n^2)."""
    q = _unit_disk("q", q)
    return ramanujan_f(q, q, terms)


def phi_product(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Product identity phi(q)=(-q;q^2)_inf^2 (q^2;q^2)_inf."""
    q = _unit_disk("q", q)
    q2 = q * q
    value = complex(q_pochhammer(-q, q2, terms)) ** 2 * complex(q_pochhammer(q2, q2, terms))
    return _real_if_close(value)


def psi(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Ramanujan psi(q)=sum_{n>=0} q^(n(n+1)/2)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 0.0 + 0.0j
    for n in range(terms + 1):
        total += q ** (n * (n + 1) // 2)
    return _real_if_close(total)


def psi_product(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Product identity psi(q)=(q^2;q^2)_inf/(q;q^2)_inf."""
    q = _unit_disk("q", q)
    q2 = q * q
    den = complex(q_pochhammer(q, q2, terms))
    if abs(den) == 0.0:
        raise ZeroDivisionError("truncated psi denominator vanished")
    return _real_if_close(complex(q_pochhammer(q2, q2, terms)) / den)


def theta2(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Jacobi theta_2(0,q)=2 sum_{n>=0} q^((n+1/2)^2)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 0.0 + 0.0j
    for n in range(terms + 1):
        total += 2.0 * q ** ((n + 0.5) ** 2)
    return _real_if_close(total)


def theta3(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Jacobi theta_3(0,q)=1+2 sum_{n>=1} q^(n^2)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 1.0 + 0.0j
    for n in range(1, terms + 1):
        total += 2.0 * q ** (n * n)
    return _real_if_close(total)


def theta4(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Jacobi theta_4(0,q)=1+2 sum_{n>=1} (-1)^n q^(n^2)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 1.0 + 0.0j
    for n in range(1, terms + 1):
        total += 2.0 * ((-1) ** n) * q ** (n * n)
    return _real_if_close(total)


def mock_theta_f(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Ramanujan third-order mock theta f(q)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 1.0 + 0.0j
    prod = 1.0 + 0.0j
    for n in range(1, terms + 1):
        prod *= 1.0 + q ** n
        if abs(prod) < 1e-30:
            raise ZeroDivisionError("mock theta f denominator vanished")
        total += q ** (n * n) / (prod * prod)
    return _real_if_close(total)


def mock_theta_omega(q: complex | float, terms: int = DEFAULT_TERMS) -> complex | float:
    """Ramanujan third-order mock theta omega(q)."""
    terms = _terms(terms)
    q = _unit_disk("q", q)
    total = 0.0 + 0.0j
    prod = 1.0 + 0.0j
    for n in range(terms):
        prod *= 1.0 - q ** (2 * n + 1)
        if abs(prod) < 1e-30:
            raise ZeroDivisionError("mock theta omega denominator vanished")
        total += q ** (2 * n * (n + 1)) / (prod * prod)
    return _real_if_close(total)


def partition_table(nmax: int) -> list[int]:
    """Exact p(0)..p(nmax) by Euler's generating-function dynamic program."""
    if isinstance(nmax, bool):
        raise ValueError("nmax must be an integer")
    nmax = int(nmax)
    if nmax < 0:
        raise ValueError("nmax must be nonnegative")
    p = [0] * (nmax + 1)
    p[0] = 1
    for k in range(1, nmax + 1):
        for n in range(k, nmax + 1):
            p[n] += p[n - k]
    return p


def partition(n: int) -> int:
    if isinstance(n, bool):
        raise ValueError("n must be an integer")
    n = int(n)
    if n < 0:
        return 0
    return partition_table(n)[n]


def hardy_ramanujan_partition(n: int) -> float:
    """Leading Hardy-Ramanujan asymptotic for p(n), n>=1."""
    if isinstance(n, bool):
        raise ValueError("n must be an integer")
    n = int(n)
    if n < 1:
        raise ValueError("n must be >= 1")
    return math.exp(math.pi * math.sqrt(2.0 * n / 3.0)) / (4.0 * n * math.sqrt(3.0))


def ramanujan_congruence_hits(n: int) -> list[dict[str, Any]]:
    """Report applicable classical partition congruence families and exact checks."""
    if isinstance(n, bool):
        raise ValueError("n must be an integer")
    n = int(n)
    if n < 0:
        return []
    pn = partition(n)
    families = ((5, 4), (7, 5), (11, 6))
    out: list[dict[str, Any]] = []
    for modulus, residue in families:
        if n % modulus == residue:
            out.append({"modulus": modulus, "residue": residue, "n": n, "p_n": pn, "divisible": (pn % modulus == 0)})
    return out


def tau_coefficients(nmax: int) -> list[int]:
    """Exact tau(1)..tau(nmax) from Delta(q)=q product_{m>=1}(1-q^m)^24."""
    if isinstance(nmax, bool):
        raise ValueError("nmax must be an integer")
    nmax = int(nmax)
    if nmax < 1:
        return []
    degree = nmax - 1
    coeff = [0] * (degree + 1)
    coeff[0] = 1
    for m in range(1, degree + 1):
        old = coeff
        new = old[:]
        for k in range(1, 25):
            step = m * k
            if step > degree:
                break
            factor = math.comb(24, k) * ((-1) ** k)
            for i, c in enumerate(old):
                j = i + step
                if j > degree:
                    break
                if c:
                    new[j] += c * factor
        coeff = new
    return [coeff[n - 1] for n in range(1, nmax + 1)]


def tau(n: int) -> int:
    if isinstance(n, bool):
        raise ValueError("n must be an integer")
    n = int(n)
    if n < 1:
        raise ValueError("n must be >= 1")
    return tau_coefficients(n)[-1]


def identity_residuals(q: complex | float, terms: int = DEFAULT_TERMS) -> dict[str, float]:
    """Numerical residuals for restored theta identities; smaller is better."""
    q = _unit_disk("q", q)
    terms = _terms(terms)
    ph = complex(phi(q, terms))
    th3 = complex(theta3(q, terms))
    th2 = complex(theta2(q, terms))
    th4 = complex(theta4(q, terms))
    return {
        "phi_vs_theta3": abs(ph - th3),
        "phi_triple_product": abs(ph - complex(phi_product(q, terms))),
        "psi_product": abs(complex(psi(q, terms)) - complex(psi_product(q, terms))),
        "jacobi_theta_quartic": abs(th3**4 - th2**4 - th4**4),
    }


def audit_receipt(q: float = 0.2, terms: int = DEFAULT_TERMS) -> dict[str, Any]:
    """Pure metadata/math receipt; no external effects."""
    residuals = identity_residuals(q, terms)
    return {
        "schema": SCHEMA,
        "q": float(q),
        "terms": int(terms),
        "residuals": residuals,
        "partition_10": partition(10),
        "tau_1_10": tau_coefficients(10),
        "authority": {
            "network": False,
            "filesystem_mutation": False,
            "scheduler": False,
            "runtime_admission": False,
            "mining_or_submit": False,
            "proof_acceptance": False,
        },
        "laws": [
            "MATHEMATICAL_IDENTITY_NE_RUNTIME_AUTHORITY",
            "THETA_SIGNAL_NE_CAUSAL_PROOF",
            "MOCK_THETA_NE_PRECOGNITION",
            "PARTITION_CONGRUENCE_NE_SCHEDULER_RULE",
            "RESTORE_MATHEMATICS_WITHOUT_RESTORING_OLD_ACTUATION",
        ],
    }
