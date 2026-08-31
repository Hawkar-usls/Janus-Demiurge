#!/usr/bin/env python3
"""TRUMP OPEN-only Slime swarm ecology R3.

Canonical C025 always runs first.  The pinned v3 16-front source-only swarm is
loaded only when canonical returns OPEN.  A challenger changes pivot proposal
order only; the exact pivot set, cap, elimination, transition replay,
certificates, macro semantics and witness recovery remain unchanged.

No front is a champion.  Fronts run in the frozen donor manifest order.  The
first SAT/UNSAT challenger must reproduce byte-identically from the original
CNF before it may stop the ecology.  P_VS_NP remains OPEN.
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

from looking_for_something_policy import paid_work
from trump_candidate import (
    TrumpCandidateError,
    canonical_bytes,
    fetch_source_bytes,
    import_candidate_module,
    load_manifest,
    primary_source,
)
from verify_slime_v3_donor_r0 import git_blob_sha

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_OPEN_ONLY_SWARM_R3_FROZEN_BENCH_V1.json"
DONOR_MANIFEST_PATH = HERE / "TRUMP_SLIME_V3_AMORTIZED_DONOR_R0.json"


class OpenOnlySwarmError(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_OPEN_ONLY_SWARM_R3_FROZEN_C1K0_BENCH_V1":
        raise OpenOnlySwarmError("FROZEN_SPEC_ID_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise OpenOnlySwarmError("WINNER_PREREGISTRATION_FORBIDDEN")
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
        raise OpenOnlySwarmError("PINNED_SOLVER_DRIFT")
    data = fetch_source_bytes(source)
    return import_candidate_module(data, source), source


def _fetch_verified(url: str, expected_blob: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "JANUS-TRUMP-SLIME-R3/1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    actual = git_blob_sha(data)
    if actual != expected_blob:
        raise OpenOnlySwarmError(f"DONOR_BLOB_MISMATCH:{actual}:{expected_blob}")
    return data


def _import_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise OpenOnlySwarmError(f"IMPORT_SPEC_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_pinned_v3_donor() -> tuple[ModuleType, dict[str, Any]]:
    donor_manifest = json.loads(DONOR_MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen = load_frozen_spec()["donor"]
    if donor_manifest.get("pinned_commit") != frozen.get("commit"):
        raise OpenOnlySwarmError("DONOR_COMMIT_DRIFT")
    files = donor_manifest.get("files") or []
    expected_v3 = frozen.get("v3_git_blob_sha")
    if not any(x.get("path") == frozen.get("v3_path") and x.get("git_blob_sha") == expected_v3 for x in files):
        raise OpenOnlySwarmError("DONOR_V3_BLOB_DRIFT")

    owner, repo = str(donor_manifest["repository"]).split("/", 1)
    commit = str(donor_manifest["pinned_commit"])
    with tempfile.TemporaryDirectory(prefix="janus-slime-r3-") as td:
        root = Path(td)
        written: dict[str, Path] = {}
        for item in files:
            rel = str(item["path"])
            data = _fetch_verified(
                f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{rel}",
                str(item["git_blob_sha"]),
            )
            target = root / Path(rel).name
            target.write_bytes(data)
            written[target.name] = target
        old_path = list(sys.path)
        sys.path.insert(0, str(root))
        try:
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
    return v3, donor_manifest


def generate_fronts(clauses: Sequence[Sequence[int]], donor_module: ModuleType) -> dict[str, Any]:
    manifest = donor_module.SlimeSemanticCandidateSwarmV3Amortized().generate_manifest(clauses)
    if len(manifest.candidates) != 16:
        raise OpenOnlySwarmError(f"EXPECTED_16_FRONTS_GOT:{len(manifest.candidates)}")
    root_vars = {abs(int(lit)) for clause in clauses for lit in clause}
    fronts = []
    projection_ops = 0
    for candidate in manifest.candidates:
        priority = []
        projection_ops += len(candidate.linear_leaf_order)
        for leaf in candidate.linear_leaf_order:
            text = str(leaf)
            if not text.startswith("v:"):
                continue
            priority.append(int(text.split(":", 1)[1]))
        if len(priority) != len(root_vars) or len(set(priority)) != len(priority) or set(priority) != root_vars:
            raise OpenOnlySwarmError(f"FRONT_NOT_ROOT_PERMUTATION:{candidate.name}")
        fronts.append({
            "name": str(candidate.name),
            "pivot_priority": tuple(priority),
            "candidate_charged_ops": int(candidate.charged_ops),
        })
    return {
        "artifact_id": manifest.artifact_id,
        "source_sha256": manifest.source_sha256,
        "fronts": fronts,
        "slime_generation_ops": int(manifest.total_generation_ops),
        "pivot_projection_ops": int(projection_ops),
    }


@contextmanager
def pivot_priority_patch(solver_module: ModuleType, priority: Sequence[int]) -> Iterator[dict[str, int]]:
    original = solver_module.canonical_pivot_order
    frozen = tuple(int(v) for v in priority)
    if len(set(frozen)) != len(frozen):
        raise OpenOnlySwarmError("DUPLICATE_PRIORITY")
    telemetry = {"pivot_order_calls": 0, "pivot_order_reorders": 0}

    def proposed(state, cnf=None):
        canonical = list(original(state, cnf))
        allowed = set(canonical)
        preferred = [v for v in frozen if v in allowed]
        preferred_set = set(preferred)
        ordered = preferred + [v for v in canonical if v not in preferred_set]
        if len(ordered) != len(canonical) or set(ordered) != allowed:
            raise AssertionError("PIVOT_SET_CHANGED")
        telemetry["pivot_order_calls"] += 1
        if ordered != canonical:
            telemetry["pivot_order_reorders"] += 1
        return ordered

    solver_module.canonical_pivot_order = proposed
    try:
        yield telemetry
    finally:
        solver_module.canonical_pivot_order = original


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


def _run_exact(solver_module: ModuleType, clauses, profile, priority=None):
    if priority is None:
        result = solver_module.solve_fail_closed(clauses, **profile)
        telemetry = {"pivot_order_calls": 0, "pivot_order_reorders": 0}
    else:
        with pivot_priority_patch(solver_module, priority) as telemetry:
            result = solver_module.solve_fail_closed(clauses, **profile)
        telemetry = dict(telemetry)
    if not _boundary_ok(result):
        raise TrumpCandidateError("R3_EXACT_BOUNDARY_VIOLATION")
    return result, telemetry


def _matching_replay(solver_module, clauses, profile, *, priority=None, expected=None):
    replay, telemetry = _run_exact(solver_module, clauses, profile, priority=priority)
    if canonical_bytes(replay) != canonical_bytes(expected):
        raise TrumpCandidateError("R3_DECISIVE_REPLAY_MISMATCH")
    return replay, telemetry


def solve_open_only_swarm(
    solver_module: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    donor_module: ModuleType | None = None,
    cap_exponent: int = 1,
    extension_exponent: int = 0,
    bounded_resolution_width: int = 3,
) -> dict[str, Any]:
    profile = {
        "cap_exponent": int(cap_exponent),
        "extension_exponent": int(extension_exponent),
        "bounded_resolution_width": int(bounded_resolution_width),
    }
    canonical, _ = _run_exact(solver_module, clauses, profile)
    baseline_work = paid_work(canonical)
    replay_work = 0
    challenger_work = 0
    attempts = []

    if canonical["status"] in {"SAT", "UNSAT"}:
        replay, _ = _matching_replay(solver_module, clauses, profile, expected=canonical)
        replay_work += paid_work(replay)
        return {
            "schema": "janus.trump.slime_open_only_swarm_r3.run.v1",
            "baseline": canonical,
            "final_result": canonical,
            "winner": "CANONICAL",
            "donor_generated": False,
            "fronts_attempted": 0,
            "front_attempts": [],
            "work": {
                "canonical_exact_paid_work": baseline_work,
                "challenger_exact_paid_work": 0,
                "replay_verification_work": replay_work,
                "slime_generation_ops": 0,
                "pivot_projection_ops": 0,
                "combined_ecology_work": baseline_work + replay_work,
            },
            "candidate_result_promoted": False,
            "same_theorem_face_learning": False,
            "scientific_boundary": {"P_VS_NP": "OPEN", "P_equals_NP_proved": False},
        }

    donor = donor_module
    if donor is None:
        donor, _ = load_pinned_v3_donor()
    generated = generate_fronts(clauses, donor)
    final_result = canonical
    winner = None
    for front in generated["fronts"]:
        first, telemetry = _run_exact(
            solver_module, clauses, profile, priority=front["pivot_priority"]
        )
        first_work = paid_work(first)
        challenger_work += first_work
        row = {
            "front_name": front["name"],
            "status": first["status"],
            "paid_work": first_work,
            "pivot_order_calls": telemetry["pivot_order_calls"],
            "pivot_order_reorders": telemetry["pivot_order_reorders"],
            "replay_match": False,
        }
        if first["status"] in {"SAT", "UNSAT"}:
            replay, _ = _matching_replay(
                solver_module,
                clauses,
                profile,
                priority=front["pivot_priority"],
                expected=first,
            )
            replay_work += paid_work(replay)
            row["replay_match"] = True
            attempts.append(row)
            final_result = first
            winner = front["name"]
            break
        attempts.append(row)

    generation_ops = int(generated["slime_generation_ops"])
    projection_ops = int(generated["pivot_projection_ops"])
    return {
        "schema": "janus.trump.slime_open_only_swarm_r3.run.v1",
        "baseline": canonical,
        "final_result": final_result,
        "winner": winner,
        "donor_generated": True,
        "fronts_attempted": len(attempts),
        "front_attempts": attempts,
        "work": {
            "canonical_exact_paid_work": baseline_work,
            "challenger_exact_paid_work": challenger_work,
            "replay_verification_work": replay_work,
            "slime_generation_ops": generation_ops,
            "pivot_projection_ops": projection_ops,
            "combined_ecology_work": baseline_work + challenger_work + replay_work + generation_ops + projection_ops,
        },
        "candidate_result_promoted": False,
        "same_theorem_face_learning": False,
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "coverage_boost_implies_speedup": False,
            "Slime_front_is_proof": False,
        },
    }


def selftest() -> dict[str, Any]:
    solver, _ = load_pinned_solver()
    donor, donor_manifest = load_pinned_v3_donor()
    # Contradictory units are a decisive canonical control: donor must not run.
    decisive = solve_open_only_swarm(solver, [[1], [-1]], donor_module=donor)
    assert decisive["final_result"]["status"] == "UNSAT"
    assert decisive["donor_generated"] is False
    assert decisive["fronts_attempted"] == 0
    # Directly verify frozen donor shape on a source formula.
    generated = generate_fronts([[1,2,3],[-1,2,4],[2,-3,5],[-2,4,5],[1,-4,6]], donor)
    assert len(generated["fronts"]) == 16
    return {
        "status": "PASS",
        "canonical_decisive_skips_donor": True,
        "front_count": len(generated["fronts"]),
        "donor_commit": donor_manifest["pinned_commit"],
        "P_VS_NP": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
