from __future__ import annotations

"""Proof-first precision dispatcher for restored Ramanujan mathematics.

Routing law
-----------
1. If an analytic certified-error lane exists for the requested function and
   the input is an exact-real candidate, try that lane first.
2. If it returns CERTIFIED_ERROR_BOUND, stop: this is the strongest available
   claim and no empirical result is needed to promote it.
3. If certification is unavailable or the proof budget is exhausted, an
   empirical adaptive-convergence fallback may run, but it can only return the
   weaker assurance class EMPIRICAL_CONVERGENCE_ONLY.
4. The dispatcher never promotes CONVERGED to CERTIFIED_ERROR_BOUND.

This module is pure mathematics routing only. It grants no scheduler, network,
mining, proof-acceptance, runtime-admission, filesystem-mutation, or automatic
control authority.
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

SCHEMA = "janus.ramanujan_proof_first_dispatcher.v2"
EMPIRICAL_ONLY = "EMPIRICAL_CONVERGENCE_ONLY"
NO_NUMERICAL_ASSURANCE = "NO_NUMERICAL_ASSURANCE"

CERTIFIED_Q_FUNCTIONS = frozenset(
    {
        "phi",
        "theta2",
        "theta3",
        "theta4",
        "psi",
        "mock_theta_f",
        "mock_theta_omega",
    }
)
CERTIFIED_GENERAL_FUNCTIONS = frozenset({"ramanujan_f"})
EMPIRICAL_Q_FUNCTIONS = frozenset(
    {
        "phi",
        "phi_product",
        "psi",
        "psi_product",
        "theta2",
        "theta3",
        "theta4",
        "mock_theta_f",
        "mock_theta_omega",
    }
)
EMPIRICAL_GENERAL_FUNCTIONS = frozenset({"ramanujan_f", "ramanujan_f_product"})


def _precision_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("precision must be a positive finite real number") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise ValueError("precision must be a positive finite real number")
    return out


def _normalize_exact_real(value: Any, name: str) -> tuple[bool, Any, str]:
    """Return whether value can enter the exact-rational certificate lane.

    Strings are accepted only when Decimal can parse them as a finite real.
    Complex values with exactly zero imaginary part are normalized to their real
    component; genuinely complex values remain empirical-only.
    """
    if isinstance(value, bool):
        return False, value, f"{name}_BOOL_NOT_EXACT_REAL_INPUT"
    if isinstance(value, complex):
        if value.imag != 0.0:
            return False, value, f"{name}_COMPLEX_INPUT_REQUIRES_EMPIRICAL_LANE"
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


def _proof_route(function: str, *, q: Any, a: Any, b: Any) -> dict[str, Any]:
    if function in CERTIFIED_Q_FUNCTIONS:
        if q is None:
            raise ValueError(f"{function} requires q")
        eligible, normalized_q, reason = _normalize_exact_real(q, "q")
        return {
            "available": True,
            "eligible": eligible,
            "reason": reason,
            "q": normalized_q,
        }
    if function in CERTIFIED_GENERAL_FUNCTIONS:
        if a is None or b is None:
            raise ValueError("ramanujan_f requires a and b")
        ea, na, ra = _normalize_exact_real(a, "a")
        eb, nb, rb = _normalize_exact_real(b, "b")
        return {
            "available": True,
            "eligible": ea and eb,
            "reason": f"{ra};{rb}",
            "a": na,
            "b": nb,
        }
    return {
        "available": False,
        "eligible": False,
        "reason": "NO_ANALYTIC_CERTIFICATE_IMPLEMENTED_FOR_FUNCTION",
    }


def _empirical(function: str, *, q: Any, a: Any, b: Any, precision: float, max_terms: int, start_terms: int, growth: float, stable_steps: int) -> dict[str, Any]:
    # For functions with two independently implemented representations, use the
    # stronger cross-identity adaptive gate rather than a single sequence.
    if function == "phi":
        return adaptive_identity_gate(
            "phi",
            q=q,
            abs_tol=precision,
            rel_tol=0.0,
            start_terms=start_terms,
            max_terms=max_terms,
            growth=growth,
            stable_steps=stable_steps,
        )
    if function == "psi":
        return adaptive_identity_gate(
            "psi",
            q=q,
            abs_tol=precision,
            rel_tol=0.0,
            start_terms=start_terms,
            max_terms=max_terms,
            growth=growth,
            stable_steps=stable_steps,
        )
    if function == "ramanujan_f":
        return adaptive_identity_gate(
            "ramanujan_f",
            a=a,
            b=b,
            abs_tol=precision,
            rel_tol=0.0,
            start_terms=start_terms,
            max_terms=max_terms,
            growth=growth,
            stable_steps=stable_steps,
        )
    if function in EMPIRICAL_Q_FUNCTIONS:
        return adaptive_evaluate(
            function,
            q=q,
            abs_tol=precision,
            rel_tol=0.0,
            start_terms=start_terms,
            max_terms=max_terms,
            growth=growth,
            stable_steps=stable_steps,
        )
    if function in EMPIRICAL_GENERAL_FUNCTIONS:
        return adaptive_evaluate(
            function,
            a=a,
            b=b,
            abs_tol=precision,
            rel_tol=0.0,
            start_terms=start_terms,
            max_terms=max_terms,
            growth=growth,
            stable_steps=stable_steps,
        )
    raise ValueError(f"unsupported function: {function}")


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
    """Return the strongest justified numerical assurance without class mixing."""
    precision_float = _precision_float(precision)
    route = _proof_route(function, q=q, a=a, b=b)
    proof_receipt: dict[str, Any] | None = None
    empirical_receipt: dict[str, Any] | None = None

    if route["available"] and route["eligible"]:
        if function == "theta2":
            proof_receipt = certify_theta2(
                q=route["q"],
                abs_error=precision,
                start_terms=proof_start_terms,
                max_terms=proof_max_terms,
                growth=proof_growth,
            )
        elif function in CERTIFIED_Q_FUNCTIONS:
            proof_receipt = certify_q_series(
                function,
                q=route["q"],
                abs_error=precision,
                start_terms=proof_start_terms,
                max_terms=proof_max_terms,
                growth=proof_growth,
            )
        else:
            proof_receipt = certify_ramanujan_f(
                a=route["a"],
                b=route["b"],
                abs_error=precision,
                start_terms=proof_start_terms,
                max_terms=proof_max_terms,
                growth=proof_growth,
            )

        if proof_receipt["status"] == CERTIFIED:
            return {
                "schema": SCHEMA,
                "function": function,
                "status": CERTIFIED,
                "assurance_class": "ANALYTIC_CERTIFIED_ERROR_BOUND",
                "requested_abs_error": str(precision),
                "proof_route": {
                    "available": True,
                    "eligible": True,
                    "reason": route["reason"],
                    "attempted": True,
                    "status": proof_receipt["status"],
                },
                "empirical_route": {
                    "attempted": False,
                    "reason": "SKIPPED_BECAUSE_STRONGER_CERTIFICATE_ALREADY_OBTAINED",
                },
                "proof_receipt": proof_receipt,
                "empirical_receipt": None,
                "claim": "|F-S_N| <= analytic_tail_bound <= requested_abs_error",
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
                    "PROOF_FIRST",
                    "CERTIFIED_ERROR_BOUND_GT_EMPIRICAL_CONVERGENCE",
                    "EMPIRICAL_CONVERGENCE_MUST_NEVER_PROMOTE_ITSELF_TO_CERTIFICATE",
                    "STRONGER_ASSURANCE_STOPS_WEAKER_FALLBACK",
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
            "proof_route": {
                "available": route["available"],
                "eligible": route["eligible"],
                "reason": route["reason"],
                "attempted": proof_receipt is not None,
                "status": proof_status,
            },
            "empirical_route": {"attempted": False, "reason": "FALLBACK_DISABLED"},
            "proof_receipt": proof_receipt,
            "empirical_receipt": None,
            "authority": {
                "network": False,
                "filesystem_mutation": False,
                "scheduler": False,
                "runtime_admission": False,
                "mining_or_submit": False,
                "proof_acceptance": False,
                "automatic_control": False,
            },
        }

    empirical_receipt = _empirical(
        function,
        q=q,
        a=a,
        b=b,
        precision=precision_float,
        max_terms=empirical_max_terms,
        start_terms=empirical_start_terms,
        growth=empirical_growth,
        stable_steps=empirical_stable_steps,
    )

    empirical_converged = empirical_receipt["status"] == CONVERGED
    return {
        "schema": SCHEMA,
        "function": function,
        "status": CONVERGED if empirical_converged else NOT_CONVERGED,
        "assurance_class": EMPIRICAL_ONLY if empirical_converged else NO_NUMERICAL_ASSURANCE,
        "requested_abs_error": str(precision),
        "proof_route": {
            "available": route["available"],
            "eligible": route["eligible"],
            "reason": route["reason"],
            "attempted": proof_receipt is not None,
            "status": proof_status,
        },
        "empirical_route": {
            "attempted": True,
            "status": empirical_receipt["status"],
            "evidence_class": empirical_receipt.get("evidence_class"),
        },
        "proof_receipt": proof_receipt,
        "empirical_receipt": empirical_receipt,
        "claim": (
            "successive truncations satisfy empirical adaptive convergence only; no analytic tail certificate"
            if empirical_converged
            else "requested numerical assurance was not obtained within configured budgets"
        ),
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
            "PROOF_FIRST",
            "PROOF_FAILURE_MAY_FALL_BACK_BUT_MUST_REMAIN_VISIBLE",
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
        "empirical_phi_product": proof_first_evaluate("phi_product", q=0.2, precision="1e-12", empirical_max_terms=256),
        "complex_theta3": proof_first_evaluate("theta3", q=0.6 * complex(math.cos(0.3), math.sin(0.3)), precision="1e-12", empirical_max_terms=256),
        "authority": "MATHEMATICS_ONLY",
    }
