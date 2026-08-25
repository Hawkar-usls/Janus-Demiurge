from __future__ import annotations

"""Rigorous finite-product certificates for Ramanujan/Jacobi q-products.

Supported positive-real rational lanes:

* phi_product(q) = (-q;q^2)_inf^2 (q^2;q^2)_inf
* psi_product(q) = (q^2;q^2)_inf / (q;q^2)_inf
* ramanujan_f_product(a,b) = (-a;ab)_inf (-b;ab)_inf (ab;ab)_inf

The proof uses elementary infinite-product inequalities. For x_k in [0,1)
with S=sum x_k < 1,

    product(1-x_k) >= 1-S,
    product(1+x_k) <= 1/(1-S).

The second follows by expanding the product and bounding each elementary
symmetric contribution by a power of S. These bounds turn the omitted product
tail into an exact rational multiplicative interval around the exact rational
finite product.
"""

from decimal import Decimal
from fractions import Fraction
import hashlib
import math
from typing import Any, Callable

SCHEMA = "janus.ramanujan_product_certified.v1"
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


def _fraction_receipt(value: Fraction, inline_bits: int = 4096) -> dict[str, Any]:
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


def _common(
    *,
    function: str,
    status: str,
    n: int,
    requested: Fraction,
    partial: Fraction,
    lower: Fraction | None,
    upper: Fraction | None,
    error: Fraction | None,
    input_payload: dict[str, Any],
    proof_formula: str,
    tail_sums: dict[str, Fraction | None],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "function": function,
        "status": status,
        "terms_used": n,
        "input": input_payload,
        "requested_abs_error": _fraction_receipt(requested),
        "partial_product": _fraction_receipt(partial),
        "estimate": float(partial),
        "estimate_is_certified": False,
        "true_value_interval": None if lower is None or upper is None else {
            "lower": _fraction_receipt(lower),
            "upper": _fraction_receipt(upper),
        },
        "absolute_error_bound": None if error is None else _fraction_receipt(error),
        "absolute_error_bound_decimal": None if error is None else f"{float(error):.17e}",
        "error_bound_le_requested": error is not None and error <= requested,
        "tail_sums": {
            key: None if value is None else _fraction_receipt(value)
            for key, value in tail_sums.items()
        },
        "proof_formula": proof_formula,
        "exact_arithmetic": True,
        "certified_object": "EXACT_RATIONAL_FINITE_PRODUCT_PLUS_RATIONAL_MULTIPLICATIVE_TAIL_INTERVAL",
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
            "FINITE_PRODUCT_NE_INFINITE_PRODUCT_WITHOUT_TAIL_BOUND",
            "PRODUCT_TAIL_INTERVAL_MUST_REMAIN_VISIBLE",
            "CERTIFICATE_REQUIRES_POSITIVE_REAL_RATIONAL_DOMAIN_IN_THIS_LANE",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }


def _choose(
    evaluator: Callable[[int], tuple[Fraction, Fraction | None, Fraction | None, dict[str, Fraction | None]]],
    *,
    requested: Fraction,
    start_terms: int,
    max_terms: int,
    growth: float,
) -> tuple[str, int, Fraction, Fraction | None, Fraction | None, Fraction | None, dict[str, Fraction | None]]:
    chosen = None
    for n in _schedule(start_terms, max_terms, growth):
        partial, lower_mult, upper_mult, tails = evaluator(n)
        lower = None if lower_mult is None else partial * lower_mult
        upper = None if upper_mult is None else partial * upper_mult
        error = None if lower is None or upper is None else max(partial - lower, upper - partial)
        chosen = (n, partial, lower, upper, error, tails)
        if error is not None and error <= requested:
            return (CERTIFIED, n, partial, lower, upper, error, tails)
    assert chosen is not None
    n, partial, lower, upper, error, tails = chosen
    return (NOT_CERTIFIED, n, partial, lower, upper, error, tails)


def certify_phi_product(
    *,
    q: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    qf = _fraction(q, "q")
    if not (0 <= qf < 1):
        raise ValueError("phi_product certified lane requires 0 <= q < 1")
    requested = _fraction(abs_error, "abs_error")
    if requested <= 0:
        raise ValueError("abs_error must be > 0")

    def evaluate(n: int):
        plus = Fraction(1, 1)
        even = Fraction(1, 1)
        for k in range(n):
            plus *= 1 + qf ** (2 * k + 1)
            even *= 1 - qf ** (2 * k + 2)
        partial = plus * plus * even
        denom = 1 - qf * qf
        s_plus = qf ** (2 * n + 1) / denom
        s_even = qf ** (2 * n + 2) / denom
        if s_plus >= 1 or s_even >= 1:
            return partial, None, None, {"plus_tail_sum": s_plus, "even_minus_tail_sum": s_even}
        lower_mult = 1 - s_even
        upper_mult = 1 / ((1 - s_plus) ** 2)
        return partial, lower_mult, upper_mult, {"plus_tail_sum": s_plus, "even_minus_tail_sum": s_even}

    status, n, partial, lower, upper, error, tails = _choose(
        evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth
    )
    return _common(
        function="phi_product",
        status=status,
        n=n,
        requested=requested,
        partial=partial,
        lower=lower,
        upper=upper,
        error=error,
        input_payload={"q": _fraction_receipt(qf), "interpretation": "EXACT_NONNEGATIVE_REAL_RATIONAL"},
        proof_formula=(
            "tail multiplier T satisfies 1-S_even <= T <= 1/(1-S_plus)^2; "
            "S_plus=q^(2N+1)/(1-q^2), S_even=q^(2N+2)/(1-q^2)"
        ),
        tail_sums=tails,
    )


def certify_psi_product(
    *,
    q: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    qf = _fraction(q, "q")
    if not (0 <= qf < 1):
        raise ValueError("psi_product certified lane requires 0 <= q < 1")
    requested = _fraction(abs_error, "abs_error")
    if requested <= 0:
        raise ValueError("abs_error must be > 0")

    def evaluate(n: int):
        even = Fraction(1, 1)
        odd = Fraction(1, 1)
        for k in range(n):
            even *= 1 - qf ** (2 * k + 2)
            odd *= 1 - qf ** (2 * k + 1)
        partial = even / odd
        denom = 1 - qf * qf
        s_even = qf ** (2 * n + 2) / denom
        s_odd = qf ** (2 * n + 1) / denom
        if s_even >= 1 or s_odd >= 1:
            return partial, None, None, {"even_minus_tail_sum": s_even, "odd_minus_tail_sum": s_odd}
        lower_mult = 1 - s_even
        upper_mult = 1 / (1 - s_odd)
        return partial, lower_mult, upper_mult, {"even_minus_tail_sum": s_even, "odd_minus_tail_sum": s_odd}

    status, n, partial, lower, upper, error, tails = _choose(
        evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth
    )
    return _common(
        function="psi_product",
        status=status,
        n=n,
        requested=requested,
        partial=partial,
        lower=lower,
        upper=upper,
        error=error,
        input_payload={"q": _fraction_receipt(qf), "interpretation": "EXACT_NONNEGATIVE_REAL_RATIONAL"},
        proof_formula=(
            "tail ratio T=B_tail/C_tail satisfies 1-S_even <= T <= 1/(1-S_odd); "
            "S_even=q^(2N+2)/(1-q^2), S_odd=q^(2N+1)/(1-q^2)"
        ),
        tail_sums=tails,
    )


def certify_ramanujan_f_product(
    *,
    a: Any,
    b: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    af, bf = _fraction(a, "a"), _fraction(b, "b")
    s = af * bf
    if af < 0 or bf < 0 or not (0 < s < 1):
        raise ValueError("ramanujan_f_product certified lane requires a>=0, b>=0, 0<a*b<1")
    requested = _fraction(abs_error, "abs_error")
    if requested <= 0:
        raise ValueError("abs_error must be > 0")

    def evaluate(n: int):
        pa = Fraction(1, 1)
        pb = Fraction(1, 1)
        ps = Fraction(1, 1)
        for k in range(n):
            sk = s ** k
            pa *= 1 + af * sk
            pb *= 1 + bf * sk
            ps *= 1 - s ** (k + 1)
        partial = pa * pb * ps
        denom = 1 - s
        sa = af * (s ** n) / denom
        sb = bf * (s ** n) / denom
        ss = s ** (n + 1) / denom
        if sa >= 1 or sb >= 1 or ss >= 1:
            return partial, None, None, {"a_plus_tail_sum": sa, "b_plus_tail_sum": sb, "ab_minus_tail_sum": ss}
        lower_mult = 1 - ss
        upper_mult = 1 / ((1 - sa) * (1 - sb))
        return partial, lower_mult, upper_mult, {"a_plus_tail_sum": sa, "b_plus_tail_sum": sb, "ab_minus_tail_sum": ss}

    status, n, partial, lower, upper, error, tails = _choose(
        evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth
    )
    return _common(
        function="ramanujan_f_product",
        status=status,
        n=n,
        requested=requested,
        partial=partial,
        lower=lower,
        upper=upper,
        error=error,
        input_payload={
            "a": _fraction_receipt(af),
            "b": _fraction_receipt(bf),
            "ab": _fraction_receipt(s),
            "interpretation": "EXACT_NONNEGATIVE_REAL_RATIONAL",
        },
        proof_formula=(
            "tail multiplier T satisfies 1-S_ab <= T <= 1/[(1-S_a)(1-S_b)]; "
            "S_a=a*(ab)^N/(1-ab), S_b=b*(ab)^N/(1-ab), S_ab=(ab)^(N+1)/(1-ab)"
        ),
        tail_sums=tails,
    )
