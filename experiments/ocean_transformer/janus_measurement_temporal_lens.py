#!/usr/bin/env python3
"""JANUS Measurement / Retro Temporal Lens v1 (research-only).

Two distinct things are deliberately separated:
  (1) standard Born probabilities, which-path dephasing, and detector sampling;
  (2) a JanusTinyTransformer trained to reproduce those ordinary predictions.

A late detector setting is a forward-time input to its own measurement, NOT
information available to an already frozen earlier readout. This module does
not create a physical tachyon, collapse mechanism, or retrocausal channel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

P0_VALUES = (0.15, 0.35, 0.5, 0.65, 0.85)
PHASES = (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)
DEPHASING = (0.0, 0.5, 1.0)
BASES = ("Z", "X", "Y")
SEED = 20261109
SCHEMA = "janus.quantum.measurement_temporal_lens.v1"
VETO = "SIMULATED_BORN_RULE_ONLY__NO_EARLY_MESSAGE__NO_PRODUCTION_PROMOTION"
MODEL_CONFIG = {
    "vocab_size": 17, "context_length": 4, "d_model": 32,
    "n_heads": 4, "n_layers": 2, "ff_mult": 2, "dropout": 0.0,
}


def born_p1(p0: float, phase: float, dephase: float, basis: str) -> float:
    """Born probability of outcome 1 after partial which-path dephasing.

    rho_01 = sqrt(p0*(1-p0)) * exp(-i*phase) * (1-dephase).
    Z measurement reads populations; X/Y read remaining coherence.
    """
    if not 0.0 <= p0 <= 1.0 or not 0.0 <= dephase <= 1.0:
        raise ValueError("Unphysical population or dephasing")
    if not math.isfinite(phase):
        raise ValueError("Nonfinite phase")
    if basis == "Z":
        p1 = 1.0 - p0
    elif basis == "X":
        p1 = 0.5 - (1.0 - dephase) * math.sqrt(p0 * (1 - p0)) * math.cos(phase)
    elif basis == "Y":
        p1 = 0.5 - (1.0 - dephase) * math.sqrt(p0 * (1 - p0)) * math.sin(phase)
    else:
        raise ValueError("Unknown measurement basis")
    return min(1.0, max(0.0, p1))


def detect(p0: float, phase: float, dephase: float, basis: str, rng: random.Random) -> int:
    """Simulate a registered detector bit; not a physical detector or collapse."""
    return int(rng.random() < born_p1(p0, phase, dephase, basis))


def settings():
    return [(i, j, k, l)
            for i in range(len(P0_VALUES))
            for j in range(len(PHASES))
            for k in range(len(DEPHASING))
            for l in range(len(BASES))]


def tokens(setting):
    """Ordered preparation -> phase -> environment -> eventual detector basis.

    No future bit, postselected herald, or target appears in the input.
    These tokens model a measurement *after* the basis is chosen, not a
    preregistered earlier prediction of the basis or the detector outcome.
    """
    i, j, k, l = setting
    return (i, 5 + j, 9 + k, 12 + l)


def target(setting):
    i, j, k, l = setting
    return born_p1(P0_VALUES[i], PHASES[j], DEPHASING[k], BASES[l])


def partition(setting):
    """Immutable settings-level split, not row-level re-use across partitions."""
    digest = hashlib.sha256(("JANUS-MEASUREMENT-HOLDOUT-V1|" + repr(setting)).encode()).digest()
    bucket = int.from_bytes(digest[:8], "big") % 10
    return "train" if bucket < 7 else ("validation" if bucket < 9 else "test")


def partitions():
    result = {k: [] for k in ("train", "validation", "test")}
    for s in settings():
        result[partition(s)].append(s)
    if min(map(len, result.values())) < 10:
        raise RuntimeError("Insufficient distinct setting combinations per split")
    return result


def no_signalling_control():
    """Exact two-qubit Bell control: local late gates do not change A's marginals.

    A local H on A before sampling the Z marginal computes an X-basis
    readout, and is performed on a fresh simulation copy each time.
    """
    from janus_cpu_quantum_emulator import StateVector

    def early_marginal(late_gate: str, basis: str):
        state = StateVector(2).h(0).cx(0, 1)
        if late_gate == "X":
            state.x(1)
        elif late_gate == "Z":
            state.z(1)
        elif late_gate == "H":
            state.h(1)
        elif late_gate != "I":
            raise ValueError("Unknown gate")
        if basis == "X":
            state.h(0)
        return state.marginal(0)

    readings = {}
    for gate in ("I", "X", "Z", "H"):
        readings[gate] = {
            basis: list(early_marginal(gate, basis)) for basis in ("Z", "X")
        }
        for probs in readings[gate].values():
            if any(abs(p - 0.5) > 1e-12 for p in probs):
                raise RuntimeError("FAIL_CLOSED_NO_SIGNALLING_CONTROL")
    return readings


def physics_report():
    visibility = []
    for deco in DEPHASING:
        visibility.append({
            "which_path_dephasing": deco,
            "x_basis_outcome_1_for_plus": born_p1(0.5, 0, deco, "X"),
            "z_basis_outcome_1_for_plus": born_p1(0.5, 0, deco, "Z"),
            "interference_visibility": 1.0 - deco,
        })
    return {
        "measurement_interaction": "system-detector entanglement / which-path distinguishability",
        "collapse_model": "Born projection is an update conditioned on an observed outcome",
        "objective_dynamical_collapse_implemented": False,
        "detector_which_path_control": visibility,
        "early_bell_marginals_independent_of_later_local_gate": no_signalling_control(),
        "late_herald_subselection_may_change_conditional_histograms": True,
        "early_operational_bit_from_late_free_choice": False,
        "physical_retrocausality_demonstrated": False,
        "tachyon_claim_supported": False,
    }


def evaluate(model, split):
    import torch
    import torch.nn.functional as F
    model.eval()
    x = torch.tensor([tokens(s) for s in split], dtype=torch.long)
    y = torch.tensor([target(s) for s in split], dtype=torch.float32)
    with torch.no_grad():
        logits, _ = model(x)
        prob = torch.softmax(logits[:, -1, 15:17], dim=-1)[:, 1].clamp(1e-7, 1 - 1e-7)
        ce = -y * torch.log(prob) - (1 - y) * torch.log1p(-prob)
        brier_to_oracle = ((prob - y) ** 2).mean()
        baseline_brier_to_oracle = ((0.5 - y) ** 2).mean()
    return {
        "settings_count": len(split),
        "expected_nll": round(float(ce.mean()), 7),
        "brier_vs_born_probability": round(float(brier_to_oracle), 7),
        "constant_half_baseline_brier": round(float(baseline_brier_to_oracle), 7),
        "beat_constant_half_baseline": bool(brier_to_oracle < baseline_brier_to_oracle),
    }


def train(steps: int, out: Path, learning_rate: float = 0.005):
    if not 1 <= steps <= 800:
        raise ValueError("Bounded steps required: 1..800")
    import torch
    import torch.nn.functional as F

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from janus_model.model import JanusModelConfig, JanusTinyTransformer, parameter_count

    torch.set_num_threads(1)
    torch.manual_seed(SEED)
    splits = partitions()
    model = JanusTinyTransformer(JanusModelConfig(**MODEL_CONFIG))
    before = evaluate(model, splits["test"])
    optim = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.001)
    x = torch.tensor([tokens(s) for s in splits["train"]], dtype=torch.long)
    y = torch.tensor([target(s) for s in splits["train"]], dtype=torch.float32)
    sampler = torch.Generator().manual_seed(SEED + 1)
    for _ in range(steps):
        model.train()
        rows = torch.randint(0, len(x), (64,), generator=sampler)
        logits, _ = model(x[rows])
        logp = F.log_softmax(logits[:, -1, 15:17], dim=-1)
        loss = -((1 - y[rows]) * logp[:, 0] + y[rows] * logp[:, 1]).mean()
        if not torch.isfinite(loss):
            raise RuntimeError("NONFINITE_TRAINING_LOSS")
        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optim.step()
    validation = evaluate(model, splits["validation"])
    after = evaluate(model, splits["test"])
    out.mkdir(parents=True, exist_ok=True)
    ckpt = out / "experimental_measurement_lens.pt"
    torch.save({
        "model_state": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "configuration": MODEL_CONFIG,
        "seed": SEED,
        "steps": steps,
        "status": "EXPERIMENT_ONLY_NOT_PRODUCTION",
    }, ckpt)
    report = {
        "schema": SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_video": {
            "url": "https://youtu.be/KkKMZLvlmKA",
            "segments": ["22:35-23:53 Wheeler-Feynman", "25:05-28:46 Cramer / detector"],
        },
        "model": "existing JanusTinyTransformer + experimental Born-rule calibration task",
        "model_parameters": parameter_count(model),
        "training": {
            "steps": steps, "seed": SEED, "independent_setting_splits": {
                name: len(group) for name, group in splits.items()
            },
            "test_before": before, "validation_after": validation,
            "test_after": after,
            "uses_postselected_examples": False,
            "has_future_choice_available_before_choice": False,
        },
        "physics": physics_report(),
        "checkpoint_sha256": hashlib.sha256(ckpt.read_bytes()).hexdigest(),
        "checkpoint_name": ckpt.name,
        "claim": VETO,
        "production_checkpoint_changed": False,
        "admission_to_production": False,
    }
    (out / "measurement_lens_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--out", type=Path, default=Path("artifacts/measurement_lens"))
    parser.add_argument("--physics-only", action="store_true")
    args = parser.parse_args()
    if args.physics_only:
        print(json.dumps({"schema": SCHEMA, "physics": physics_report(), "claim": VETO},
                         indent=2, sort_keys=True))
        return
    print(json.dumps(train(args.steps, args.out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
