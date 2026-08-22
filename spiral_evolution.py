#!/usr/bin/env python3
"""Canonical JANUS/Demiurge spiral evolution primitives.

The active entity is allowed to change, but its identity, prior states, failed
attempts and lessons are not erased. Re-visiting a slot is a new spiral turn,
not a reset to the same point.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _jsonable(value.to_dict())
        except Exception:
            pass
    return repr(value)


def fingerprint_payload(value: Any) -> str:
    raw = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class SpiralTurn:
    entity_id: str
    turn: int
    parent_fingerprint: Optional[str]
    state_before: Any
    candidate_state: Any
    active_state_after: Any
    outcome: str
    lessons: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    score_before: Optional[float] = None
    score_candidate: Optional[float] = None
    promoted: bool = False
    fingerprint: str = ""

    def seal(self) -> "SpiralTurn":
        body = asdict(self)
        body.pop("fingerprint", None)
        self.fingerprint = fingerprint_payload(body)
        return self

    def to_dict(self) -> Dict[str, Any]:
        return _jsonable(asdict(self))


class SpiralLedger:
    """Append-only lineage ledger for one persistent entity identity."""

    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.turns: List[SpiralTurn] = []

    @property
    def next_turn(self) -> int:
        return len(self.turns)

    @property
    def parent_fingerprint(self) -> Optional[str]:
        return self.turns[-1].fingerprint if self.turns else None

    def ascend(
        self,
        *,
        state_before: Any,
        candidate_state: Any,
        active_state_after: Any,
        lessons: Optional[Iterable[str]] = None,
        constraints: Optional[Iterable[str]] = None,
        score_before: Optional[float] = None,
        score_candidate: Optional[float] = None,
        promoted: bool = False,
        outcome: Optional[str] = None,
    ) -> SpiralTurn:
        lesson_list = [str(x) for x in (lessons or []) if str(x).strip()]
        constraint_list = [str(x) for x in (constraints or []) if str(x).strip()]
        if outcome is None:
            outcome = "ASCENDED" if promoted else ("INTEGRATED_LESSON" if lesson_list else "NO_ASCENT")
        turn = SpiralTurn(
            entity_id=self.entity_id,
            turn=self.next_turn,
            parent_fingerprint=self.parent_fingerprint,
            state_before=_jsonable(state_before),
            candidate_state=_jsonable(candidate_state),
            active_state_after=_jsonable(active_state_after),
            outcome=outcome,
            lessons=lesson_list,
            constraints=constraint_list,
            score_before=score_before,
            score_candidate=score_candidate,
            promoted=bool(promoted),
        ).seal()
        self.turns.append(turn)
        return turn


class PreservingWindow:
    """Bounded active window with an append-only overflow archive.

    Iteration exposes the active window for backwards-compatible algorithms.
    `all_items()` exposes the complete lineage, including archived overflow.
    """

    def __init__(self, maxlen: int):
        if maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self.maxlen = int(maxlen)
        self.active: List[Any] = []
        self.archive: List[Any] = []

    def append(self, value: Any) -> None:
        if len(self.active) >= self.maxlen:
            self.archive.append(self.active.pop(0))
        self.active.append(value)

    def all_items(self) -> List[Any]:
        return [*self.archive, *self.active]

    def __iter__(self):
        return iter(self.active)

    def __len__(self) -> int:
        return len(self.active)

    def __getitem__(self, item):
        return self.active[item]


SPIRAL_LAWS = (
    "NO_LEARNING_ENTITY_DELETION",
    "FAILURE_BECOMES_LESSON",
    "IDENTITY_PERSISTS_ACROSS_TURNS",
    "ITERATION_IS_SPIRAL_NOT_RING",
    "ACTIVE_FRONTIER_MAY_CHANGE_WITHOUT_ERASING_LINEAGE",
    "BOUNDED_WORKING_MEMORY_REQUIRES_ARCHIVE_OR_SUMMARY",
)
