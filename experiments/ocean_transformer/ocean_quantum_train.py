#!/usr/bin/env python3
"""Train the EXISTING JanusTinyTransformer on synthetic quantum measurement data.

Supervised target: ordinary Born-rule projective-readout sample AFTER a public
preparation and unread dephasing setting. This demonstrates statistical
learning, NOT controllable collapse, future sensing, tachyon electron or a
physical retrocausal channel. Validation and test are independent RNG streams.
The analytical Born oracle is a comparison baseline, not a teacher for labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from janus_model.model import JanusModelConfig, JanusTinyTransformer, parameter_count
import measurement_priors as priors

torch.set_num_threads(1)
SEED = 20261109
CONFIG = JanusModelConfig(
    vocab_size=16, context_length=3, d_model=24, n_heads=2,
    n_layers=1, ff_mult=2, dropout=0.0
)


def draw(n: int, seed: int):
    rng = random.Random(seed)
    x, y, theoretical = [], [], []
    for _ in range(n):
        ti = rng.randrange(len(priors.THETAS))
        basis = priors.BASES[rng.randrange(len(priors.BASES))]
        qi = rng.randrange(len(priors.DEPHASING))
        p = priors.born_probability(ti, basis, qi)
        x.append(priors.model_tokens(ti, basis, qi))
        y.append(int(rng.random() < p))
        theoretical.append(p)
    return (torch.tensor(x, dtype=torch.long),
            torch.tensor(y, dtype=torch.long),
            torch.tensor(theoretical, dtype=torch.float32))


def evaluate(model, data):
    x, y, oracle = data
    model.eval()
    with torch.no_grad():
        logits, _ = model(x)
        probs = F.softmax(logits[:, -1, :2], -1)[:, 1]
        brier = float(((probs-y.float())**2).mean())
        logloss = float(F.binary_cross_entropy(probs.clamp(1e-7, 1-1e-7), y.float()))
        oracle_brier = float(((oracle-y.float())**2).mean())
        oracle_logloss = float(F.binary_cross_entropy(
            oracle.clamp(1e-7, 1-1e-7), y.float()))
        return {
            "cases": len(y),
            "accuracy": round(float(((probs>=.5)==y.bool()).float().mean()), 6),
            "brier": round(brier, 6), "logloss": round(logloss, 6),
            "analytic_born_oracle_brier": round(oracle_brier, 6),
            "analytic_born_oracle_logloss": round(oracle_logloss, 6),
        }


def train(steps: int, batch: int, output: str, wolfram_receipt: str | None = None):
    if not 1 <= steps <= 300 or not 8 <= batch <= 512:
        raise ValueError("OUT_OF_BOUNDS_TRAINING_BUDGET")
    out = Path(output)
    if out.exists():
        raise RuntimeError("REFUSE_OVERWRITE_EXISTING_RESEARCH_RUN")
    wolfram_attachment = {
        "status": "NOT_PROVIDED",
        "physical_retrocausality_proven": False,
        "used_as_training_labels": False,
    }
    if wolfram_receipt is not None:
        # Receipt can annotate research evidence but cannot provide targets.
        # The upstream response is numerically verified, not provider-signed.
        import wolfram_alpha_bridge as wolfram
        raw = Path(wolfram_receipt).read_bytes()
        upstream = json.loads(raw.decode("utf-8"))
        wolfram.verify_live_math_receipt(upstream)
        wolfram_attachment = {
            "status": "LIVE_MATH_RECEIPT_VALIDATED_RESEARCH_ONLY",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(upstream["queries"]),
            "provider_signature_verified": False,
            "physical_retrocausality_proven": False,
            "used_as_training_labels": False,
        }
    torch.manual_seed(SEED)
    model = JanusTinyTransformer(CONFIG)
    initial = JanusTinyTransformer(CONFIG)
    initial.load_state_dict(model.state_dict())
    initial.eval()
    optim = torch.optim.AdamW(model.parameters(), lr=0.004, weight_decay=0.0005)
    rng = random.Random(SEED + 17)
    train_x, train_y, _ = draw(8192, SEED + 100)
    test = draw(2048, SEED + 9001)
    before = evaluate(initial, test)
    model.train()
    for _ in range(steps):
        ids = torch.tensor([rng.randrange(len(train_y)) for _ in range(batch)])
        logits, _ = model(train_x[ids])
        loss = F.cross_entropy(logits[:, -1, :2], train_y[ids])
        if not torch.isfinite(loss):
            raise RuntimeError("NONFINITE_TRAINING_LOSS")
        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optim.step()
    after = evaluate(model, test)
    # Fresh, label-independent random future control. Not a proposed
    # algorithm for detecting future messages or a validation target.
    random_control_x = test[0]
    secure = os.urandom(len(random_control_x))
    independent_y = torch.tensor([b & 1 for b in secure], dtype=torch.long)
    control = evaluate(model, (random_control_x, independent_y, torch.full(
        (len(independent_y),), .5, dtype=torch.float32)))
    assessment = (
        "SYNTHETIC_BORN_RULE_LEARNING_GAIN_ONLY"
        if after["brier"] + 0.01 < before["brier"]
        else "HOLD_NO_MEASURED_SYNTHETIC_GAIN"
    )
    out.mkdir(parents=True)
    ckpt = out / "ocean_measurement_candidate.pt"
    torch.save({
        "model": model.state_dict(), "config": CONFIG.to_dict(),
        "source": priors.SCHEMA, "production_promotion": False,
    }, ckpt)
    report = {
        "schema": "janus.ocean.measurement_transformer_benchmark.v1",
        "source_code": "experiments/ocean_transformer/ocean_quantum_train.py",
        "model": "JanusTinyTransformer",
        "configuration": CONFIG.to_dict(),
        "parameters": parameter_count(model),
        "training_rows": len(train_y),
        "training_steps": steps,
        "test_rows": len(test[1]),
        "independent_test_seed": SEED+9001,
        "untrained_holdout": before,
        "trained_holdout": after,
        "independent_future_random_negative_control": control,
        "ocean_candidate_sha256": hashlib.sha256(ckpt.read_bytes()).hexdigest(),
        "assessment": assessment,
        "dataset_type": "SYNTHETIC_STANDARD_QUANTUM_MEASUREMENT",
        "future_labels_seen_at_training": False,
        "postselection_on_test_results": False,
        "physically_triggered_wavefunction_collapse": False,
        "proven_tachyons_or_retrocausal_communication": False,
        "production_checkpoint_changed": False,
        "wolfram_source_class": "PUBLIC_MATHEMATICS_OPTIONAL_NOT_TRAINING_LABELS",
        "wolfram_advisory_receipt": wolfram_attachment,
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "assessment": assessment,
        "before_brier": before["brier"], "after_brier": after["brier"],
        "oracle_brier": after["analytic_born_oracle_brier"],
        "future_random_control_accuracy": control["accuracy"],
        "production_changed": False,
    }, sort_keys=True))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wolfram-receipt", help="Optional validated live math receipt (cannot be offline fixture)")
    args = parser.parse_args()
    train(args.steps, args.batch, args.output, wolfram_receipt=args.wolfram_receipt)


if __name__ == "__main__":
    main()
