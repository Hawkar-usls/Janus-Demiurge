from __future__ import annotations

"""Rigorous complex-q certificates using exact Gaussian rationals.

This lane deliberately avoids floating/ball arithmetic by restricting inputs to
exact complex numbers with rational real and imaginary components.  All finite
series arithmetic is therefore exact in Q(i).

For z=x+iy define the exact rational majorant

    rho(z) = |x| + |y| >= |z|.

Whenever rho(q) < 1, integer-power q-series tails can be bounded by replacing
|q| with rho(q).  This gives rigorous, if conservative, certificates on the
L1 diamond |Re q|+|Im q|<1.

Supported q-series:
    phi/theta3, theta4, psi, mock_theta_f, mock_theta_omega.
Supported two-parameter series:
    Ramanujan f(a,b) when rho(a)*rho(b) < 1.

Theta2 is intentionally excluded because q^(1/4) requires a branch-aware
algebraic/validated-transcendental representation. Product-side complex lanes
are also left separate for a later proof.
"""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import hashlib
import math
from typing import Any

SCHEMA = "janus.ramanujan_complex_certified.v1"
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
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return Fraction(value)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, str):
        try:
            d = Decimal(value)
        except Exception as exc:
            raise ValueError(f"invalid exact decimal for {name}") from exc
        if not d.is_finite():
            raise ValueError(f"{name} must be finite")
        return Fraction(d)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return Fraction(Decimal(str(value)))
    raise ValueError(f"unsupported exact-real type for {name}")


@dataclass(frozen=True)
class GaussianRational:
    re: Fraction
    im: Fraction

    def __add__(self, other: "GaussianRational") -> "GaussianRational":
        return GaussianRational(self.re + other.re, self.im + other.im)

    def __sub__(self, other: "GaussianRational") -> "GaussianRational":
        return GaussianRational(self.re - other.re, self.im - other.im)

    def __neg__(self) -> "GaussianRational":
        return GaussianRational(-self.re, -self.im)

    def __mul__(self, other: "GaussianRational") -> "GaussianRational":
        return GaussianRational(
            self.re * other.re - self.im * other.im,
            self.re * other.im + self.im * other.re,
        )

    def __truediv__(self, other: "GaussianRational") -> "GaussianRational":
        d = other.re * other.re + other.im * other.im
        if d == 0:
            raise ZeroDivisionError("division by zero Gaussian rational")
        return GaussianRational(
            (self.re * other.re + self.im * other.im) / d,
            (self.im * other.re - self.re * other.im) / d,
        )

    def __pow__(self, exponent: int) -> "GaussianRational":
        if isinstance(exponent, bool):
            raise ValueError("exponent must be a nonnegative integer")
        exponent = int(exponent)
        if exponent < 0:
            raise ValueError("negative powers are not used in this certificate lane")
        out = ONE
        base = self
        e = exponent
        while e:
            if e & 1:
                out = out * base
            base = base * base
            e >>= 1
        return out

    def l1(self) -> Fraction:
        return abs(self.re) + abs(self.im)

    def to_complex(self) -> complex:
        return complex(float(self.re), float(self.im))


ZERO = GaussianRational(Fraction(0), Fraction(0))
ONE = GaussianRational(Fraction(1), Fraction(0))
TWO = GaussianRational(Fraction(2), Fraction(0))


def _gr(value: Any, name: str) -> GaussianRational:
    if isinstance(value, GaussianRational):
        return value
    if isinstance(value, dict):
        if "re" not in value or "im" not in value:
            raise ValueError(f"{name} mapping must contain re and im")
        return GaussianRational(_fraction(value["re"], f"{name}.re"), _fraction(value["im"], f"{name}.im"))
    if isinstance(value, (tuple, list)):
        if len(value) != 2:
            raise ValueError(f"{name} pair must contain [re, im]")
        return GaussianRational(_fraction(value[0], f"{name}.re"), _fraction(value[1], f"{name}.im"))
    # Exact-real values are embedded as imaginary part zero.
    return GaussianRational(_fraction(value, name), Fraction(0))


def is_exact_complex_container(value: Any) -> bool:
    return (
        isinstance(value, GaussianRational)
        or (isinstance(value, dict) and "re" in value and "im" in value)
        or (isinstance(value, (tuple, list)) and len(value) == 2)
    )


def as_empirical_complex(value: Any) -> complex:
    """Convert exact complex input to a display/empirical Python complex."""
    return _gr(value, "z").to_complex()


def _digest_integer(value: int) -> str:
    sign = b"-" if value < 0 else b"+"
    magnitude = abs(value)
    raw = magnitude.to_bytes(max(1, (magnitude.bit_length() + 7) // 8), "big")
    return hashlib.sha256(sign + raw).hexdigest()


def _fraction_receipt(value: Fraction, inline_bits: int = 2048) -> dict[str, Any]:
    num, den = value.numerator, value.denominator
    out = {
        "numerator_bits": abs(num).bit_length(),
        "denominator_bits": den.bit_length(),
        "numerator_sha256": _digest_integer(num),
        "denominator_sha256": _digest_integer(den),
    }
    if abs(num).bit_length() <= inline_bits and den.bit_length() <= inline_bits:
        out["numerator"] = str(num)
        out["denominator"] = str(den)
    return out


def _gr_receipt(value: GaussianRational) -> dict[str, Any]:
    return {
        "re": _fraction_receipt(value.re),
        "im": _fraction_receipt(value.im),
        "l1_majorant": _fraction_receipt(value.l1()),
    }


def _tol(value: Any) -> Fraction:
    out = _fraction(value, "abs_error")
    if out <= 0:
        raise ValueError("abs_error must be > 0")
    return out


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


def _theta_square_tail(rho: Fraction, n: int, factor: int) -> Fraction:
    first = rho ** ((n + 1) ** 2)
    ratio = rho ** (2 * n + 3)
    return factor * first / (1 - ratio)


def _psi_tail(rho: Fraction, n: int) -> Fraction:
    first = rho ** ((n + 1) * (n + 2) // 2)
    ratio = rho ** (n + 2)
    return first / (1 - ratio)


def _general_f_tail(alpha: Fraction, beta: Fraction, n: int) -> Fraction | None:
    s = alpha * beta
    if s >= 1:
        return None
    m = n + 1
    rp = alpha * (s ** m)
    rn = beta * (s ** m)
    if rp >= 1 or rn >= 1:
        return None
    pos_first = (alpha ** (m * (m + 1) // 2)) * (beta ** (m * (m - 1) // 2))
    neg_first = (alpha ** (m * (m - 1) // 2)) * (beta ** (m * (m + 1) // 2))
    return pos_first / (1 - rp) + neg_first / (1 - rn)


def _q_product_lower_bound(rho: Fraction, factors: int) -> Fraction | None:
    prod = Fraction(1)
    for k in range(1, factors + 1):
        prod *= 1 - rho ** k
    tail_sum = rho ** (factors + 1) / (1 - rho)
    if tail_sum >= 1:
        return None
    return prod * (1 - tail_sum)


def _odd_product_lower_bound(rho: Fraction, factors: int) -> Fraction | None:
    prod = Fraction(1)
    for k in range(factors):
        prod *= 1 - rho ** (2 * k + 1)
    tail_sum = rho ** (2 * factors + 1) / (1 - rho * rho)
    if tail_sum >= 1:
        return None
    return prod * (1 - tail_sum)


def _sum_phi(q: GaussianRational, n: int, alternating: bool = False) -> GaussianRational:
    total = ONE
    for k in range(1, n + 1):
        term = q ** (k * k)
        if alternating and k % 2:
            term = -term
        total = total + TWO * term
    return total


def _sum_psi(q: GaussianRational, n: int) -> GaussianRational:
    total = ZERO
    for k in range(0, n + 1):
        total = total + q ** (k * (k + 1) // 2)
    return total


def _sum_general_f(a: GaussianRational, b: GaussianRational, n: int) -> GaussianRational:
    total = ZERO
    for k in range(-n, n + 1):
        ea = k * (k + 1) // 2
        eb = k * (k - 1) // 2
        total = total + (a ** ea) * (b ** eb)
    return total


def _sum_mock_f(q: GaussianRational, n: int) -> GaussianRational:
    total = ONE
    prod = ONE
    for k in range(1, n + 1):
        prod = prod * (ONE + (q ** k))
        total = total + (q ** (k * k)) / (prod * prod)
    return total


def _sum_mock_omega(q: GaussianRational, n: int) -> GaussianRational:
    total = ZERO
    prod = ONE
    for k in range(0, n + 1):
        prod = prod * (ONE - (q ** (2 * k + 1)))
        total = total + (q ** (2 * k * (k + 1))) / (prod * prod)
    return total


def _common_receipt(
    *,
    function: str,
    status: str,
    terms_used: int,
    requested: Fraction,
    tail: Fraction | None,
    value: GaussianRational | None,
    input_payload: dict[str, Any],
    proof_formula: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "function": function,
        "status": status,
        "terms_used": terms_used,
        "requested_abs_error": _fraction_receipt(requested),
        "input": input_payload,
        "proof_formula": proof_formula,
        "exact_arithmetic": "GAUSSIAN_RATIONAL_Q_I",
        "certified_object": "EXACT_GAUSSIAN_RATIONAL_PARTIAL_SUM_PLUS_RATIONAL_MODULUS_TAIL_BOUND",
        "estimate_is_certified": False,
        "bound_geometry": "L1_MAJORANT_DIAMOND",
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
            "GAUSSIAN_RATIONAL_FINITE_ARITHMETIC_IS_EXACT",
            "L1_MAJORANT_GE_COMPLEX_MODULUS",
            "COMPLEX_CERTIFICATE_DOMAIN_MUST_REMAIN_VISIBLE",
            "COMPLEX_FLOAT_DISPLAY_NE_CERTIFIED_OBJECT",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }
    if tail is not None:
        out["tail_bound"] = _fraction_receipt(tail)
        out["tail_bound_decimal"] = f"{float(tail):.17e}"
        out["tail_bound_le_requested"] = tail <= requested
    if value is not None:
        out["partial_sum"] = _gr_receipt(value)
        z = value.to_complex()
        out["estimate"] = [z.real, z.imag]
    if extra:
        out.update(extra)
    return out


def certify_complex_q_series(
    function: str,
    *,
    q: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
    denominator_factors: int | None = None,
) -> dict[str, Any]:
    qg = _gr(q, "q")
    rho = qg.l1()
    requested = _tol(abs_error)
    if rho >= 1:
        return _common_receipt(
            function=function,
            status=OUTSIDE_BOUND_DOMAIN,
            terms_used=0,
            requested=requested,
            tail=None,
            value=None,
            input_payload={"q": _gr_receipt(qg), "rho_l1": _fraction_receipt(rho)},
            proof_formula="current complex certificate requires rho=|Re q|+|Im q|<1",
        )

    if function in {"phi", "theta3"}:
        tail_fn = lambda n: _theta_square_tail(rho, n, 2)
        sum_fn = lambda n: _sum_phi(qg, n, False)
        proof_formula = "|R_N|<=2*rho^((N+1)^2)/(1-rho^(2N+3)), rho=|Re q|+|Im q|"
    elif function == "theta4":
        tail_fn = lambda n: _theta_square_tail(rho, n, 2)
        sum_fn = lambda n: _sum_phi(qg, n, True)
        proof_formula = "|R_N|<=2*rho^((N+1)^2)/(1-rho^(2N+3)) by absolute majorization"
    elif function == "psi":
        tail_fn = lambda n: _psi_tail(rho, n)
        sum_fn = lambda n: _sum_psi(qg, n)
        proof_formula = "|R_N|<=rho^((N+1)(N+2)/2)/(1-rho^(N+2))"
    elif function == "mock_theta_f":
        denom = int(denominator_factors if denominator_factors is not None else max(32, start_terms + 1))
        if denom < 1 or denom > MAX_TERMS:
            raise ValueError("denominator_factors out of range")
        while denom < MAX_TERMS and _q_product_lower_bound(rho, denom) is None:
            denom = min(MAX_TERMS, max(denom + 1, int(math.ceil(denom * 1.5))))
        lower = _q_product_lower_bound(rho, denom)
        tail_fn = lambda n: None if lower is None else _theta_square_tail(rho, n, 1) / (lower * lower)
        sum_fn = lambda n: _sum_mock_f(qg, n)
        proof_formula = "|R_N|<=[rho^((N+1)^2)/(1-rho^(2N+3))]/L_rho^2; |prod(1+q^k)|>=prod(1-rho^k)>=L_rho"
    elif function == "mock_theta_omega":
        denom = int(denominator_factors if denominator_factors is not None else max(32, start_terms + 1))
        if denom < 1 or denom > MAX_TERMS:
            raise ValueError("denominator_factors out of range")
        while denom < MAX_TERMS and _odd_product_lower_bound(rho, denom) is None:
            denom = min(MAX_TERMS, max(denom + 1, int(math.ceil(denom * 1.5))))
        lower = _odd_product_lower_bound(rho, denom)
        def omega_tail(n: int) -> Fraction | None:
            if lower is None:
                return None
            first = rho ** (2 * (n + 1) * (n + 2))
            ratio = rho ** (4 * (n + 2))
            return first / (1 - ratio) / (lower * lower)
        tail_fn = omega_tail
        sum_fn = lambda n: _sum_mock_omega(qg, n)
        proof_formula = "|R_N|<=[rho^(2(N+1)(N+2))/(1-rho^(4(N+2)))]/L_odd^2 with |1-q^(2k+1)|>=1-rho^(2k+1)"
    else:
        raise ValueError("unsupported function for exact complex q-series certificate lane")

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
    if function in {"mock_theta_f", "mock_theta_omega"}:
        extra["denominator_factors_used"] = denom
        extra["denominator_modulus_lower_bound"] = None if lower is None else _fraction_receipt(lower)

    return _common_receipt(
        function=function,
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "q": _gr_receipt(qg),
            "rho_l1": _fraction_receipt(rho),
            "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS",
        },
        proof_formula=proof_formula,
        extra=extra,
    )


def certify_complex_ramanujan_f(
    *,
    a: Any,
    b: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    ag, bg = _gr(a, "a"), _gr(b, "b")
    alpha, beta = ag.l1(), bg.l1()
    s = alpha * beta
    requested = _tol(abs_error)
    if s >= 1:
        return _common_receipt(
            function="ramanujan_f",
            status=OUTSIDE_BOUND_DOMAIN,
            terms_used=0,
            requested=requested,
            tail=None,
            value=None,
            input_payload={
                "a": _gr_receipt(ag),
                "b": _gr_receipt(bg),
                "alpha_beta_l1": _fraction_receipt(s),
            },
            proof_formula="current complex f(a,b) certificate requires rho(a)*rho(b)<1",
        )

    chosen_n = max_terms
    chosen_tail: Fraction | None = None
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = _general_f_tail(alpha, beta, n)
        chosen_n = n
        chosen_tail = tail
        if tail is not None and tail <= requested:
            status = CERTIFIED
            break

    exact_sum = _sum_general_f(ag, bg, chosen_n)
    return _common_receipt(
        function="ramanujan_f",
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "a": _gr_receipt(ag),
            "b": _gr_receipt(bg),
            "alpha_l1": _fraction_receipt(alpha),
            "beta_l1": _fraction_receipt(beta),
            "alpha_beta_l1": _fraction_receipt(s),
            "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS",
        },
        proof_formula="positive and negative f(a,b) tails are bounded by geometric majorants using alpha=rho(a), beta=rho(b), alpha*beta<1",
    )
