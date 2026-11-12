"""JANUS Neural Kombucha: independently trained, SHA-bound CPU micro-transformer cells.

Bounded DEVELOPMENT-ONLY synthetic learning demonstration with the actual
JanusTinyTransformer. No arbitrary source execution, weight promotion, or
claim of predictive skill on live GitHub outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

import torch
import torch.nn.functional as F

from janus_model.model import JanusModelConfig, JanusTinyTransformer, parameter_count

torch.set_num_threads(1)

CELL_NAMES = ("sensing", "memory", "planning", "verification", "recovery", "coding")
CFG = JanusModelConfig(
    vocab_size=8, context_length=7, d_model=16, n_heads=2,
    n_layers=1, ff_mult=2, dropout=0.0
)
INITIAL_SEED = 2026111201
NOISE_PROB = 0.035
SCHEMA = "janus.neural_kombucha.cell.v1"
ROUND_LIMIT = 180
MIN_STEPS = 40


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def cell_name(index):
    if type(index) is not int or not 0 <= index < len(CELL_NAMES):
        raise ValueError("CELL_NOT_ADMITTED")
    return CELL_NAMES[index]


def make_model(cell):
    cell_name(cell)
    torch.manual_seed(INITIAL_SEED + cell * 1049)
    return JanusTinyTransformer(CFG)


def draw(cell, n, generator):
    """Synthetic token context with cell-specific, observable forward-time rule."""
    cell_name(cell)
    if not 1 <= n <= 4096:
        raise ValueError("SAMPLE_COUNT_BOUNDS")
    bits = torch.randint(0, 2, (n, CFG.context_length - 1), generator=generator)
    prefix = torch.full((n, 1), cell + 2, dtype=torch.long)
    x = torch.cat((prefix, bits), dim=1)
    # Distinct temporal operators: copy, invert, delay, and delayed inversion.
    source_bit = bits[:, -1] if cell in (0, 2, 4) else bits[:, -2]
    invert = cell in (2, 3)
    noise = (torch.rand(n, generator=generator) < NOISE_PROB).long()
    target = (source_bit ^ int(invert) ^ noise).long()
    return x, target


@torch.no_grad()
def logits_for(model, x):
    model.eval()
    return model(x)[0][:, -1, :2].float()


def score(logits, y):
    p = torch.softmax(logits, -1)[:, 1]
    return {
        "n": int(len(y)),
        "accuracy": round(float(((p >= 0.5) == y.bool()).float().mean()), 6),
        "nll": round(float(F.cross_entropy(logits, y)), 6),
        "brier": round(float(((p - y.float()) ** 2).mean()), 6),
    }


def observation_header(path):
    p = Path(path)
    obj = json.loads(p.read_text())
    if (obj.get("schema") != "janus.cooling_tower.async_microkernel.v1"
        or obj.get("bounded_rounds") != 2
        or obj.get("private_repositories_excluded") is not True
        or obj.get("new_workflow_dispatches") != 0
        or obj.get("production_code_writes") != 0
        or obj.get("full_autonomy_accepted") is not False
        or obj.get("public_repositories", 0) < 30
        or len(obj.get("observations", [])) != 2):
        raise ValueError("OBSERVATION_CONTRACT_REJECTED")
    return {"sha256": sha256(p), "schema": obj["schema"],
            "run_id": obj.get("run_id"), "source_sha": obj.get("source_sha"),
            "real_history_used_for_gradients": False}


def train_cell(cell, observation, out, *, steps=120, batch=48, budget=75):
    name = cell_name(cell)
    if not MIN_STEPS <= steps <= ROUND_LIMIT or not 8 <= batch <= 128:
        raise ValueError("TRAIN_BUDGET_INVALID")
    if not 10 <= budget <= 110:
        raise ValueError("TIME_BUDGET_INVALID")
    header = observation_header(observation)
    model = make_model(cell)
    params = parameter_count(model)
    if params > 10000:
        raise ValueError("CELL_TOO_LARGE")
    final_gen = torch.Generator().manual_seed(808000 + cell * 2003)
    hold_x, hold_y = draw(cell, 512, final_gen)
    before_logits = logits_for(model, hold_x)
    before = score(before_logits, hold_y)
    data_rng = torch.Generator().manual_seed(110000 + cell * 1009)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.009, weight_decay=0.001)
    start = time.monotonic()
    completed = 0
    # Yaksa-inspired bounded priority replay. Entries are TRAIN examples only;
    # the frozen independent holdout is never inserted into this buffer.
    replay = []
    replay_uses = 0
    for _ in range(steps):
        if completed >= MIN_STEPS and time.monotonic() - start > budget:
            break
        x, y = draw(cell, batch, data_rng)
        if replay and completed % 4 == 0:
            # Detached, immutable samples; no unrelated tasks or outside data.
            replay_batch = sorted(replay, key=lambda item: -item[0])[:min(8, len(replay))]
            x = torch.cat([x, torch.stack([item[1] for item in replay_batch])], dim=0)
            y = torch.cat([y, torch.stack([item[2] for item in replay_batch])], dim=0)
            replay_uses += len(replay_batch)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits, _ = model(x)
        per_example = F.cross_entropy(logits[:, -1, :2], y, reduction="none")
        loss = per_example.mean()
        if not torch.isfinite(loss).item():
            raise ValueError("NONFINITE_TRAIN_LOSS")
        # Store only difficult NEW training samples, never replayed samples.
        hardest = torch.topk(per_example[:batch].detach(), min(2, batch)).indices
        replay.extend((float(per_example[index].detach()),
                       x[index].detach().clone(), y[index].detach().clone())
                      for index in hardest.tolist())
        replay = sorted(replay, key=lambda item: -item[0])[:64]
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        if any(not bool(torch.isfinite(weight).all())
               for weight in model.parameters()):
            raise ValueError("NONFINITE_CELL_PARAMETERS")
        completed += 1
    after_logits = logits_for(model, hold_x)
    after = score(after_logits, hold_y)
    if not math.isfinite(after["nll"]) or not math.isfinite(after["brier"]):
        raise ValueError("NONFINITE_HOLDOUT")
    passed = (after["nll"] < before["nll"] - 0.02 and
              after["accuracy"] > 0.65 and completed >= MIN_STEPS)
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    weights = root / "weights.pt"
    torch.save({
        "schema": SCHEMA, "cell_index": cell, "cell_name": name,
        "configuration": CFG.to_dict(), "observation_sha256": header["sha256"],
        "model_state": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "production_promotion": False,
    }, weights)
    report = {
        "schema": SCHEMA, "cell_index": cell, "cell_name": name,
        "model": "JanusTinyTransformer", "configuration": CFG.to_dict(),
        "parameters": params, "rounds": completed, "train_examples": completed * batch,
        "heldout_seed": 808000 + cell * 2003,
        "heldout_before": before, "heldout_after": after,
        "weights_sha256": sha256(weights),
        "source": header,
        "replay_source": "ONLINE_TRAINING_BATCHES_ONLY",
        "replay_capacity": 64,
        "replay_uses": replay_uses,
        "frozen_holdout_never_replayed": True,
        "dataset_class": "SYNTHETIC_CAUSAL_TEMPORAL_BIT_TASK",
        "uses_future_labels_for_training": False,
        "real_github_observations_used_for_gradients": False,
        "task_specific_model_weights": True,
        "phase": "DEVELOPMENT_ONLY",
        "synthetic_learning_gate": "PASS_SYNTHETIC" if passed else "HOLD_NO_SYNTHETIC_GAIN",
        "operational_decision_authority": False,
        "production_promotion": False,
        "autonomous_module_installation": False,
        "failure_isolation": "INDEPENDENT_GITHUB_ACTIONS_JOB",
        "training_seconds": round(time.monotonic() - start, 3),
    }
    save_json(root / "receipt.json", report)
    print(json.dumps({"cell": name, "rounds": completed,
                      "synthetic_learning_gate": report["synthetic_learning_gate"],
                      "before": before, "after": after}, sort_keys=True))
    return report


def verify_cell(folder, expected_index, observation_sha):
    root = Path(folder)
    report = json.loads((root / "receipt.json").read_text())
    cell = cell_name(expected_index)
    if (report.get("schema") != SCHEMA or report.get("cell_index") != expected_index or
        report.get("cell_name") != cell or report.get("configuration") != CFG.to_dict() or
        report.get("source", {}).get("sha256") != observation_sha or
        report.get("dataset_class") != "SYNTHETIC_CAUSAL_TEMPORAL_BIT_TASK" or
        report.get("real_github_observations_used_for_gradients") is not False or
        report.get("operational_decision_authority") is not False or
        report.get("production_promotion") is not False or
        report.get("autonomous_module_installation") is not False or
        report.get("replay_source") != "ONLINE_TRAINING_BATCHES_ONLY" or
        report.get("replay_capacity") != 64 or
        type(report.get("replay_uses")) is not int or
        not 0 <= report["replay_uses"] <= report.get("rounds", 0) * 8 or
        report.get("frozen_holdout_never_replayed") is not True):
        raise ValueError("CELL_RECEIPT_REJECTED")
    weights = root / "weights.pt"
    if sha256(weights) != report.get("weights_sha256"):
        raise ValueError("CELL_WEIGHTS_DIGEST_MISMATCH")
    saved = torch.load(weights, weights_only=True, map_location="cpu")
    if (saved.get("schema") != SCHEMA or saved.get("cell_index") != expected_index or
        saved.get("cell_name") != cell or saved.get("configuration") != CFG.to_dict() or
        saved.get("observation_sha256") != observation_sha or
        saved.get("production_promotion") is not False):
        raise ValueError("CELL_WEIGHTS_IDENTITY_MISMATCH")
    original = make_model(expected_index).state_dict()
    state = saved["model_state"]
    if set(state) != set(original):
        raise ValueError("CELL_WEIGHTS_LAYOUT")
    for name, ref in original.items():
        got = state[name]
        if (got.shape != ref.shape or got.dtype != ref.dtype or
            not bool(torch.isfinite(got).all())):
            raise ValueError("CELL_WEIGHTS_NONFINITE_OR_LAYOUT")
    return report


def aggregate(observation, input_dir, out):
    header = observation_header(observation)
    root = Path(input_dir)
    reports = []
    holds = []
    for cell, name in enumerate(CELL_NAMES):
        folder = root / f"cell-{cell}"
        if not (folder / "receipt.json").is_file():
            holds.append({"cell_index": cell, "cell": name, "reason": "MISSING_CELL_ARTIFACT"})
            continue
        try:
            item = verify_cell(folder, cell, header["sha256"])
            reports.append(item)
            if item["synthetic_learning_gate"] != "PASS_SYNTHETIC":
                holds.append({"cell_index": cell, "cell": name, "reason": "NO_HOLDOUT_GAIN"})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            holds.append({"cell_index": cell, "cell": name, "reason": type(exc).__name__})
    result = {
        "schema": "janus.neural_kombucha.aggregate.v1",
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_sha": os.environ.get("GITHUB_SHA"),
        "observation_sha256": header["sha256"],
        "expected_cells": len(CELL_NAMES), "verified_cells": len(reports),
        "cells": reports, "holdouts": holds,
        "synthetic_readiness": "PASS_ALL_CELLS" if not holds else "HOLD_PARTIAL_OR_NO_GAIN",
        "operational_learning": "HOLD_NO_CHRONOLOGICAL_REAL_HISTORY",
        "actual_real_data_training": False,
        "model_weights_are_mutually_independent": True,
        "federated_average": False,
        "independent_holdout_per_cell": True,
        "cross_cell_communication": "JSON_PROVENANCE_ONLY",
        "full_autonomy_accepted": False,
        "production_promotion": False,
        "code_self_modification": False,
        "remote_module_import": False,
        "nas_access": False,
    }
    save_json(out, result)
    print(json.dumps({k: result[k] for k in
                     ("expected_cells", "verified_cells", "synthetic_readiness",
                      "operational_learning")}, sort_keys=True))
    return result


def main():
    parser = argparse.ArgumentParser()
    cmds = parser.add_subparsers(dest="command", required=True)
    worker = cmds.add_parser("worker")
    worker.add_argument("--cell", type=int, required=True)
    worker.add_argument("--observation", required=True)
    worker.add_argument("--out", required=True)
    worker.add_argument("--steps", type=int, default=120)
    worker.add_argument("--batch", type=int, default=48)
    worker.add_argument("--budget", type=float, default=75)
    group = cmds.add_parser("aggregate")
    group.add_argument("--observation", required=True)
    group.add_argument("--input", required=True)
    group.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "worker":
        train_cell(args.cell, args.observation, args.out,
                   steps=args.steps, batch=args.batch, budget=args.budget)
    else:
        aggregate(args.observation, args.input, args.out)


if __name__ == "__main__":
    main()
