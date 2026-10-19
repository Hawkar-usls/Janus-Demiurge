from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import random
import re
import zipfile
from pathlib import Path

import torch

from janus_model.eval_contract import (
    ADAPTIVE_REGRESSION_TOLERANCE,
    ANCHOR_REGRESSION_TOLERANCE,
    BOOTSTRAP_FINITE_LOSS_CEILING,
    DEFAULT_ANCHOR,
    EVAL_BATCHES,
    EVAL_BATCH_SIZE,
    MIN_MEANINGFUL_IMPROVEMENT_FRACTION,
    VERIFIED_NONREGRESSION_NOISE_FRACTION,
    contract_identity,
    sha256_file,
)
from janus_model.model import (
    ByteTokenizer,
    JanusModelConfig,
    JanusTinyTransformer,
    parameter_count,
)


def seed_everything(seed):
    random.seed(seed)
    torch.manual_seed(seed)


def resolve_training_seed(requested_seed):
    """Keep local runs reproducible while making GitHub Actions exploration unique.

    The historical 1337 value remains the local/default sentinel. Inside Actions,
    that sentinel is deterministically expanded from the immutable run identity,
    so every distinct run gets a distinct, replayable training trajectory.
    """
    run_id = os.environ.get("GITHUB_RUN_ID")
    if requested_seed != 1337 or not run_id:
        return requested_seed, "CLI_EXPLICIT_OR_LOCAL_DEFAULT"
    material = ":".join(
        [
            run_id,
            os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            os.environ.get("GITHUB_SHA", ""),
        ]
    ).encode("utf-8")
    derived = int.from_bytes(hashlib.sha256(material).digest()[:4], "big") & 0x7FFFFFFF
    return (derived or 1), "GITHUB_RUN_ID_DERIVED"


def tokens(path):
    return torch.tensor(
        ByteTokenizer.encode(
            Path(path).read_text(encoding="utf-8", errors="replace"),
            bos=True,
            eos=True,
        ),
        dtype=torch.long,
    )


def batch_from(stream, batch_size, context, g):
    if stream.numel() <= context + 2:
        raise RuntimeError("TOKEN_STREAM_TOO_SMALL")
    starts = torch.randint(
        0,
        stream.numel() - context - 1,
        (batch_size,),
        generator=g,
    )
    x = torch.stack([stream[int(s) : int(s) + context] for s in starts])
    y = torch.stack([stream[int(s) + 1 : int(s) + context + 1] for s in starts])
    return x, y


@torch.no_grad()
def eval_loss(model, stream, batches, batch_size, seed):
    model.eval()
    g = torch.Generator().manual_seed(seed)
    vals = []
    for _ in range(batches):
        x, y = batch_from(stream, batch_size, model.config.context_length, g)
        _, loss = model(x, y)
        vals.append(float(loss.item()))
    return sum(vals) / len(vals)


MAX_CHECKPOINT_BYTES = 100_000_000  # GitHub's per-file limit; larger weights need sharding.
MAX_CHECKPOINT_UNCOMPRESSED_BYTES = 100_000_000
MAX_MODEL_PARAMETERS = 30_000_000
PROMOTED_CHECKPOINT = Path(__file__).resolve().parent / "checkpoints" / "promoted.pt"
PROMOTED_STATE = Path(__file__).resolve().parent / "state" / "JANUS_MODEL_STATE.json"


def _checkpoint_digest(path, expected_sha256):
    """Verify the byte identity *before* any PyTorch deserialization.

    The canonical promoted model must match its committed state even when the
    caller did not pass a hash. Other checkpoints may supply an explicit hash.
    This is an integrity check, not a signature against rewritten Git history.
    """
    path = Path(path)
    if expected_sha256 is not None and (
        not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
    ):
        raise RuntimeError("JANUS_CHECKPOINT_EXPECTED_DIGEST_INVALID")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RuntimeError("JANUS_CHECKPOINT_UNREADABLE") from exc
    if size <= 0 or size > MAX_CHECKPOINT_BYTES:
        raise RuntimeError("JANUS_CHECKPOINT_SIZE_REJECTED")
    if path.resolve() == PROMOTED_CHECKPOINT.resolve():
        try:
            state = json.loads(PROMOTED_STATE.read_text(encoding="utf-8"))
            state_sha256 = state["checkpoint_sha256"]
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise RuntimeError("JANUS_PROMOTED_CHECKPOINT_STATE_MISSING_OR_INVALID") from exc
        if not isinstance(state_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", state_sha256):
            raise RuntimeError("JANUS_PROMOTED_CHECKPOINT_STATE_MISSING_OR_INVALID")
        if expected_sha256 is not None and not hmac.compare_digest(expected_sha256, state_sha256):
            raise RuntimeError("JANUS_CHECKPOINT_EXPECTED_DIGEST_CONFLICT")
        expected_sha256 = state_sha256
    if expected_sha256 is not None:
        digest = sha256_file(path)
        if not hmac.compare_digest(digest, expected_sha256):
            raise RuntimeError("JANUS_CHECKPOINT_SHA256_MISMATCH")

    # Refuse legacy pickle-only files and grossly oversized ZIP payloads even
    # before calling the restricted weights-only unpickler.
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 4096 or sum(info.file_size for info in members) > MAX_CHECKPOINT_UNCOMPRESSED_BYTES:
                raise RuntimeError("JANUS_CHECKPOINT_ARCHIVE_LIMIT_REJECTED")
            if not any(info.filename.endswith("/data.pkl") for info in members):
                raise RuntimeError("JANUS_CHECKPOINT_ARCHIVE_STRUCTURE_REJECTED")
    except (zipfile.BadZipFile, OSError) as exc:
        raise RuntimeError("JANUS_CHECKPOINT_ARCHIVE_INVALID") from exc


def _validated_model_config(raw):
    if not isinstance(raw, dict):
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_INVALID")
    limits = {
        "vocab_size": (258, 258),
        "context_length": (32, 8192),
        "d_model": (16, 1024),
        "n_heads": (1, 64),
        "n_layers": (1, 32),
        "ff_mult": (1, 32),
    }
    if set(raw) != {*limits, "dropout"}:
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_INVALID")
    for name, (minimum, maximum) in limits.items():
        value = raw[name]
        if type(value) is not int or not minimum <= value <= maximum:
            raise RuntimeError("JANUS_CHECKPOINT_CONFIG_INVALID")
    dropout = raw["dropout"]
    if type(dropout) not in (float, int) or not math.isfinite(dropout) or not 0 <= dropout < 1:
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_INVALID")
    if raw["d_model"] % raw["n_heads"]:
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_INVALID")
    d = raw["d_model"]
    ff = raw["ff_mult"]
    estimated_parameters = (
        (raw["vocab_size"] + raw["context_length"] + 2) * d
        + raw["n_layers"] * ((4 + 2 * ff) * d * d + (9 + ff) * d)
    )
    if estimated_parameters > MAX_MODEL_PARAMETERS:
        raise RuntimeError("JANUS_CHECKPOINT_PARAMETER_LIMIT_REJECTED")
    return JanusModelConfig.from_dict(raw)


def load_checkpoint(path, *, expected_sha256=None):
    _checkpoint_digest(path, expected_sha256)
    # Explicit is essential: default changed in newer torch versions. Do not
    # enable safe_globals or fall back to pickle for an incompatible artifact.
    obj = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(obj, dict) or set(obj) != {"config", "model_state", "meta"}:
        raise RuntimeError("JANUS_CHECKPOINT_SCHEMA_INVALID")
    cfg = _validated_model_config(obj["config"])
    if not isinstance(obj["meta"], dict):
        raise RuntimeError("JANUS_CHECKPOINT_METADATA_INVALID")
    try:
        metadata_size = len(json.dumps(obj["meta"], allow_nan=False))
    except (TypeError, ValueError, RecursionError) as exc:
        raise RuntimeError("JANUS_CHECKPOINT_METADATA_INVALID") from exc
    if metadata_size > 1_000_000:
        raise RuntimeError("JANUS_CHECKPOINT_METADATA_LIMIT_REJECTED")
    state = obj["model_state"]
    if not isinstance(state, dict) or not state or len(state) > 4096:
        raise RuntimeError("JANUS_CHECKPOINT_STATE_INVALID")
    parameters = 0
    for name, tensor in state.items():
        if not isinstance(name, str) or not isinstance(tensor, torch.Tensor):
            raise RuntimeError("JANUS_CHECKPOINT_STATE_INVALID")
        if tensor.layout != torch.strided or not tensor.is_floating_point():
            raise RuntimeError("JANUS_CHECKPOINT_STATE_INVALID")
        parameters += tensor.numel()
        if parameters > MAX_MODEL_PARAMETERS:
            raise RuntimeError("JANUS_CHECKPOINT_PARAMETER_LIMIT_REJECTED")
        if not bool(torch.isfinite(tensor).all()):
            raise RuntimeError("JANUS_CHECKPOINT_NONFINITE_WEIGHTS")
    model = JanusTinyTransformer(cfg)
    model.load_state_dict(state, strict=True)
    return model, obj


def save_checkpoint(path, model, meta):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": model.config.to_dict(),
            "model_state": model.state_dict(),
            "meta": meta,
        },
        path,
    )


def promotion_gate(
    *,
    candidate_loss,
    incumbent_loss,
    candidate_anchor_loss,
    incumbent_anchor_loss,
    adaptive_regression_tolerance=ADAPTIVE_REGRESSION_TOLERANCE,
    anchor_regression_tolerance=ANCHOR_REGRESSION_TOLERANCE,
    nonregression_noise_fraction=VERIFIED_NONREGRESSION_NOISE_FRACTION,
    min_meaningful_improvement_fraction=MIN_MEANINGFUL_IMPROVEMENT_FRACTION,
):
    """Return a bounded verified-improvement promotion decision.

    The adaptive and frozen-anchor tolerances remain hard outer safety gates.
    Promotion is stricter than merely staying inside those tolerances: both
    protected metrics must be non-regressing inside a small noise band and at
    least one must improve by a minimum meaningful fraction. This prevents a
    long sequence of individually tolerated but cumulatively worse checkpoints.
    """

    candidate_finite = math.isfinite(candidate_loss)
    candidate_anchor_finite = math.isfinite(candidate_anchor_loss)

    if incumbent_loss is None:
        adaptive_ok = candidate_finite and candidate_loss < BOOTSTRAP_FINITE_LOSS_CEILING
        anchor_ok = (
            candidate_anchor_finite
            and candidate_anchor_loss < BOOTSTRAP_FINITE_LOSS_CEILING
        )
        promote = adaptive_ok and anchor_ok
        if promote:
            reason = "BOOTSTRAP_DUAL_FINITE_LOSS_GATE"
        elif not adaptive_ok:
            reason = "BOOTSTRAP_ADAPTIVE_GATE_REJECTED"
        else:
            reason = "BOOTSTRAP_ANCHOR_GATE_REJECTED"
        return {
            "promote": promote,
            "reason": reason,
            "adaptive_ok": adaptive_ok,
            "anchor_ok": anchor_ok,
            "adaptive_limit": BOOTSTRAP_FINITE_LOSS_CEILING,
            "anchor_limit": BOOTSTRAP_FINITE_LOSS_CEILING,
            "adaptive_nonregression": adaptive_ok,
            "anchor_nonregression": anchor_ok,
            "adaptive_meaningful_improvement": None,
            "anchor_meaningful_improvement": None,
            "meaningful_improvement": None,
            "verified_improvement_gate": promote,
        }

    incumbent_finite = math.isfinite(incumbent_loss)
    incumbent_anchor_finite = (
        incumbent_anchor_loss is not None and math.isfinite(incumbent_anchor_loss)
    )
    adaptive_limit = (
        incumbent_loss * (1.0 + adaptive_regression_tolerance)
        if incumbent_finite
        else None
    )
    anchor_limit = (
        incumbent_anchor_loss * (1.0 + anchor_regression_tolerance)
        if incumbent_anchor_finite
        else None
    )
    adaptive_ok = (
        candidate_finite
        and incumbent_finite
        and candidate_loss <= adaptive_limit
    )
    anchor_ok = (
        candidate_anchor_finite
        and incumbent_anchor_finite
        and candidate_anchor_loss <= anchor_limit
    )

    adaptive_nonregression_limit = (
        incumbent_loss * (1.0 + nonregression_noise_fraction)
        if incumbent_finite
        else None
    )
    anchor_nonregression_limit = (
        incumbent_anchor_loss * (1.0 + nonregression_noise_fraction)
        if incumbent_anchor_finite
        else None
    )
    adaptive_nonregression = (
        candidate_finite
        and incumbent_finite
        and candidate_loss <= adaptive_nonregression_limit
    )
    anchor_nonregression = (
        candidate_anchor_finite
        and incumbent_anchor_finite
        and candidate_anchor_loss <= anchor_nonregression_limit
    )

    adaptive_meaningful_limit = (
        incumbent_loss * (1.0 - min_meaningful_improvement_fraction)
        if incumbent_finite
        else None
    )
    anchor_meaningful_limit = (
        incumbent_anchor_loss * (1.0 - min_meaningful_improvement_fraction)
        if incumbent_anchor_finite
        else None
    )
    adaptive_meaningful_improvement = (
        candidate_finite
        and incumbent_finite
        and candidate_loss <= adaptive_meaningful_limit
    )
    anchor_meaningful_improvement = (
        candidate_anchor_finite
        and incumbent_anchor_finite
        and candidate_anchor_loss <= anchor_meaningful_limit
    )
    meaningful_improvement = adaptive_meaningful_improvement or anchor_meaningful_improvement
    verified_improvement_gate = (
        adaptive_ok
        and anchor_ok
        and adaptive_nonregression
        and anchor_nonregression
        and meaningful_improvement
    )
    promote = verified_improvement_gate

    if not adaptive_ok:
        reason = "CANDIDATE_REJECTED_BY_ADAPTIVE_HOLDOUT_GATE"
    elif not anchor_ok:
        reason = "CANDIDATE_REJECTED_BY_FROZEN_ANCHOR_GATE"
    elif not adaptive_nonregression or not anchor_nonregression:
        reason = "CANDIDATE_REJECTED_BY_VERIFIED_NONREGRESSION_GATE"
    elif not meaningful_improvement:
        reason = "CANDIDATE_NO_MEANINGFUL_VERIFIED_GAIN"
    else:
        reason = "CANDIDATE_PASSED_VERIFIED_IMPROVEMENT_AND_DUAL_GATES"

    return {
        "promote": promote,
        "reason": reason,
        "adaptive_ok": adaptive_ok,
        "anchor_ok": anchor_ok,
        "adaptive_limit": adaptive_limit,
        "anchor_limit": anchor_limit,
        "adaptive_nonregression_limit": adaptive_nonregression_limit,
        "anchor_nonregression_limit": anchor_nonregression_limit,
        "adaptive_meaningful_limit": adaptive_meaningful_limit,
        "anchor_meaningful_limit": anchor_meaningful_limit,
        "adaptive_nonregression": adaptive_nonregression,
        "anchor_nonregression": anchor_nonregression,
        "adaptive_meaningful_improvement": adaptive_meaningful_improvement,
        "anchor_meaningful_improvement": anchor_meaningful_improvement,
        "meaningful_improvement": meaningful_improvement,
        "verified_improvement_gate": verified_improvement_gate,
        "nonregression_noise_fraction": nonregression_noise_fraction,
        "minimum_meaningful_improvement_fraction": min_meaningful_improvement_fraction,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--corpus-manifest", required=True)
    ap.add_argument("--incumbent")
    ap.add_argument("--anchor", default=str(DEFAULT_ANCHOR))
    ap.add_argument("--out", required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=1337)
    a = ap.parse_args()

    training_seed, training_seed_source = resolve_training_seed(a.seed)
    seed_everything(training_seed)
    train_stream = tokens(a.train)
    holdout_stream = tokens(a.holdout)
    anchor_path = Path(a.anchor)
    anchor_stream = tokens(anchor_path)
    corpus = json.loads(Path(a.corpus_manifest).read_text())

    # The training seed is exploratory. Evaluation seeds stay frozen inside the
    # evaluation contract so candidates from different attempts remain comparable.
    local_contract = contract_identity(anchor_path)
    adaptive_eval_seed = int(local_contract["adaptive"]["seed"])
    anchor_eval_seed = int(local_contract["anchor"]["seed"])
    manifest_contract_sha = corpus.get("evaluation_contract_sha256")
    if manifest_contract_sha != local_contract["contract_sha256"]:
        raise RuntimeError(
            "EVALUATION_CONTRACT_MISMATCH:"
            f"manifest={manifest_contract_sha}:local={local_contract['contract_sha256']}"
        )
    if corpus.get("anchor_is_training_source") is not False:
        raise RuntimeError("ANCHOR_TRAINING_FIREWALL_NOT_SEALED")
    anchor_sha256 = local_contract["anchor"]["sha256"]

    incumbent_path = Path(a.incumbent) if a.incumbent else None
    incumbent_loss = None
    incumbent_anchor_loss = None
    parent_sha = None

    if incumbent_path and incumbent_path.exists():
        incumbent_model, _ = load_checkpoint(incumbent_path)
        incumbent_loss = eval_loss(
            incumbent_model,
            holdout_stream,
            EVAL_BATCHES,
            EVAL_BATCH_SIZE,
            adaptive_eval_seed,
        )
        incumbent_anchor_loss = eval_loss(
            incumbent_model,
            anchor_stream,
            EVAL_BATCHES,
            EVAL_BATCH_SIZE,
            anchor_eval_seed,
        )
        candidate = JanusTinyTransformer(incumbent_model.config)
        candidate.load_state_dict(incumbent_model.state_dict())
        parent_sha = sha256_file(incumbent_path)
        mode = "CONTINUE_PROMOTED_WEIGHTS"
    else:
        candidate = JanusTinyTransformer(JanusModelConfig())
        mode = "BOOTSTRAP_FROM_SCRATCH"

    candidate.train()
    opt = torch.optim.AdamW(candidate.parameters(), lr=a.lr, weight_decay=0.01)
    g = torch.Generator().manual_seed(training_seed + 1)
    losses = []
    for _ in range(a.steps):
        x, y = batch_from(
            train_stream,
            a.batch_size,
            candidate.config.context_length,
            g,
        )
        _, loss = candidate(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(candidate.parameters(), 1.0)
        opt.step()
        losses.append(float(loss.item()))

    candidate_loss = eval_loss(
        candidate,
        holdout_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        adaptive_eval_seed,
    )
    candidate_anchor_loss = eval_loss(
        candidate,
        anchor_stream,
        EVAL_BATCHES,
        EVAL_BATCH_SIZE,
        anchor_eval_seed,
    )

    gate = promotion_gate(
        candidate_loss=candidate_loss,
        incumbent_loss=incumbent_loss,
        candidate_anchor_loss=candidate_anchor_loss,
        incumbent_anchor_loss=incumbent_anchor_loss,
    )
    promote = gate["promote"]
    reason = gate["reason"]

    evaluation_contract = {
        **local_contract,
        "adaptive": {
            **local_contract["adaptive"],
            "source_digest": corpus["source_digest"],
            "registry_source_digest": corpus.get("registry_source_digest"),
            "incumbent_loss": incumbent_loss,
            "candidate_loss": candidate_loss,
            "gate_pass": gate["adaptive_ok"],
        },
        "anchor": {
            **local_contract["anchor"],
            "incumbent_loss": incumbent_anchor_loss,
            "candidate_loss": candidate_anchor_loss,
            "gate_pass": gate["anchor_ok"],
        },
        "verified_improvement": {
            **local_contract["verified_improvement"],
            "adaptive_nonregression": gate["adaptive_nonregression"],
            "anchor_nonregression": gate["anchor_nonregression"],
            "adaptive_meaningful_improvement": gate["adaptive_meaningful_improvement"],
            "anchor_meaningful_improvement": gate["anchor_meaningful_improvement"],
            "meaningful_improvement": gate["meaningful_improvement"],
            "gate_pass": gate["verified_improvement_gate"],
            "reason": reason,
        },
        "historical_comparability": (
            "ANCHOR_BASELINE_ESTABLISHED"
            if incumbent_anchor_loss is None
            else "FROZEN_ANCHOR_V1_COMPARABLE"
        ),
        "legacy_records_without_anchor": "NON_COMPARABLE_LEGACY",
    }

    out = Path(a.out)
    checkpoint_sha = None
    if promote:
        meta = {
            "source_repository": corpus["source_repository"],
            "source_commit": corpus["source_commit"],
            "source_digest": corpus["source_digest"],
            "registry_source_digest": corpus.get("registry_source_digest"),
            "evaluation_contract_sha256": local_contract["contract_sha256"],
            "parent_checkpoint_sha256": parent_sha,
            "training_mode": mode,
            "seed": training_seed,
            "training_seed": training_seed,
            "training_seed_source": training_seed_source,
            "requested_seed": a.seed,
            "evaluation_seeds": {
                "adaptive": adaptive_eval_seed,
                "anchor": anchor_eval_seed,
            },
            "steps": a.steps,
            "candidate_eval_loss": candidate_loss,
            "incumbent_eval_loss": incumbent_loss,
            "candidate_anchor_eval_loss": candidate_anchor_loss,
            "incumbent_anchor_eval_loss": incumbent_anchor_loss,
            "anchor_sha256": anchor_sha256,
            "evaluation_contract": evaluation_contract,
            "promotion_gate": gate,
            "parameter_count": parameter_count(candidate),
        }
        save_checkpoint(out, candidate, meta)
        checkpoint_sha = sha256_file(out)

    prompt = "JANUS remembers the registry. "
    context = torch.tensor(
        [ByteTokenizer.encode(prompt, bos=True)],
        dtype=torch.long,
    )
    torch.manual_seed(training_seed + 99)
    sample_ids = candidate.generate(
        context,
        max_new_tokens=96,
        temperature=0.75,
        top_k=32,
    )[0].tolist()
    sample = ByteTokenizer.decode(sample_ids)

    receipt = {
        "schema": "janus.model.training_receipt.v2",
        "status": "PROMOTED" if promote else "REJECTED",
        "promotion_reason": reason,
        "promotion_gate": gate,
        "training_mode": mode,
        "source_commit": corpus["source_commit"],
        "source_digest": corpus["source_digest"],
        "registry_source_digest": corpus.get("registry_source_digest"),
        "evaluation_contract_sha256": local_contract["contract_sha256"],
        "parent_checkpoint_sha256": parent_sha,
        "candidate_checkpoint_sha256": checkpoint_sha,
        "incumbent_eval_loss": incumbent_loss,
        "candidate_eval_loss": candidate_loss,
        "incumbent_anchor_eval_loss": incumbent_anchor_loss,
        "candidate_anchor_eval_loss": candidate_anchor_loss,
        "anchor_sha256": anchor_sha256,
        "evaluation_contract": evaluation_contract,
        "final_train_loss": losses[-1],
        "mean_last_20_train_loss": sum(losses[-20:]) / min(20, len(losses)),
        "parameter_count": parameter_count(candidate),
        "config": candidate.config.to_dict(),
        "steps": a.steps,
        "seed": training_seed,
        "training_seed": training_seed,
        "training_seed_source": training_seed_source,
        "requested_seed": a.seed,
        "evaluation_seeds": {
            "adaptive": adaptive_eval_seed,
            "anchor": anchor_eval_seed,
        },
        "sample": sample[-500:],
        "claim_ceiling": {
            "own_weights_trained": True,
            "external_llm_used_for_training_or_inference": False,
            "registry_text_is_automatic_truth": False,
            "anchor_is_training_source": False,
            "anchor_gate_can_override_failed_adaptive_gate": False,
            "training_seed_is_exploratory_only": True,
            "evaluation_seeds_frozen": True,
            "neutral_noise_zone_can_promote": False,
            "promotion_requires_meaningful_verified_gain": True,
            "general_intelligence_proven": False,
            "self_development": "BOUNDED_WEIGHT_UPDATE_WITH_VERIFIED_IMPROVEMENT_PROMOTION_GATE",
        },
    }
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "training_mode": receipt["training_mode"],
                "promotion_reason": reason,
                "source_digest": corpus["source_digest"],
                "registry_source_digest": corpus.get("registry_source_digest"),
                "evaluation_contract_sha256": local_contract["contract_sha256"],
                "training_seed": training_seed,
                "training_seed_source": training_seed_source,
                "requested_seed": a.seed,
                "evaluation_seeds": {
                    "adaptive": adaptive_eval_seed,
                    "anchor": anchor_eval_seed,
                },
                "incumbent_eval_loss": incumbent_loss,
                "candidate_eval_loss": candidate_loss,
                "incumbent_anchor_eval_loss": incumbent_anchor_loss,
                "candidate_anchor_eval_loss": candidate_anchor_loss,
                "meaningful_improvement": gate["meaningful_improvement"],
                "verified_improvement_gate": gate["verified_improvement_gate"],
                "anchor_sha256": anchor_sha256,
                "candidate_checkpoint_sha256": checkpoint_sha,
            },
            indent=2,
        )
    )
    raise SystemExit(0 if promote else 2)


if __name__ == "__main__":
    main()
