#!/usr/bin/env python3
"""Proof-carrying Slime -> C025 pivot-order adapter R1.

The adapter changes proposal order only.  It does not change the pivot set,
CNF semantics, cap, exact elimination, transition replay, certificate lanes,
macro semantics, witness recovery, or theorem boundary.

A pinned Slime v3 manifest is generated once from the root CNF.  Each candidate
leaf order is projected to its `v:<id>` subsequence and used only as a stable
priority over currently-live variables.  Any extension variables absent from
that root priority remain in the solver's original canonical order.

P_VS_NP remains OPEN.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import Any, Iterator, Sequence
import urllib.request

from trump_candidate import (
    TrumpCandidateError,
    fetch_source_bytes,
    import_candidate_module,
    load_manifest,
    primary_source,
)
from verify_slime_v3_donor_r0 import git_blob_sha

HERE = Path(__file__).resolve().parent
DONOR_MANIFEST = HERE / "TRUMP_SLIME_V3_AMORTIZED_DONOR_R0.json"


class SlimePivotAdapterError(RuntimeError):
    pass


def _fetch_verified(url: str, expected_blob_sha: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "JANUS-TRUMP-SLIME-PIVOT-R1/1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    actual = git_blob_sha(data)
    if actual != expected_blob_sha:
        raise SlimePivotAdapterError(f"PINNED_BLOB_MISMATCH:{actual}:{expected_blob_sha}")
    return data


def _import_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SlimePivotAdapterError(f"IMPORT_SPEC_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_pinned_solver() -> tuple[ModuleType, dict[str, Any]]:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    module = import_candidate_module(data, source)
    return module, source


def load_pinned_v3_donor() -> tuple[ModuleType, dict[str, Any]]:
    manifest = json.loads(DONOR_MANIFEST.read_text(encoding="utf-8"))
    repo = str(manifest["repository"])
    owner, name = repo.split("/", 1)
    commit = str(manifest["pinned_commit"])
    files = manifest["files"]
    if not isinstance(files, list) or len(files) < 3:
        raise SlimePivotAdapterError("DONOR_FILE_MANIFEST_INVALID")

    with tempfile.TemporaryDirectory(prefix="janus-slime-pivot-r1-") as td:
        root = Path(td)
        written: dict[str, Path] = {}
        for item in files:
            rel = str(item["path"])
            expected = str(item["git_blob_sha"])
            url = f"https://raw.githubusercontent.com/{owner}/{name}/{commit}/{rel}"
            data = _fetch_verified(url, expected)
            target = root / Path(rel).name
            target.write_bytes(data)
            written[target.name] = target

        old_path = list(sys.path)
        sys.path.insert(0, str(root))
        try:
            # Clear only the exact frozen donor module names so a prior import
            # cannot silently satisfy this load with a different body.
            for module_name in (
                "slime_semantic_candidate_router",
                "slime_semantic_candidate_swarm_v2",
                "slime_semantic_candidate_swarm_v3_amortized",
            ):
                sys.modules.pop(module_name, None)
            _import_path("slime_semantic_candidate_router", written["slime_semantic_candidate_router.py"])
            _import_path("slime_semantic_candidate_swarm_v2", written["slime_semantic_candidate_swarm_v2.py"])
            v3 = _import_path(
                "slime_semantic_candidate_swarm_v3_amortized",
                written["slime_semantic_candidate_swarm_v3_amortized.py"],
            )
        finally:
            sys.path[:] = old_path
    return v3, manifest


def generate_root_pivot_priorities(
    clauses: Sequence[Sequence[int]],
    *,
    donor_module: ModuleType,
) -> dict[str, Any]:
    engine = donor_module.SlimeSemanticCandidateSwarmV3Amortized()
    manifest = engine.generate_manifest(clauses)
    priorities: dict[str, tuple[int, ...]] = {}
    root_vars = sorted({abs(int(lit)) for clause in clauses for lit in clause})
    root_set = set(root_vars)

    for candidate in manifest.candidates:
        order: list[int] = []
        for leaf in candidate.linear_leaf_order:
            text = str(leaf)
            if not text.startswith("v:"):
                continue
            try:
                var = int(text.split(":", 1)[1])
            except ValueError as exc:
                raise SlimePivotAdapterError(f"INVALID_VARIABLE_LEAF:{text}") from exc
            order.append(var)
        if len(order) != len(root_vars) or len(set(order)) != len(order) or set(order) != root_set:
            raise SlimePivotAdapterError(f"PIVOT_PRIORITY_NOT_ROOT_PERMUTATION:{candidate.name}")
        priorities[str(candidate.name)] = tuple(order)

    if len(priorities) != 16:
        raise SlimePivotAdapterError(f"EXPECTED_16_FRONTS_GOT:{len(priorities)}")
    return {
        "artifact_id": manifest.artifact_id,
        "source_sha256": manifest.source_sha256,
        "front_count": len(priorities),
        "priorities": priorities,
        "slime_generation_ops": int(manifest.total_generation_ops),
        "feature_certificate": manifest.feature_certificate,
    }


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


@contextmanager
def pivot_priority_patch(
    solver_module: ModuleType,
    priority: Sequence[int],
) -> Iterator[dict[str, int]]:
    """Temporarily replace only canonical pivot ordering, preserving its set."""
    original = solver_module.canonical_pivot_order
    calls = {"pivot_order_calls": 0, "pivot_order_reorders": 0}
    frozen_priority = tuple(int(v) for v in priority)
    if len(set(frozen_priority)) != len(frozen_priority):
        raise SlimePivotAdapterError("DUPLICATE_PIVOT_PRIORITY")

    def proposed(state, cnf=None):
        canonical = list(original(state, cnf))
        canonical_set = set(canonical)
        preferred = [v for v in frozen_priority if v in canonical_set]
        preferred_set = set(preferred)
        ordered = preferred + [v for v in canonical if v not in preferred_set]
        if len(ordered) != len(canonical) or set(ordered) != canonical_set:
            raise AssertionError("PIVOT_SET_CHANGED")
        calls["pivot_order_calls"] += 1
        if ordered != canonical:
            calls["pivot_order_reorders"] += 1
        return ordered

    solver_module.canonical_pivot_order = proposed
    try:
        yield calls
    finally:
        solver_module.canonical_pivot_order = original


def solve_with_front(
    solver_module: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    front_name: str,
    pivot_priority: Sequence[int],
    cap_exponent: int,
    extension_exponent: int,
    bounded_resolution_width: int,
) -> dict[str, Any]:
    with pivot_priority_patch(solver_module, pivot_priority) as patch_stats:
        result = solver_module.solve_fail_closed(
            clauses,
            cap_exponent=cap_exponent,
            extension_exponent=extension_exponent,
            bounded_resolution_width=bounded_resolution_width,
        )
    if not _boundary_ok(result):
        raise TrumpCandidateError("SLIME_PIVOT_R1_EXACT_RESULT_BOUNDARY_VIOLATION")
    return {
        "schema": "janus.trump.slime_pivot_r1.run.v1",
        "front_name": front_name,
        "pivot_priority": list(pivot_priority),
        "pivot_adapter": {
            "proposal_only": True,
            "pivot_set_changed": False,
            **patch_stats,
        },
        "exact_result": result,
        "authority": {
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False,
        },
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "Slime_order_is_proof": False,
        },
    }


def solve_canonical(
    solver_module: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    cap_exponent: int,
    extension_exponent: int,
    bounded_resolution_width: int,
) -> dict[str, Any]:
    result = solver_module.solve_fail_closed(
        clauses,
        cap_exponent=cap_exponent,
        extension_exponent=extension_exponent,
        bounded_resolution_width=bounded_resolution_width,
    )
    if not _boundary_ok(result):
        raise TrumpCandidateError("CANONICAL_EXACT_RESULT_BOUNDARY_VIOLATION")
    return result


def selftest() -> dict[str, Any]:
    solver, _ = load_pinned_solver()
    donor, donor_manifest = load_pinned_v3_donor()
    formula = [[1, 2, 3], [-1, 2, 4], [2, -3, 5], [-2, 4, 5], [1, -4, 6]]
    generated = generate_root_pivot_priorities(formula, donor_module=donor)
    assert generated["front_count"] == 16
    root = set(range(1, 7))
    assert all(set(order) == root for order in generated["priorities"].values())
    front = sorted(generated["priorities"])[0]
    run = solve_with_front(
        solver,
        formula,
        front_name=front,
        pivot_priority=generated["priorities"][front],
        cap_exponent=1,
        extension_exponent=0,
        bounded_resolution_width=3,
    )
    assert run["exact_result"]["status"] in {"SAT", "UNSAT", "OPEN"}
    assert run["pivot_adapter"]["pivot_set_changed"] is False
    return {
        "status": "PASS",
        "front_count": generated["front_count"],
        "donor_commit": donor_manifest["pinned_commit"],
        "solver_status": run["exact_result"]["status"],
        "P_VS_NP": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
