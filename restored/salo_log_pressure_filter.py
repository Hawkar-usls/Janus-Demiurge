from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any

SCHEMA = "janus.salo.log_pressure.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _norm_level(level: Any) -> str:
    return str(level or "INFO").strip().upper() or "INFO"


def _norm_message(message: Any) -> str:
    return " ".join(str(message or "").split())


@dataclass
class _State:
    last_seen: float
    emitted_at: float
    total_count: int = 1
    suppressed_since_emit: int = 0


class SaloLogPressureFilter:
    """Bounded display-pressure filter. Every observation returns an evidence receipt."""

    def __init__(self, repeat_window_s: float = 5.0, max_signatures: int = 1024):
        self.repeat_window_s = max(0.0, float(repeat_window_s))
        self.max_signatures = max(8, int(max_signatures))
        self._state: dict[str, _State] = {}

    def _signature(self, level: str, message: str) -> str:
        return hashlib.sha256(_canon({"level": level, "message": message})).hexdigest()

    def _evict_if_needed(self) -> None:
        while len(self._state) > self.max_signatures:
            victim = min(self._state.items(), key=lambda item: (item[1].last_seen, item[0]))[0]
            del self._state[victim]

    def observe(self, level: Any, message: Any, *, now: float) -> dict[str, Any]:
        lvl = _norm_level(level)
        msg = _norm_message(message)
        sig = self._signature(lvl, msg)
        timestamp = float(now)
        state = self._state.get(sig)

        if state is None:
            state = _State(last_seen=timestamp, emitted_at=timestamp)
            self._state[sig] = state
            decision = "EMIT"
            summary_count = 0
        else:
            state.total_count += 1
            within_window = (timestamp - state.emitted_at) < self.repeat_window_s
            if within_window:
                state.last_seen = timestamp
                state.suppressed_since_emit += 1
                decision = "DISPLAY_SUPPRESS_REPEAT"
                summary_count = state.suppressed_since_emit
            else:
                summary_count = state.suppressed_since_emit
                state.last_seen = timestamp
                state.emitted_at = timestamp
                state.suppressed_since_emit = 0
                decision = "EMIT_WITH_REPEAT_SUMMARY" if summary_count else "EMIT"

        self._evict_if_needed()
        receipt_body = {
            "schema": SCHEMA,
            "signature_sha256": sig,
            "level": lvl,
            "message": msg,
            "observed_at": timestamp,
            "decision": decision,
            "total_count_for_signature": state.total_count,
            "repeat_count_since_last_emit": summary_count,
            "evidence_preserved": True,
            "authority": {
                "deletes_log_evidence": False,
                "kills_services": False,
                "modifies_runtime": False,
                "display_pressure_only": True,
            },
            "laws": [
                "DISPLAY_SUPPRESSION_NE_EVIDENCE_DELETION",
                "SALO_LOG_ORGANIZER_NE_SALO_JUDGE",
                "REPEATED_FAILURES_MUST_REMAIN_COUNTABLE"
            ]
        }
        receipt_body["receipt_sha256"] = hashlib.sha256(_canon(receipt_body)).hexdigest()
        return receipt_body

    def snapshot(self) -> dict[str, Any]:
        rows = []
        for sig, state in sorted(self._state.items()):
            rows.append({
                "signature_sha256": sig,
                "last_seen": state.last_seen,
                "emitted_at": state.emitted_at,
                "total_count": state.total_count,
                "suppressed_since_emit": state.suppressed_since_emit,
            })
        body = {"schema": "janus.salo.snapshot.v1", "signatures": rows}
        body["snapshot_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
        return body
