from __future__ import annotations

"""Proof-first precision dispatcher for restored Ramanujan mathematics.

Assurance order:
    CERTIFIED_ERROR_BOUND > EMPIRICAL_CONVERGENCE_ONLY > NO_NUMERICAL_ASSURANCE

A successful analytic certificate always stops the weaker empirical lane.  A
failed, unavailable, or domain-ineligible proof may fall back to adaptive
numerics, but that fallback can never relabel itself as a certificate.

Version 4 adds an exact complex lane: callers may supply Gaussian-rational
components as ``(re, im)`` / ``[re, im]`` or ``{"re":..., "im":...}``.  Those
inputs can obtain rigorous complex certificates for the supported integer-power
direct q-series.  Ordinary Python ``complex`` values remain empirical because
their floating components are not silently reinterpreted as exact input.
"""

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import math
from typing import Any

from restored.ramanujan_adaptive_precision import (
    CONVERGED,
    NOT_CONVERGED,
    adaptive_evaluate,
    adaptive_identity_gate,
)
from restored.ramanujan_certified_bounds import (
    CERTIFIED,
    NOT_CERTIFIED,
    MAX_TERMS,
    certify_q_series,
    certify_ramanujan_f,
)
from restored.ramanujan_theta2_certified import certify_theta2
from restored.ramanujan_product_certified import (
    certify_phi_product,
    certify_psi_product,
    certify_ramanujan_f_product,
)
from restored.ramanujan_complex_certified import (
    as_empirical_complex,
    certify_complex_q_series,
    certify_complex_ramanujan_f,
    is_exact_complex_container,
)

SCHEMA = "janus.ramanujan_proof_first_dispatcher.v4"
EMPIRICAL_ONLY = "EMPIRICAL_CONVERGENCE_ONLY"
NO_NUMERICAL_ASSURANCE = "NO_NUMERICAL_ASSURANCE"

CERTIFIED_Q_FUNCTIONS = frozenset({
    "phi", "phi_product", "psi", "psi_product", "theta2", "theta3",
    "theta4", "mock_theta_f", "mock_theta_omega",
})
CERTIFIED_GENERAL_FUNCTIONS = frozenset({"ramanujan_f", "ramanujan_f_product"})
COMPLEX_CERTIFIED_Q_FUNCTIONS = frozenset({
    "phi", "psi", "theta3", "theta4", "mock_theta_f", "mock_theta_omega",
})
COMPLEX_CERTIFIED_GENERAL_FUNCTIONS = frozenset({"ramanujan_f"})
EMPIRICAL_Q_FUNCTIONS = CERTIFIED_Q_FUNCTIONS
EMPIRICAL_GENERAL_FUNCTIONS = CERTIFIED_GENERAL_FUNCTIONS


def _authority() -> dict[str, bool]:
    return {
        "network": False,
        "filesystem_mutation": False,
        "scheduler": False,
        "runtime_admission": False,
        "mining_or_submit": False,
        "proof_acceptance": False,
        "automatic_control": False,
    }


def _precision_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("precision must be a positive finite real number") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise ValueError("precision must be a positive finite real number")
    return out


def _normalize_exact_real(value: Any, name: str) -> tuple[bool, Any, str]:
    if isinstance(value, bool):
        return False, value, f"{name}_BOOL_NOT_EXACT_REAL_INPUT"
    if isinstance(value, complex):
        if value.imag != 0.0:
            return False, value, f"{name}_PYTHON_COMPLEX_FLOAT_REMAINS_EMPIRICAL"
        value = value.real
    if isinstance(value, Fraction):
        return True, value, f"{name}_EXACT_FRACTION"
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return True, value, f"{name}_EXACT_DECIMAL"
    if isinstance(value, int):
        return True, value, f"{name}_EXACT_INTEGER"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return True, value, f"{name}_FINITE_FLOAT_DECIMAL_SPELLING"
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            return False, value, f"{name}_STRING_NOT_FINITE_REAL_DECIMAL"
        if not parsed.is_finite():
            raise ValueError(f"{name} must be finite")
        return True, value, f"{name}_EXACT_DECIMAL_STRING"
    return False, value, f"{name}_TYPE_NOT_SUPPORTED_BY_CERTIFIED_REAL_LANE"


def _route_fraction(value: Any, name: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Decimal):
        return Fraction(value)
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(Decimal(str(value)))
    if isinstance(value, str):
        return Fraction(Decimal(value))
    raise ValueError(f"{name} is not an exact-real route value")


def _proof_route(function: str, *, q: Any, a: Any, b: Any) -> dict[str, Any]:
    if function in CERTIFIED_Q_FUNCTIONS:
        if q is None:
            raise ValueError(f"{function} requires q")

        if is_exact_complex_container(q):
            if function in COMPLEX_CERTIFIED_Q_FUNCTIONS:
                return {
                    "available": True,
                    "eligible": True,
                    "mode": "EXACT_GAUSSIAN_RATIONAL_Q",
                    "reason": "EXACT_COMPLEX_COMPONENTS_ROUTE_TO_GAUSSIAN_RATIONAL_CERTIFICATE",
                    "q": q,
                }
            return {
                "available": True,
                "eligible": False,
                "mode": "EXACT_COMPLEX_UNSUPPORTED",
                "reason": f"NO_EXACT_COMPLEX_CERTIFICATE_IMPLEMENTED_FOR_{function.upper()}",
                "q": q,
            }

        eligible, normalized_q, reason = _normalize_exact_real(q, "q")
        if eligible:
            qf = _route_fraction(normalized_q, "q")
            if abs(qf) >= 1:
                raise ValueError(f"{function} requires |q| < 1")
            if function == "theta2" and not (0 < qf < 1):
                eligible = False
                reason = "THETA2_CERTIFICATE_REQUIRES_0_LT_Q_LT_1"
            elif function in {"phi_product", "psi_product"} and not (0 <= qf < 1):
                eligible = False
                reason = f"{function.upper()}_CERTIFICATE_REQUIRES_0_LE_Q_LT_1"
        return {
            "available": True,
            "eligible": eligible,
            "mode": "EXACT_REAL_RATIONAL",
            "reason": reason,
            "q": normalized_q,
        }

    if function in CERTIFIED_GENERAL_FUNCTIONS:
        if a is None or b is None:
            raise ValueError(f"{function} requires a and b")

        if is_exact_complex_container(a) or is_exact_complex_container(b):
            if function in COMPLEX_CERTIFIED_GENERAL_FUNCTIONS:
                return {
                    "available": True,
                    "eligible": True,
                    "mode": "EXACT_GAUSSIAN_RATIONAL_GENERAL",
                    "reason": "EXACT_COMPLEX_COMPONENTS_ROUTE_TO_GAUSSIAN_RATIONAL_CERTIFICATE",
                    "a": a,
                    "b": b,
                }
            return {
                "available": True,
                "eligible": False,
                "mode": "EXACT_COMPLEX_UNSUPPORTED",
                "reason": f"NO_EXACT_COMPLEX_CERTIFICATE_IMPLEMENTED_FOR_{function.upper()}",
                "a": a,
                "b": b,
            }

        ea, na, ra = _normalize_exact_real(a, "a")
        eb, nb, rb = _normalize_exact_real(b, "b")
        eligible = ea and eb
        reason = f"{ra};{rb}"
        if eligible:
            af, bf = _route_fraction(na, "a"), _route_fraction(nb, "b")
            if abs(af * bf) >= 1:
                raise ValueError(f"{function} requires |a*b| < 1")
            if function == "ramanujan_f_product" and not (af >= 0 and bf >= 0 and af * bf > 0):
                eligible = False
                reason = "RAMANUJAN_F_PRODUCT_CERTIFICATE_REQUIRES_A_GE_0_B_GE_0_AND_0_LT_AB_LT_1"
        return {
            "available": True,
            "eligible": eligible,
            "mode": "EXACT_REAL_RATIONAL",
            "reason": reason,
            "a": na,
            "b": nb,
        }

    return {
        "available": False,
        "eligible": False,
        "mode": "NONE",
        "reason": "NO_ANALYTIC_CERTIFICATE_IMPLEMENTED_FOR_FUNCTION",
    }


def _empirical_number(value: Any) -> Any:
    if is_exact_complex_container(value):
        return as_empirical_complex(value)
    return value


def _empirical(function: str, *, q: Any, a: Any, b: Any, precision: float, max_terms: int, start_terms: int, growth: float, stable_steps: int) -> dict[str, Any]:
    q_emp = _empirical_number(q)
    a_emp = _empirical_number(a)
    b_emp = _empirical_number(b)
    if function == "phi":
        return adaptive_identity_gate("phi", q=q_emp, abs_tol=precision, rel_tol=0.0, start_terms=start_terms, max_terms=max_terms, growth=growth, stable_steps=stable_steps)
    if function == "psi":
        return adaptive_identity_gate("psi", q=q_emp, abs_tol=precision, rel_tol=0.0, start_terms=start_terms, max_terms=max_terms, growth=growth, stable_steps=stable_steps)
    if function == "ramanujan_f":
        return adaptive_identity_gate("ramanujan_f", a=a_emp, b=b_emp, abs_tol=precision, rel_tol=0.0, start_terms=start_terms, max_terms=max_terms, growth=growth, stable_steps=stable_steps)
    if function in EMPIRICAL_Q_FUNCTIONS:
        return adaptive_evaluate(function, q=q_emp, abs_tol=precision, rel_tol=0.0, start_terms=start_terms, max_terms=max_terms, growth=growth, stable_steps=stable_steps)
    if function in EMPIRICAL_GENERAL_FUNCTIONS:
        return adaptive_evaluate(function, a=a_emp, b=b_emp, abs_tol=precision, rel_tol=0.0, start_terms=start_terms, max_terms=max_terms, growth=growth, stable_steps=stable_steps)
    raise ValueError(f"unsupported function: {function}")


def _certified_attempt(function: str, *, route: dict[str, Any], precision: Any, start_terms: int, max_terms: int, growth: float) -> dict[str, Any]:
    mode = route["mode"]
    if mode == "EXACT_GAUSSIAN_RATIONAL_Q":
        return certify_complex_q_series(function, q=route["q"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if mode == "EXACT_GAUSSIAN_RATIONAL_GENERAL":
        return certify_complex_ramanujan_f(a=route["a"], b=route["b"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function == "theta2":
        return certify_theta2(q=route["q"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function == "phi_product":
        return certify_phi_product(q=route["q"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function == "psi_product":
        return certify_psi_product(q=route["q"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function in {"phi", "psi", "theta3", "theta4", "mock_theta_f", "mock_theta_omega"}:
        return certify_q_series(function, q=route["q"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function == "ramanujan_f_product":
        return certify_ramanujan_f_product(a=route["a"], b=route["b"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    if function == "ramanujan_f":
        return certify_ramanujan_f(a=route["a"], b=route["b"], abs_error=precision, start_terms=start_terms, max_terms=max_terms, growth=growth)
    raise ValueError(f"no certified attempt implementation for {function}")


def _proof_route_view(route: dict[str, Any], *, attempted: bool, status: str | None) -> dict[str, Any]:
    return {
        "available": route["available"],
        "eligible": route["eligible"],
        "mode": route.get("mode"),
        "reason": route["reason"],
        "attempted": attempted,
        "status": status,
    }


def proof_first_evaluate(
    function: str,
    *,
    q: Any = None,
    a: Any = None,
    b: Any = None,
    precision: Any = "1e-12",
    proof_start_terms: int = 4,
    proof_max_terms: int = MAX_TERMS,
    proof_growth: float = 1.5,
    empirical_start_terms: int = 16,
    empirical_max_terms: int = MAX_TERMS,
    empirical_growth: float = 2.0,
    empirical_stable_steps: int = 2,
    allow_empirical_fallback: bool = True,
) -> dict[str, Any]:
    """Return the strongest justified assurance class without evidence mixing."""
    precision_float = _precision_float(precision)
    route = _proof_route(function, q=q, a=a, b=b)
    proof_receipt: dict[str, Any] | None = None

    if route["available"] and route["eligible"]:
        proof_receipt = _certified_attempt(function, route=route, precision=precision, start_terms=proof_start_terms, max_terms=proof_max_terms, growth=proof_growth)
        if proof_receipt["status"] == CERTIFIED:
            return {
                "schema": SCHEMA,
                "function": function,
                "status": CERTIFIED,
                "assurance_class": "ANALYTIC_CERTIFIED_ERROR_BOUND",
                "requested_abs_error": str(precision),
                "proof_route": _proof_route_view(route, attempted=True, status=CERTIFIED),
                "empirical_route": {"attempted": False, "reason": "SKIPPED_BECAUSE_STRONGER_CERTIFICATE_ALREADY_OBTAINED"},
                "proof_receipt": proof_receipt,
                "empirical_receipt": None,
                "claim": "|F-S_N| <= analytic_error_bound <= requested_abs_error",
                "authority": _authority(),
                "laws": [
                    "PROOF_FIRST",
                    "CERTIFIED_ERROR_BOUND_GT_EMPIRICAL_CONVERGENCE",
                    "EXACT_COMPLEX_INPUT_MUST_BE_EXPLICIT_NOT_INFERRED_FROM_PYTHON_COMPLEX_FLOAT",
                    "EMPIRICAL_CONVERGENCE_MUST_NEVER_PROMOTE_ITSELF_TO_CERTIFICATE",
                    "NUMERICAL_ASSURANCE_NE_RUNTIME_AUTHORITY",
                ],
            }

    proof_status = None if proof_receipt is None else proof_receipt["status"]
    if not allow_empirical_fallback:
        return {
            "schema": SCHEMA,
            "function": function,
            "status": proof_status or NOT_CERTIFIED,
            "assurance_class": NO_NUMERICAL_ASSURANCE,
            "requested_abs_error": str(precision),
            "proof_route": _proof_route_view(route, attempted=proof_receipt is not None, status=proof_status),
            "empirical_route": {"attempted": False, "reason": "FALLBACK_DISABLED"},
            "proof_receipt": proof_receipt,
            "empirical_receipt": None,
            "authority": _authority(),
        }

    empirical_receipt = _empirical(function, q=q, a=a, b=b, precision=precision_float, max_terms=empirical_max_terms, start_terms=empirical_start_terms, growth=empirical_growth, stable_steps=empirical_stable_steps)
    empirical_converged = empirical_receipt["status"] == CONVERGED
    return {
        "schema": SCHEMA,
        "function": function,
        "status": CONVERGED if empirical_converged else NOT_CONVERGED,
        "assurance_class": EMPIRICAL_ONLY if empirical_converged else NO_NUMERICAL_ASSURANCE,
        "requested_abs_error": str(precision),
        "proof_route": _proof_route_view(route, attempted=proof_receipt is not None, status=proof_status),
        "empirical_route": {"attempted": True, "status": empirical_receipt["status"], "evidence_class": empirical_receipt.get("evidence_class")},
        "proof_receipt": proof_receipt,
        "empirical_receipt": empirical_receipt,
        "claim": (
            "successive truncations satisfy empirical adaptive convergence only; no analytic certificate"
            if empirical_converged else
            "requested numerical assurance was not obtained within configured budgets"
        ),
        "authority": _authority(),
        "laws": [
            "PROOF_FIRST",
            "PROOF_FAILURE_OR_DOMAIN_INELIGIBILITY_MAY_FALL_BACK_BUT_MUST_REMAIN_VISIBLE",
            "EMPIRICAL_CONVERGENCE_MUST_NEVER_PROMOTE_ITSELF_TO_CERTIFICATE",
            "ASSURANCE_CLASS_MUST_MATCH_EVIDENCE_CLASS",
            "NUMERICAL_ASSURANCE_NE_RUNTIME_AUTHORITY",
        ],
    }


def canonical_dispatch_suite() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "certified_phi": proof_first_evaluate("phi", q="0.9", precision="1e-12"),
        "certified_theta2": proof_first_evaluate("theta2", q="0.2", precision="1e-12", proof_max_terms=128),
        "certified_phi_product": proof_first_evaluate("phi_product", q="0.5", precision="1e-12", proof_max_terms=128),
        "certified_complex_theta3": proof_first_evaluate("theta3", q=("0.3", "0.2"), precision="1e-12", proof_max_terms=128),
        "certified_complex_general_f": proof_first_evaluate("ramanujan_f", a=("0.2", "0.1"), b=("0.3", "-0.05"), precision="1e-12", proof_max_terms=128),
        "python_complex_empirical": proof_first_evaluate("theta3", q=0.3 + 0.2j, precision="1e-12", empirical_max_terms=256),
        "authority": "MATHEMATICS_ONLY",
    }
