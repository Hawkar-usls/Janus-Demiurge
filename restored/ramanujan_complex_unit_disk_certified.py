from __future__ import annotations

"""Rigorous complex Ramanujan certificates on the full exact open unit disk.

This module keeps finite arithmetic exact in Gaussian rationals Q(i), but
replaces the older L1-only convergence gate with a sharper exact rational
majorant.  For z=x+iy let

    s = x^2 + y^2 = |z|^2  (exact rational)
    rho_AMGM = (1+s)/2.

Because (1-sqrt(s))^2 >= 0,

    |z| = sqrt(s) <= (1+s)/2.

Therefore s<1 implies rho_AMGM<1 without evaluating any square root.  We use

    rho(z) = min(|x|+|y|, (1+s)/2),

which is still an exact rational upper bound for |z|, never weaker than the
old L1 majorant, and covers every exact Gaussian-rational point with |z|<1.

Supported direct series:
    phi/theta3, theta4, psi, mock_theta_f, mock_theta_omega, Ramanujan f(a,b).
Supported product representations:
    phi_product, psi_product, Ramanujan f_product.

Complex theta2 remains separate because q^(1/4) requires a branch-aware
validated algebraic/ball representation.  This module is mathematics-only and
grants no runtime, network, scheduler, mining, filesystem, or control authority.
"""

from fractions import Fraction
import math
from typing import Any, Callable

from restored.ramanujan_complex_certified import (
    GaussianRational,
    ONE,
    _gr,
    _fraction_receipt,
    _gr_receipt,
    _tol,
    _schedule,
    _theta_square_tail,
    _psi_tail,
    _q_product_lower_bound,
    _odd_product_lower_bound,
    _sum_phi,
    _sum_psi,
    _sum_general_f,
    _sum_mock_f,
    _sum_mock_omega,
)

SCHEMA = "janus.ramanujan_complex_unit_disk_certified.v2"
CERTIFIED = "CERTIFIED_ERROR_BOUND"
NOT_CERTIFIED = "NOT_CERTIFIED_WITHIN_BUDGET"
OUTSIDE_BOUND_DOMAIN = "NOT_CERTIFIED_OUTSIDE_CURRENT_COMPLEX_BOUND_DOMAIN"
MAX_TERMS = 4096
BOUND_GEOMETRY = "FULL_EXACT_OPEN_UNIT_DISK_VIA_RATIONAL_AMGM_MAJORANT"


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


def exact_squared_modulus(z: GaussianRational) -> Fraction:
    """Return |z|^2 exactly in Q."""
    return z.re * z.re + z.im * z.im


def rational_euclidean_majorant(z: GaussianRational) -> Fraction:
    """Exact rational upper bound (1+|z|^2)/2 >= |z|."""
    s = exact_squared_modulus(z)
    return (Fraction(1) + s) / 2


def selected_modulus_majorant(z: GaussianRational) -> Fraction:
    """Tightest of two exact rational upper bounds available here."""
    return min(z.l1(), rational_euclidean_majorant(z))


def _profile(z: GaussianRational) -> dict[str, Any]:
    s = exact_squared_modulus(z)
    l1 = z.l1()
    amgm = (Fraction(1) + s) / 2
    selected = min(l1, amgm)
    return {
        "squared_modulus_exact": _fraction_receipt(s),
        "l1_majorant": _fraction_receipt(l1),
        "amgm_euclidean_majorant": _fraction_receipt(amgm),
        "selected_modulus_majorant": _fraction_receipt(selected),
        "inside_open_unit_disk": s < 1,
        "selection": "MIN_L1_AMGM",
    }


def _general_f_tail(alpha: Fraction, beta: Fraction, gamma: Fraction, n: int) -> Fraction | None:
    """Two-sided f(a,b) tail using gamma >= |ab| independently of alpha*beta.

    For m=N+1, positive terms obey
        |t_m| <= alpha^m gamma^(m(m-1)/2)
        |t_{k+1}/t_k| <= alpha gamma^m,  k>=m.
    The negative side is identical with beta.
    """
    if gamma >= 1:
        return None
    m = n + 1
    rp = alpha * (gamma ** m)
    rn = beta * (gamma ** m)
    if rp >= 1 or rn >= 1:
        return None
    shared = gamma ** (m * (m - 1) // 2)
    pos_first = (alpha ** m) * shared
    neg_first = (beta ** m) * shared
    return pos_first / (1 - rp) + neg_first / (1 - rn)


def _series_receipt(
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
        "certified_object": "EXACT_GAUSSIAN_RATIONAL_PARTIAL_SUM_PLUS_RATIONAL_ANALYTIC_TAIL_BOUND",
        "estimate_is_certified": False,
        "bound_geometry": BOUND_GEOMETRY,
        "authority": _authority(),
        "laws": [
            "GAUSSIAN_RATIONAL_FINITE_ARITHMETIC_IS_EXACT",
            "SQUARED_MODULUS_OF_GAUSSIAN_RATIONAL_IS_EXACT_RATIONAL",
            "AMGM_RATIONAL_MAJORANT_GE_COMPLEX_MODULUS",
            "SELECTED_MAJORANT_IS_MIN_OF_TWO_PROVED_UPPER_BOUNDS",
            "EXACT_OPEN_UNIT_DISK_REPLACES_L1_DIAMOND_AS_PROOF_DOMAIN",
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


def certify_complex_q_series_disk(
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
    s = exact_squared_modulus(qg)
    rho = selected_modulus_majorant(qg)
    requested = _tol(abs_error)
    if s >= 1:
        return _series_receipt(
            function=function,
            status=OUTSIDE_BOUND_DOMAIN,
            terms_used=0,
            requested=requested,
            tail=None,
            value=None,
            input_payload={"q": _gr_receipt(qg), "majorant_profile": _profile(qg)},
            proof_formula="exact complex certificate requires |q|^2=(Re q)^2+(Im q)^2<1",
        )

    if function in {"phi", "theta3"}:
        tail_fn = lambda n: _theta_square_tail(rho, n, 2)
        sum_fn = lambda n: _sum_phi(qg, n, False)
        proof_formula = "|R_N|<=2*rho^((N+1)^2)/(1-rho^(2N+3)); |q|<=rho=min(L1,(1+|q|^2)/2)<1"
    elif function == "theta4":
        tail_fn = lambda n: _theta_square_tail(rho, n, 2)
        sum_fn = lambda n: _sum_phi(qg, n, True)
        proof_formula = "theta4 tail is absolutely majorized by the theta-square tail with exact rational rho>=|q|"
    elif function == "psi":
        tail_fn = lambda n: _psi_tail(rho, n)
        sum_fn = lambda n: _sum_psi(qg, n)
        proof_formula = "|R_N|<=rho^((N+1)(N+2)/2)/(1-rho^(N+2)), with exact rational rho>=|q|"
    elif function == "mock_theta_f":
        denom = int(denominator_factors if denominator_factors is not None else max(32, start_terms + 1))
        if denom < 1 or denom > MAX_TERMS:
            raise ValueError("denominator_factors out of range")
        while denom < MAX_TERMS and _q_product_lower_bound(rho, denom) is None:
            denom = min(MAX_TERMS, max(denom + 1, int(math.ceil(denom * 1.5))))
        lower = _q_product_lower_bound(rho, denom)
        tail_fn = lambda n: None if lower is None else _theta_square_tail(rho, n, 1) / (lower * lower)
        sum_fn = lambda n: _sum_mock_f(qg, n)
        proof_formula = "mock f tail <= theta-square numerator majorant / L_rho^2, with |1+q^k|>=1-rho^k"
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
        proof_formula = "mock omega tail uses exact rational rho>=|q| and a proved odd-product denominator lower bound"
    else:
        raise ValueError("unsupported function for exact complex unit-disk q-series lane")

    chosen_n = max_terms
    chosen_tail: Fraction | None = None
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = tail_fn(n)
        chosen_n, chosen_tail = n, tail
        if tail is not None and tail <= requested:
            status = CERTIFIED
            break
    exact_sum = sum_fn(chosen_n)

    extra: dict[str, Any] = {}
    if function in {"mock_theta_f", "mock_theta_omega"}:
        extra["denominator_factors_used"] = denom
        extra["denominator_modulus_lower_bound"] = None if lower is None else _fraction_receipt(lower)

    return _series_receipt(
        function=function,
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "q": _gr_receipt(qg),
            "majorant_profile": _profile(qg),
            "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS",
        },
        proof_formula=proof_formula,
        extra=extra,
    )


def certify_complex_ramanujan_f_disk(
    *,
    a: Any,
    b: Any,
    abs_error: Any = "1e-12",
    start_terms: int = 4,
    max_terms: int = MAX_TERMS,
    growth: float = 1.5,
) -> dict[str, Any]:
    ag, bg = _gr(a, "a"), _gr(b, "b")
    abg = ag * bg
    alpha = selected_modulus_majorant(ag)
    beta = selected_modulus_majorant(bg)
    gamma = selected_modulus_majorant(abg)
    s_ab = exact_squared_modulus(abg)
    requested = _tol(abs_error)
    if s_ab >= 1:
        return _series_receipt(
            function="ramanujan_f",
            status=OUTSIDE_BOUND_DOMAIN,
            terms_used=0,
            requested=requested,
            tail=None,
            value=None,
            input_payload={
                "a": _gr_receipt(ag), "b": _gr_receipt(bg), "ab": _gr_receipt(abg),
                "a_profile": _profile(ag), "b_profile": _profile(bg), "ab_profile": _profile(abg),
            },
            proof_formula="Ramanujan f(a,b) direct certificate requires exact |a*b|^2<1",
        )

    chosen_n = max_terms
    chosen_tail: Fraction | None = None
    status = NOT_CERTIFIED
    for n in _schedule(start_terms, max_terms, growth):
        tail = _general_f_tail(alpha, beta, gamma, n)
        chosen_n, chosen_tail = n, tail
        if tail is not None and tail <= requested:
            status = CERTIFIED
            break
    exact_sum = _sum_general_f(ag, bg, chosen_n)
    return _series_receipt(
        function="ramanujan_f",
        status=status,
        terms_used=chosen_n,
        requested=requested,
        tail=chosen_tail,
        value=exact_sum,
        input_payload={
            "a": _gr_receipt(ag), "b": _gr_receipt(bg), "ab": _gr_receipt(abg),
            "a_profile": _profile(ag), "b_profile": _profile(bg), "ab_profile": _profile(abg),
            "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS",
        },
        proof_formula="two-sided f tails use alpha>=|a|, beta>=|b|, gamma>=|ab|<1 independently; ratios <=alpha*gamma^m and beta*gamma^m",
    )


def _product_receipt(
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
        "requested_abs_error": _fraction_receipt(requested),
        "input": input_payload,
        "proof_formula": proof_formula,
        "exact_arithmetic": "GAUSSIAN_RATIONAL_Q_I",
        "bound_geometry": BOUND_GEOMETRY,
        "certified_object": "EXACT_GAUSSIAN_RATIONAL_FINITE_PRODUCT_PLUS_RATIONAL_COMPLEX_TAIL_BOUND",
        "estimate_is_certified": False,
        "authority": _authority(),
        "laws": [
            "COMPLEX_FINITE_PRODUCT_NE_INFINITE_PRODUCT_WITHOUT_TAIL_BOUND",
            "SQUARED_MODULUS_OF_GAUSSIAN_RATIONAL_IS_EXACT_RATIONAL",
            "AMGM_RATIONAL_MAJORANT_GE_COMPLEX_MODULUS",
            "EXACT_OPEN_UNIT_DISK_REPLACES_L1_DIAMOND_AS_PROOF_DOMAIN",
            "CERTIFIED_ERROR_BOUND_NE_RUNTIME_AUTHORITY",
        ],
    }
    if partial is not None:
        out["partial_product"] = _gr_receipt(partial)
        z = partial.to_complex()
        out["estimate"] = [z.real, z.imag]
    if error is not None:
        out["absolute_error_bound"] = _fraction_receipt(error)
        out["absolute_error_bound_decimal"] = f"{float(error):.17e}"
        out["error_bound_le_requested"] = error <= requested
    if tail_payload is not None:
        out["tail_majorants"] = {k: _fraction_receipt(v) for k, v in tail_payload.items()}
    return out


def _choose_product(
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


def certify_complex_phi_product_disk(*, q: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    qg = _gr(q, "q")
    s = exact_squared_modulus(qg)
    rho = selected_modulus_majorant(qg)
    requested = _tol(abs_error)
    if s >= 1:
        return _product_receipt(function="phi_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"q": _gr_receipt(qg), "majorant_profile": _profile(qg)}, proof_formula="requires exact |q|^2<1", tail_payload=None)

    def evaluate(n: int):
        plus, even = ONE, ONE
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

    status, n, partial, error, tails = _choose_product(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _product_receipt(function="phi_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"q": _gr_receipt(qg), "majorant_profile": _profile(qg), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="tail factors use exact rational rho>=|q|; if combined S<1 then |T-1|<=S/(1-S)", tail_payload=tails)


def certify_complex_psi_product_disk(*, q: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    qg = _gr(q, "q")
    s = exact_squared_modulus(qg)
    rho = selected_modulus_majorant(qg)
    requested = _tol(abs_error)
    if s >= 1:
        return _product_receipt(function="psi_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"q": _gr_receipt(qg), "majorant_profile": _profile(qg)}, proof_formula="requires exact |q|^2<1", tail_payload=None)

    def evaluate(n: int):
        even, odd = ONE, ONE
        for k in range(n):
            even = even * (ONE - qg ** (2 * k + 2))
            odd = odd * (ONE - qg ** (2 * k + 1))
        partial = even / odd
        den = 1 - rho * rho
        se = rho ** (2 * n + 2) / den
        so = rho ** (2 * n + 1) / den
        if se >= 1 or so >= 1:
            error = None
        else:
            de = se / (1 - se)
            do = so / (1 - so)
            ratio_deviation = (de + do) / (1 - so)
            error = partial.l1() * ratio_deviation
        return partial, error, {"even_tail_sum": se, "odd_tail_sum": so}

    status, n, partial, error, tails = _choose_product(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _product_receipt(function="psi_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"q": _gr_receipt(qg), "majorant_profile": _profile(qg), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="tail ratio E/O is bounded with exact rho>=|q| and |O|>=1-S_odd", tail_payload=tails)


def certify_complex_ramanujan_f_product_disk(*, a: Any, b: Any, abs_error: Any = "1e-12", start_terms: int = 4, max_terms: int = MAX_TERMS, growth: float = 1.5) -> dict[str, Any]:
    ag, bg = _gr(a, "a"), _gr(b, "b")
    abg = ag * bg
    alpha = selected_modulus_majorant(ag)
    beta = selected_modulus_majorant(bg)
    gamma = selected_modulus_majorant(abg)
    s_ab = exact_squared_modulus(abg)
    requested = _tol(abs_error)
    if s_ab >= 1:
        return _product_receipt(function="ramanujan_f_product", status=OUTSIDE_BOUND_DOMAIN, n=0, requested=requested, partial=None, error=None, input_payload={"a": _gr_receipt(ag), "b": _gr_receipt(bg), "ab": _gr_receipt(abg), "ab_profile": _profile(abg)}, proof_formula="triple product requires exact |a*b|^2<1", tail_payload=None)

    def evaluate(n: int):
        pa, pb, ps = ONE, ONE, ONE
        for k in range(n):
            sk = abg ** k
            pa = pa * (ONE + ag * sk)
            pb = pb * (ONE + bg * sk)
            ps = ps * (ONE - abg ** (k + 1))
        partial = pa * pb * ps
        den = 1 - gamma
        sa = alpha * gamma ** n / den
        sb = beta * gamma ** n / den
        ss = gamma ** (n + 1) / den
        total = sa + sb + ss
        error = None if total >= 1 else partial.l1() * total / (1 - total)
        return partial, error, {"a_plus_tail_sum": sa, "b_plus_tail_sum": sb, "ab_minus_tail_sum": ss, "combined_tail_sum": total}

    status, n, partial, error, tails = _choose_product(evaluate, requested=requested, start_terms=start_terms, max_terms=max_terms, growth=growth)
    return _product_receipt(function="ramanujan_f_product", status=status, n=n, requested=requested, partial=partial, error=error, input_payload={"a": _gr_receipt(ag), "b": _gr_receipt(bg), "ab": _gr_receipt(abg), "a_profile": _profile(ag), "b_profile": _profile(bg), "ab_profile": _profile(abg), "interpretation": "EXACT_GAUSSIAN_RATIONAL_COMPONENTS"}, proof_formula="omitted (-a;ab),(-b;ab),(ab;ab) factors use independent alpha>=|a|, beta>=|b|, gamma>=|ab|<1", tail_payload=tails)
