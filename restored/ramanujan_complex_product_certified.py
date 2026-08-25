from __future__ import annotations

"""Exact Gaussian-rational certificates for complex Ramanujan q-products.

For an infinite tail product T=prod_j(1+u_j), if
S=sum_j |u_j| < 1, expansion of the product gives

    |T-1| <= S/(1-S).

We upper-bound |u_j| with exact L1 majorants of Gaussian rationals.  The finite
product is exact in Q(i), so

    |P-P_N| <= ||P_N||_1 * |T-1|

is an exact rational error certificate.  The psi quotient uses an additional
lower bound on the denominator tail.

The current proof domain uses L1 majorants and is intentionally conservative.
"""

from decimal import Decimal
from fractions import Fraction
import hashlib
import math
from typing import Any, Callable

from restored.ramanujan_complex_certified import GaussianRational, ONE, _gr

SCHEMA = "janus.ramanujan_complex_product_certified.v1"
CERTIFIED = "CERTIFIED_ERROR_BOUND"
NOT_CERTIFIED = "NOT_CERTIFIED_WITHIN_BUDGET"
OUTSIDE_BOUND_DOMAIN = "NOT_CERTIFIED_OUTSIDE_CURRENT_COMPLEX_BOUND_DOMAIN"
MAX_TERMS = 4096


def _fraction(value: Any, name: str) -> Fraction:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, str):
        try:
            return Fraction(Decimal(value))
        except Exception as exc:
            raise ValueError(f"invalid exact decimal for {name}") from exc
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return Fraction(Decimal(str(value)))
    raise ValueError(f"unsupported exact-real type for {name}")


def _digest_integer(value: int) -> str:
    sign = b"-" if value < 0 else b"+"
    magnitude = abs(value)
    raw = magnitude.to_bytes(max(1, (magnitude.bit_length() + 7) // 8), "big")
    return hashlib.sha256(sign + raw).hexdigest()


def _fr(value: Fraction, inline_bits: int = 2048) -> dict[str, Any]:
    n, d = value.numerator, value.denominator
    out = {
        "numerator_bits": abs(n).bit_length(),
        "denominator_bits": d.bit_length(),
        "numerator_sha256": _digest_integer(n),
        "denominator_sha256": _digest_integer(d),
    }
    if abs(n).bit_length() <= inline_bits and d.bit_length() <= inline_bits:
        out["numerator"] = str(n)
        out["denominator"] = str(d)
    return out


def _grr(value: GaussianRational) -> dict[str, Any]:
    return {"re": _fr(value.re), "im": _fr(value.im), "l1_majorant": _fr(value.l1())}


def _schedule(start_terms: int, max_terms: int, growth: float) -> list[int]:
    if isinstance(start_terms, bool) or isinstance(max_terms, bool):
        raise ValueError("term budgets must be integers")
    start_terms, max_terms = int(start_terms), int(max_terms)
    growth = float(growth)
    if start_terms < 0:
        raise ValueError("start_terms must be >= 0")
    if max_terms < start_terms or max_terms > MAX_TERMS:
        raise ValueError(f"max_terms must be in [start_terms,{MAX_TERMS}]")
    if not math.isfinite(growth) or growth <= 1.0:
        raise ValueError("growth must be finite and > 1")
    out = [start_terms]
    current = start_terms
    while current < max_terms:
        nxt = min(max_terms, max(current + 1, int(math.ceil(max(1, current) * growth))))
        if nxt == current:
            break
        out.append(nxt)
        current = nxt
    return out


def _tol(value: Any) -> Fraction:
    out = _fraction(value, "abs_error")
    if out <= 0:
        raise ValueError("abs_error must be > 0")
    return out


def _common(
    *,
    function: str,
    status: str,
    n: int,
    requested: Fraction,
    partial: GaussianRational | None,
    error: Fraction | None,
    input_payload: dict[str, Any],
    proof_formula: str,
    tail_payload: dict[str, Fraction] | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "function": function,
        "status": status,
        "terms_used": n,
        "requested_abs_error": _fr(requested),
        "input": input_payload,
        "proof_formula": proof_formula,
        "exact_arithmetic": "GAUSSIAN_RATIONAL_Q_I",
        "bound_geometry": "L1_MAJORANT_DIAMOND",
        "certified_object": "EXACT_GAUSSIAN_RATIONAL_FINITE_PRODUCT_PLUS_RATIONAL_COMPLEX_TAIL_BOUND",
        "estimate_is_certified": False,
        "authority": {
            "network": False,
            "filesystem_mutation": False,
            "scheduler": False,
            "runtime_admission": False,
            "mining_or_submit": False,
            "proof_acceptance": False,
            "automatic_control": False,
        },
        "laws": [
            "COMPLEX_FINITE_PRODUCT_NE_INFINITE_PRODUCT_WITHOUT_TAIL_BOUND",
            "GAUSSIAN_RATIONAL_FINITE_ARITHMETIC_IS_EXACT",
            "L1_MAJORANT_GE_COMPLEX_MODULUS",
            "COMPLEX_PRODUCT_PROOF_DOMAIN_MUST_REMAIN_VISIBLE",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }
    if partial is not None:
        out["partial_product"] = _grr(partial)
        z = partial.to_complex()
        out["estimate"] = [z.real, z.imag]
    if error is not None:
        out["absolute_error_bound"] = _fr(error)
        out["absolute_error_bound_decimal"] = f"{float(error):.17e}"
        out["error_bound_le_requested"] = error <= requested
    if tail_payload is not None:
        out["tail_majorants"] = {k: _fr(v) for k, v in tail_payload.items()}
    return out


def _choose(
    evaluator: Callable[[int], tuple[GaussianRational, Fraction | None, dict[str, Fraction]]],
    *,
    requested: Fraction,
    start_terms: int,
    max_terms: int,
    growth: float,
) -> tuple[str, int, GaussianRational, Fraction | None, dict[str, Fraction]]:
    chosen = None
    for n in _schedule(start_terms, max_terms, growth):
        partial, error, tails = evaluator(n)
        chosen = (n, partial, error, tails)
        if error is not None and error <= requested:
            return CERTIFIED, n, partial, error, tails
    assert chosen is not None
    n, partial, error, tails = chosen
    return NOT_CERTIFIED, n, partial, error, tails


def certify_complex_phi_product(*, q: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    qg = _gr(q, "q")
    rho = qg.l1()
    requested = _tol(abs_error)
    if rho >= 1:
        return _common(function="phi_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"q": _grr(qg), "rho_l1": _fr(rho)}, proof_formula="requires rho=|Re q|+|Im q|<1", tail_payload=None)

    def evaluate(n: int):
        plus = ONE
        even = ONE
        for k in range(n):
            plus = plus * (ONE + qg ** (2 * k + 1))
            even = even * (ONE - qg ** (2 * k + 2))
        partial = plus * plus * even
        den = 1 - rho * rho
        s_plus = rho ** (2 * n + 1) / den
        s_even = rho ** (2 * n + 2) / den
        total = 2 * s_plus + s_even
        error = None if total >= 1 else partial.l1() * total / (1 - total)
        return partial, error, {"plus_tail_sum_each": s_plus, "even_minus_tail_sum": s_even, "combined_tail_sum": total}

    status, n, partial, error, tails = _choose(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _common(function="phi_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"q": _grr(qg), "rho_l1": _fr(rho), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="combine all omitted factors as T=prod(1+u_j); if S=2*S_plus+S_even<1 then |T-1|<=S/(1-S), hence |P-P_N|<=||P_N||_1*S/(1-S)", tail_payload=tails)


def certify_complex_psi_product(*, q: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    qg = _gr(q, "q")
    rho = qg.l1()
    requested = _tol(abs_error)
    if rho >= 1:
        return _common(function="psi_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"q": _grr(qg), "rho_l1": _fr(rho)}, proof_formula="requires rho=|Re q|+|Im q|<1", tail_payload=None)

    def evaluate(n: int):
        even = ONE
        odd = ONE
        for k in range(n):
            even = even * (ONE - qg ** (2 * k + 2))
            odd = odd * (ONE - qg ** (2 * k + 1))
        partial = even / odd
        den = 1 - rho * rho
        se = rho ** (2 * n + 2) / den
        so = rho ** (2 * n + 1) / den
        # |E-1| and |O-1| from product expansion; |O|>=1-so.
        if se >= 1 or so >= 1:
            error = None
        else:
            de = se / (1 - se)
            do = so / (1 - so)
            ratio_deviation = (de + do) / (1 - so)
            error = partial.l1() * ratio_deviation
        return partial, error, {"even_tail_sum": se, "odd_tail_sum": so}

    status, n, partial, error, tails = _choose(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _common(function="psi_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"q": _grr(qg), "rho_l1": _fr(rho), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="write tail ratio E/O; |E/O-1|<=([S_e/(1-S_e)]+[S_o/(1-S_o)])/(1-S_o), using |O|>=1-S_o", tail_payload=tails)


def certify_complex_ramanujan_f_product(*, a: Any, b: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    ag, bg = _gr(a, "a"), _gr(b, "b")
    sg = ag * bg
    alpha, beta, gamma = ag.l1(), bg.l1(), sg.l1()
    requested = _tol(abs_error)
    if gamma >= 1:
        return _common(function="ramanujan_f_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"a": _grr(ag), "b": _grr(bg), "ab": _grr(sg), "rho_ab_l1": _fr(gamma)}, proof_formula="requires rho(a*b)<1 in current complex product lane", tail_payload=None)

    def evaluate(n: int):
        pa = ONE
        pb = ONE
        ps = ONE
        for k in range(n):
            sk = sg ** k
            pa = pa * (ONE + ag * sk)
            pb = pb * (ONE + bg * sk)
            ps = ps * (ONE - sg ** (k + 1))
        partial = pa * pb * ps
        den = 1 - gamma
        sa = alpha * gamma ** n / den
        sb = beta * gamma ** n / den
        ss = gamma ** (n + 1) / den
        total = sa + sb + ss
        error = None if total >= 1 else partial.l1() * total / (1 - total)
        return partial, error, {"a_plus_tail_sum": sa, "b_plus_tail_sum": sb, "ab_minus_tail_sum": ss, "combined_tail_sum": total}

    status, n, partial, error, tails = _choose(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _common(function="ramanujan_f_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"a": _grr(ag), "b": _grr(bg), "ab": _grr(sg), "alpha_l1": _fr(alpha), "beta_l1": _fr(beta), "gamma_ab_l1": _fr(gamma), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="combine omitted (-a;ab),(-b;ab),(ab;ab) factors; if S=S_a+S_b+S_ab<1 then |T-1|<=S/(1-S)", tail_payload=tails)
