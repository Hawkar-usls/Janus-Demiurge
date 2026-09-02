#!/usr/bin/env python3
"""TRUMP Pyramidal Genesis-Return candidate operator v1.

Search/regeneration advisory only.
It does NOT solve SAT, prove coverage, establish polynomiality, or promote
scientific/theorem claims. P_VS_NP remains OPEN.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

OPERATOR_ID = "TRUMP_PYRAMIDAL_GENESIS_RETURN_OPERATOR_V1"


class PyramidalGenesisReturnError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def apply(parent_seed: Any, children: Iterable[dict]) -> dict:
    """Return a deterministic advisory regeneration receipt."""
    apex_seed_hash = digest(parent_seed)
    seen_ids: set[str] = set()
    child_receipt_hashes: list[str] = []
    returned: dict[str, Any] = {}
    verified_delta_ids: list[str] = []
    verified_delta_hashes: list[str] = []

    child_rows = list(children)
    for child in child_rows:
        child_id = str(child.get("child_id", ""))
        if not child_id:
            raise PyramidalGenesisReturnError("MISSING_CHILD_ID")
        if child_id in seen_ids:
            raise PyramidalGenesisReturnError("DUPLICATE_CHILD_ID")
        seen_ids.add(child_id)
        if "observation" not in child:
            raise PyramidalGenesisReturnError("MISSING_CHILD_OBSERVATION")

        child_receipt_hashes.append(digest(child))
        observation = child["observation"]
        delta_digest = digest(observation)
        returned.setdefault(delta_digest, observation)
        if child.get("verified") is True and child.get("replay_match") is True:
            verified_delta_ids.append(child_id)
            verified_delta_hashes.append(delta_digest)

    unique_verified_hashes = sorted(set(verified_delta_hashes))
    unique_returned_hashes = sorted(returned)
    delta_bundle = {
        "returned_delta_hashes": unique_returned_hashes,
        "verified_delta_hashes": unique_verified_hashes,
    }
    delta_hash = digest(delta_bundle)
    regenerated_seed = {
        "operator_id": OPERATOR_ID,
        "parent_seed_hash": apex_seed_hash,
        "verified_delta_hashes": unique_verified_hashes,
        "exit_preserved": True,
        "parent_write_authority_after_release": False,
    }
    regenerated_seed_hash = digest(regenerated_seed)

    return {
        "schema": "janus.trump.pyramidal_genesis_return.receipt.v1",
        "operator_id": OPERATOR_ID,
        "apex_seed_hash": apex_seed_hash,
        "child_count": len(child_rows),
        "child_receipt_hashes": sorted(child_receipt_hashes),
        "independent_witness_count": len(seen_ids),
        "returned_delta_count": len(unique_returned_hashes),
        "verified_delta_count": len(unique_verified_hashes),
        "verified_delta_ids": sorted(verified_delta_ids),
        "delta_hash": delta_hash,
        "regenerated_seed": regenerated_seed,
        "regenerated_seed_hash": regenerated_seed_hash,
        "proof_gate_status": "UNCHANGED__NO_THEOREM_PROMOTION",
        "exit_preserved": True,
        "parent_write_authority_after_release": False,
        "authority": {
            "advisory_only": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "formula_semantics_changed": False,
        },
        "scientific_boundary": {
            "universal_coverage_proved": False,
            "uniform_resolver_proved": False,
            "polynomial_uniform_resolver_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
        "laws": [
            "EXPANSION != COVERAGE",
            "CHILD_EXPERIENCE != AUTOMATIC_TRUTH",
            "RETURNED_DELTA != PROOF",
            "REGENERATION != THEOREM_PROMOTION",
        ],
    }


def selftest() -> None:
    parent = {"frontier": "R39", "state": "OPEN"}
    children = [
        {"child_id": "A", "observation": {"structure": "qhorn_candidate"}, "verified": True, "replay_match": True},
        {"child_id": "B", "observation": {"structure": "counterexample_candidate"}, "verified": False, "replay_match": True},
        {"child_id": "C", "observation": {"structure": "qhorn_candidate"}, "verified": True, "replay_match": True},
    ]
    a = apply(parent, children)
    b = apply(parent, list(reversed(children)))
    assert a["regenerated_seed_hash"] == b["regenerated_seed_hash"]
    assert a["returned_delta_count"] == 2
    assert a["verified_delta_count"] == 1
    assert a["proof_gate_status"] == "UNCHANGED__NO_THEOREM_PROMOTION"
    assert a["scientific_boundary"]["P_VS_NP"] == "OPEN"
    assert a["exit_preserved"] is True
    assert a["parent_write_authority_after_release"] is False


if __name__ == "__main__":
    selftest()
    print("PASS: TRUMP Pyramidal Genesis-Return selftest")
    print("P_VS_NP = OPEN")
