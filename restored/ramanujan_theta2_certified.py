from __future__ import annotations

"""Analytic tail certificate for Jacobi theta_2(0,q), real rational lane.

For 0 < q < 1,

    theta_2(0,q) = 2*q^(1/4) * sum_{n>=0} q^(n(n+1)).

When q is rational, the finite coefficient

    C_N = 2 * sum_{n=0}^N q^(n(n+1))

is exactly rational, while q^(1/4) may be irrational. We therefore keep the
partial sum as an exact symbolic algebraic object ``q^(1/4) * C_N`` instead of
pretending it is rational.

For the omitted tail, q^(1/4) <= 1 and the ratio of successive coefficient
terms is at most q^(2N+4), giving the rigorous rational majorant

    |R_N| <= 2*q^((N+1)(N+2)) / (1-q^(2N+4)).

Thus a successful receipt certifies the full theta_2 value despite using a
symbolic finite term. Float estimates are display-only.
"""

from decimal import Decimal
from fractions import Fraction
import hashlib
import math
from typing import Any

SCHEMA = "janus.ramanujan_theta2_certified.v1"
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
    num = value.numerator
    den = value.denominator
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
    start_terms = int(start_terms)
    max_terms = int(max_terms)
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


def _coefficient(q: Fraction, n: int) -> Fraction:
    total = Fraction(0, 1)
    for k in range(0, n + 1):
        total += q ** (k * (k + 1))
    return 2 * total


def theta2_tail_bound(q: Fraction, n: int) -> Fraction:
    """Rigorous rational bound for the omitted theta2 tail after n."""
    if not (0 < q < 1):
        raise ValueError("certified theta2 lane requires 0 < q < 1")
    first = q ** ((n + 1) * (n + 2))
    ratio = q ** (2 * n + 4)
    return 2 * first / (1 - ratio)


def certify_theta2(
    *,
    q: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    qf = _fraction(q, "q")
    if not (0 < qf < 1):
        raise ValueError("certified theta2 lane requires real rational 0 < q < 1")
    requested = _fraction(abs_error, "abs_error")
    if requested <= 0:
        raise ValueError("abs_error must be > 0")

    chosen_n = max_terms
    chosen_tail = theta2_tail_bound(qf, max_terms)
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = theta2_tail_bound(qf, n)
        chosen_n = n
        chosen_tail = tail
        if tail <= requested:
            status = CERTIFIED
            break

    coefficient = _coefficient(qf, chosen_n)
    estimate = (float(qf) ** 0.25) * float(coefficient)
    return {
        "schema": SCHEMA,
        "function": "theta2",
        "status": status,
        "terms_used": chosen_n,
        "input": {
            "q": _fraction_receipt(qf),
            "interpretation": "EXACT_POSITIVE_REAL_RATIONAL_FROM_DECIMAL_SPELLING",
        },
        "requested_abs_error": _fraction_receipt(requested),
        "tail_bound": _fraction_receipt(chosen_tail),
        "tail_bound_decimal": f"{float(chosen_tail):.17e}",
        "tail_bound_le_requested": chosen_tail <= requested,
        "exact_symbolic_partial_sum": {
            "expression": "q^(1/4) * C_N",
            "C_N": _fraction_receipt(coefficient),
            "C_N_definition": "2*sum_{n=0}^N q^(n(n+1))",
            "common_algebraic_factor": "q^(1/4)",
        },
        "estimate": estimate,
        "estimate_is_certified": False,
        "certified_object": "EXACT_SYMBOLIC_ALGEBRAIC_PARTIAL_SUM_PLUS_RATIONAL_ANALYTIC_TAIL_BOUND",
        "proof_formula": "|R_N| <= 2*q^((N+1)(N+2))/(1-q^(2N+4)); q^(1/4)<=1 and successive coefficient ratios are <=q^(2N+4)",
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
            "ALGEBRAIC_SYMBOLIC_EXACTNESS_NE_FLOAT_APPROXIMATION",
            "THETA2_FRACTIONAL_EXPONENT_NE_UNCERTIFIED_FLOAT_REQUIREMENT",
            "CERTIFICATE_MAY_USE_SYMBOLIC_EXACT_PARTIAL_SUM",
            "TAIL_BOUND_MUST_BE_RIGOROUS",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }
