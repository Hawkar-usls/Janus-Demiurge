#!/usr/bin/env python3
"""TRUMP Slime Forge R0: receipt-bound advisory profile memory.

The forge replaces permanent-champion / Gold-style routing with a bounded
portfolio governor.  It may reorder an already declared profile set, but it
cannot add/drop profiles, change CNF semantics, grant theorem authority, or
learn from the current theorem face before a finalized sealed receipt exists.

Historical Slime genes intentionally retained here:
- Golden/OldPvP: challenger history + loser/negative memory, not champion truth;
- TRUE_SLIME: baseline comparison, small-N confidence, exploration, anti-cult;
- pheromone/path Slime: decaying-ish route preference is advisory only;
- Absolute Idle: source/context change cold-resets *use* of old champion memory;
- M2R/YAKSA: resource accounting is separate from correctness;
- Tachyon truth gates: replay/quorum discipline before reinforcement;
- JANUS Soul: theorem face never self-learns.

P_VS_NP remains OPEN.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "janus.trump.slime_forge_memory.r0"
AUTHORITY = {
    "proof_authority": False,
    "scientific_claim_promotion_authority": False,
    "command_authority": False,
    "external_effect_authority": False,
    "physical_runtime_effect_authority": False,
}


class SlimeForgeError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def profile_key(profile: dict[str, Any]) -> str:
    try:
        c = int(profile["cap_exponent"])
        k = int(profile["extension_exponent"])
    except Exception as exc:
        raise SlimeForgeError("INVALID_PROFILE") from exc
    if c < 1 or k < 0:
        raise SlimeForgeError("INVALID_PROFILE")
    return f"C{c}_K{k}"


def source_identity_from_receipt(receipt: dict[str, Any]) -> str:
    source = receipt.get("source") or {}
    required = ("repository", "commit", "path", "git_blob_sha")
    if any(not source.get(k) for k in required):
        raise SlimeForgeError("SOURCE_IDENTITY_FIELDS_REQUIRED")
    return digest({k: source[k] for k in required})


def verify_sealed_receipt(receipt: dict[str, Any]) -> None:
    if not isinstance(receipt, dict):
        raise SlimeForgeError("RECEIPT_OBJECT_REQUIRED")
    claimed = receipt.get("receipt_hash")
    if not isinstance(claimed, str) or len(claimed) != 64:
        raise SlimeForgeError("RECEIPT_HASH_REQUIRED")
    body = dict(receipt)
    body.pop("receipt_hash", None)
    if digest(body) != claimed:
        raise SlimeForgeError("RECEIPT_HASH_MISMATCH")
    authority = receipt.get("authority") or {}
    for key, expected in AUTHORITY.items():
        if authority.get(key) is not expected:
            raise SlimeForgeError("AUTHORITY_CEILING_VIOLATION")
    boundary = receipt.get("scientific_boundary") or {}
    if boundary.get("P_VS_NP") != "OPEN":
        raise SlimeForgeError("P_VS_NP_BOUNDARY_REQUIRED")
    if boundary.get("P_equals_NP_proved") is not False:
        raise SlimeForgeError("P_EQ_NP_PROMOTION_FORBIDDEN")
    if receipt.get("candidate_result_promoted") is not False:
        raise SlimeForgeError("CANDIDATE_PROMOTION_FORBIDDEN")


def _rows_from_receipt(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    terminal = receipt.get("terminal")
    if terminal == "TRUMP_LOOKING_FOR_SOMETHING_PORTFOLIO_COMPLETE":
        report = receipt.get("policy_report") or {}
        rows = report.get("ranked_candidates")
        if not isinstance(rows, list) or not rows:
            raise SlimeForgeError("FINALIZED_PORTFOLIO_ROWS_REQUIRED")
        out = []
        for row in rows:
            out.append({
                "profile": row.get("profile"),
                "status": row.get("status"),
                "paid_work": row.get("FAST_paid_work"),
                "replay_match": row.get("WARM_replay_match"),
                "real": row.get("REAL_fail_closed_boundary"),
            })
        return out
    if terminal == "TRUMP_SLIME_FORGE_BOUNDED_SOLVE_COMPLETE":
        attempts = receipt.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            raise SlimeForgeError("FINALIZED_ATTEMPTS_REQUIRED")
        out = []
        for attempt in attempts:
            result = attempt.get("result") or {}
            out.append({
                "profile": attempt.get("profile"),
                "status": result.get("status"),
                "paid_work": attempt.get("paid_work"),
                "replay_match": attempt.get("replay_match"),
                "real": attempt.get("real_boundary"),
            })
        return out
    raise SlimeForgeError("UNSUPPORTED_FINALIZED_RECEIPT_TERMINAL")


def _empty_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "P_VS_NP": "OPEN",
        "episodes": {},
        "sources": {},
        "laws": [
            "CHAMPION_IS_NOT_TRUTH",
            "OPEN_IS_NOT_NEGATIVE_EVIDENCE",
            "RESOURCE_COST_IS_NOT_CORRECTNESS",
            "SMALL_N_CANNOT_MONOPOLIZE",
            "SOURCE_IDENTITY_CHANGE_COLD_RESETS_ADVICE_WITHOUT_DELETING_HISTORY",
            "PROFILE_SET_MAY_BE_REORDERED_BUT_NOT_DROPPED",
            "LEARN_ONLY_FROM_FINALIZED_INTEGRITY_VALID_RECEIPT",
            "CURRENT_THEOREM_FACE_NEVER_SELF_LEARNS",
            "P_VS_NP_OPEN",
        ],
    }


def _seal_state(state: dict[str, Any]) -> dict[str, Any]:
    body = dict(state)
    body.pop("state_hash", None)
    body["state_hash"] = digest(body)
    return body


def _validate_state(state: dict[str, Any]) -> None:
    if state.get("schema") != SCHEMA or state.get("P_VS_NP") != "OPEN":
        raise SlimeForgeError("STATE_SCHEMA_OR_BOUNDARY_INVALID")
    claimed = state.get("state_hash")
    if claimed is not None:
        body = dict(state)
        body.pop("state_hash", None)
        if digest(body) != claimed:
            raise SlimeForgeError("STATE_HASH_MISMATCH")
    if not isinstance(state.get("episodes"), dict) or not isinstance(state.get("sources"), dict):
        raise SlimeForgeError("STATE_PLANES_INVALID")


class SlimeForgeMemory:
    def __init__(self, state: dict[str, Any] | None = None):
        self.state = _empty_state() if state is None else dict(state)
        _validate_state(self.state)
        self.state.pop("state_hash", None)

    @classmethod
    def load(cls, path: str | Path) -> "SlimeForgeMemory":
        p = Path(path)
        if not p.exists():
            return cls()
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def snapshot(self) -> dict[str, Any]:
        return _seal_state(self.state)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        sealed = self.snapshot()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(sealed, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, p)

    def learn_finalized_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Append one verified episode. Duplicate receipt hashes are replay, not evidence."""
        verify_sealed_receipt(receipt)
        rid = str(receipt["receipt_hash"])
        if rid in self.state["episodes"]:
            return {"status": "REPLAY_IGNORED", "receipt_hash": rid, "state": self.snapshot()}
        rows = _rows_from_receipt(receipt)
        source_id = source_identity_from_receipt(receipt)
        input_digest = receipt.get("input_digest")
        if not isinstance(input_digest, str) or len(input_digest) != 64:
            raise SlimeForgeError("INPUT_DIGEST_REQUIRED")

        decisive = {str(row.get("status")) for row in rows if row.get("status") in {"SAT", "UNSAT"}}
        if len(decisive) > 1:
            raise SlimeForgeError("CONTRADICTORY_EXACT_TERMINALS")

        source_plane = self.state["sources"].setdefault(source_id, {"profiles": {}, "receipt_count": 0})
        episode_rows = []
        for row in rows:
            profile = row.get("profile")
            key = profile_key(profile)
            status = str(row.get("status"))
            if status not in {"SAT", "UNSAT", "OPEN"}:
                raise SlimeForgeError("INVALID_TERMINAL_STATUS")
            if row.get("real") is not True:
                raise SlimeForgeError("NON_REAL_BOUNDARY_ROW_REJECTED")
            try:
                work = max(0, int(row.get("paid_work")))
            except Exception as exc:
                raise SlimeForgeError("PAID_WORK_REQUIRED") from exc
            replay_match = row.get("replay_match") is True

            stats = source_plane["profiles"].setdefault(key, {
                "episodes": 0,
                "decisive": 0,
                "open": 0,
                "replay_confirmed_decisive": 0,
                "decisive_work_sum": 0,
                "observed_work_sum": 0,
            })
            stats["episodes"] += 1
            stats["observed_work_sum"] += work
            if status in {"SAT", "UNSAT"}:
                stats["decisive"] += 1
                stats["decisive_work_sum"] += work
                if replay_match:
                    stats["replay_confirmed_decisive"] += 1
            else:
                # OPEN is preserved but does not lower the epistemic utility.
                stats["open"] += 1
            episode_rows.append({
                "profile_key": key,
                "status": status,
                "paid_work": work,
                "replay_match": replay_match,
            })

        source_plane["receipt_count"] += 1
        self.state["episodes"][rid] = {
            "source_identity": source_id,
            "input_digest": input_digest,
            "terminal": receipt.get("terminal"),
            "rows": episode_rows,
        }
        return {"status": "LEARNED", "receipt_hash": rid, "source_identity": source_id, "state": self.snapshot()}

    def rank_profiles(
        self,
        profiles: Iterable[dict[str, Any]],
        *,
        source_identity: str,
    ) -> dict[str, Any]:
        """Reorder, never remove, the declared profile set.

        Evidence and resource scores are deliberately separate. OPEN changes only
        observation/exploration counts; it is not a failure.  A Beta(2,2) prior
        shrinks small decisive samples toward neutral so one lucky bout cannot
        become a permanent Gold champion.
        """
        declared = [dict(p) for p in profiles]
        keys = [profile_key(p) for p in declared]
        if len(set(keys)) != len(keys):
            raise SlimeForgeError("DUPLICATE_DECLARED_PROFILE")
        source_plane = self.state["sources"].get(source_identity, {"profiles": {}, "receipt_count": 0})
        rows = []
        for index, (profile, key) in enumerate(zip(declared, keys)):
            s = (source_plane.get("profiles") or {}).get(key, {})
            episodes = int(s.get("episodes", 0))
            decisive = int(s.get("decisive", 0))
            open_count = int(s.get("open", 0))
            replay_decisive = int(s.get("replay_confirmed_decisive", 0))
            decisive_work = int(s.get("decisive_work_sum", 0))

            # All admitted decisive rows are exact/fail-closed candidate terminals.
            # Beta(2,2) is a neutral small-N shrinkage prior. OPEN contributes
            # neither success nor failure to this evidence term.
            posterior_decisive = (decisive + 2.0) / (decisive + 4.0)
            evidence_utility = 2.0 * posterior_decisive - 1.0
            replay_ratio = replay_decisive / decisive if decisive else 0.0
            mean_decisive_work = decisive_work / decisive if decisive else None
            resource_efficiency = (
                1.0 / (1.0 + math.log1p(mean_decisive_work))
                if mean_decisive_work is not None else 0.0
            )
            exploration_floor = 0.10 / math.sqrt(episodes + 1.0)
            # Fresh exact evidence dominates resource preference. Exploration is
            # deliberately nonzero so no historical champion can own the route.
            rank_score = (
                0.65 * evidence_utility
                + 0.20 * replay_ratio
                + 0.15 * resource_efficiency
                + exploration_floor
            )
            rows.append({
                "declared_index": index,
                "profile": profile,
                "profile_key": key,
                "rank_score": round(rank_score, 12),
                "verified_route_score": round(evidence_utility, 12),
                "resource_efficiency_score": round(resource_efficiency, 12),
                "exploration_floor": round(exploration_floor, 12),
                "stats": {
                    "episodes": episodes,
                    "decisive": decisive,
                    "open": open_count,
                    "replay_confirmed_decisive": replay_decisive,
                    "mean_decisive_work": mean_decisive_work,
                },
            })

        ranked = sorted(rows, key=lambda r: (-r["rank_score"], r["declared_index"]))
        ordered_profiles = [row["profile"] for row in ranked]
        if {profile_key(p) for p in ordered_profiles} != set(keys) or len(ordered_profiles) != len(keys):
            raise AssertionError("PROFILE_SET_CHANGED")
        return {
            "schema": "janus.trump.slime_forge_advice.r0",
            "component": "TRUMP_SLIME_FORGE_R0",
            "source_identity": source_identity,
            "cold_context": source_identity not in self.state["sources"],
            "declared_profile_count": len(declared),
            "ordered_profiles": ordered_profiles,
            "ranking": ranked,
            "learning_performed": False,
            "candidate_set_changed": False,
            "authority": dict(AUTHORITY),
            "scientific_boundary": {"P_VS_NP": "OPEN", "P_equals_NP_proved": False},
            "laws": [
                "ADVICE_MAY_REORDER_BUT_NEVER_DROP_DECLARED_PROFILES",
                "OPEN_IS_NEUTRAL_EVIDENCE",
                "SMALL_N_IS_SHRUNK_TOWARD_NEUTRAL",
                "EXPLORATION_FLOOR_PREVENTS_PERMANENT_CHAMPION",
                "SOURCE_CHANGE_USES_COLD_CONTEXT_WITHOUT_HISTORY_DELETION",
            ],
        }


def source_identity(source: dict[str, Any]) -> str:
    required = ("repository", "pinned_commit", "path", "git_blob_sha")
    if any(not source.get(k) for k in required):
        raise SlimeForgeError("SOURCE_IDENTITY_FIELDS_REQUIRED")
    return digest({k: source[k] for k in required})


def selftest() -> None:
    mem = SlimeForgeMemory()
    profiles = [
        {"cap_exponent": 1, "extension_exponent": 0},
        {"cap_exponent": 2, "extension_exponent": 0},
        {"cap_exponent": 2, "extension_exponent": 1},
    ]
    cold = mem.rank_profiles(profiles, source_identity="0" * 64)
    assert cold["cold_context"] is True
    assert len(cold["ordered_profiles"]) == len(profiles)
    assert {profile_key(p) for p in cold["ordered_profiles"]} == {profile_key(p) for p in profiles}
    assert all(r["verified_route_score"] == 0.0 for r in cold["ranking"])


if __name__ == "__main__":
    selftest()
    print(json.dumps({"status": "PASS", "component": "TRUMP_SLIME_FORGE_R0", "P_VS_NP": "OPEN"}, sort_keys=True))
