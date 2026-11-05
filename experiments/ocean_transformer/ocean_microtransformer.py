#!/usr/bin/env python3
"""JANUS Ocean Server: bounded federated training of the existing JanusTinyTransformer.

This is an observable synthetic next-token forecasting benchmark, not a physical
retrocausal channel, SHA-256 preimage predictor, or production model updater.
Rivers produce disjoint seeded datasets and local training deltas. The Ocean
aggregates their model weights, evaluates genuinely disjoint holdout data, and
calibrates probabilities using separate calibration data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from janus_model.model import JanusModelConfig, JanusTinyTransformer, parameter_count

torch.set_num_threads(1)
INIT_SEED = 20261106
CFG = JanusModelConfig(
    vocab_size=4, context_length=8, d_model=16, n_heads=2,
    n_layers=1, ff_mult=2, dropout=0.0,
)
# Token 2: "copy the final bit"; token 3: "invert the final bit".
# This requires a contextual instruction and cannot be solved by just
# predicting the majority label. 5% stochastic label noise is deliberate.
NOISE_PROB = 0.05


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_init() -> JanusTinyTransformer:
    torch.manual_seed(INIT_SEED)
    return JanusTinyTransformer(CFG)


def draw(n: int, rng: torch.Generator):
    mode = torch.randint(0, 2, (n,), generator=rng)
    bits = torch.randint(0, 2, (n, CFG.context_length - 1), generator=rng)
    sequence = torch.cat(((mode + 2).unsqueeze(1), bits), dim=1).long()
    noise = (torch.rand(n, generator=rng) < NOISE_PROB).long()
    target = (bits[:, -1] ^ mode ^ noise).long()
    return sequence, target


@torch.no_grad()
def predict_logits(model, x, batch_size=512):
    model.eval()
    return torch.cat([
        model(x[i:i + batch_size])[0][:, -1, :2].float()
        for i in range(0, len(x), batch_size)
    ], dim=0)


def scores(logits, y, temperature=1.0):
    probs = torch.softmax(logits / temperature, dim=-1)[:, 1]
    confidence = torch.maximum(probs, 1 - probs)
    correct = (probs >= 0.5) == y.bool()
    ece = 0.0
    for i in range(10):
        mask = (confidence >= 0.5 + 0.05 * i) & (
            (confidence < 0.5 + 0.05 * (i + 1)) if i < 9 else
            (confidence <= 1.0)
        )
        if bool(mask.any()):
            ece += float(mask.float().mean()) * abs(
                float(correct[mask].float().mean()) - float(confidence[mask].mean())
            )
    return {
        "n": int(len(y)),
        "accuracy": round(float(correct.float().mean()), 6),
        "nll": round(float(F.cross_entropy(logits / temperature, y)), 6),
        "brier": round(float(((probs - y.float()) ** 2).mean()), 6),
        "ece10": round(ece, 6),
    }


def worker(args):
    begin = time.monotonic()
    wid = args.worker
    assert 0 <= wid < 256
    model = model_init()
    optim = torch.optim.AdamW(model.parameters(), lr=0.006, weight_decay=0.001)
    rng = torch.Generator().manual_seed(800000 + wid * 1009)
    # Independent training and monitor samples; neither is reused for final holdout.
    monitor_rng = torch.Generator().manual_seed(2000000 + wid * 1009)
    monitor_x, monitor_y = draw(768, monitor_rng)
    initial = scores(predict_logits(model, monitor_x), monitor_y)
    model.train()
    count = 0
    for step in range(args.steps):
        if step >= 80 and time.monotonic() - begin > args.train_seconds:
            break
        x, y = draw(args.batch_size, rng)
        optim.zero_grad(set_to_none=True)
        logits, _ = model(x)
        loss = F.cross_entropy(logits[:, -1, :2], y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optim.step()
        count += 1
    final = scores(predict_logits(model, monitor_x), monitor_y)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    weight_path = out / "weights.pt"
    torch.save({
        "worker_id": wid, "configuration": CFG.to_dict(),
        "source_samples": count * args.batch_size,
        "model_state": {k: v.detach().cpu() for k, v in model.state_dict().items()},
    }, weight_path)
    record = {
        "schema": "janus.ocean.river.v1",
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "worker_id": wid,
        "source": "synthetic_seeded_lookback_parity_with_mode",
        "training_seed": 800000 + wid * 1009,
        "initial_model_seed": INIT_SEED,
        "training_steps_completed": count,
        "training_samples_generated": count * args.batch_size,
        "model_parameters": parameter_count(model),
        "training_seconds": round(time.monotonic() - begin, 3),
        "monitor_before": initial,
        "monitor_after": final,
        "weights_sha256": sha256(weight_path),
        "physical_retrocausal_channel": False,
        "dataset_class": "SYNTHETIC_FORECAST__NOT_FUTURE_RANDOM_SHA",
    }
    (out / "river.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))


def aggregate(args):
    start = time.monotonic()
    root = Path(args.input)
    records = sorted(root.glob("*/river.json"))
    if len(records) != args.expected_workers:
        raise SystemExit(
            f"FAIL_CLOSED: expected {args.expected_workers} rivers, got {len(records)}"
        )
    init = model_init()
    state = init.state_dict()
    seen = set()
    weighted = None
    total = 0
    evidence = []
    for r in records:
        info = json.loads(r.read_text())
        wid = info["worker_id"]
        if wid in seen or wid < 0 or wid >= args.expected_workers:
            raise SystemExit("FAIL_CLOSED: duplicate or unexpected worker")
        seen.add(wid)
        path = r.parent / "weights.pt"
        if sha256(path) != info["weights_sha256"]:
            raise SystemExit("FAIL_CLOSED: corrupted weights")
        obj = torch.load(path, map_location="cpu", weights_only=True)
        if obj["worker_id"] != wid or obj["configuration"] != CFG.to_dict():
            raise SystemExit("FAIL_CLOSED: incompatible river")
        count = obj["source_samples"]
        if not isinstance(count, int) or count <= 0:
            raise SystemExit("FAIL_CLOSED: invalid data count")
        candidate = obj["model_state"]
        if set(candidate) != set(state):
            raise SystemExit("FAIL_CLOSED: state layout mismatch")
        for k in state:
            v = candidate[k]
            if v.shape != state[k].shape or v.dtype != state[k].dtype:
                raise SystemExit("FAIL_CLOSED: tensor layout mismatch")
            if not torch.isfinite(v).all():
                raise SystemExit("FAIL_CLOSED: nonfinite weights")
        if weighted is None:
            weighted = {
                k: torch.zeros_like(v, dtype=torch.float64)
                for k, v in candidate.items()
            }
        for k, v in candidate.items():
            weighted[k] += v.double() * count
        total += count
        evidence.append(info)
    assert seen == set(range(args.expected_workers))
    for k, v in weighted.items():
        weighted[k] = (v / total).to(dtype=state[k].dtype)
    ocean = model_init()
    ocean.load_state_dict(weighted, strict=True)
    init.eval()
    ocean.eval()

    # Calibration and held-out distributions are disjoint by seed AND by
    # independent Generator states, and never used in training.
    cg = torch.Generator().manual_seed(990019)
    hx = torch.Generator().manual_seed(772239)
    cal_x, cal_y = draw(4096, cg)
    hold_x, hold_y = draw(8192, hx)
    init_logits = predict_logits(init, hold_x)
    final_logits = predict_logits(ocean, hold_x)
    cal_logits = predict_logits(ocean, cal_x)

    candidates = [0.5, 0.65, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
    optimal_t = min(
        candidates, key=lambda t: float(F.cross_entropy(cal_logits / t, cal_y))
    )
    baseline = scores(init_logits, hold_y)
    raw = scores(final_logits, hold_y)
    calibrated = scores(final_logits, hold_y, optimal_t)
    # A deliberately strong, known-data generating process upper baseline
    # and naive 0.5 baseline, NOT a future-peeking model.
    last_bit = hold_x[:, -1]
    mode = hold_x[:, 0] - 2
    true_rule_accuracy = float(((last_bit ^ mode) == hold_y).float().mean())
    # A negative control: future OS-random binary outcomes independent of x.
    secure_bytes = secrets.token_bytes(len(hold_y))
    crypto_y = torch.tensor([byte & 1 for byte in secure_bytes], dtype=torch.long)
    crypto_control = scores(final_logits, crypto_y, optimal_t)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    weights_path = out / "ocean_candidate.pt"
    torch.save({
        "configuration": CFG.to_dict(),
        "model_state": ocean.state_dict(),
        "training_sample_count": total,
        "source_worker_ids": sorted(seen),
        "calibration_temperature": optimal_t,
        "production_promotion": False,
    }, weights_path)
    result = {
        "schema": "janus.ocean.microtransformer.result.v1",
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "architecture": "JanusTinyTransformer from Janus-Demiurge/janus_model/model.py",
        "configuration": CFG.to_dict(),
        "parameter_count": parameter_count(ocean),
        "worker_count_requested": args.expected_workers,
        "worker_count_verified": len(seen),
        "workers": evidence,
        "training_samples_generated": total,
        "aggregation": "weighted Federated Averaging of identical-initialized tiny transformer weights",
        "calibration_method": "held-out grid-search temperature scaling",
        "calibration_temperature": optimal_t,
        "holdout_distribution": "synthetic sequence task with independently seeded hidden labels",
        "holdout_initial_untrained": baseline,
        "holdout_merged_raw": raw,
        "holdout_merged_calibrated": calibrated,
        "holdout_rule_oracle_accuracy_upper_bound": round(true_rule_accuracy, 6),
        "holdout_random_guess_accuracy_reference": 0.5,
        "future_crypto_random_control": crypto_control,
        "ocean_weights_sha256": sha256(weights_path),
        "model_training_seconds_total_workers": round(
            sum(w["training_seconds"] for w in evidence), 3
        ),
        "aggregation_seconds": round(time.monotonic() - start, 3),
        "assessment": (
            "DEVELOPMENT_ONLY__SYNTHETIC_FORECAST_LEARNED__NOT_FUTURE_PREDICTION"
            if calibrated["nll"] < baseline["nll"] - 0.01
            and calibrated["accuracy"] > 0.55
            else "HOLD_NO_CONFIRMED_GAIN"
        ),
        "physical_retrocausality_proven": False,
        "sha256_prediction_proven": False,
        "production_checkpoint_changed": False,
        "oracle_integration": "AURA-type probabilistic scoring only; no AURA runtime or oracle secrets accessed",
        "proof_boundaries": [
            "The training labels were generated by a known synthetic forward-time rule",
            "All worker results are carried as GitHub Action artifacts",
            "Temperature calibrated on separate data; holdout not used for fitting",
            "Future OS-cryptographic random bits are a negative control",
            "Do not infer backwards-in-time communication from synthetic learning",
        ],
    }
    (out / "ocean_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    summary = (
        "## JANUS Ocean Server - distributed micro-transformer\n\n"
        f"- Verified rivers: **{len(seen)}**\n"
        f"- Training examples (generated): **{total:,}**\n"
        f"- Heldout initial accuracy: **{baseline['accuracy']:.3f}**\n"
        f"- Heldout ocean accuracy: **{calibrated['accuracy']:.3f}**\n"
        f"- Heldout NLL before/after: **{baseline['nll']:.3f} / {calibrated['nll']:.3f}**\n"
        f"- Temperature calibration: **{optimal_t}**\n"
        f"- Future crypto-random negative control: **{crypto_control['accuracy']:.3f}**\n"
        f"- Gate: **{result['assessment']}**\n\n"
        "This does **not** demonstrate prediction of independent future randomness or retrocausality.\n"
    )
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a") as fh:
        fh.write(summary)
    print(json.dumps({k: v for k, v in result.items() if k != "workers"}, indent=2))


def main():
    p = argparse.ArgumentParser(description="JANUS Ocean distributed microtransformer")
    sub = p.add_subparsers(dest="command", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--worker", type=int, required=True)
    w.add_argument("--steps", type=int, default=300)
    w.add_argument("--train-seconds", type=float, default=65)
    w.add_argument("--batch-size", type=int, default=96)
    w.add_argument("--output", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--expected-workers", type=int, default=20)
    a.add_argument("--input", required=True)
    a.add_argument("--output", required=True)
    args = p.parse_args()
    if args.command == "worker":
        worker(args)
    else:
        aggregate(args)


if __name__ == "__main__":
    main()
