from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import torch

from janus_model.eval_contract import (
    ADAPTIVE_SEED_OFFSET,
    ANCHOR_SEED_OFFSET,
    DEFAULT_ANCHOR,
    EVAL_BATCHES,
    EVAL_BATCH_SIZE,
)
from janus_model.model import ByteTokenizer, JanusTinyTransformer
from janus_model.train_registry import batch_from, eval_loss, load_checkpoint

LEDGER_SCHEMA = "janus.keymaster.attribution_ablation_ledger.v1"
MANIFEST_SCHEMA = "janus.keymaster.learning_contribution_manifest.v2"
SIGNAL_EPSILON = 0.0005


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def tokens_from_text(text: str) -> torch.Tensor:
    return torch.tensor(ByteTokenizer.encode(text, bos=True, eos=True), dtype=torch.long)


def build_variant_specs(manifest: dict) -> list[dict]:
    contributors = manifest.get("contributors") or []
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("status") != "READY_8_OF_8":
        raise RuntimeError("ATTRIBUTION_REQUIRES_KEYMASTER_V2_READY_8_OF_8")
    if len(contributors) != 8:
        raise RuntimeError("ATTRIBUTION_REQUIRES_EXACT_EIGHT_CONTRIBUTORS")
    all_ids = [row["id"] for row in contributors]
    core = [row["id"] for row in contributors if row.get("cohort") == "CORE_5"]
    extended = [row["id"] for row in contributors if row.get("cohort") == "EXTENDED_3"]
    if len(core) != 5 or len(extended) != 3:
        raise RuntimeError("ATTRIBUTION_COHORT_PARTITION_REJECTED")

    specs = [{
        "variant_id": "FULL_8_OF_8",
        "kind": "FULL",
        "included_ids": all_ids,
        "excluded_ids": [],
    }]
    for contributor_id in all_ids:
        specs.append({
            "variant_id": f"FULL_MINUS_{contributor_id}_7_OF_8",
            "kind": "FULL_LEAVE_ONE_OUT",
            "included_ids": [x for x in all_ids if x != contributor_id],
            "excluded_ids": [contributor_id],
        })
    specs.append({
        "variant_id": "CORE_5_OF_5",
        "kind": "CORE_FULL",
        "included_ids": core,
        "excluded_ids": [x for x in all_ids if x not in core],
    })
    for contributor_id in core:
        specs.append({
            "variant_id": f"CORE_MINUS_{contributor_id}_4_OF_5",
            "kind": "CORE_LEAVE_ONE_OUT",
            "included_ids": [x for x in core if x != contributor_id],
            "excluded_ids": [contributor_id],
        })
    specs.extend([
        {
            "variant_id": "EXTENDED_3_OF_3",
            "kind": "EXTENDED_FULL",
            "included_ids": extended,
            "excluded_ids": [x for x in all_ids if x not in extended],
        },
        {
            "variant_id": "FULL_8_SHUFFLED_RECORD_ORDER_CONTROL",
            "kind": "SHUFFLED_RECORD_ORDER_CONTROL",
            "included_ids": all_ids,
            "excluded_ids": [],
        },
    ])
    if len(specs) != 17 or len({row["variant_id"] for row in specs}) != 17:
        raise RuntimeError("ATTRIBUTION_VARIANT_SET_NOT_EXACT_17")
    return specs


def load_verified_packs(keymaster_dir: Path, manifest: dict) -> dict[str, str]:
    packs: dict[str, str] = {}
    for row in manifest["contributors"]:
        path = keymaster_dir / "packs" / f"{row['id']}.txt"
        if not path.exists():
            raise RuntimeError(f"ATTRIBUTION_PACK_MISSING:{row['id']}")
        raw = path.read_bytes()
        if sha256_bytes(raw) != row.get("training_pack_sha256"):
            raise RuntimeError(f"ATTRIBUTION_PACK_HASH_MISMATCH:{row['id']}")
        if len(raw) != int(row.get("contributed_bytes", -1)) or len(raw) <= 0:
            raise RuntimeError(f"ATTRIBUTION_PACK_BYTES_MISMATCH:{row['id']}")
        packs[row["id"]] = raw.decode("utf-8", errors="replace")
    if len(packs) != 8:
        raise RuntimeError("ATTRIBUTION_PACK_COUNT_NOT_EIGHT")
    return packs


def shuffle_records(text: str, seed: int) -> str:
    marker = "</JANUS_KEYMASTER_RECORD>"
    records = []
    pos = 0
    while True:
        end = text.find(marker, pos)
        if end < 0:
            tail = text[pos:]
            if tail.strip():
                records.append(tail)
            break
        end += len(marker)
        records.append(text[pos:end])
        pos = end
    if len(records) < 2:
        raise RuntimeError("ATTRIBUTION_SHUFFLE_CONTROL_TOO_FEW_RECORDS")
    rng = random.Random(seed)
    rng.shuffle(records)
    return "\n".join(records) + "\n"


def build_variant_training_text(registry_train: str, packs: dict[str, str], spec: dict, seed: int) -> str:
    selected = "".join(packs[x] for x in spec["included_ids"])
    if spec["kind"] == "SHUFFLED_RECORD_ORDER_CONTROL":
        selected = shuffle_records(selected, seed + 991)
    return registry_train + selected


def train_variant(
    incumbent_model: JanusTinyTransformer,
    train_text: str,
    holdout_stream: torch.Tensor,
    anchor_stream: torch.Tensor,
    *,
    steps: int,
    batch_size: int,
    lr: float,
    seed: int,
) -> dict:
    random.seed(seed)
    torch.manual_seed(seed)
    candidate = JanusTinyTransformer(incumbent_model.config)
    candidate.load_state_dict(incumbent_model.state_dict())
    candidate.train()
    train_stream = tokens_from_text(train_text)
    opt = torch.optim.AdamW(candidate.parameters(), lr=lr, weight_decay=0.01)
    g = torch.Generator().manual_seed(seed + 1)
    losses = []
    for _ in range(steps):
        x, y = batch_from(train_stream, batch_size, candidate.config.context_length, g)
        _, loss = candidate(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(candidate.parameters(), 1.0)
        opt.step()
        losses.append(float(loss.item()))

    adaptive = eval_loss(
        candidate,
        holdout_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        seed + ADAPTIVE_SEED_OFFSET,
    )
    anchor = eval_loss(
        candidate,
        anchor_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        seed + ANCHOR_SEED_OFFSET,
    )
    return {
        "candidate_eval_loss": adaptive,
        "candidate_anchor_eval_loss": anchor,
        "final_train_loss": losses[-1],
        "mean_last_20_train_loss": sum(losses[-20:]) / min(20, len(losses)),
        "train_bytes": len(train_text.encode("utf-8")),
    }


def classify_signal(adaptive_marginal: float, anchor_marginal: float) -> str:
    if abs(adaptive_marginal) <= SIGNAL_EPSILON and abs(anchor_marginal) <= SIGNAL_EPSILON:
        return "INDETERMINATE_SIGNAL"
    if adaptive_marginal > SIGNAL_EPSILON and anchor_marginal > SIGNAL_EPSILON:
        return "SUPPORTIVE_SIGNAL"
    if adaptive_marginal < -SIGNAL_EPSILON and anchor_marginal < -SIGNAL_EPSILON:
        return "ADVERSE_SIGNAL"
    return "MIXED_SIGNAL"


def build_ledger(
    *,
    registry_train_path: Path,
    holdout_path: Path,
    anchor_path: Path,
    keymaster_dir: Path,
    corpus_manifest_path: Path,
    incumbent_path: Path,
    steps: int = 80,
    batch_size: int = 12,
    lr: float = 3e-4,
    seed: int = 7331,
) -> dict:
    if steps < 8 or steps > 240:
        raise RuntimeError("ATTRIBUTION_STEPS_OUT_OF_BOUNDS")
    manifest = json.loads((keymaster_dir / "manifest.json").read_text(encoding="utf-8"))
    corpus = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    if corpus.get("keymaster_contributor_count") != 8:
        raise RuntimeError("ATTRIBUTION_CORPUS_NOT_KEYMASTER_8")
    if corpus.get("keymaster_contribution_sha256") != manifest.get("contribution_sha256"):
        raise RuntimeError("ATTRIBUTION_CORPUS_KEYMASTER_IDENTITY_MISMATCH")
    if corpus.get("keymaster_adaptive_holdout_inclusion") is not False or corpus.get("keymaster_frozen_anchor_inclusion") is not False:
        raise RuntimeError("ATTRIBUTION_EVALUATION_LEAKAGE_FIREWALL_REJECTED")

    packs = load_verified_packs(keymaster_dir, manifest)
    specs = build_variant_specs(manifest)
    registry_train = registry_train_path.read_text(encoding="utf-8", errors="replace")
    holdout_stream = tokens_from_text(holdout_path.read_text(encoding="utf-8", errors="replace"))
    anchor_stream = tokens_from_text(anchor_path.read_text(encoding="utf-8", errors="replace"))
    incumbent_model, _ = load_checkpoint(incumbent_path)
    incumbent_sha = sha256_file(incumbent_path)
    incumbent_eval_loss = eval_loss(
        incumbent_model,
        holdout_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        seed + ADAPTIVE_SEED_OFFSET,
    )
    incumbent_anchor_loss = eval_loss(
        incumbent_model,
        anchor_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        seed + ANCHOR_SEED_OFFSET,
    )

    variants = []
    by_id = {}
    for spec in specs:
        text = build_variant_training_text(registry_train, packs, spec, seed)
        result = train_variant(
            incumbent_model,
            text,
            holdout_stream,
            anchor_stream,
            steps=steps,
            batch_size=batch_size,
            lr=lr,
            seed=seed,
        )
        row = {
            **spec,
            **result,
            "adaptive_delta_from_incumbent": result["candidate_eval_loss"] - incumbent_eval_loss,
            "anchor_delta_from_incumbent": result["candidate_anchor_eval_loss"] - incumbent_anchor_loss,
        }
        variants.append(row)
        by_id[spec["variant_id"]] = row

    full = by_id["FULL_8_OF_8"]
    core_full = by_id["CORE_5_OF_5"]
    attribution = []
    for contributor in manifest["contributors"]:
        cid = contributor["id"]
        loo = by_id[f"FULL_MINUS_{cid}_7_OF_8"]
        adaptive_marginal = loo["candidate_eval_loss"] - full["candidate_eval_loss"]
        anchor_marginal = loo["candidate_anchor_eval_loss"] - full["candidate_anchor_eval_loss"]
        row = {
            "id": cid,
            "repository": contributor["repository"],
            "head_sha": contributor["head_sha"],
            "cohort": contributor["cohort"],
            "full_8_marginal_adaptive_loss": adaptive_marginal,
            "full_8_marginal_anchor_loss": anchor_marginal,
            "full_8_signal": classify_signal(adaptive_marginal, anchor_marginal),
        }
        if contributor["cohort"] == "CORE_5":
            core_loo = by_id[f"CORE_MINUS_{cid}_4_OF_5"]
            core_adaptive = core_loo["candidate_eval_loss"] - core_full["candidate_eval_loss"]
            core_anchor = core_loo["candidate_anchor_eval_loss"] - core_full["candidate_anchor_eval_loss"]
            row.update({
                "core_5_marginal_adaptive_loss": core_adaptive,
                "core_5_marginal_anchor_loss": core_anchor,
                "core_5_signal": classify_signal(core_adaptive, core_anchor),
            })
        attribution.append(row)

    shuffled = by_id["FULL_8_SHUFFLED_RECORD_ORDER_CONTROL"]
    ledger = {
        "schema": LEDGER_SCHEMA,
        "status": "COMPLETE_SINGLE_SEED_DIAGNOSTIC",
        "source_digest": corpus["source_digest"],
        "registry_source_digest": corpus.get("registry_source_digest"),
        "keymaster_contribution_sha256": manifest["contribution_sha256"],
        "keymaster_training_pack_sha256": manifest["training_pack_sha256"],
        "checkpoint_sha256": incumbent_sha,
        "incumbent_eval_loss": incumbent_eval_loss,
        "incumbent_anchor_eval_loss": incumbent_anchor_loss,
        "seed": seed,
        "steps_per_variant": steps,
        "batch_size": batch_size,
        "learning_rate": lr,
        "variant_count": len(variants),
        "variants": variants,
        "attribution": attribution,
        "shuffled_control": {
            "variant_id": shuffled["variant_id"],
            "adaptive_loss_delta_vs_full": shuffled["candidate_eval_loss"] - full["candidate_eval_loss"],
            "anchor_loss_delta_vs_full": shuffled["candidate_anchor_eval_loss"] - full["candidate_anchor_eval_loss"],
            "interpretation": "ORDER_SENSITIVITY_CONTROL_ONLY__NOT_SEMANTIC_NULL",
        },
        "claim_ceiling": {
            "single_seed_establishes_causality": False,
            "ablation_signal_is_world_truth": False,
            "ablation_signal_grants_authority": False,
            "automatic_contributor_removal": False,
            "automatic_weighting_change": False,
            "same_incumbent_checkpoint": True,
            "same_seed": True,
            "same_steps": True,
            "same_holdout": True,
            "same_frozen_anchor": True,
            "authority_delta": 0,
        },
    }
    ledger["ledger_sha256"] = sha256_bytes(canonical_bytes(ledger))
    return ledger


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-train", required=True)
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--keymaster-dir", required=True)
    ap.add_argument("--corpus-manifest", required=True)
    ap.add_argument("--incumbent", required=True)
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--out", required=True)
    ap.add_argument("--steps", type=int, default=80)
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=7331)
    args = ap.parse_args()
    ledger = build_ledger(
        registry_train_path=Path(args.registry_train),
        holdout_path=Path(args.holdout),
        anchor_path=Path(args.anchor),
        keymaster_dir=Path(args.keymaster_dir),
        corpus_manifest_path=Path(args.corpus_manifest),
        incumbent_path=Path(args.incumbent),
        steps=args.steps,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": ledger["status"],
        "variant_count": ledger["variant_count"],
        "checkpoint_sha256": ledger["checkpoint_sha256"],
        "source_digest": ledger["source_digest"],
        "ledger_sha256": ledger["ledger_sha256"],
        "signals": [
            {"id": row["id"], "full_8_signal": row["full_8_signal"], "core_5_signal": row.get("core_5_signal")}
            for row in ledger["attribution"]
        ],
        "authority_delta": ledger["claim_ceiling"]["authority_delta"],
    }, indent=2))


if __name__ == "__main__":
    main()
