from __future__ import annotations

"""Adaptive numerical precision gate for restored Ramanujan theta mathematics.

The gate replaces fixed silent truncation with an explicit convergence receipt.
It increases the truncation budget until the requested numerical tolerance is
met or the hard budget is exhausted.

Important boundary
------------------
`CONVERGED` means that successive finite truncations satisfy the configured
Cauchy-style numerical criterion. It is numerical convergence evidence, not a
formal proof of the infinite-series error bound. No scheduler, network, mining,
proof-acceptance, runtime-admission, filesystem-mutation or model-control
authority is granted by this module.
"""

import math
from typing import Any, Callable

from restored.ramanujan_theta_kernel import (
    MAX_TERMS,
    mock_theta_f,
    mock_theta_omega,
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

SCHEMA = "janus.ramanujan_adaptive_precision.v1"
CONVERGED = "CONVERGED"
NOT_CONVERGED = "NOT_CONVERGED_WITHIN_BUDGET"


def _finite(z: complex) -> bool:
    return math.isfinite(z.real) and math.isfinite(z.imag)


def _validate_tolerances(abs_tol: float, rel_tol: float) -> tuple[float, float]:
    abs_tol = float(abs_tol)
    rel_tol = float(rel_tol)
    if not math.isfinite(abs_tol) or not math.isfinite(rel_tol):
        raise ValueError("tolerances must be finite")
    if abs_tol <= 0.0 or rel_tol < 0.0:
        raise ValueError("require abs_tol > 0 and rel_tol >= 0")
    return abs_tol, rel_tol


def _validate_budget(start_terms: int, max_terms: int, growth: float, stable_steps: int) -> tuple[int, int, float, int]:
    if isinstance(start_terms, bool) or isinstance(max_terms, bool) or isinstance(stable_steps, bool):
        raise ValueError("term budgets and stable_steps must be integers")
    start_terms = int(start_terms)
    max_terms = int(max_terms)
    stable_steps = int(stable_steps)
    growth = float(growth)
    if start_terms < 1:
        raise ValueError("start_terms must be >= 1")
    if max_terms < start_terms or max_terms > MAX_TERMS:
        raise ValueError(f"max_terms must be in [start_terms,{MAX_TERMS}]")
    if not math.isfinite(growth) or growth <= 1.0:
        raise ValueError("growth must be finite and > 1")
    if stable_steps < 1:
        raise ValueError("stable_steps must be >= 1")
    return start_terms, max_terms, growth, stable_steps


def _schedule(start_terms: int, max_terms: int, growth: float) -> list[int]:
    out = [start_terms]
    current = start_terms
    while current < max_terms:
        nxt = min(max_terms, max(current + 1, int(math.ceil(current * growth))))
        if nxt == current:
            break
        out.append(nxt)
        current = nxt
    return out


def _threshold(value: complex, abs_tol: float, rel_tol: float) -> float:
    return abs_tol + rel_tol * max(1.0, abs(value))


def _encode(z: complex) -> list[float]:
    return [float(z.real), float(z.imag)]


def _single_evaluator(name: str, *, q: complex | float | None, a: complex | float | None, b: complex | float | None) -> Callable[[int], complex]:
    q_map: dict[str, Callable[[complex | float, int], complex | float]] = {
        "phi": phi,
        "phi_product": phi_product,
        "psi": psi,
        "psi_product": psi_product,
        "theta2": theta2,
        "theta3": theta3,
        "theta4": theta4,
        "mock_theta_f": mock_theta_f,
        "mock_theta_omega": mock_theta_omega,
    }
    if name in q_map:
        if q is None:
            raise ValueError(f"{name} requires q")
        fn = q_map[name]
        return lambda terms: complex(fn(q, terms))
    if name == "ramanujan_f":
        if a is None or b is None:
            raise ValueError("ramanujan_f requires a and b")
        return lambda terms: complex(ramanujan_f(a, b, terms))
    if name == "ramanujan_f_product":
        if a is None or b is None:
            raise ValueError("ramanujan_f_product requires a and b")
        return lambda terms: complex(ramanujan_f_product(a, b, terms))
    raise ValueError(f"unsupported evaluator: {name}")


def adaptive_evaluate(
    name: str,
    *,
    q: complex | float | None = None,
    a: complex | float | None = None,
    b: complex | float | None = None,
    abs_tol: float = 1e-12,
    rel_tol: float = 1e-12,
    start_terms: int = 16,
    max_terms: int = MAX_TERMS,
    growth: float = 2.0,
    stable_steps: int = 2,
) -> dict[str, Any]:
    """Adaptively evaluate one finite-truncation sequence.

    Promotion to CONVERGED requires `stable_steps` consecutive truncation deltas
    to be below abs_tol + rel_tol*max(1, |value|).
    """
    abs_tol, rel_tol = _validate_tolerances(abs_tol, rel_tol)
    start_terms, max_terms, growth, stable_steps = _validate_budget(start_terms, max_terms, growth, stable_steps)
    evaluate = _single_evaluator(name, q=q, a=a, b=b)

    rows: list[dict[str, Any]] = []
    previous: complex | None = None
    stable_run = 0
    status = NOT_CONVERGED

    for terms in _schedule(start_terms, max_terms, growth):
        value = evaluate(terms)
        if not _finite(value):
            raise ArithmeticError("non-finite adaptive evaluation")
        threshold = _threshold(value, abs_tol, rel_tol)
        delta = None if previous is None else abs(value - previous)
        stable = delta is not None and delta <= threshold
        stable_run = stable_run + 1 if stable else 0
        rows.append({
            "terms": terms,
            "value": _encode(value),
            "step_delta": delta,
            "threshold": threshold,
            "stable": stable,
            "stable_run": stable_run,
        })
        if stable_run >= stable_steps:
            status = CONVERGED
            break
        previous = value

    final = rows[-1]
    return {
        "schema": SCHEMA,
        "kind": "SINGLE_SEQUENCE",
        "evaluator": name,
        "status": status,
        "requested": {
            "abs_tol": abs_tol,
            "rel_tol": rel_tol,
            "stable_steps": stable_steps,
            "start_terms": start_terms,
            "max_terms": max_terms,
            "growth": growth,
        },
        "terms_used": final["terms"],
        "value": final["value"],
        "error_proxy": final["step_delta"],
        "threshold": final["threshold"],
        "rows": rows,
        "evidence_class": "EMPIRICAL_CAUCHY_TRUNCATION_RECEIPT",
        "formal_error_bound": False,
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


def _identity_pair(kind: str, *, q: complex | float | None, a: complex | float | None, b: complex | float | None) -> tuple[str, str, Callable[[int], complex], Callable[[int], complex]]:
    if kind == "phi":
        if q is None:
            raise ValueError("phi identity requires q")
        return "phi", "phi_product", lambda t: complex(phi(q, t)), lambda t: complex(phi_product(q, t))
    if kind == "psi":
        if q is None:
            raise ValueError("psi identity requires q")
        return "psi", "psi_product", lambda t: complex(psi(q, t)), lambda t: complex(psi_product(q, t))
    if kind == "ramanujan_f":
        if a is None or b is None:
            raise ValueError("ramanujan_f identity requires a and b")
        return "ramanujan_f", "ramanujan_f_product", lambda t: complex(ramanujan_f(a, b, t)), lambda t: complex(ramanujan_f_product(a, b, t))
    raise ValueError("identity kind must be phi, psi, or ramanujan_f")


def adaptive_identity_gate(
    kind: str,
    *,
    q: complex | float | None = None,
    a: complex | float | None = None,
    b: complex | float | None = None,
    abs_tol: float = 1e-12,
    rel_tol: float = 1e-12,
    start_terms: int = 16,
    max_terms: int = MAX_TERMS,
    growth: float = 2.0,
    stable_steps: int = 2,
) -> dict[str, Any]:
    """Adaptive cross-identity gate for direct and product representations.

    CONVERGED requires both representations to stabilize independently and the
    direct/product residual to satisfy the same requested tolerance.
    """
    abs_tol, rel_tol = _validate_tolerances(abs_tol, rel_tol)
    start_terms, max_terms, growth, stable_steps = _validate_budget(start_terms, max_terms, growth, stable_steps)
    left_name, right_name, left_eval, right_eval = _identity_pair(kind, q=q, a=a, b=b)

    rows: list[dict[str, Any]] = []
    previous_left: complex | None = None
    previous_right: complex | None = None
    left_run = 0
    right_run = 0
    status = NOT_CONVERGED

    for terms in _schedule(start_terms, max_terms, growth):
        left = left_eval(terms)
        right = right_eval(terms)
        if not (_finite(left) and _finite(right)):
            raise ArithmeticError("non-finite adaptive identity evaluation")

        left_delta = None if previous_left is None else abs(left - previous_left)
        right_delta = None if previous_right is None else abs(right - previous_right)
        left_threshold = _threshold(left, abs_tol, rel_tol)
        right_threshold = _threshold(right, abs_tol, rel_tol)
        identity_scale = max(1.0, abs(left), abs(right))
        identity_threshold = abs_tol + rel_tol * identity_scale
        identity_residual = abs(left - right)

        left_stable = left_delta is not None and left_delta <= left_threshold
        right_stable = right_delta is not None and right_delta <= right_threshold
        left_run = left_run + 1 if left_stable else 0
        right_run = right_run + 1 if right_stable else 0
        identity_ok = identity_residual <= identity_threshold

        rows.append({
            "terms": terms,
            "left": _encode(left),
            "right": _encode(right),
            "left_step_delta": left_delta,
            "right_step_delta": right_delta,
            "identity_residual": identity_residual,
            "left_threshold": left_threshold,
            "right_threshold": right_threshold,
            "identity_threshold": identity_threshold,
            "left_stable_run": left_run,
            "right_stable_run": right_run,
            "identity_ok": identity_ok,
        })

        if left_run >= stable_steps and right_run >= stable_steps and identity_ok:
            status = CONVERGED
            break

        previous_left = left
        previous_right = right

    final = rows[-1]
    return {
        "schema": SCHEMA,
        "kind": "CROSS_IDENTITY",
        "identity": kind,
        "representations": [left_name, right_name],
        "status": status,
        "requested": {
            "abs_tol": abs_tol,
            "rel_tol": rel_tol,
            "stable_steps": stable_steps,
            "start_terms": start_terms,
            "max_terms": max_terms,
            "growth": growth,
        },
        "terms_used": final["terms"],
        "identity_residual": final["identity_residual"],
        "identity_threshold": final["identity_threshold"],
        "rows": rows,
        "evidence_class": "DUAL_REPRESENTATION_ADAPTIVE_CONVERGENCE_RECEIPT",
        "formal_error_bound": False,
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
            "FIXED_TRUNCATION_NE_PRECISION_CLAIM",
            "CONVERGED_MEANS_NUMERICAL_RECEIPT_NOT_FORMAL_TAIL_PROOF",
            "BUDGET_EXHAUSTION_MUST_RETURN_NOT_CONVERGED",
            "DIRECT_AND_PRODUCT_REPRESENTATIONS_MUST_STABILIZE_INDEPENDENTLY",
            "PRECISION_GATE_NE_RUNTIME_AUTHORITY",
        ],
    }
