#!/usr/bin/env python3
"""Run the LOOKING FOR SOMETHING policy over the admitted TRUMP candidate.

This is an outer, bounded portfolio experiment. It never changes CNF semantics,
never treats a ranking score as proof, and preserves the TRUMP scientific
boundary. The underlying exact candidate is still loaded from its pinned
Fundamentum commit/blob through trump_candidate.py.

The optional Pyramidal Genesis-Return face treats fixed-profile runs as released
candidate children. Returned observations can shape a next advisory seed only
when their result boundary is valid and an exact replay matches. This remains a
search/regeneration mechanism, never theorem promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from looking_for_something_policy import (
    DEFAULT_PROFILES,
    evaluate_portfolio,
    selftest as policy_selftest,
)
from pyramidal_genesis_return import (
    apply as pyramidal_regenerate,
    selftest as pyramidal_selftest,
)
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


def _validate_candidate_result(result: dict) -> None:
    sb = result.get("scientific_boundary", {})
    if (
        result.get("status") not in {"SAT", "UNSAT", "OPEN"}
        or sb.get("P_VS_NP") != "OPEN"
        or sb.get("claims_p_eq_np") is not False
        or sb.get("claims_p_neq_np") is not False
    ):
        raise TrumpCandidateError("LOOKING_POLICY_SCIENTIFIC_BOUNDARY_VIOLATION")


def _pyramidal_children(candidates: list[dict]) -> list[dict]:
    """Translate exact portfolio receipts into bounded child observations."""
    children = []
    for candidate in candidates:
        profile = candidate["profile"]
        result = candidate["result"]
        c = int(profile["cap_exponent"])
        k = int(profile["extension_exponent"])
        children.append(
            {
                "child_id": f"C{c}_K{k}",
                "observation": {
                    "profile": {"cap_exponent": c, "extension_exponent": k},
                    "result_digest": hashlib.sha256(canonical_bytes(result)).hexdigest(),
                    "status": result.get("status"),
                    "reason": result.get("reason"),
                    "residual_units": result.get("residual_units"),
                },
                "verified": True,
                "replay_match": candidate.get("replay_match") is True,
            }
        )
    return children


def run_portfolio(
    clauses: list,
    *,
    profiles: tuple[dict, ...] = DEFAULT_PROFILES,
    replay: bool = False,
) -> dict:
    manifest = load_manifest()
    source = primary_source(manifest)
    data = fetch_source_bytes(source)
    module = import_candidate_module(data, source)

    candidates = []
    for profile in profiles:
        c = int(profile["cap_exponent"])
        k = int(profile["extension_exponent"])
        result = module.solve_fail_closed(
            clauses,
            cap_exponent=c,
            extension_exponent=k,
        )
        _validate_candidate_result(result)

        replay_match = False
        replay_digest = None
        if replay:
            second = module.solve_fail_closed(
                clauses,
                cap_exponent=c,
                extension_exponent=k,
            )
            _validate_candidate_result(second)
            replay_match = canonical_bytes(result) == canonical_bytes(second)
            replay_digest = hashlib.sha256(canonical_bytes(second)).hexdigest()

        candidates.append(
            {
                "profile": {
                    "cap_exponent": c,
                    "extension_exponent": k,
                },
                "result": result,
                "replay_match": replay_match,
                "replay_digest": replay_digest,
            }
        )

    policy_report = evaluate_portfolio(candidates)
    input_digest = hashlib.sha256(canonical_bytes(clauses)).hexdigest()
    pyramid_report = pyramidal_regenerate(
        {
            "operation": "LOOKING_FOR_SOMETHING_BOUNDED_CANDIDATE_PORTFOLIO",
            "input_digest": input_digest,
            "P_VS_NP": "OPEN",
        },
        _pyramidal_children(candidates),
    )

    receipt = base_receipt(manifest, source)
    receipt.update(
        {
            "terminal": "TRUMP_LOOKING_FOR_SOMETHING_PORTFOLIO_COMPLETE",
            "operation": "LOOKING_FOR_SOMETHING_BOUNDED_CANDIDATE_PORTFOLIO",
            "source_loaded": True,
            "execution_performed": True,
            "candidate_result_promoted": False,
            "input_digest": input_digest,
            "policy_report": policy_report,
            "pyramidal_genesis_return_report": pyramid_report,
            "scientific_claim": "NONE",
        }
    )
    return seal_receipt(receipt)


def selftest() -> None:
    policy_selftest()
    pyramidal_selftest()


def _read_json_input(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(__import__("sys").stdin)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JANUS TRUMP LOOKING FOR SOMETHING bounded portfolio"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    run = sub.add_parser("portfolio")
    run.add_argument("--input", help="JSON CNF array; default stdin")
    run.add_argument(
        "--replay",
        action="store_true",
        help="repeat each fixed profile; only replay-matching child deltas may enter pyramidal regeneration",
    )
    args = parser.parse_args()

    if args.command == "selftest":
        selftest()
        out = {
            "terminal": "TRUMP_LOOKING_FOR_SOMETHING_POLICY_SELFTEST_PASS",
            "pyramidal_genesis_return": "PASS",
            "proof_authority": False,
            "P_VS_NP": "OPEN",
        }
    elif args.command == "portfolio":
        clauses = _read_json_input(args.input)
        if not isinstance(clauses, list):
            raise TrumpCandidateError("TRUMP_INPUT_MUST_BE_CNF_ARRAY")
        out = run_portfolio(clauses, replay=args.replay)
    else:
        raise AssertionError(args.command)

    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
