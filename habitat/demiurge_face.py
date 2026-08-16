#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded JANUS Habitat face extracted from the legacy Demiurge sandbox.

The legacy repository is preserved unchanged. This module reuses only safe
proposal-generation patterns from architect_ai.py, auto_evolution.py and
bayes_optimizer.py.

Core law:
    PROPOSED != TESTED != SELECTED != AUTHORIZED

The module is stdlib-only and intentionally has no network, subprocess,
filesystem-write, model-training, source-mutation or command-execution surface.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


FACE_SCHEMA = "janus.habitat.demiurge_face.v1"
REQUEST_SCHEMA = "janus.habitat.demiurge_request.v1"
PROPOSAL_SCHEMA = "janus.habitat.demiurge_proposal_set.v1"
RANKING_SCHEMA = "janus.habitat.demiurge_ranking.v1"
SOURCE_COMMIT = "98974d9c02637cb471ef73f5b62cf81797895a44"
MAX_CANDIDATES = 16

ARCH_TYPES = (
    "transformer",
    "wide_transformer",
    "deep_transformer",
    "sparse_transformer",
    "hybrid",
    "recurrent_transformer",
    "mixture_of_experts",
)
N_EMBD = (128, 256, 384, 512, 768)
N_HEAD = (4, 8, 12, 16)
N_LAYER = (4, 6, 8, 10, 12)
CORE_RANGES = {
    "alpha": (0.01, 0.5),
    "gamma": (0.8, 0.999),
    "epsilon": (0.01, 0.9),
}
_SAFE_OBJECTIVE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


class DemiurgeFaceError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _closed_keys(obj: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = set(obj) - allowed
    if extra:
        raise DemiurgeFaceError(f"{label}: unexpected keys: {sorted(extra)}")


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemiurgeFaceError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise DemiurgeFaceError(f"{label} must be finite")
    return value


def _choice_near(rng: random.Random, values: Sequence[int], current: int) -> int:
    idx = min(range(len(values)), key=lambda i: abs(values[i] - current))
    step = rng.choice((-1, 0, 1))
    return int(values[max(0, min(len(values) - 1, idx + step))])


def _repair_heads(n_embd: int, proposed_head: int) -> int:
    valid = [head for head in N_HEAD if n_embd % head == 0]
    if not valid:
        raise DemiurgeFaceError("no admissible n_head divides n_embd")
    return min(valid, key=lambda head: abs(head - proposed_head))


def _safe_objective_name(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise DemiurgeFaceError("objective must be a non-empty string <= 64 chars")
    if value == "proposal_id" or any(char not in _SAFE_OBJECTIVE_CHARS for char in value):
        raise DemiurgeFaceError("objective contains reserved or unsafe characters")
    return value


@dataclass(frozen=True)
class HabitatDemiurgeFace:
    """Pure proposal/ranking face with zero effect authority."""

    face_id: str = "DEMIURGE_BOUNDED_PROPOSAL_BUILDER"

    def describe(self) -> dict[str, Any]:
        return {
            "schema": FACE_SCHEMA,
            "face_id": self.face_id,
            "source_repository": "Hawkar-usls/Janus-Demiurge",
            "source_commit": SOURCE_COMMIT,
            "primary_role": "RESEARCH",
            "subrole": "BOUNDED_PROPOSAL_BUILDER",
            "can_propose": True,
            "can_rank_external_measurements": True,
            "can_verify": False,
            "can_execute_proposal": False,
            "can_mutate_source": False,
            "can_trigger_external_effect": False,
            "write_back_default": "DENY",
            "laws": [
                "PROPOSED != TESTED",
                "TESTED != SELECTED",
                "SELECTED != AUTHORIZED",
                "RANKING != TRUTH",
                "SIMULATION_OUTPUT != FUTURE_FACT",
                "FACE_COUNT != AUTHORITY",
            ],
        }

    def propose(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request, Mapping):
            raise DemiurgeFaceError("request must be an object")
        _closed_keys(
            request,
            {"schema", "request_id", "mode", "seed", "candidate_count", "base_config"},
            "request",
        )
        if request.get("schema") != REQUEST_SCHEMA:
            raise DemiurgeFaceError("unsupported request schema")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            raise DemiurgeFaceError("request_id must be a non-empty string <= 128 chars")
        seed = request.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise DemiurgeFaceError("seed must be an integer")
        count = request.get("candidate_count", 4)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_CANDIDATES:
            raise DemiurgeFaceError(f"candidate_count must be 1..{MAX_CANDIDATES}")
        mode = request.get("mode")
        base = request.get("base_config")
        if not isinstance(base, Mapping):
            raise DemiurgeFaceError("base_config must be an object")

        if mode == "ARCHITECTURE_VARIATION":
            proposals = self._architecture_variants(base, seed, count)
        elif mode == "CORE_PARAMETER_VARIATION":
            proposals = self._core_variants(base, seed, count)
        else:
            raise DemiurgeFaceError("unsupported mode")

        request_digest = canonical_sha256(dict(request))
        rows = []
        for index, proposal in enumerate(proposals):
            proposal_id = canonical_sha256(
                {"request_digest": request_digest, "index": index, "proposal": proposal}
            )[:24]
            rows.append(
                {
                    "proposal_id": proposal_id,
                    "config": proposal,
                    "tested": False,
                    "selected": False,
                    "authorized": False,
                }
            )

        result = {
            "schema": PROPOSAL_SCHEMA,
            "face_id": self.face_id,
            "source_commit": SOURCE_COMMIT,
            "request_id": request_id,
            "request_digest": request_digest,
            "proposal_count": len(rows),
            "proposals": rows,
            "execution_requested": False,
            "source_writeback_requested": False,
            "selection_authority_claimed": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result

    def _architecture_variants(
        self, base: Mapping[str, Any], seed: int, count: int
    ) -> list[dict[str, Any]]:
        _closed_keys(base, {"arch_type", "n_embd", "n_head", "n_layer"}, "base_config")
        arch = base.get("arch_type", "transformer")
        n_embd = base.get("n_embd", 256)
        n_head = base.get("n_head", 8)
        n_layer = base.get("n_layer", 6)
        if arch not in ARCH_TYPES:
            raise DemiurgeFaceError("unsupported arch_type")
        if n_embd not in N_EMBD or n_head not in N_HEAD or n_layer not in N_LAYER:
            raise DemiurgeFaceError("base architecture lies outside admitted discrete ranges")
        if n_embd % n_head != 0:
            raise DemiurgeFaceError("base n_embd must be divisible by n_head")

        rng = random.Random(seed)
        out: list[dict[str, Any]] = []
        for _ in range(count):
            embd = _choice_near(rng, N_EMBD, int(n_embd))
            head = _repair_heads(embd, _choice_near(rng, N_HEAD, int(n_head)))
            layer = _choice_near(rng, N_LAYER, int(n_layer))
            arch_next = arch if rng.random() >= 0.30 else rng.choice(ARCH_TYPES)
            out.append(
                {
                    "arch_type": arch_next,
                    "n_embd": embd,
                    "n_head": head,
                    "n_layer": layer,
                }
            )
        return out

    def _core_variants(
        self, base: Mapping[str, Any], seed: int, count: int
    ) -> list[dict[str, Any]]:
        _closed_keys(base, set(CORE_RANGES), "base_config")
        normalized: dict[str, float] = {}
        for key, (low, high) in CORE_RANGES.items():
            value = _finite_number(base.get(key), f"base_config.{key}")
            if not low <= value <= high:
                raise DemiurgeFaceError(f"base_config.{key} outside admitted range")
            normalized[key] = value

        rng = random.Random(seed)
        factors = {"alpha": (0.8, 1.2), "gamma": (0.95, 1.05), "epsilon": (0.7, 1.3)}
        out: list[dict[str, Any]] = []
        for _ in range(count):
            row: dict[str, Any] = {}
            for key, value in normalized.items():
                low, high = CORE_RANGES[key]
                flo, fhi = factors[key]
                mutated = value * rng.uniform(flo, fhi)
                row[key] = round(max(low, min(high, mutated)), 12)
            out.append(row)
        return out

    def _validated_proposal_ids(self, proposal_set: Mapping[str, Any]) -> set[str]:
        if not isinstance(proposal_set, Mapping):
            raise DemiurgeFaceError("proposal_set must be an object")
        _closed_keys(
            proposal_set,
            {
                "schema", "face_id", "source_commit", "request_id", "request_digest",
                "proposal_count", "proposals", "execution_requested",
                "source_writeback_requested", "selection_authority_claimed", "receipt_sha256"
            },
            "proposal_set",
        )
        if proposal_set.get("schema") != PROPOSAL_SCHEMA:
            raise DemiurgeFaceError("invalid proposal_set schema")
        if proposal_set.get("face_id") != self.face_id or proposal_set.get("source_commit") != SOURCE_COMMIT:
            raise DemiurgeFaceError("proposal_set provenance mismatch")
        if proposal_set.get("execution_requested") is not False:
            raise DemiurgeFaceError("proposal_set requests execution")
        if proposal_set.get("source_writeback_requested") is not False:
            raise DemiurgeFaceError("proposal_set requests source writeback")
        if proposal_set.get("selection_authority_claimed") is not False:
            raise DemiurgeFaceError("proposal_set claims selection authority")

        receipt = proposal_set.get("receipt_sha256")
        if not isinstance(receipt, str) or len(receipt) != 64 or any(c not in "0123456789abcdef" for c in receipt):
            raise DemiurgeFaceError("proposal_set receipt is malformed")
        unsigned = dict(proposal_set)
        unsigned.pop("receipt_sha256", None)
        if canonical_sha256(unsigned) != receipt:
            raise DemiurgeFaceError("proposal_set receipt mismatch")

        proposals = proposal_set.get("proposals")
        if not isinstance(proposals, list) or not 1 <= len(proposals) <= MAX_CANDIDATES:
            raise DemiurgeFaceError("proposal_set proposals must be a bounded list")
        if proposal_set.get("proposal_count") != len(proposals):
            raise DemiurgeFaceError("proposal_count mismatch")

        ids: set[str] = set()
        for row in proposals:
            if not isinstance(row, Mapping):
                raise DemiurgeFaceError("proposal row must be an object")
            _closed_keys(row, {"proposal_id", "config", "tested", "selected", "authorized"}, "proposal")
            proposal_id = row.get("proposal_id")
            if (
                not isinstance(proposal_id, str)
                or len(proposal_id) != 24
                or any(c not in "0123456789abcdef" for c in proposal_id)
            ):
                raise DemiurgeFaceError("proposal_id must be 24 lowercase hex chars")
            if proposal_id in ids:
                raise DemiurgeFaceError("duplicate proposal_id")
            if not isinstance(row.get("config"), Mapping):
                raise DemiurgeFaceError("proposal config must be an object")
            if row.get("tested") is not False or row.get("selected") is not False or row.get("authorized") is not False:
                raise DemiurgeFaceError("input proposal_set may not pre-assert test/selection/authorization")
            ids.add(proposal_id)
        return ids

    def rank_evaluated(
        self,
        proposal_set: Mapping[str, Any],
        evaluations: Sequence[Mapping[str, Any]],
        *,
        objective: str = "score",
        maximize: bool = True,
    ) -> dict[str, Any]:
        """Rank only externally supplied finite measurements.

        This function never executes or evaluates a proposal itself. It merely
        orders measurements already supplied by another face/harness. The
        proposal receipt is replayed before any ranking to bind evaluation to
        the exact generated candidate set.
        """
        objective = _safe_objective_name(objective)
        ids = self._validated_proposal_ids(proposal_set)
        if isinstance(evaluations, (str, bytes)) or not isinstance(evaluations, Sequence):
            raise DemiurgeFaceError("evaluations must be a sequence of objects")
        seen: set[str] = set()
        ranked: list[dict[str, Any]] = []
        for row in evaluations:
            if not isinstance(row, Mapping):
                raise DemiurgeFaceError("evaluation row must be an object")
            _closed_keys(row, {"proposal_id", objective}, "evaluation")
            proposal_id = row.get("proposal_id")
            if not isinstance(proposal_id, str) or proposal_id not in ids:
                raise DemiurgeFaceError("evaluation references unknown proposal_id")
            if proposal_id in seen:
                raise DemiurgeFaceError("duplicate evaluation proposal_id")
            seen.add(proposal_id)
            ranked.append(
                {
                    "proposal_id": proposal_id,
                    objective: _finite_number(row.get(objective), f"evaluation.{objective}"),
                }
            )
        if seen != ids:
            raise DemiurgeFaceError("every proposal must have exactly one external evaluation")
        ranked.sort(key=lambda row: row[objective], reverse=bool(maximize))
        result = {
            "schema": RANKING_SCHEMA,
            "face_id": self.face_id,
            "proposal_receipt_sha256": proposal_set.get("receipt_sha256"),
            "objective": objective,
            "maximize": bool(maximize),
            "ranking": ranked,
            "selected_proposal_id": ranked[0]["proposal_id"],
            "selection_is_recommendation_only": True,
            "authorized": False,
            "execution_requested": False,
            "source_writeback_requested": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
