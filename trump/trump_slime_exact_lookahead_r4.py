#!/usr/bin/env python3
"""TRUMP Keymaster/Pivot-Slime exact-lookahead ecology R4.

R4 is an OPEN-rescue tissue, not a proof rule and not a replacement for a
canonical decisive result.  The outer ecology always runs the pinned canonical
C025 solver first.  Only canonical OPEN may restart from the original CNF under
this selector.

At every C025 `first_capped_elimination` request, R4:
  1. derives cheap current-residual structural features inspired by the frozen
     Keymaster pivot feature microscope;
  2. builds a diverse top-k shortlist (maximum four pivots);
  3. executes the unchanged exact capped elimination for every shortlisted
     pivot and independently verifies each successful transition;
  4. chooses only among already exact-verified transitions using frozen
     post-state criteria.

The live pivot set, formula semantics, cap, exact elimination implementation,
transition verifier, macro/certificate lanes and witness recovery are unchanged.
No same-theorem-face learning occurs.  P_VS_NP remains OPEN.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Sequence

from looking_for_something_policy import paid_work
from trump_candidate import (
    TrumpCandidateError,
    canonical_bytes,
    fetch_source_bytes,
    import_candidate_module,
    load_manifest,
    primary_source,
)

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_EXACT_LOOKAHEAD_R4_FROZEN_BENCH_V1.json"


class ExactLookaheadR4Error(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_EXACT_LOOKAHEAD_R4_FROZEN_C1K0_BENCH_V1":
        raise ExactLookaheadR4Error("FROZEN_SPEC_ID_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise ExactLookaheadR4Error("WINNER_PREREGISTRATION_FORBIDDEN")
    return spec


def load_pinned_solver() -> tuple[ModuleType, dict[str, Any]]:
    manifest = load_manifest()
    source = primary_source(manifest)
    expected = load_frozen_spec()["solver"]
    if (
        source.get("repository") != expected.get("repository")
        or source.get("pinned_commit") != expected.get("commit")
        or source.get("path") != expected.get("path")
        or source.get("git_blob_sha") != expected.get("git_blob_sha")
    ):
        raise ExactLookaheadR4Error("PINNED_SOLVER_DRIFT")
    data = fetch_source_bytes(source)
    return import_candidate_module(data, source), source


def _mean_width(rows: Sequence[Sequence[int]]) -> float:
    return sum(len(c) for c in rows) / max(1, len(rows))


def structural_feature_rows(
    solver_module: ModuleType,
    cnf,
    canonical_pivots: Sequence[int],
) -> tuple[list[dict[str, Any]], int]:
    """Frozen cheap Keymaster feature plane; no pair enumeration or SAT signal."""
    pivots = [int(v) for v in canonical_pivots]
    if len(set(pivots)) != len(pivots):
        raise ExactLookaheadR4Error("DUPLICATE_CANONICAL_PIVOT")
    canonical_index = {v: i for i, v in enumerate(pivots)}
    live = set(pivots)
    clause_scan_units = sum(1 + len(c) for c in cnf)
    literal_updates = sum(len(c) for c in cnf)

    rows: list[dict[str, Any]] = []
    for pivot in pivots:
        pos = [c for c in cnf if pivot in c]
        neg = [c for c in cnf if -pivot in c]
        retained = [c for c in cnf if pivot not in c and -pivot not in c]
        others = [v for v in pivots if v != pivot]
        p, q = len(pos), len(neg)
        pairs = p * q
        conflict_mass = 0
        aligned_mass = 0
        overlap_mass = 0
        for v in others:
            pp = sum(v in c for c in pos)
            pm = sum(-v in c for c in pos)
            np = sum(v in c for c in neg)
            nm = sum(-v in c for c in neg)
            conflict_mass += pp * nm + pm * np
            aligned_mass += pp * np + pm * nm
            overlap_mass += (pp + pm) * (np + nm)
        retained_units = solver_module.state_units(tuple(retained))
        rows.append({
            "var": pivot,
            "canonical_index": canonical_index[pivot],
            "degree_d": p + q,
            "positive_p": p,
            "negative_q": q,
            "balance_ratio": min(p, q) / max(1, max(p, q)),
            "parent_pairs": pairs,
            "positive_parent_mean_width": _mean_width(pos),
            "negative_parent_mean_width": _mean_width(neg),
            "parent_mean_width_sum": _mean_width(pos) + _mean_width(neg),
            "retained_clause_count": len(retained),
            "retained_units": retained_units,
            "single_conflict_mass_per_pair": conflict_mass / max(1, pairs),
            "same_sign_mass_per_pair": aligned_mass / max(1, pairs),
            "support_overlap_mass_per_pair": overlap_mass / max(1, pairs),
        })

    # Frozen accounting contract.  No claim that this is Python instruction
    # count; it is a conservative explicit resource charge for R4 comparison.
    feature_work = clause_scan_units + 4 * literal_updates + 20 * len(pivots)
    return rows, int(feature_work)


def _axis_value(row: dict[str, Any], axis: str) -> float:
    if axis == "parent_mean_width_sum":
        return float(row["positive_parent_mean_width"]) + float(row["negative_parent_mean_width"])
    return float(row[axis])


def _normalized_vectors(rows: list[dict[str, Any]]) -> dict[int, tuple[float, ...]]:
    axes = (
        "degree_d",
        "balance_ratio",
        "parent_pairs",
        "parent_mean_width_sum",
        "retained_units",
        "single_conflict_mass_per_pair",
        "same_sign_mass_per_pair",
        "support_overlap_mass_per_pair",
    )
    mins = {a: min(_axis_value(r, a) for r in rows) for a in axes}
    maxs = {a: max(_axis_value(r, a) for r in rows) for a in axes}
    out: dict[int, tuple[float, ...]] = {}
    for row in rows:
        values = []
        for axis in axes:
            lo, hi = mins[axis], maxs[axis]
            x = _axis_value(row, axis)
            values.append(0.0 if hi == lo else (x - lo) / (hi - lo))
        out[int(row["var"])] = tuple(values)
    return out


def build_shortlist(
    solver_module: ModuleType,
    cnf,
    canonical_pivots: Sequence[int],
) -> tuple[list[int], dict[str, Any]]:
    pivots = [int(v) for v in canonical_pivots]
    if not pivots:
        return [], {"feature_work": 0, "rows": [], "views": {}, "shortlist": []}
    rows, feature_work = structural_feature_rows(solver_module, cnf, pivots)
    by_var = {int(r["var"]): r for r in rows}

    canonical = pivots[0]
    low_pair = min(
        rows,
        key=lambda r: (
            int(r["parent_pairs"]),
            int(r["retained_units"]),
            float(r["parent_mean_width_sum"]),
            int(r["canonical_index"]),
        ),
    )["var"]
    conflict = max(
        rows,
        key=lambda r: (
            float(r["single_conflict_mass_per_pair"]),
            -int(r["parent_pairs"]),
            -int(r["canonical_index"]),
        ),
    )["var"]

    anchor = int(low_pair) if int(low_pair) != canonical else canonical
    vectors = _normalized_vectors(rows)
    av = vectors[anchor]
    diversity = max(
        rows,
        key=lambda r: (
            sum(abs(a - b) for a, b in zip(vectors[int(r["var"])], av)),
            -int(r["canonical_index"]),
        ),
    )["var"]

    ordered_views = [canonical, int(low_pair), int(conflict), int(diversity)]
    shortlist: list[int] = []
    for v in ordered_views:
        if v not in shortlist:
            shortlist.append(v)
    if len(shortlist) > 4:
        raise AssertionError("R4_SHORTLIST_BOUND_EXCEEDED")
    if any(v not in set(pivots) for v in shortlist):
        raise AssertionError("R4_SHORTLIST_EXPANDED_PIVOT_SET")
    return shortlist, {
        "feature_work": feature_work,
        "rows": rows,
        "views": {
            "canonical": canonical,
            "low_pair_risk": int(low_pair),
            "conflict_cancellation": int(conflict),
            "structural_diversity": int(diversity),
            "diversity_anchor": anchor,
        },
        "shortlist": shortlist,
    }


def _certificate_readiness_tier(out) -> int:
    if () in out or all(len(c) <= 2 for c in out):
        return 0
    return 1


@contextmanager
def exact_lookahead_patch(solver_module: ModuleType) -> Iterator[dict[str, Any]]:
    """Patch only the exact elimination selector; all transition primitives stay stock."""
    original = solver_module.first_capped_elimination
    telemetry: dict[str, Any] = {
        "shortlist_calls": 0,
        "feature_work": 0,
        "shortlist_size_sum": 0,
        "lookahead_candidates_attempted": 0,
        "verified_candidates": 0,
        "failed_cap_candidates": 0,
        "selected_noncanonical": 0,
        "selected_certificate_ready": 0,
        "roots_only_calls": 0,
    }

    def lookahead(state, cnf=None, roots_only=False):
        f = state.residual if cnf is None else cnf
        pivots = list(solver_module.canonical_pivot_order(state, f))
        if roots_only:
            rootset = set(state.root_vars)
            pivots = [v for v in pivots if v in rootset]
            telemetry["roots_only_calls"] += 1
        if not pivots:
            return None

        shortlist, detail = build_shortlist(solver_module, f, pivots)
        telemetry["shortlist_calls"] += 1
        telemetry["feature_work"] += int(detail["feature_work"])
        telemetry["shortlist_size_sum"] += len(shortlist)
        candidates = []
        canonical_index = {v: i for i, v in enumerate(pivots)}

        for var in shortlist:
            telemetry["lookahead_candidates_attempted"] += 1
            state.ledger.proposal_work += 1
            out, stats = solver_module.eliminate_var_capped(f, var, state.state_cap)
            pairs = int(stats.get("pairs", 0))
            state.ledger.elimination_pair_work += pairs
            state.ledger.certificate_discovery_work += 1 + pairs
            if out is None:
                telemetry["failed_cap_candidates"] += 1
                continue
            state.ledger.verification_work += 1 + pairs
            if not solver_module.verify_elimination_transition(f, var, out, state.state_cap):
                raise AssertionError("R4 exact elimination replay mismatch")
            telemetry["verified_candidates"] += 1
            candidates.append({
                "pivot": var,
                "out": out,
                "stats": stats,
                "selection": (
                    _certificate_readiness_tier(out),
                    int(state.progress_phi(out)),
                    int(solver_module.state_units(out)),
                    int(stats.get("raw_units", solver_module.state_units(out))),
                    pairs,
                    int(canonical_index[var]),
                ),
            })

        if not candidates:
            return None
        chosen = min(candidates, key=lambda x: x["selection"])
        if int(chosen["pivot"]) != int(pivots[0]):
            telemetry["selected_noncanonical"] += 1
        if chosen["selection"][0] == 0:
            telemetry["selected_certificate_ready"] += 1
        return int(chosen["pivot"]), chosen["out"], chosen["stats"]

    solver_module.first_capped_elimination = lookahead
    try:
        yield telemetry
    finally:
        solver_module.first_capped_elimination = original


def _boundary_ok(result: dict[str, Any]) -> bool:
    sb = result.get("scientific_boundary") or {}
    return (
        result.get("status") in {"SAT", "UNSAT", "OPEN"}
        and sb.get("P_VS_NP") == "OPEN"
        and sb.get("claims_p_eq_np") is False
        and sb.get("claims_p_neq_np") is False
        and sb.get("heuristic_promotion") is False
        and sb.get("general_sat_oracle") is False
        and sb.get("semantic_equivalence_oracle") is False
    )


def solve_r4_fallback(
    solver_module: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    cap_exponent: int = 1,
    extension_exponent: int = 0,
    bounded_resolution_width: int = 3,
) -> dict[str, Any]:
    with exact_lookahead_patch(solver_module) as telemetry:
        result = solver_module.solve_fail_closed(
            clauses,
            cap_exponent=cap_exponent,
            extension_exponent=extension_exponent,
            bounded_resolution_width=bounded_resolution_width,
        )
    if not _boundary_ok(result):
        raise TrumpCandidateError("R4_EXACT_RESULT_BOUNDARY_VIOLATION")
    return {
        "schema": "janus.trump.slime_exact_lookahead_r4.fallback.v1",
        "exact_result": result,
        "telemetry": dict(telemetry),
        "exact_paid_work": paid_work(result),
        "feature_work": int(telemetry["feature_work"]),
        "combined_fallback_work": paid_work(result) + int(telemetry["feature_work"]),
        "candidate_result_promoted": False,
        "same_theorem_face_learning": False,
        "authority": {
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False,
        },
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "exact_one_step_best_is_global_optimum": False,
        },
    }


def solve_canonical_then_r4(
    solver_module: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    cap_exponent: int = 1,
    extension_exponent: int = 0,
    bounded_resolution_width: int = 3,
) -> dict[str, Any]:
    profile = {
        "cap_exponent": int(cap_exponent),
        "extension_exponent": int(extension_exponent),
        "bounded_resolution_width": int(bounded_resolution_width),
    }
    canonical = solver_module.solve_fail_closed(clauses, **profile)
    if not _boundary_ok(canonical):
        raise TrumpCandidateError("R4_CANONICAL_BOUNDARY_VIOLATION")
    canonical_work = paid_work(canonical)
    if canonical["status"] in {"SAT", "UNSAT"}:
        replay = solver_module.solve_fail_closed(clauses, **profile)
        if canonical_bytes(canonical) != canonical_bytes(replay):
            raise TrumpCandidateError("R4_CANONICAL_DECISIVE_REPLAY_MISMATCH")
        return {
            "schema": "janus.trump.slime_exact_lookahead_r4.ecology.v1",
            "baseline": canonical,
            "final_result": canonical,
            "winner": "CANONICAL",
            "r4_invoked": False,
            "canonical_exact_paid_work": canonical_work,
            "canonical_replay_work": paid_work(replay),
            "r4": None,
            "candidate_result_promoted": False,
            "scientific_boundary": {"P_VS_NP": "OPEN", "P_equals_NP_proved": False},
        }

    first = solve_r4_fallback(solver_module, clauses, **profile)
    second = solve_r4_fallback(solver_module, clauses, **profile)
    if canonical_bytes(first["exact_result"]) != canonical_bytes(second["exact_result"]):
        raise TrumpCandidateError("R4_FALLBACK_EXACT_REPLAY_MISMATCH")
    if first["telemetry"] != second["telemetry"]:
        raise TrumpCandidateError("R4_FALLBACK_TELEMETRY_REPLAY_MISMATCH")
    final = first["exact_result"]
    return {
        "schema": "janus.trump.slime_exact_lookahead_r4.ecology.v1",
        "baseline": canonical,
        "final_result": final,
        "winner": "R4" if final["status"] in {"SAT", "UNSAT"} else None,
        "r4_invoked": True,
        "canonical_exact_paid_work": canonical_work,
        "canonical_replay_work": 0,
        "r4": first,
        "r4_replay_verification_work": second["combined_fallback_work"],
        "candidate_result_promoted": False,
        "same_theorem_face_learning": False,
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "coverage_boost_implies_speedup": False,
        },
    }


def selftest() -> dict[str, Any]:
    solver, _ = load_pinned_solver()
    formula = [[1,2,3],[-1,2,4],[1,-3,4],[-2,-3,5],[2,3,-5],[-1,4,5]]
    root = solver.canon_cnf(formula)
    pivots = solver.vars_of(root)
    shortlist, detail = build_shortlist(solver, root, pivots)
    assert shortlist and shortlist[0] == pivots[0]
    assert len(shortlist) <= 4 and set(shortlist) <= set(pivots)
    # Check every successful shortlisted transition is independently replayable.
    verified = 0
    cap = max(10**6, solver.state_units(root) ** 2)
    for pivot in shortlist:
        out, _ = solver.eliminate_var_capped(root, pivot, cap)
        if out is not None:
            assert solver.verify_elimination_transition(root, pivot, out, cap)
            verified += 1
    decisive = solve_canonical_then_r4(solver, [[1],[-1]])
    assert decisive["winner"] == "CANONICAL" and decisive["r4_invoked"] is False
    return {
        "status": "PASS",
        "shortlist_size": len(shortlist),
        "verified_shortlist_transitions": verified,
        "feature_work": detail["feature_work"],
        "canonical_decisive_skips_R4": True,
        "P_VS_NP": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
