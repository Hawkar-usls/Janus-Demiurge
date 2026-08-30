"""JANUS Soul v1: exact hindsight guards for TRUMP candidate mode.

This module intentionally does *less* than a theorem solver:
- it can remember an independently verified exact failure;
- it can reject the exact same state/action pair later;
- it can enforce a strict macro-rank descent gate ("NO_HOTEL_CALIFORNIA");
- it can charge bounded work/bytes;
- it never promotes "not known bad" to "proved good".

Structural/generalized hindsight rules require a separate proof receipt and are
therefore outside this v1 runtime candidate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Tuple


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Decision(str, Enum):
    REJECT_KNOWN_BAD = "REJECT_KNOWN_BAD"
    NOT_KNOWN_BAD = "NOT_KNOWN_BAD"
    REJECT_NO_PROGRESS = "REJECT_NO_PROGRESS"
    PASS_PROGRESS = "PASS_PROGRESS"
    REJECT_DEBT_BOUND = "REJECT_DEBT_BOUND"
    PASS_DEBT_BOUND = "PASS_DEBT_BOUND"
    OPEN = "OPEN"


@dataclass(frozen=True)
class FailureReceipt:
    state_digest: str
    action_digest: str
    axis: str
    mechanism: str
    trace_digest: str
    verifier_digest: str
    charged_work: int
    charged_bytes: int

    @property
    def receipt_digest(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class ExactFailureGuard:
    """L1 exact-replay guard.

    It is intentionally scoped to one exact state/action digest pair.
    Generalization is forbidden without an external proof-authorized layer.
    """

    state_digest: str
    action_digest: str
    source_receipt_digest: str
    axis: str
    mechanism: str
    authority: str = "L1_EXACT_REPLAY_GUARD"

    def matches(self, state: Any, action: Any) -> bool:
        return self.state_digest == digest(state) and self.action_digest == digest(action)


@dataclass
class DebtLedger:
    max_work: int
    max_bytes: int
    work: int = 0
    bytes_used: int = 0

    def charge(self, *, work: int = 0, bytes_used: int = 0) -> Decision:
        if work < 0 or bytes_used < 0:
            raise ValueError("Debt charges must be non-negative.")
        next_work = self.work + work
        next_bytes = self.bytes_used + bytes_used
        if next_work > self.max_work or next_bytes > self.max_bytes:
            return Decision.REJECT_DEBT_BOUND
        self.work = next_work
        self.bytes_used = next_bytes
        return Decision.PASS_DEBT_BOUND

    def snapshot(self) -> Dict[str, int]:
        return {
            "max_work": self.max_work,
            "max_bytes": self.max_bytes,
            "work": self.work,
            "bytes_used": self.bytes_used,
        }


class HindsightSoul:
    """Append-only candidate hindsight compiler with a theorem-mode freeze."""

    def __init__(self, *, max_work: int, max_bytes: int) -> None:
        if max_work < 0 or max_bytes < 0:
            raise ValueError("Resource bounds must be non-negative.")
        self._receipts: List[FailureReceipt] = []
        self._guards: List[ExactFailureGuard] = []
        self._receipt_ids = set()
        self._frozen = False
        self.ledger = DebtLedger(max_work=max_work, max_bytes=max_bytes)

    @property
    def frozen(self) -> bool:
        return self._frozen

    @property
    def guards(self) -> Tuple[ExactFailureGuard, ...]:
        return tuple(self._guards)

    @property
    def receipts(self) -> Tuple[FailureReceipt, ...]:
        return tuple(self._receipts)

    def record_exact_failure(
        self,
        *,
        state: Any,
        action: Any,
        axis: str,
        mechanism: str,
        trace_digest: str,
        verifier_digest: str,
        charged_work: int = 0,
        charged_bytes: int = 0,
    ) -> FailureReceipt:
        """Record a verified exact failure and compile an exact-only guard.

        This method is LEARNING_FACE behavior. Once freeze() is called, adding
        new lessons is forbidden.
        """
        if self._frozen:
            raise RuntimeError("THEOREM_FACE is frozen: post-hoc repair is forbidden.")
        if not axis or not mechanism or not trace_digest or not verifier_digest:
            raise ValueError("Failure receipt fields must be non-empty.")
        decision = self.ledger.charge(work=charged_work, bytes_used=charged_bytes)
        if decision is Decision.REJECT_DEBT_BOUND:
            raise RuntimeError("Failure receipt would exceed the configured debt bound.")

        receipt = FailureReceipt(
            state_digest=digest(state),
            action_digest=digest(action),
            axis=axis,
            mechanism=mechanism,
            trace_digest=trace_digest,
            verifier_digest=verifier_digest,
            charged_work=charged_work,
            charged_bytes=charged_bytes,
        )
        rid = receipt.receipt_digest
        if rid not in self._receipt_ids:
            self._receipt_ids.add(rid)
            self._receipts.append(receipt)
            self._guards.append(
                ExactFailureGuard(
                    state_digest=receipt.state_digest,
                    action_digest=receipt.action_digest,
                    source_receipt_digest=rid,
                    axis=axis,
                    mechanism=mechanism,
                )
            )
        return receipt

    def classify(self, *, state: Any, action: Any, match_work: int = 1) -> Decision:
        """Return known-bad vs not-known-bad.

        NOT_KNOWN_BAD is deliberately *not* a safety or usefulness proof.
        """
        if match_work < 0:
            raise ValueError("match_work must be non-negative.")
        decision = self.ledger.charge(work=match_work * max(1, len(self._guards)))
        if decision is Decision.REJECT_DEBT_BOUND:
            return decision
        for guard in self._guards:
            if guard.matches(state, action):
                return Decision.REJECT_KNOWN_BAD
        return Decision.NOT_KNOWN_BAD

    @staticmethod
    def hotel_california_gate(
        *,
        before_rank: int,
        after_rank: int,
        polynomial_rank_cap: int,
    ) -> Decision:
        """Enforce strict macro progress.

        A state change is not progress unless a frozen, non-negative,
        polynomially capped rank strictly decreases.
        """
        if min(before_rank, after_rank, polynomial_rank_cap) < 0:
            raise ValueError("Ranks must be non-negative.")
        if before_rank > polynomial_rank_cap or after_rank > polynomial_rank_cap:
            return Decision.REJECT_NO_PROGRESS
        if after_rank >= before_rank:
            return Decision.REJECT_NO_PROGRESS
        return Decision.PASS_PROGRESS

    def freeze(self) -> str:
        """Switch from LEARNING_FACE to immutable THEOREM_FACE candidate mode."""
        self._frozen = True
        return self.snapshot_digest()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "schema": "janus.soul.hindsight.runtime_snapshot.v1",
            "frozen": self._frozen,
            "scientific_boundary": {
                "hindsight_is_oracle": False,
                "not_known_bad_is_proved_good": False,
                "generalized_guard_authority": False,
                "P_equals_NP_proved": False,
                "P_VS_NP": "OPEN",
            },
            "receipts": [asdict(r) for r in self._receipts],
            "guards": [asdict(g) for g in self._guards],
            "ledger": self.ledger.snapshot(),
        }

    def snapshot_digest(self) -> str:
        return digest(self.snapshot())


def selftest() -> Dict[str, Any]:
    soul = HindsightSoul(max_work=100, max_bytes=1000)
    state = {"clauses": [[1, -2], [2, 3]], "phase": "candidate"}
    bad_action = {"op": "expand", "pivot": 2}
    other_action = {"op": "factor", "pivot": 2}

    receipt = soul.record_exact_failure(
        state=state,
        action=bad_action,
        axis="POLY_HOLD",
        mechanism="REPRESENTATION_BLOWUP",
        trace_digest="trace:" + digest(["demo-trace"]),
        verifier_digest="verifier:" + digest(["demo-verifier"]),
        charged_work=2,
        charged_bytes=20,
    )

    assert soul.classify(state=state, action=bad_action) is Decision.REJECT_KNOWN_BAD
    assert soul.classify(state=state, action=other_action) is Decision.NOT_KNOWN_BAD

    assert (
        soul.hotel_california_gate(before_rank=8, after_rank=7, polynomial_rank_cap=10)
        is Decision.PASS_PROGRESS
    )
    assert (
        soul.hotel_california_gate(before_rank=8, after_rank=8, polynomial_rank_cap=10)
        is Decision.REJECT_NO_PROGRESS
    )
    assert (
        soul.hotel_california_gate(before_rank=8, after_rank=9, polynomial_rank_cap=10)
        is Decision.REJECT_NO_PROGRESS
    )

    frozen_digest = soul.freeze()
    try:
        soul.record_exact_failure(
            state=state,
            action=other_action,
            axis="POLY_FIND",
            mechanism="POST_HOC_TEST",
            trace_digest="x",
            verifier_digest="y",
        )
    except RuntimeError:
        post_hoc_rejected = True
    else:
        post_hoc_rejected = False
    assert post_hoc_rejected

    return {
        "status": "PASS",
        "receipt_digest": receipt.receipt_digest,
        "snapshot_digest": frozen_digest,
        "guard_count": len(soul.guards),
        "scientific_boundary": "P_VS_NP_OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
