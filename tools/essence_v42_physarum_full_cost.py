#!/usr/bin/env python3
"""ESSENCE v4.2: measure full Physarum search cost vs 14-step fixed baseline.

No new external holdout file is read in this module. Runs on pinned G3 weights,
reports wall + CPU process timing for all probes, the adaptive Physarum selector,
final model updates and development scoring. Produces a byte-sealed 14-step
control checkpoint. No production promotion. Timing is runner-specific.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter, process_time

from tools import essence_v37_codex_gpt as core
from tools import essence_v38_inheritance as prior
from tools import essence_v40_physarum_bridge as phys

SCHEMA = "janus.essence.physarum_full_cost_replay/4.2"
LOCK = "research/essence/physarum_v42/preregistered_new_source_cohort.json"
BASELINE_STEPS = 14
BASELINE_SEED = 4002


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def read_lock(path):
    data = prior.read_json(path)
    require(data.get("schema") ==
            "janus.essence.physarum_costmatched_cleanroom_holdout/4.2" and
            data.get("frozen_before_any_v42_costmatched_model_training") is True and
            data.get("status") == "PREREGISTERED_NOT_EVALUATED" and
            data.get("historical_g4_run_id") == 43650540561 and
            data.get("g3_checkpoint_sha256") == phys.G3_WEIGHTS_SHA256 and
            data.get("frozen_physarum_checkpoint_sha256") ==
            "dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f" and
            data.get("cost_contract", {}).get("physarum_total_model_train_steps") == 14 and
            data["cost_contract"]["baseline14_model_train_steps"] == 14 and
            data["cost_contract"]["baseline14_seed"] == BASELINE_SEED and
            data["cost_contract"]["physarum_expected_lr"] == 0.00075 and
            data["cost_contract"]["reuse_of_old_v41_external_exam_for_selection"] is False and
            data["production_authority"] is False,
            "V42_FROZEN_COST_CONTRACT_CHANGED")
    require(len(data.get("source_repos", [])) == 4 and
            sum(len(r.get("paths", [])) for r in data["source_repos"]) == 12,
            "V42_FROZEN_COHORT_UNEXPECTED")
    return data


def clock():
    return perf_counter(), process_time()


def elapsed(start):
    return {"wall_seconds": perf_counter() - start[0],
            "process_cpu_seconds": process_time() - start[1]}


def clone(torch, model):
    copy = core.new_model(torch)
    copy.load_state_dict(model.state_dict(), strict=True)
    return copy


def measured_trial(root, g3_dir, freeze_path, out_dir,
                   lock_path=LOCK):
    import torch
    torch.set_num_threads(1)
    lock = read_lock(lock_path)
    freeze, ancestor, origin = phys.load_g3(g3_dir, freeze_path, torch)
    train, val = prior.train_bytes(root, freeze)
    parent_hash = origin["weights_sha256"]
    require(parent_hash == phys.G3_WEIGHTS_SHA256,
            "NON_FROZEN_G3_WEIGHTS")

    # Measure a budget-matched fixed baseline: exactly 14 steps, as
    # compared with 6 Physarum probe steps + 8 final steps.
    ctrl_cfg = phys.config(phys.BASELINE_INDEX)
    fixed = clone(torch, ancestor)
    start = clock()
    rejects = phys.train_steps(torch, fixed, train,
                               lr=ctrl_cfg["lr"], clip=ctrl_cfg["clip"],
                               steps=BASELINE_STEPS, seed=BASELINE_SEED)
    baseline_train = elapsed(start)
    start = clock()
    baseline_dev = float(core.val_loss(torch, fixed, val))
    baseline_validation = elapsed(start)
    require(math.isfinite(baseline_dev), "BASELINE14_NONFINITE")
    path = Path(out_dir)
    require(not path.exists() and not path.is_symlink(),
            "OUTPUT_MUST_BE_NEW")
    checkpoint = prior.save_checkpoint(
        path / "baseline14", torch, fixed, generation="g4_fixed_budget14",
        freeze=freeze, initial_weights_sha256=parent_hash,
        parent_manifest_sha256=origin["manifest_sha256"],
        trained_steps=BASELINE_STEPS, rejected=rejects)

    # Replay the original Physarum decision from real G3 bytes, with the
    # exact same seeds and fixed candidate list as v4.0.
    probe = {}
    probes = []
    t_probes = clock()
    for idx in phys.PROBE_INDICES:
        cfg = phys.config(idx)
        challenger = clone(torch, ancestor)
        start = clock()
        r = phys.train_steps(torch, challenger, train,
                             lr=cfg["lr"], clip=cfg["clip"],
                             steps=phys.PROBE_STEPS, seed=phys.RNG_SEED)
        duration = elapsed(start)
        start = clock()
        metric = float(core.val_loss(torch, challenger, val))
        score_time = elapsed(start)
        probe[idx] = metric
        probes.append({"grid_index": idx, "development_loss": metric,
                       "gradients_rejected": r,
                       "train_time": duration,
                       "development_score_time": score_time})
    probe_total = elapsed(t_probes)
    start = clock()
    choice = phys.choose_physarum(probe)
    search = elapsed(start)
    require(choice["selected"] == phys.config(8),
            "PHYSARUM_POLICY_CHANGED_AFTER_FREEZE")
    final = clone(torch, ancestor)
    cfg = choice["selected"]
    start = clock()
    pr = phys.train_steps(torch, final, train,
                          lr=cfg["lr"], clip=cfg["clip"],
                          steps=phys.SIBLING_STEPS, seed=phys.RNG_SEED+1)
    final_time = elapsed(start)
    start = clock()
    adaptive_dev = float(core.val_loss(torch, final, val))
    adaptive_validation = elapsed(start)
    final_raw, _ = prior.weight_bytes(torch, final)
    final_sha = hashlib.sha256(final_raw).hexdigest()
    # A clean replay must reproduce the *already frozen* model, otherwise
    # any timing from this run cannot be used as provenance for that model.
    require(final_sha ==
            lock["frozen_physarum_checkpoint_sha256"],
            "COST_REPLAY_WEIGHTS_NOT_IDENTICAL_TO_FROZEN_G4")
    require(sum(p["gradients_rejected"] for p in probes) == 0 and
            pr == 0 and rejects == 0,
            "REJECTED_GRADIENTS_AFFECTED_COST_PAIR")
    return prior.sealed({
        "schema": SCHEMA,
        "lock_sha256": prior.sha(lock),
        "g3_source_sha256": parent_hash,
        "physarum_source_sha256": final_sha,
        "baseline14_manifest_sha256": checkpoint["manifest_sha256"],
        "baseline14_weights_sha256": checkpoint["weights_sha256"],
        "development_only": True,
        "external_exam_bytes_read": False,
        "baseline14": {"lr": ctrl_cfg["lr"], "clip": ctrl_cfg["clip"],
                       "train_steps": BASELINE_STEPS,
                       "development_loss": baseline_dev,
                       "train_duration": baseline_train,
                       "validation_duration": baseline_validation},
        "physarum": {
            "probe_steps": len(phys.PROBE_INDICES)*phys.PROBE_STEPS,
            "final_steps": phys.SIBLING_STEPS,
            "total_training_steps": 14,
            "probe_records": probes,
            "probes_duration_including_dev_validation": probe_total,
            "network_and_swarm_duration": search,
            "selected_config": cfg,
            "final_train_duration": final_time,
            "final_dev_score_duration": adaptive_validation,
            "development_loss": adaptive_dev
        },
        "runner_hardware_timing_specific": True,
        "full_cost_includes_all_probes_and_selection": True,
        "independent_external_researcher": False,
        "production_authority": False
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--g3-dir", required=True)
    p.add_argument("--freeze", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--lock", default=LOCK)
    args = p.parse_args()
    folder = Path(args.out_dir)
    receipt = measured_trial(args.repo_root, args.g3_dir, args.freeze,
                             folder, args.lock)
    prior.immutable_json(folder / "full-cost-receipt.json", receipt)
    print(json.dumps({
        "status": "SEALED_COST_MATCHED_BASELINE_READY",
        "baseline14_sha256": receipt["baseline14_weights_sha256"],
        "physarum_sha256": receipt["physarum_source_sha256"],
        "baseline14_development_loss":
            receipt["baseline14"]["development_loss"],
        "physarum_development_loss": receipt["physarum"]["development_loss"],
        "receipt_sha256": receipt["receipt_sha256"],
        "production_authority": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
