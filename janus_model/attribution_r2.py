from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

SINGLE_SCHEMA = "janus.keymaster.attribution_ablation_ledger.v1"
CHECKPOINT_SCHEMA = "janus.keymaster.attribution_r2_checkpoint.v1"
SUMMARY_SCHEMA = "janus.keymaster.attribution_r2_summary.v1"
DIRECTIONAL = {"SUPPORTIVE_SIGNAL", "ADVERSE_SIGNAL"}
ALLOWED_SINGLE = DIRECTIONAL | {"MIXED_SIGNAL", "INDETERMINATE_SIGNAL"}
FINAL_CLASSES = {"STABLE_SUPPORTIVE", "CONTEXT_DEPENDENT", "STABLE_ADVERSE", "UNRESOLVED"}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _median(values: list[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _consensus(signals: list[str]) -> str:
    if not signals:
        return "NO_CONTEXT"
    if any(s not in ALLOWED_SINGLE for s in signals):
        raise RuntimeError("R2_UNKNOWN_SINGLE_SIGNAL")
    if len(set(signals)) == 1 and signals[0] in DIRECTIONAL:
        return signals[0]
    if len(set(signals)) == 1 and signals[0] == "INDETERMINATE_SIGNAL":
        return "INDETERMINATE_SIGNAL"
    return "MIXED_SIGNAL"


def validate_single_ledgers(ledgers: list[dict], min_seeds: int = 3) -> None:
    if len(ledgers) < min_seeds:
        raise RuntimeError("R2_INSUFFICIENT_SEED_REPLICATES")
    seeds = set()
    identity = None
    ids = None
    for ledger in ledgers:
        if ledger.get("schema") != SINGLE_SCHEMA or ledger.get("status") != "COMPLETE_SINGLE_SEED_DIAGNOSTIC":
            raise RuntimeError("R2_SINGLE_LEDGER_SCHEMA_REJECTED")
        if ledger.get("variant_count") != 17 or len(ledger.get("attribution") or []) != 8:
            raise RuntimeError("R2_SINGLE_LEDGER_SHAPE_REJECTED")
        ceiling = ledger.get("claim_ceiling") or {}
        if ceiling.get("single_seed_establishes_causality") is not False:
            raise RuntimeError("R2_SINGLE_LEDGER_CAUSALITY_FIREWALL_REJECTED")
        seed = ledger.get("seed")
        if not isinstance(seed, int) or seed in seeds:
            raise RuntimeError("R2_SEED_DUPLICATE_OR_INVALID")
        seeds.add(seed)
        ident = (
            ledger.get("checkpoint_sha256"),
            ledger.get("source_digest"),
            ledger.get("keymaster_contribution_sha256"),
            ledger.get("keymaster_training_pack_sha256"),
            ledger.get("steps_per_variant"),
            ledger.get("batch_size"),
            ledger.get("learning_rate"),
        )
        if identity is None:
            identity = ident
        elif ident != identity:
            raise RuntimeError("R2_SEED_LEDGER_IDENTITY_MISMATCH")
        current_ids = tuple(sorted(row.get("id") for row in ledger["attribution"]))
        if ids is None:
            ids = current_ids
        elif current_ids != ids:
            raise RuntimeError("R2_CONTRIBUTOR_SET_MISMATCH")


def build_checkpoint_evidence(ledgers: list[dict], *, sequence_run_id: int, min_seeds: int = 3) -> dict:
    validate_single_ledgers(ledgers, min_seeds=min_seeds)
    first = ledgers[0]
    by_seed = {int(x["seed"]): x for x in ledgers}
    seeds = sorted(by_seed)
    contributors: list[dict] = []
    first_rows = {row["id"]: row for row in first["attribution"]}
    for cid in sorted(first_rows):
        rows = [{r["id"]: r for r in ledger["attribution"]}[cid] for ledger in ledgers]
        full_signals = [r["full_8_signal"] for r in rows]
        core_signals = [r.get("core_5_signal") for r in rows if r.get("core_5_signal") is not None]
        contributors.append({
            "id": cid,
            "repository": first_rows[cid]["repository"],
            "cohort": first_rows[cid]["cohort"],
            "head_sha": first_rows[cid]["head_sha"],
            "full_8_seed_signals": full_signals,
            "full_8_consensus": _consensus(full_signals),
            "full_8_median_marginal_adaptive_loss": _median([float(r["full_8_marginal_adaptive_loss"]) for r in rows]),
            "full_8_median_marginal_anchor_loss": _median([float(r["full_8_marginal_anchor_loss"]) for r in rows]),
            "core_5_seed_signals": core_signals,
            "core_5_consensus": _consensus(core_signals) if core_signals else None,
            "core_5_median_marginal_adaptive_loss": _median([float(r["core_5_marginal_adaptive_loss"]) for r in rows if r.get("core_5_marginal_adaptive_loss") is not None]),
            "core_5_median_marginal_anchor_loss": _median([float(r["core_5_marginal_anchor_loss"]) for r in rows if r.get("core_5_marginal_anchor_loss") is not None]),
        })
    obj: dict[str, Any] = {
        "schema": CHECKPOINT_SCHEMA,
        "status": "SEED_REPLICATION_COMPLETE",
        "sequence_run_id": int(sequence_run_id),
        "checkpoint_sha256": first["checkpoint_sha256"],
        "source_digest": first["source_digest"],
        "keymaster_contribution_sha256": first["keymaster_contribution_sha256"],
        "keymaster_training_pack_sha256": first["keymaster_training_pack_sha256"],
        "steps_per_variant": first["steps_per_variant"],
        "batch_size": first["batch_size"],
        "learning_rate": first["learning_rate"],
        "seed_count": len(seeds),
        "seeds": seeds,
        "contributors": contributors,
        "claim_ceiling": {
            "seed_consensus_is_world_causality": False,
            "seed_consensus_grants_authority": False,
            "automatic_weighting_change": False,
            "automatic_contributor_removal": False,
            "authority_delta": 0,
        },
    }
    obj["checkpoint_evidence_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def load_checkpoint_history(history_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if not history_dir.is_dir():
        return rows
    for path in sorted(history_dir.glob("keymaster-attribution-r2-checkpoint-*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if obj.get("schema") != CHECKPOINT_SCHEMA or obj.get("status") != "SEED_REPLICATION_COMPLETE":
            continue
        rows.append(obj)
    by_checkpoint: dict[str, dict] = {}
    for row in rows:
        cp = row.get("checkpoint_sha256")
        if not isinstance(cp, str):
            continue
        previous = by_checkpoint.get(cp)
        if previous is None or int(row.get("sequence_run_id", -1)) > int(previous.get("sequence_run_id", -1)):
            by_checkpoint[cp] = row
    return sorted(by_checkpoint.values(), key=lambda r: int(r.get("sequence_run_id", -1)))


def _stable_direction(signals: list[str]) -> str | None:
    if signals and len(set(signals)) == 1 and signals[0] in DIRECTIONAL:
        return signals[0]
    return None


def _classify(records: list[dict], cid: str, cohort: str, min_checkpoints: int) -> tuple[str, dict]:
    rows = []
    for record in records:
        found = next((x for x in record.get("contributors") or [] if x.get("id") == cid), None)
        if found is not None:
            rows.append(found)
    if len(rows) < min_checkpoints:
        return "UNRESOLVED", {"reason": "INSUFFICIENT_SUCCESSIVE_CHECKPOINTS", "observed_checkpoints": len(rows)}
    window = rows[-min_checkpoints:]
    full = [r.get("full_8_consensus") for r in window]
    full_dir = _stable_direction(full)
    core = [r.get("core_5_consensus") for r in window] if cohort == "CORE_5" else []
    core_dir = _stable_direction(core) if core else None
    if cohort == "CORE_5":
        if full_dir and core_dir and full_dir != core_dir:
            return "CONTEXT_DEPENDENT", {"reason": "REPRODUCIBLE_FULL_CORE_DIRECTION_DIVERGENCE", "full": full, "core": core}
        if full_dir == "SUPPORTIVE_SIGNAL" and core_dir == "SUPPORTIVE_SIGNAL":
            return "STABLE_SUPPORTIVE", {"reason": "REPRODUCIBLE_SUPPORT_ACROSS_FULL_AND_CORE", "full": full, "core": core}
        if full_dir == "ADVERSE_SIGNAL" and core_dir == "ADVERSE_SIGNAL":
            return "STABLE_ADVERSE", {"reason": "REPRODUCIBLE_ADVERSE_ACROSS_FULL_AND_CORE", "full": full, "core": core}
        return "UNRESOLVED", {"reason": "DIRECTION_NOT_REPRODUCIBLE_ACROSS_REQUIRED_CONTEXTS", "full": full, "core": core}
    if full_dir == "SUPPORTIVE_SIGNAL":
        return "STABLE_SUPPORTIVE", {"reason": "REPRODUCIBLE_SUPPORT_IN_FULL_CONTEXT", "full": full}
    if full_dir == "ADVERSE_SIGNAL":
        return "STABLE_ADVERSE", {"reason": "REPRODUCIBLE_ADVERSE_IN_FULL_CONTEXT", "full": full}
    return "UNRESOLVED", {"reason": "FULL_CONTEXT_DIRECTION_NOT_REPRODUCIBLE", "full": full}


def build_r2_summary(
    current: dict,
    history: list[dict],
    *,
    min_checkpoints: int = 3,
    min_seeds: int = 3,
    max_history: int = 8,
) -> dict:
    if current.get("schema") != CHECKPOINT_SCHEMA or current.get("seed_count", 0) < min_seeds:
        raise RuntimeError("R2_CURRENT_CHECKPOINT_EVIDENCE_REJECTED")
    by_checkpoint = {r.get("checkpoint_sha256"): r for r in history if r.get("schema") == CHECKPOINT_SCHEMA}
    by_checkpoint[current["checkpoint_sha256"]] = current
    records = sorted(by_checkpoint.values(), key=lambda r: int(r.get("sequence_run_id", -1)))[-max_history:]
    latest_rows = {r["id"]: r for r in current["contributors"]}
    attribution: list[dict] = []
    for cid in sorted(latest_rows):
        latest = latest_rows[cid]
        final_class, evidence = _classify(records, cid, latest["cohort"], min_checkpoints)
        if final_class not in FINAL_CLASSES:
            raise RuntimeError("R2_FINAL_CLASS_INTERNAL_ERROR")
        attribution.append({
            "id": cid,
            "repository": latest["repository"],
            "cohort": latest["cohort"],
            "latest_head_sha": latest["head_sha"],
            "class": final_class,
            "evidence": evidence,
        })
    mature = len(records) >= min_checkpoints
    obj: dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "status": "REPLICATED_EVIDENCE_READY" if mature else "ACCUMULATING_SUCCESSIVE_CHECKPOINTS",
        "latest_checkpoint_sha256": current["checkpoint_sha256"],
        "latest_source_digest": current["source_digest"],
        "latest_checkpoint_sequence_run_id": current["sequence_run_id"],
        "seed_replication": {
            "minimum_seeds_per_checkpoint": min_seeds,
            "latest_seed_count": current["seed_count"],
            "latest_seeds": current["seeds"],
        },
        "checkpoint_replication": {
            "minimum_successive_checkpoints": min_checkpoints,
            "observed_checkpoint_count": len(records),
            "checkpoint_sha256s": [r["checkpoint_sha256"] for r in records],
            "sequence_run_ids": [r["sequence_run_id"] for r in records],
        },
        "attribution": attribution,
        "classification_policy": {
            "STABLE_SUPPORTIVE": "same supportive direction across required contexts for every checkpoint in the replication window",
            "STABLE_ADVERSE": "same adverse direction across required contexts for every checkpoint in the replication window",
            "CONTEXT_DEPENDENT": "full and core contexts reproducibly disagree in direction across the entire replication window",
            "UNRESOLVED": "insufficient checkpoints, seed disagreement, mixed direction, or unstable checkpoint-to-checkpoint evidence",
        },
        "claim_ceiling": {
            "r2_class_is_world_causality": False,
            "r2_class_is_world_truth": False,
            "r2_class_grants_authority": False,
            "automatic_weighting_change": False,
            "automatic_contributor_removal": False,
            "failed_or_missing_run_is_negative_evidence": False,
            "authority_delta": 0,
        },
        "law": "REPLICATED CONTROLLED ABLATION MAY ESTABLISH A STABLE INTERVENTION SIGNAL, NOT UNIVERSAL CAUSAL TRUTH; NO CLASS MAY DIRECTLY CHANGE AUTHORITY, WEIGHTS, OR MEMBERSHIP.",
    }
    obj["r2_sha256"] = sha256_bytes(canonical_bytes(obj))
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", action="append", required=True)
    ap.add_argument("--history-dir", required=True)
    ap.add_argument("--sequence-run-id", type=int, required=True)
    ap.add_argument("--out-checkpoint", required=True)
    ap.add_argument("--out-summary", required=True)
    ap.add_argument("--min-seeds", type=int, default=3)
    ap.add_argument("--min-checkpoints", type=int, default=3)
    args = ap.parse_args()
    ledgers = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.ledger]
    current = build_checkpoint_evidence(ledgers, sequence_run_id=args.sequence_run_id, min_seeds=args.min_seeds)
    history = load_checkpoint_history(Path(args.history_dir))
    summary = build_r2_summary(current, history, min_checkpoints=args.min_checkpoints, min_seeds=args.min_seeds)
    cp_path = Path(args.out_checkpoint)
    sum_path = Path(args.out_summary)
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    sum_path.parent.mkdir(parents=True, exist_ok=True)
    cp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    sum_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "checkpoint": current["checkpoint_sha256"],
        "seeds": current["seeds"],
        "observed_checkpoints": summary["checkpoint_replication"]["observed_checkpoint_count"],
        "classes": {r["id"]: r["class"] for r in summary["attribution"]},
        "r2_sha256": summary["r2_sha256"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
