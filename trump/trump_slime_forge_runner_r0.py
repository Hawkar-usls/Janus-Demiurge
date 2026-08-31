#!/usr/bin/env python3
"""Bounded TRUMP runner using TRUMP_SLIME_FORGE_R0 advice.

R0 never mutates the declared C/K profile set. It only chooses an execution
order from memory that existed before this theorem face. A decisive SAT/UNSAT
candidate is accepted for early stop only after deterministic exact replay of
that same profile. OPEN continues to the next declared profile and is never
converted into negative evidence.

Learning is a separate CLI command over the finalized sealed receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from looking_for_something_policy import DEFAULT_PROFILES, paid_work
from trump_candidate import (
    TrumpCandidateError,
    base_receipt,
    canonical_bytes,
    fetch_source_bytes,
    import_candidate_module,
    load_manifest,
    primary_source,
    seal_receipt,
)
from trump_slime_forge_r0 import SlimeForgeMemory, source_identity


def _real_boundary(result: dict[str, Any]) -> bool:
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


def _validate_result(result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or not _real_boundary(result):
        raise TrumpCandidateError("TRUMP_SLIME_FORGE_RESULT_BOUNDARY_VIOLATION")


def execute_order(
    clauses: list,
    *,
    ordered_profiles: list[dict[str, Any]],
    solve: Callable[..., dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, bool]:
    """Execute all OPEN profiles, but stop after replay-confirmed decisive result."""
    attempts: list[dict[str, Any]] = []
    final_status = "OPEN"
    decisive_stop = False
    for profile in ordered_profiles:
        c = int(profile["cap_exponent"])
        k = int(profile["extension_exponent"])
        result = solve(clauses, cap_exponent=c, extension_exponent=k)
        _validate_result(result)
        status = str(result["status"])
        replay_match = False
        replay_digest = None
        if status in {"SAT", "UNSAT"}:
            replay = solve(clauses, cap_exponent=c, extension_exponent=k)
            _validate_result(replay)
            replay_match = canonical_bytes(result) == canonical_bytes(replay)
            replay_digest = hashlib.sha256(canonical_bytes(replay)).hexdigest()
            if not replay_match:
                raise TrumpCandidateError("TRUMP_SLIME_FORGE_DECISIVE_REPLAY_MISMATCH")
            final_status = status
            decisive_stop = True

        attempts.append({
            "profile": {"cap_exponent": c, "extension_exponent": k},
            "result": result,
            "paid_work": paid_work(result),
            "real_boundary": True,
            "replay_match": replay_match,
            "replay_digest": replay_digest,
        })
        if decisive_stop:
            break
    return attempts, final_status, decisive_stop


def run_forge(
    clauses: list,
    *,
    memory: SlimeForgeMemory | None = None,
    profiles: tuple[dict, ...] = DEFAULT_PROFILES,
) -> dict[str, Any]:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    module = import_candidate_module(data, source)
    mem = memory or SlimeForgeMemory()

    # Snapshot-before-run law: advice is computed from already-finalized history.
    sid = source_identity(source)
    advice = mem.rank_profiles(profiles, source_identity=sid)
    ordered = advice["ordered_profiles"]
    attempts, final_status, decisive_stop = execute_order(
        clauses, ordered_profiles=ordered, solve=module.solve_fail_closed
    )

    receipt = base_receipt(manifest, source)
    receipt.update({
        "terminal": "TRUMP_SLIME_FORGE_BOUNDED_SOLVE_COMPLETE",
        "operation": "SLIME_FORGE_REORDERED_DECLARED_PROFILE_SEARCH_WITH_REPLAY_DECISIVE_STOP",
        "source_loaded": True,
        "execution_performed": True,
        "candidate_result_promoted": False,
        "input_digest": hashlib.sha256(canonical_bytes(clauses)).hexdigest(),
        "slime_advice": advice,
        "attempts": attempts,
        "attempted_profile_count": len(attempts),
        "declared_profile_count": len(ordered),
        "profiles_not_executed_after_exact_decisive_stop": max(0, len(ordered) - len(attempts)),
        "decisive_stop": decisive_stop,
        "final_candidate_status": final_status,
        "learning_performed_in_this_theorem_face": False,
        "counterfactual_work_savings_claimed": False,
        "scientific_claim": "NONE",
    })
    return seal_receipt(receipt)


def _read_json(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(__import__("sys").stdin)


def main() -> int:
    ap = argparse.ArgumentParser(description="TRUMP Slime Forge R0")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("solve")
    s.add_argument("--input", help="CNF JSON, default stdin")
    s.add_argument("--memory", help="existing Slime Forge state; read-only during solve")
    l = sub.add_parser("learn")
    l.add_argument("--receipt", required=True, help="finalized sealed TRUMP receipt JSON")
    l.add_argument("--memory", required=True, help="state JSON to append/update")
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.command == "selftest":
        from trump_slime_forge_r0 import selftest
        selftest()
        out = {"status": "PASS", "component": "TRUMP_SLIME_FORGE_R0", "P_VS_NP": "OPEN"}
    elif args.command == "solve":
        clauses = _read_json(args.input)
        if not isinstance(clauses, list):
            raise TrumpCandidateError("TRUMP_INPUT_MUST_BE_CNF_ARRAY")
        memory = SlimeForgeMemory.load(args.memory) if args.memory else SlimeForgeMemory()
        out = run_forge(clauses, memory=memory)
    elif args.command == "learn":
        receipt = _read_json(args.receipt)
        memory = SlimeForgeMemory.load(args.memory)
        learned = memory.learn_finalized_receipt(receipt)
        memory.save(args.memory)
        out = {
            "status": learned["status"],
            "receipt_hash": learned["receipt_hash"],
            "memory_state_hash": memory.snapshot()["state_hash"],
            "P_VS_NP": "OPEN",
        }
    else:
        raise AssertionError(args.command)

    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
