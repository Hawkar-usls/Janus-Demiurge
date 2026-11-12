"""R2 experimental 256/512-byte native-model context shadow.

This never writes/checkpoints/promotes a model. It copies a verified v1
checkpoint into an ephemeral expanded architecture, preserving the original
128 positional weights and leaving added positions *untrained*. A finite
forward pass only proves the larger input fits; it does not prove improved
reasoning or memory understanding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from janus_model.hrain_memory_cortex import canonical_hash, sha256
from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer, parameter_count

ALLOWED_CONTEXTS = (256, 512)
MAX_R1_PACKET = 16_384
MAX_QUERY = 120


class ContextV2Hold(ValueError):
    pass


def clone_expanded(base: JanusTinyTransformer, context_length: int) -> JanusTinyTransformer:
    """Return an independent model, with a separate untrained positional tail."""
    import torch
    if type(context_length) is not int or context_length not in ALLOWED_CONTEXTS:
        raise ContextV2Hold("CONTEXT_CANDIDATE_NOT_ALLOWLISTED")
    if base.config.context_length != 128:
        raise ContextV2Hold("V1_SOURCE_CONTEXT_REQUIRED")
    if (base.config.vocab_size != 258 or base.config.n_heads < 1 or
            base.config.d_model % base.config.n_heads):
        raise ContextV2Hold("V1_SOURCE_ARCHITECTURE_HOLD")
    old_cfg = base.config.to_dict()
    cfg = JanusModelConfig.from_dict({**old_cfg, "context_length": context_length})
    candidate = JanusTinyTransformer(cfg)
    original = base.state_dict()
    expanded = candidate.state_dict()
    with torch.no_grad():
        for key, value in original.items():
            if key == "pos.weight":
                continue
            if key not in expanded or expanded[key].shape != value.shape:
                raise ContextV2Hold("CANDIDATE_WEIGHT_SHAPE_DRIFT")
            expanded[key].copy_(value)
        original_pos = original["pos.weight"]
        expanded["pos.weight"][:128].copy_(original_pos)
        # Conservative deterministic new-position seed; NO generalization
        # claim. These rows require separate training and prospective testing.
        for i in range(128, context_length):
            j = i % 128
            residual = torch.arange(cfg.d_model, dtype=expanded["pos.weight"].dtype, device=expanded["pos.weight"].device)
            residual = 0.005 * torch.sin(residual * (i + 1) * 0.003)
            expanded["pos.weight"][i].copy_(0.5 * original_pos[j] + residual)
        candidate.load_state_dict(expanded, strict=True)
    if any(not torch.isfinite(t).all() for t in candidate.state_dict().values()):
        raise ContextV2Hold("NONFINITE_CANDIDATE")
    # Verify independence: no storage sharing with authoritative base.
    if any(candidate.state_dict()[k].data_ptr() == v.data_ptr()
           for k, v in original.items()):
        raise ContextV2Hold("SHARED_STATE_STORAGE_FORBIDDEN")
    candidate.eval()
    return candidate


def _require_packet(text: str, receipt: dict) -> None:
    if not isinstance(receipt, dict):
        raise ContextV2Hold("R1_RECEIPT_REQUIRED")
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or claimed != canonical_hash(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"}):
        raise ContextV2Hold("R1_RECEIPT_DIGEST_HOLD")
    if (receipt.get("schema") != "janus.native.hrain_memory_cortex.r1" or
            receipt.get("status") != "VERIFIED_CONTEXT_PACKET_READY" or
            receipt.get("model_checkpoint_modified") is not False or
            receipt.get("new_training_source_admitted") is not False or
            receipt.get("native_v1_context_length_changed") is not False or
            receipt.get("holdout_used") is not False or
            receipt.get("scientific_authority_delta") != 0 or
            receipt.get("write_authority") is not False or
            receipt.get("source_content_is_instruction") is not False or
            not receipt.get("selected_sources")):
        raise ContextV2Hold("R1_RECEIPT_AUTHORITY_HOLD")
    encoded = text.encode("utf-8")
    if (len(encoded) > MAX_R1_PACKET or
            len(encoded) != receipt.get("candidate_text_bytes") or
            sha256(encoded) != receipt.get("candidate_text_sha256")):
        raise ContextV2Hold("R1_SOURCE_TEXT_SHA_HOLD")


def pack_shadow_input(query: str, r1_text: str, r1_receipt: dict, context_length: int) -> tuple[str, dict]:
    if context_length not in ALLOWED_CONTEXTS:
        raise ContextV2Hold("CONTEXT_CANDIDATE_NOT_ALLOWLISTED")
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > MAX_QUERY:
        raise ContextV2Hold("QUERY_EXCEEDS_BUDGET")
    _require_packet(r1_text, r1_receipt)
    # Source is untrusted JSON data, not a system prompt or command. We remove
    # verbose transport headers only in this derived candidate input; exact
    # path, source SHA and complete bytes remain in R1 sidecar receipt.
    sentinel = "]\n"
    first_header = r1_text.find(sentinel)
    if not r1_text.startswith("[UNTRUSTED_JSON_SOURCE ") or first_header < 0:
        raise ContextV2Hold("R1_TEXT_FRAME_INVALID")
    body = r1_text[first_header + len(sentinel):]
    end = body.find("\n[/UNTRUSTED_JSON_SOURCE]")
    if end < 0:
        raise ContextV2Hold("R1_TEXT_FRAME_INCOMPLETE")
    body = body[:end]
    # Preserve intent and response delimiter. BOS occupies a separate byte.
    prefix = f"Q:{query}\nUNTRUSTED_MEMORY_JSON:"
    suffix = "\nA:"
    budget = context_length - 1 - len((prefix + suffix).encode("utf-8"))
    if budget < 32:
        raise ContextV2Hold("SOURCE_CONTEXT_FIT_HOLD")
    excerpt = body.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
    if len(excerpt.encode("utf-8")) < 1:
        raise ContextV2Hold("EMPTY_SOURCE_EXCERPT")
    packed = prefix + excerpt + suffix
    tokens = ByteTokenizer.encode(packed, bos=True)
    if len(tokens) > context_length:
        raise ContextV2Hold("CONTEXT_OVERFLOW_HOLD")
    if "Q:" + query not in packed or not packed.endswith("\nA:"):
        raise ContextV2Hold("QUERY_EVICTED_HOLD")
    receipt = {
        "schema": "janus.native.context_candidate_r2.input.v1",
        "status": "SHADOW_PACKED_UNTRAINED_POSITIONAL_TAIL",
        "context_length_bytes": context_length,
        "model_input_bytes": len(packed.encode("utf-8")),
        "source_excerpt_bytes": len(excerpt.encode("utf-8")),
        "source_excerpt_truncated": excerpt != body,
        "source_packet_sha256": sha256(r1_text.encode("utf-8")),
        "source_receipt_sha256": r1_receipt["receipt_sha256"],
        "source_count_available": len(r1_receipt["selected_sources"]),
        "source_count_in_model_input": 1,
        "source_claim_verified": False,
        "model_weights_promoted": False,
        "scientific_authority_delta": 0,
        "external_effect_authority": False,
    }
    receipt["receipt_sha256"] = canonical_hash(receipt)
    return packed, receipt


def forward_shadow(base: JanusTinyTransformer, query: str, r1_text: str, r1_receipt: dict,
                   context_length: int) -> dict:
    import torch
    candidate = clone_expanded(base, context_length)
    packed, receipt = pack_shadow_input(query, r1_text, r1_receipt, context_length)
    ids = torch.tensor([ByteTokenizer.encode(packed, bos=True)], dtype=torch.long)
    with torch.no_grad():
        logits, _ = candidate(ids)
    if logits.shape != (1, ids.shape[1], base.config.vocab_size) or not torch.isfinite(logits).all():
        raise ContextV2Hold("CANDIDATE_FORWARD_INVALID")
    report = {
        **receipt,
        "status": "SHADOW_MODEL_FORWARD_PASS_NOT_QUALITY_PROOF",
        "v1_parameter_count": parameter_count(base),
        "candidate_parameter_count": parameter_count(candidate),
        "model_inference_executed": True,
        "model_weights_modified": False,
        "model_weights_promoted": False,
        "model_answer_quality_verified": False,
        "candidate_training_completed": False,
        "logits_finite": True,
    }
    report["receipt_sha256"] = canonical_hash({k: v for k, v in report.items() if k != "receipt_sha256"})
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-length", type=int, choices=ALLOWED_CONTEXTS, required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--r1-text", type=Path, required=True)
    ap.add_argument("--r1-receipt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise ContextV2Hold("REPORT_EXISTS")
    # SHA-preflight for authoritative promoted v1 before torch.load. No
    # candidate checkpoints are serialized or promoted in this run.
    from janus_model.train_registry import load_checkpoint
    from janus_model.checkpoint_admission import PROMOTED
    model, _ = load_checkpoint(PROMOTED)
    raw = args.r1_text.read_bytes()
    if len(raw) > MAX_R1_PACKET:
        raise ContextV2Hold("R1_TEXT_LIMIT")
    receipt = json.loads(args.r1_receipt.read_text(encoding="utf-8"))
    report = forward_shadow(model, args.query, raw.decode("utf-8"), receipt, args.context_length)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status", "context_length_bytes", "model_input_bytes",
        "source_excerpt_bytes", "v1_parameter_count", "candidate_parameter_count",
        "model_answer_quality_verified", "model_weights_promoted"
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
