#!/usr/bin/env python3
"""ESSENCE v3.7: bounded neural donor derived from the user's JGPT CODEX.

The historic MIT source is never imported/executed. Reimplements its
ByteTransformer, gradient protection, EMA and INT8 shadow evaluation as an
ephemeral, read-only, CPU research microcore. No NAS, pickle or egress.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "janus.essence.codex_gpt_neural_donor/3.7"
SOURCE = {
    "library_name": "JGPT_CODEX(2).py",
    "source_sha256": "3b594ad258d8afb4d571f5cae9e87f0194e246a9a1fe517fd87a6df1b5f69606",
    "library_file_id": "file_000000001d6071f48c57d0de1b02e391",
    "size_bytes": 36341,
    "license": "MIT",
    "adapted": ["ByteTransformer", "GradientBlackholeGuard",
                "RollingEMA", "INT8 shadow exporter"],
    "legacy_python_executed": False,
}
BLOCK, EMBED, MAX_STEPS, MAX_FILE_BYTES = 24, 32, 20, 80000
SPLIT = {
    "train": ("tools/essence_v36_juxtapose_exact.py",
              "tools/essence_v32_keymaster_memory.py"),
    "val": ("tools/essence_v33_epistemic_exchange.py",
            "tools/essence_v19_gradirnya.py"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_corpus(root, split=SPLIT):
    base = Path(root).resolve(strict=True)
    require(set(split) == {"train", "val"}, "INVALID_SPLIT")
    names = list(split["train"]) + list(split["val"])
    require(len(names) == 4 and len(names) == len(set(names)),
            "UNTRUSTED_CORPUS_LIST")
    chunks, hashes, paths = {}, set(), {}
    for part in ("train", "val"):
        raw, meta = [], []
        for name in split[part]:
            require(isinstance(name, str) and name.startswith("tools/")
                    and name.endswith(".py"), "UNSAFE_CORPUS_FILE")
            path = base / name
            require(path.resolve().is_relative_to(base) and
                    not path.is_symlink() and path.is_file(),
                    "UNSAFE_CORPUS_PATH")
            require(128 <= path.stat().st_size <= MAX_FILE_BYTES,
                    "INVALID_CORPUS_SIZE")
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            require(digest not in hashes, "TRAIN_VAL_CONTENT_LEAKAGE")
            hashes.add(digest)
            raw.append(content)
            meta.append({"path": name, "sha256": digest,
                         "bytes": len(content)})
        chunks[part], paths[part] = b"\n\n".join(raw), meta
        require(len(chunks[part]) > BLOCK * 8, "SHORT_CORPUS")
    return chunks, paths


def new_model(torch):
    nn = torch.nn

    class ByteTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok = nn.Embedding(256, EMBED)
            self.pos = nn.Embedding(BLOCK, EMBED)
            layer = nn.TransformerEncoderLayer(
                d_model=EMBED, nhead=4, dim_feedforward=EMBED * 4,
                dropout=0.0, activation="gelu", batch_first=True,
                norm_first=True)
            self.transformer = nn.TransformerEncoder(
                layer, num_layers=1, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(EMBED)
            self.head = nn.Linear(EMBED, 256, bias=False)

        def forward(self, idx):
            length = idx.shape[1]
            require(0 < length <= BLOCK, "INVALID_BLOCK")
            x = self.tok(idx) + self.pos(
                torch.arange(length, device=idx.device))[None, :, :]
            mask = torch.triu(torch.full(
                (length, length), float("-inf"), device=idx.device), diagonal=1)
            return self.head(self.norm(self.transformer(x, mask=mask)))

    return ByteTransformer()


def val_loss(torch, model, val):
    """Immutable deterministic window positions for each evaluation."""
    model.eval()
    pos = [k * (len(val) - BLOCK - 1) // 15 for k in range(16)]
    x = torch.stack([val[p:p+BLOCK] for p in pos])
    y = torch.stack([val[p+1:p+BLOCK+1] for p in pos])
    with torch.no_grad():
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(logits.reshape(-1, 256),
                                                  y.reshape(-1))
    result = float(loss.item())
    require(math.isfinite(result), "NONFINITE_VAL_LOSS")
    return result


def quant_shadow(torch, model, val):
    state = model.state_dict()
    dequant = {}
    digest = hashlib.sha256()
    count = 0
    max_error = 0.0
    for key in sorted(state):
        tensor = state[key].detach().float().cpu().contiguous()
        require(bool(torch.isfinite(tensor).all()), "NONFINITE_WEIGHT")
        scale = float(tensor.abs().max()) / 127.0 or 1.0
        q = torch.round(tensor / scale).clamp(-127, 127).to(torch.int8)
        recovered = q.float() * scale
        count += tensor.numel()
        max_error = max(max_error, float((tensor-recovered).abs().max()))
        dequant[key] = recovered
        digest.update(key.encode("utf-8") + b"\0" + bytes((v & 255) for v in q.reshape(-1).tolist()) +
                      scale.hex().encode("ascii"))
    shadow = new_model(torch)
    shadow.load_state_dict(dequant, strict=True)
    return {
        "method": "PER_TENSOR_INT8_DEQUANTIZED_FP32_REPLAY",
        "parameter_count": count,
        "fp32_parameter_bytes": count * 4,
        "estimated_int8_plus_scale_bytes": count + 4 * len(state),
        "maximum_absolute_weight_error": max_error,
        "int8_shadow_validation_loss": val_loss(torch, shadow, val),
        "quant_state_sha256": digest.hexdigest(),
        "native_int8_speed_proven": False,
        "quant_weights_deployed": False,
    }


def run(root, *, steps=12, split=SPLIT, verify_juxtapose=True):
    require(type(steps) is int and 1 <= steps <= MAX_STEPS,
            "UNBOUNDED_TRAINING_STEPS")
    content, manifests = read_corpus(root, split)
    import torch  # do not import legacy JGPT_CODEX
    torch.set_num_threads(1)
    torch.manual_seed(3701)
    model = new_model(torch)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001,
                                   weight_decay=0.01)
    train = torch.tensor(list(content["train"]), dtype=torch.long)
    val = torch.tensor(list(content["val"]), dtype=torch.long)
    baseline = val_loss(torch, model, val)
    ema, best, clipped, rejected = None, baseline, 0, 0
    for k in range(steps):
        model.train()
        starts = torch.randint(len(train)-BLOCK-1, (4,))
        x = torch.stack([train[i:i+BLOCK] for i in starts])
        y = torch.stack([train[i+1:i+BLOCK+1] for i in starts])
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(logits.reshape(-1, 256),
                                                  y.reshape(-1))
        require(bool(torch.isfinite(loss)), "NONFINITE_TRAIN_LOSS")
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        if not all(bool(torch.isfinite(g).all()) for g in grads):
            rejected += 1
            optimizer.zero_grad(set_to_none=True)
            continue
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if not math.isfinite(float(norm)):
            rejected += 1
            optimizer.zero_grad(set_to_none=True)
            continue
        clipped += int(float(norm) > 1.0)
        optimizer.step()
        if k == steps-1 or k % 4 == 3:
            current = val_loss(torch, model, val)
            best = min(best, current)
            ema = current if ema is None else 0.8 * ema + 0.2 * current
    final = val_loss(torch, model, val)
    quant = quant_shadow(torch, model, val)
    juxtapose_receipt = None
    if verify_juxtapose:
        from tools import essence_v36_juxtapose_exact as jux
        exact = jux.field_search([[1, 2], [-1, 3], [2, -3]], 80)
        require(exact["coverage_ratio"] == 1.0 and
                exact["status"] == "EXACT_TRANSITION_WITNESS_FOUND" and
                exact["exact_verifier_has_veto"] is True and
                exact["production_authority"] is False,
                "JUXTAPOSE_EXACT_VETO_FAILED")
        juxtapose_receipt = exact["receipt_sha256"]
    result = {
        "schema": SCHEMA,
        "source": SOURCE,
        "training": manifests["train"],
        "validation": manifests["val"],
        "split": "FILE_DISJOINT_AND_SHA256_VETO",
        "steps": steps,
        "baseline_val_loss": baseline,
        "final_val_loss": final,
        "best_observed_val_loss": best,
        "validation_ema": ema,
        "grad_clipped_steps": clipped,
        "grad_rejected_nonfinite_steps": rejected,
        "quantization": quant,
        "juxtapose_exact_receipt_sha256": juxtapose_receipt,
        "actual_ephemeral_neural_weight_updates": steps > rejected,
        "production_weights_modified": False,
        "external_generalization_proven": False,
        "new_generation_promoted": False,
        "legacy_monolith_executed": False,
        "auto_install_microkernel": False,
        "production_authority": False,
    }
    result["receipt_sha256"] = seal(result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--steps", type=int, default=12)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    require(not args.out.exists() and not args.out.is_symlink(),
            "IMMUTABLE_RECEIPT_PATH_REQUIRED")
    receipt = run(args.repo_root, steps=args.steps)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"steps": receipt["steps"],
                      "baseline_val_loss": receipt["baseline_val_loss"],
                      "final_val_loss": receipt["final_val_loss"],
                      "production_authority": False,
                      "receipt_sha256": receipt["receipt_sha256"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
