from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = "janus.model.evaluation_contract.v1"
EVAL_BATCHES = 24
EVAL_BATCH_SIZE = 8
ADAPTIVE_REGRESSION_TOLERANCE = 0.002
ANCHOR_REGRESSION_TOLERANCE = 0.01
BOOTSTRAP_FINITE_LOSS_CEILING = 8.0
ADAPTIVE_SEED_OFFSET = 11
ANCHOR_SEED_OFFSET = 29
DEFAULT_ANCHOR = Path(__file__).resolve().parent / "eval" / "JANUS_ANCHOR_EVAL-v1.txt"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def contract_identity(anchor: Path | None = None, *, seed: int = 1337) -> dict:
    anchor_path = Path(anchor) if anchor is not None else DEFAULT_ANCHOR
    if not anchor_path.exists():
        raise RuntimeError(f"FROZEN_ANCHOR_MISSING:{anchor_path}")

    obj = {
        "schema": SCHEMA,
        "adaptive": {
            "kind": "CURRENT_REGISTRY_HASH_SPLIT_HOLDOUT",
            "batches": EVAL_BATCHES,
            "batch_size": EVAL_BATCH_SIZE,
            "seed": seed + ADAPTIVE_SEED_OFFSET,
            "regression_tolerance_fraction": ADAPTIVE_REGRESSION_TOLERANCE,
        },
        "anchor": {
            "kind": "FROZEN_VERSIONED_TEXT_HOLDOUT",
            "path": "janus_model/eval/JANUS_ANCHOR_EVAL-v1.txt",
            "sha256": sha256_file(anchor_path),
            "batches": EVAL_BATCHES,
            "batch_size": EVAL_BATCH_SIZE,
            "seed": seed + ANCHOR_SEED_OFFSET,
            "regression_tolerance_fraction": ANCHOR_REGRESSION_TOLERANCE,
        },
        "promotion_rule": "ADAPTIVE_GATE_AND_FROZEN_ANCHOR_GATE",
        "anchor_is_training_source": False,
        "anchor_gate_can_override_failed_adaptive_gate": False,
    }
    canonical = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    obj["contract_sha256"] = hashlib.sha256(canonical).hexdigest()
    return obj


def combine_learning_cycle_digest(registry_digest: str, evaluation_contract_sha256: str) -> str:
    raw = (
        "JANUS_LEARNING_CYCLE_V1\n"
        f"registry={registry_digest}\n"
        f"evaluation_contract={evaluation_contract_sha256}\n"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
