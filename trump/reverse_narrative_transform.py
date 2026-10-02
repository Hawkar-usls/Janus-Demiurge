#!/usr/bin/env python3
"""TRUMP REVERSE NARRATIVE TRANSFORM R0.

Semantic seed: Candy Dulfer & David A. Stewart — "Lily Was Here" interpreted
as a reverse-reading process metaphor.

The operator is deliberately weak in authority: it may reorder a frozen search
trajectory or a frozen portfolio schedule, but it MUST NOT alter witness bytes,
formula semantics, verifier rules, theorem face, or resource accounting.

This is a candidate search operator, not a theorem and not a SAT oracle.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Sequence

OPERATOR_ID = "TRUMP_REVERSE_NARRATIVE_TRANSFORM_R0"
MODES = ("FORWARD", "REVERSE", "BIDIRECTIONAL")


class ReverseNarrativeError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _item_digests(items: Iterable[Any]) -> list[str]:
    return [digest(item) for item in items]


def _bidirectional_indices(n: int) -> list[int]:
    out: list[int] = []
    lo, hi = 0, n - 1
    while lo <= hi:
        out.append(lo)
        if lo != hi:
            out.append(hi)
        lo += 1
        hi -= 1
    return out


def schedule(sequence: Sequence[Any], mode: str) -> list[Any]:
    """Return a reordered copy of an already-frozen sequence.

    No item is created, modified, dropped, or duplicated. Only order may change.
    """
    if mode not in MODES:
        raise ReverseNarrativeError("UNKNOWN_REVERSE_NARRATIVE_MODE")
    frozen = list(sequence)
    if mode == "FORWARD":
        out = list(frozen)
    elif mode == "REVERSE":
        out = list(reversed(frozen))
    else:
        out = [frozen[i] for i in _bidirectional_indices(len(frozen))]
    verify_reordering(frozen, out, mode)
    return out


def verify_reordering(original: Sequence[Any], transformed: Sequence[Any], mode: str) -> None:
    if len(original) != len(transformed):
        raise ReverseNarrativeError("TRAJECTORY_CARDINALITY_CHANGED")
    # Multiset equality over exact canonical item digests prevents hidden mutation,
    # drop, or duplication while allowing repeated identical items.
    if sorted(_item_digests(original)) != sorted(_item_digests(transformed)):
        raise ReverseNarrativeError("TRAJECTORY_CONTENT_CHANGED")

    expected = (
        list(original)
        if mode == "FORWARD"
        else list(reversed(original))
        if mode == "REVERSE"
        else [list(original)[i] for i in _bidirectional_indices(len(original))]
    )
    if canonical_bytes(expected) != canonical_bytes(list(transformed)):
        raise ReverseNarrativeError("TRAJECTORY_ORDER_NOT_CANONICAL")


def transform_receipt(sequence: Sequence[Any], mode: str) -> dict:
    transformed = schedule(sequence, mode)
    body = {
        "schema": "janus.trump.reverse_narrative_transform.receipt.v0.1",
        "operator_id": OPERATOR_ID,
        "mode": mode,
        "input_sequence_digest": digest(list(sequence)),
        "output_sequence_digest": digest(transformed),
        "item_multiset_digest": digest(sorted(_item_digests(sequence))),
        "input_items": len(sequence),
        "output_items": len(transformed),
        "semantics_changed": False,
        "witness_changed": False,
        "verifier_changed": False,
        "theorem_face_changed": False,
        "authority": {
            "advisory_only": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "solver_oracle": False,
        },
        "scientific_boundary": {
            "finite_success_implies_polynomial": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN",
        },
    }
    body["receipt_hash"] = digest(body)
    return body


def selftest() -> None:
    seq = [
        {"step": 0, "state": "LILY_WAS_HERE"},
        {"step": 1, "state": "IS_HERE"},
        {"step": 2, "state": "CAME_HOME"},
    ]
    assert [x["step"] for x in schedule(seq, "FORWARD")] == [0, 1, 2]
    assert [x["step"] for x in schedule(seq, "REVERSE")] == [2, 1, 0]
    assert [x["step"] for x in schedule(seq, "BIDIRECTIONAL")] == [0, 2, 1]
    r = transform_receipt(seq, "REVERSE")
    assert r["semantics_changed"] is False
    assert r["authority"]["proof_authority"] is False
    assert r["scientific_boundary"]["P_VS_NP"] == "OPEN"


if __name__ == "__main__":
    selftest()
    print("PASS: TRUMP REVERSE NARRATIVE TRANSFORM R0")
    print("P_VS_NP = OPEN")
