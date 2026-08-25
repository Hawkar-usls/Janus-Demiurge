from __future__ import annotations

"""Analytic tail-bound certificates for restored Ramanujan/q-series mathematics.

This module upgrades selected real-rational q-series evaluations from empirical
successive-truncation convergence to mathematically derived tail bounds.

For supported functions, the finite partial sum is evaluated exactly with
``fractions.Fraction`` and the omitted infinite tail is bounded analytically.
Therefore, when status == ``CERTIFIED_ERROR_BOUND``, the receipt proves

    |F - S_N| <= tail_bound <= requested_abs_error

for the exact rational input recorded in the receipt.

Scope boundary
--------------
* Supported lane: real rational inputs with |q| < 1 (or |ab| < 1 for f(a,b)).
* The floating ``estimate`` field is convenience only and is NOT the certified
  object. Certification attaches to the exact finite rational sum S_N and the
  exact rational tail bound.
* Complex-q and irrational-input certification remain open; those continue to
  use the empirical adaptive-precision lane.
* No scheduler, network, mining, proof-acceptance, runtime-admission,
  filesystem-mutation, or model-control authority is granted.
"""

from decimal import Decimal
from fractions import Fraction
import hashlib
import math
from typing import Any, Callable

SCHEMA = "janus.ramanujan_certified_bounds.v1"
CERTIFIED = "CERTIFIED_ERROR_BOUND"
NOT_CERTIFIED = "NOT_CERTIFIED_WITHIN_BUDGET"
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
        except Exception as exc:  # pragma: no cover - defensive boundary
            raise ValueError(f"invalid exact decimal for {name}") from exc
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        # Interpret the human-visible shortest decimal spelling exactly.
        return Fraction(Decimal(str(value)))
    raise ValueError(f"unsupported exact-real type for {name}")


def _tol(value: Any) -> Fraction:
    out = _fraction(value, "abs_error")
    if out <= 0:
        raise ValueError("abs_error must be > 0")
    return out


def _budget(start_terms: int, max_terms: int, growth: float) -> tuple[int, int, float]:
    if isinstance(start_terms, bool) or isinstance(max_terms, bool):
        raise ValueError("term budgets must be integers")
    start_terms = int(start_terms)
    max_terms = int(max_terms)
    growth = float(growth)
    if start_terms < 0:
        raise ValueError("start_terms must be >= 0")
    if max_terms < start_terms or max_terms > MAX_TERMS:
        raise ValueError(f"max_terms must be in [start_terms,{MAX_TERMS}]")
    if not math.isfinite(growth) or growth <= 1.0:
        raise ValueError("growth must be finite and > 1")
    return start_terms, max_terms, growth


def _schedule(start_terms: int, max_terms: int, growth: float) -> list[int]:
    out = [start_terms]
    current = start_terms
    while current < max_terms:
        nxt = min(max_terms, max(current + 1, int(math.ceil(max(1, current) * growth))))
        if nxt == current:
            break
        out.append(nxt)
        current = nxt
    return out


def _digest_integer(value: int) -> str:
    sign = b"-" if value < 0 else b"+"
    magnitude = abs(value)
    raw = magnitude.to_bytes(max(1, (magnitude.bit_length() + 7) // 8), "big")
    return hashlib.sha256(sign + raw).hexdigest()


def _fraction_receipt(value: Fraction, inline_bits: int = 4096) -> dict[str, Any]:
    num = value.numerator
    den = value.denominator
    base = {
        "numerator_bits": abs(num).bit_length(),
        "denominator_bits": den.bit_length(),
        "numerator_sha256": _digest_integer(num),
        "denominator_sha256": _digest_integer(den),
    }
    if abs(num).bit_length() <= inline_bits and den.bit_length() <= inline_bits:
        base["numerator"] = str(num)
        base["denominator"] = str(den)
    return base


def _decimal_scientific(value: Fraction, digits: int = 17) -> str:
    if value == 0:
        return "0"
    return f"{float(value):.{digits}e}"


def _theta_square_tail(r: Fraction, n: int, factor: int = 1) -> Fraction:
    """Bound sum_{k=n+1}^inf factor*r^(k^2), 0<=r<1."""
    first = r ** ((n + 1) ** 2)
    ratio = r ** (2 * n + 3)
    return Fraction(factor, 1) * first / (1 - ratio)


def _psi_tail(r: Fraction, n: int) -> Fraction:
    """Bound sum_{k=n+1}^inf r^(k(k+1)/2)."""
    first_exp = (n + 1) * (n + 2) // 2
    first = r ** first_exp
    ratio = r ** (n + 2)
    return first / (1 - ratio)


def _general_f_tail(a: Fraction, b: Fraction, n: int) -> Fraction | None:
    """Two-sided geometric majorant for Ramanujan f(a,b) after [-n,n]."""
    aa = abs(a)
    bb = abs(b)
    s = aa * bb
    if s >= 1:
        raise ValueError("Ramanujan f(a,b) requires |a*b| < 1")
    m = n + 1

    pos_ratio = aa * (s ** m)
    neg_ratio = bb * (s ** m)
    if pos_ratio >= 1 or neg_ratio >= 1:
        return None

    pos_first = (aa ** (m * (m + 1) // 2)) * (bb ** (m * (m - 1) // 2))
    neg_first = (aa ** (m * (m - 1) // 2)) * (bb ** (m * (m + 1) // 2))
    return pos_first / (1 - pos_ratio) + neg_first / (1 - neg_ratio)


def _q_product_lower_bound(r: Fraction, factors: int) -> Fraction | None:
    """Lower bound for product_{k>=1}(1-r^k) using first ``factors`` terms.

    The tail inequality product(1-x_k) >= 1-sum(x_k) is used when the latter
    is positive.
    """
    if not (0 <= r < 1):
        raise ValueError("r must satisfy 0 <= r < 1")
    prod = Fraction(1, 1)
    for k in range(1, factors + 1):
        prod *= 1 - r ** k
    tail_sum = r ** (factors + 1) / (1 - r)
    if tail_sum >= 1:
        return None
    return prod * (1 - tail_sum)


def _odd_q_product_lower_bound(r: Fraction, factors: int) -> Fraction | None:
    """Lower bound for product_{k>=0}(1-r^(2k+1))."""
    if not (0 <= r < 1):
        raise ValueError("r must satisfy 0 <= r < 1")
    prod = Fraction(1, 1)
    for k in range(factors):
        prod *= 1 - r ** (2 * k + 1)
    tail_sum = r ** (2 * factors + 1) / (1 - r * r)
    if tail_sum >= 1:
        return None
    return prod * (1 - tail_sum)


def _mock_f_tail(r: Fraction, n: int, denominator_factors: int) -> Fraction | None:
    lower = _q_product_lower_bound(r, denominator_factors)
    if lower is None or lower <= 0:
        return None
    numerator_tail = _theta_square_tail(r, n, factor=1)
    return numerator_tail / (lower * lower)


def _mock_omega_tail(r: Fraction, n: int, denominator_factors: int) -> Fraction | None:
    lower = _odd_q_product_lower_bound(r, denominator_factors)
    if lower is None or lower <= 0:
        return None
    first_n = n + 1
    first = r ** (2 * first_n * (first_n + 1))
    ratio = r ** (4 * (n + 2))
    numerator_tail = first / (1 - ratio)
    return numerator_tail / (lower * lower)


def _sum_phi(q: Fraction, n: int) -> Fraction:
    total = Fraction(1, 1)
    for k in range(1, n + 1):
        total += 2 * (q ** (k * k))
    return total


def _sum_theta4(q: Fraction, n: int) -> Fraction:
    total = Fraction(1, 1)
    for k in range(1, n + 1):
        total += 2 * ((-1) ** k) * (q ** (k * k))
    return total


def _sum_psi(q: Fraction, n: int) -> Fraction:
    total = Fraction(0, 1)
    for k in range(0, n + 1):
        total += q ** (k * (k + 1) // 2)
    return total


def _sum_general_f(a: Fraction, b: Fraction, n: int) -> Fraction:
    total = Fraction(0, 1)
    for k in range(-n, n + 1):
        ea = k * (k + 1) // 2
        eb = k * (k - 1) // 2
        total += (a ** ea) * (b ** eb)
    return total


def _sum_mock_f(q: Fraction, n: int) -> Fraction:
    total = Fraction(1, 1)
    prod = Fraction(1, 1)
    for k in range(1, n + 1):
        prod *= 1 + q ** k
        total += q ** (k * k) / (prod * prod)
    return total


def _sum_mock_omega(q: Fraction, n: int) -> Fraction:
    total = Fraction(0, 1)
    prod = Fraction(1, 1)
    for k in range(0, n + 1):
        prod *= 1 - q ** (2 * k + 1)
        total += q ** (2 * k * (k + 1)) / (prod * prod)
    return total


def _common_receipt(
    *,
    function: str,
    status: str,
    terms_used: int,
    requested: Fraction,
    tail: Fraction | None,
    value: Fraction | None,
    input_payload: dict[str, Any],
    proof_formula: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "function": function,
        "status": status,
        "terms_used": terms_used,
        "requested_abs_error": _fraction_receipt(requested),
        "requested_abs_error_decimal": _decimal_scientific(requested),
        "input": input_payload,
        "proof_formula": proof_formula,
        "exact_arithmetic": True,
        "certified_object": "EXACT_RATIONAL_PARTIAL_SUM_PLUS_ANALYTIC_TAIL_BOUND",
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
            "EMPIRICAL_CONVERGENCE_NE_CERTIFIED_ERROR_BOUND",
            "CERTIFICATE_REQUIRES_EXACT_PARTIAL_SUM_AND_ANALYTIC_TAIL_MAJORANT",
            "FLOAT_ESTIMATE_IS_DISPLAY_ONLY",
            "COMPLEX_Q_REMAINS_UNCERTIFIED_IN_THIS_LANE",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }
    if tail is not None:
        receipt["tail_bound"] = _fraction_receipt(tail)
        receipt["tail_bound_decimal"] = _decimal_scientific(tail)
        receipt["tail_bound_le_requested"] = tail <= requested
    if value is not None:
        receipt["partial_sum"] = _fraction_receipt(value)
        receipt["estimate"] = float(value)
    if extra:
        receipt.update(extra)
    return receipt


def certify_q_series(
    function: str,
    *,
    q: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
    denominator_factors: int | None = None,
) -> dict[str, Any]:
    """Certify a supported real-rational q-series to an absolute tail bound.

    Supported functions: phi, theta3, theta4, psi, mock_theta_f,
    mock_theta_omega.
    """
    qf = _fraction(q, "q")
    if abs(qf) >= 1:
        raise ValueError("q must satisfy |q| < 1")
    requested = _tol(abs_error)
    start_terms, max_terms, growth = _budget(start_terms, max_terms, growth)
    r = abs(qf)

    if function in ("phi", "theta3"):
        tail_fn: Callable[[int], Fraction | None] = lambda n: _theta_square_tail(r, n, factor=2)
        sum_fn = lambda n: _sum_phi(qf, n)
        proof_formula = "|R_N| <= 2*r^((N+1)^2)/(1-r^(2N+3))"
    elif function == "theta4":
        tail_fn = lambda n: _theta_square_tail(r, n, factor=2)
        sum_fn = lambda n: _sum_theta4(qf, n)
        proof_formula = "|R_N| <= 2*r^((N+1)^2)/(1-r^(2N+3)) by absolute majorization"
    elif function == "psi":
        tail_fn = lambda n: _psi_tail(r, n)
        sum_fn = lambda n: _sum_psi(qf, n)
        proof_formula = "|R_N| <= r^((N+1)(N+2)/2)/(1-r^(N+2))"
    elif function == "mock_theta_f":
        denom = denominator_factors if denominator_factors is not None else max(32, start_terms + 1)
        denom = int(denom)
        if denom < 1 or denom > MAX_TERMS:
            raise ValueError("denominator_factors out of range")
        # Increase the denominator-product proof depth if necessary.
        while denom < MAX_TERMS and _q_product_lower_bound(r, denom) is None:
            denom = min(MAX_TERMS, max(denom + 1, int(math.ceil(denom * 1.5))))
        tail_fn = lambda n: _mock_f_tail(r, n, denom)
        sum_fn = lambda n: _sum_mock_f(qf, n)
        proof_formula = "|R_N| <= [r^((N+1)^2)/(1-r^(2N+3))] / L_q^2, where L_q <= (r;r)_infinity is a proved positive lower bound"
    elif function == "mock_theta_omega":
        denom = denominator_factors if denominator_factors is not None else max(32, start_terms + 1)
        denom = int(denom)
        if denom < 1 or denom > MAX_TERMS:
            raise ValueError("denominator_factors out of range")
        while denom < MAX_TERMS and _odd_q_product_lower_bound(r, denom) is None:
            denom = min(MAX_TERMS, max(denom + 1, int(math.ceil(denom * 1.5))))
        tail_fn = lambda n: _mock_omega_tail(r, n, denom)
        sum_fn = lambda n: _sum_mock_omega(qf, n)
        proof_formula = "|R_N| <= [r^(2(N+1)(N+2))/(1-r^(4(N+2)))] / L_odd^2, with a proved positive odd-product lower bound"
    else:
        raise ValueError("unsupported function for certified q-series lane")

    chosen_n = max_terms
    chosen_tail: Fraction | None = None
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = tail_fn(n)
        chosen_n = n
        chosen_tail = tail
        if tail is not None and tail <= requested:
            status = CERTIFIED
            break

    exact_sum = sum_fn(chosen_n)
    extra: dict[str, Any] = {}
    if function in ("mock_theta_f", "mock_theta_omega"):
        extra["denominator_factors_used"] = denom
        if function == "mock_theta_f":
            lower = _q_product_lower_bound(r, denom)
            extra["denominator_infinite_product_lower_bound"] = None if lower is None else _fraction_receipt(lower)
        else:
            lower = _odd_q_product_lower_bound(r, denom)
            extra["denominator_infinite_product_lower_bound"] = None if lower is None else _fraction_receipt(lower)

    return _common_receipt(
        function=function,
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "q": _fraction_receipt(qf),
            "q_decimal": str(Decimal(qf.numerator) / Decimal(qf.denominator)) if qf.denominator.bit_length() < 512 else None,
            "interpretation": "EXACT_REAL_RATIONAL_FROM_DECIMAL_SPELLING",
        },
        proof_formula=proof_formula,
        extra=extra,
    )


def certify_ramanujan_f(
    *,
    a: Any,
    b: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    """Certify the symmetric direct series for Ramanujan f(a,b), real rational lane."""
    af = _fraction(a, "a")
    bf = _fraction(b, "b")
    if abs(af * bf) >= 1:
        raise ValueError("Ramanujan f(a,b) requires |a*b| < 1")
    requested = _tol(abs_error)
    start_terms, max_terms, growth = _budget(start_terms, max_terms, growth)

    chosen_n = max_terms
    chosen_tail: Fraction | None = None
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = _general_f_tail(af, bf, n)
        chosen_n = n
        chosen_tail = tail
        if tail is not None and tail <= requested:
            status = CERTIFIED
            break

    exact_sum = _sum_general_f(af, bf, chosen_n)
    return _common_receipt(
        function="ramanujan_f",
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "a": _fraction_receipt(af),
            "b": _fraction_receipt(bf),
            "abs_ab": _fraction_receipt(abs(af * bf)),
            "interpretation": "EXACT_REAL_RATIONAL_FROM_DECIMAL_SPELLING",
        },
        proof_formula=(
            "positive and negative tails are bounded separately by geometric majorants; "
            "successive term ratios are <= |a|*|ab|^(N+1) and |b|*|ab|^(N+1)"
        ),
    )


def canonical_certificate_suite() -> dict[str, Any]:
    """Small deterministic certificate suite used by tests and audits."""
    return {
        "schema": SCHEMA,
        "phi_q_0_9": certify_q_series("phi", q="0.9", abs_error="1e-12", max_terms=256),
        "psi_q_0_9": certify_q_series("psi", q="0.9", abs_error="1e-12", max_terms=256),
        "mock_f_q_0_2": certify_q_series("mock_theta_f", q="0.2", abs_error="1e-12", max_terms=128),
        "general_f": certify_ramanujan_f(a="0.2", b="0.3", abs_error="1e-12", max_terms=128),
        "authority": "MATHEMATICS_ONLY",
    }
