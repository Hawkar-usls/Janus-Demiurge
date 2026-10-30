"""Read-only dual-architecture replay of a SHA-pinned JANUS candidate.

Replays native PyTorch loss on the frozen anchor and pre-registered RFC sample.
External RFC text is public and NOT an independently escrowed blind dataset.
No production promotion, main write, workflow dispatch or new training occurs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from daddy_keymaster.broker import canonical, sha
from daddy_keymaster.champion_release import Hold, hash_file, read_json, require

SCHEMA = "janus.daddy_keymaster.cloud_checkpoint_replay.v1"
CANDIDATE_ID = "R2_LOCAL_B"
QUARANTINE_SCHEMA = "janus.daddy_keymaster.research_checkpoint_quarantine.v1"


def replay(root, candidate_file, manifest_file, training_file,
           pre_registration_file, external_raw_file):
    import torch
    from janus_model.eval_contract import (
        DEFAULT_ANCHOR, EVAL_BATCHES, EVAL_BATCH_SIZE, contract_identity,
        MIN_MEANINGFUL_IMPROVEMENT_FRACTION,
    )
    from janus_model.train_registry import eval_loss, load_checkpoint
    from janus_model.model import ByteTokenizer

    root = Path(root).resolve()
    manifest = read_json(manifest_file)
    training = read_json(training_file)
    prereg = read_json(pre_registration_file)
    incumbent_file = root / "janus_model/checkpoints/promoted.pt"
    parent_sha = manifest.get("parent_checkpoint_sha256")
    candidate_sha = manifest.get("candidate_checkpoint_sha256")
    require(manifest.get("schema") == QUARANTINE_SCHEMA and
            manifest.get("status") ==
                "RESEARCH_CANDIDATE_QUARANTINED__NO_PRODUCTION_AUTHORITY" and
            manifest.get("candidate_id") == CANDIDATE_ID and
            manifest.get("automatic_production_promotion") is False and
            manifest.get("consumer_rollout_authorized") is False and
            manifest.get("independent_blind_final_proven") is False and
            manifest.get("authority_delta") == 0,
            "REPLAY_UNSAFE_QUARANTINE")
    require(hash_file(incumbent_file) == parent_sha and
            hash_file(candidate_file) == candidate_sha and
            Path(candidate_file).stat().st_size == manifest.get("candidate_bytes") and
            0 < Path(candidate_file).stat().st_size <= 5_000_000,
            "REPLAY_CHECKPOINT_SHA_OR_SIZE_MISMATCH")
    require(hash_file(training_file) ==
            manifest["local_evidence"]["training_receipt_b_sha256"] and
            training.get("candidate_checkpoint_sha256") == candidate_sha and
            training.get("parent_checkpoint_sha256") == parent_sha and
            training.get("source_digest") == manifest.get("corpus_source_digest") and
            training.get("evaluation_contract_sha256") ==
                manifest.get("evaluation_contract_sha256") and
            training.get("status") == "PROMOTED" and
            training.get("steps") == 64 and
            training.get("training_seed") == 20261032,
            "REPLAY_TRAINING_RECEIPT_MISMATCH")
    require(hash_file(pre_registration_file) ==
            manifest["external_final"]["pre_registration_sha256"] and
            prereg.get("schema") ==
                "janus.daddy_keymaster.external_final_pre_registration.v1" and
            prereg.get("candidate_sha256") == candidate_sha and
            prereg.get("incumbent_sha256") == parent_sha and
            prereg.get("production_promotion_authorized") is False and
            prereg.get("independent_blind_custody") is False and
            prereg.get("selected_source", {}).get("url") ==
                "https://www.rfc-editor.org/rfc/rfc9113.txt" and
            prereg.get("window_bytes") == [10000, 110000] and
            prereg.get("seeds") == [21357, 21358, 21359, 21360, 21361] and
            prereg.get("evaluation_batch_count") == EVAL_BATCHES and
            prereg.get("evaluation_batch_size") == EVAL_BATCH_SIZE,
            "REPLAY_PREREGISTRATION_MISMATCH")
    contract = contract_identity()
    require(contract.get("contract_sha256") ==
            manifest.get("evaluation_contract_sha256") and
            contract["anchor"]["sha256"] == training.get("anchor_sha256") and
            contract["anchor"]["seed"] == 1366,
            "REPLAY_FROZEN_CONTRACT_DRIFT")
    raw = Path(external_raw_file).read_bytes()
    require(110000 <= len(raw) <= 1_000_000, "REPLAY_EXTERNAL_SOURCE_SIZE")
    sample = raw[10000:110000].decode("utf-8", errors="replace")
    sample_bytes = sample.encode("utf-8")
    import hashlib
    sample_sha = hashlib.sha256(sample_bytes).hexdigest()
    require(sample_sha == manifest["external_final"]["sample_sha256"],
            "REPLAY_EXTERNAL_SOURCE_SHA_MISMATCH")

    torch.set_num_threads(2)
    incumbent, _ = load_checkpoint(incumbent_file)
    candidate, _ = load_checkpoint(candidate_file)
    require(incumbent.config == candidate.config and
            candidate.config.to_dict() == training.get("config"),
            "REPLAY_MODEL_CONFIG_MISMATCH")
    from janus_model.train_registry import tokens
    anchor = tokens(DEFAULT_ANCHOR)
    final = torch.tensor(ByteTokenizer.encode(sample, bos=True, eos=True),
                         dtype=torch.long)
    anchor_seed = contract["anchor"]["seed"]
    a0 = eval_loss(incumbent, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, anchor_seed)
    a1 = eval_loss(candidate, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, anchor_seed)
    rows = []
    for seed in prereg["seeds"]:
        old = eval_loss(incumbent, final, EVAL_BATCHES, EVAL_BATCH_SIZE, seed)
        new = eval_loss(candidate, final, EVAL_BATCHES, EVAL_BATCH_SIZE, seed)
        rows.append({"seed": seed, "incumbent": old, "candidate": new,
                     "gain_fraction": (old-new)/old})
    threshold = MIN_MEANINGFUL_IMPROVEMENT_FRACTION
    successful = (
        all(math.isfinite(v) and v > 0 for v in
            [a0, a1] + [x[k] for x in rows
                          for k in ("incumbent", "candidate")])
        and a1 <= a0 * (1 - threshold)
        and all(r["candidate"] <= r["incumbent"] * (1 - threshold)
                for r in rows)
    )
    result = {
        "schema": SCHEMA,
        "status": ("REPLAY_PASS__RESEARCH_ONLY" if successful
                   else "HOLD__REPLAY_NOT_REPRODUCIBLE"),
        "repository": manifest["repository"],
        "candidate_checkpoint_sha256": candidate_sha,
        "parent_checkpoint_sha256": parent_sha,
        "quarantine_manifest_sha256": hash_file(manifest_file),
        "pre_registration_sha256": hash_file(pre_registration_file),
        "source_sha256": sample_sha,
        "runner_arch": os.environ.get("RUNNER_ARCH", "LOCAL"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "frozen_anchor": {"seed": anchor_seed,
                          "incumbent_loss": a0, "candidate_loss": a1},
        "external_final": rows,
        "minimum_improvement_fraction": threshold,
        "adaptive_source_replayed": False,
        "independent_blind_custody": False,
        "production_promotion_authorized": False,
        "authority_delta": 0,
    }
    result["receipt_sha256"] = sha(result)
    return result


def main():
    p = argparse.ArgumentParser()
    for name in ("root", "candidate", "manifest", "training",
                 "pre-registration", "external-raw", "out"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    try:
        receipt = replay(a.root, a.candidate, a.manifest, a.training,
                         getattr(a, "pre_registration"),
                         getattr(a, "external_raw"))
    except Hold as e:
        raise SystemExit("CHAMPION_REPLAY_HOLD:" + str(e)) from e
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(canonical(receipt) + b"\n")
    print(json.dumps({"status": receipt["status"],
                      "runner_arch": receipt["runner_arch"],
                      "anchor": receipt["frozen_anchor"],
                      "external_final": receipt["external_final"],
                      "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    if receipt["status"] != "REPLAY_PASS__RESEARCH_ONLY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
