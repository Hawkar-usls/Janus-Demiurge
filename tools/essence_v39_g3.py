#!/usr/bin/env python3
"""ESSENCE v3.9: real G2 -> G3 inherited checkpoint, external-source blind exam.

G3 inherits sealed G2 float32 tensor bytes from v3.8. Exam data are produced by
independent upstream software projects; no external benchmark bytes enter G3
training. Exact Git source commits and blob IDs, learning steps, optimizer,
score and verdict rules are frozen BEFORE the first G3 train. Independent
source does NOT imply independent scientific replication or private custodian.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

from tools import essence_v37_codex_gpt as core
from tools import essence_v38_inheritance as previous
from tools import essence_v36_juxtapose_exact as exact

SCHEMA = "janus.essence.g3_real_inherited_neural_checkpoint/3.9"
EXAM = "janus.essence.g3_external_source_frozen_paired_exam/3.9"
LOCK_SCHEMA = "janus.essence.g3_external_source_lock/3.9"
LOCK_PATH = "research/essence/codex_v39/external_source_lock.json"
STEPS = 8
LEARNING_RATE = 0.0005
SEED = 3903
MIN_MEAN_GAIN = 0.0001
MAX_FAMILY_REGRESSION = 0.0001
G2_RUN_ID = 43648008998
G2_FREEZE_SHA256 = "d1633f6c6172c46014a675b4cccf7c72a466ad959d4aa844120e73f3bc31cd56"
G2_MANIFEST_SHA256 = "7233dd73acc54a0f9080806615a9b2148a6bd39771548b923dd6848ad8b0425f"
G2_WEIGHT_SHA256 = "218fc4e75230eb0d96140e6c4319e2f2dcc3cda7ff363e43b2932f4998b33cbf"
SOURCE_REPOS = ("psf/requests", "pallets/click")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def require(value, code):
    if not value:
        raise ValueError(code)


def sealed(value):
    return previous.sealed(value)


def examine_lock(data):
    require(isinstance(data, dict) and data.get("schema") == LOCK_SCHEMA,
            "INVALID_G3_LOCK_SCHEMA")
    require(data.get("date_frozen_utc") == "2026-11-15" and
            data.get("frozen_before_g3_training") is True and
            data.get("allowed_only_on_trusted_main") is True and
            data.get("external_source_only_not_external_replicator") is True and
            data.get("production_authority") is False,
            "G3_FREEZE_AUTHORITY_INVALID")
    require(data.get("g2_run_id") == G2_RUN_ID and
            data.get("g2_freeze_receipt_sha256") == G2_FREEZE_SHA256 and
            data.get("g2_checkpoint_manifest_sha256") == G2_MANIFEST_SHA256 and
            data.get("g2_checkpoint_weights_sha256") == G2_WEIGHT_SHA256,
            "G2_ORIGIN_CHANGED")
    require(data.get("train_contract") == {
        "steps": STEPS, "lr": LEARNING_RATE, "seed": SEED,
        "gradient_clip_norm": 1.0, "optimizer_state_inherited": False
    }, "POST_HOC_TRAINING_DRIFT")
    require(data.get("exam_contract") == {
        "metric": "EQUAL_FILE_WEIGHT_MEAN_NEXT_BYTE_CROSS_ENTROPY",
        "min_mean_decrease": MIN_MEAN_GAIN,
        "max_allowed_repo_family_regression": MAX_FAMILY_REGRESSION,
        "original_holdout_files": 4,
        "first_only_no_retest_after_result": True,
        "missing_data_is_unknown": True
    }, "POST_HOC_EXAM_DRIFT")
    entries = data.get("external_files")
    require(isinstance(entries, list) and len(entries) == 4,
            "EXTERNAL_COHORT_NOT_FIXED")
    require([row.get("repo") if isinstance(row, dict) else None
             for row in entries] ==
            ["psf/requests", "psf/requests", "pallets/click", "pallets/click"],
            "UNAPPROVED_EXTERNAL_ORIGINS")
    names = set()
    for e in entries:
        require(set(e) == {"repo", "commit", "path", "git_blob_sha1",
                           "license"} and
                bool(HEX40.fullmatch(e["commit"])) and
                bool(HEX40.fullmatch(e["git_blob_sha1"])) and
                isinstance(e["path"], str) and
                e["path"].startswith("src/") and
                e["path"].endswith(".py") and
                ".." not in e["path"].split("/") and
                e["license"] in ("Apache-2.0", "BSD-3-Clause"),
                "UNTRUSTED_EXTERNAL_FILE")
        require((e["repo"], e["path"]) not in names, "DUPLICATE_HOLDOUT")
        names.add((e["repo"], e["path"]))
    return data


def load_lock(path):
    return examine_lock(previous.read_json(path))


def check_g2(g2_directory, freeze_path, lock):
    freeze = previous.check_freeze(previous.read_json(freeze_path))
    require(freeze["receipt_sha256"] == G2_FREEZE_SHA256,
            "G2_FREEZE_CHANGED")
    import torch
    model, manifest = previous.load_checkpoint(g2_directory, torch, freeze)
    require(manifest.get("generation") == "child" and
            manifest.get("manifest_sha256") == lock["g2_checkpoint_manifest_sha256"] and
            manifest.get("weights_sha256") == lock["g2_checkpoint_weights_sha256"] and
            manifest.get("parent_manifest_sha256") ==
            "6482479f3b8d99afd27e4bc6c3572d81da4694f7dd3bddd8a7c01f9904f9ec33",
            "UNVERIFIED_G2_CHECKPOINT_LINEAGE")
    return freeze, model, manifest


def train_g3(root, lock, g2_directory, freeze_path, checkpoint_dir):
    """Never opens, downloads or imports external holdout sources."""
    examine_lock(lock)
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(SEED)
    freeze, model, g2 = check_g2(g2_directory, freeze_path, lock)
    train, val = previous.train_bytes(root, freeze)
    start, _ = previous.weight_bytes(torch, model)
    start_hash = hashlib.sha256(start).hexdigest()
    require(start_hash == g2["weights_sha256"], "G3_NOT_STARTING_FROM_G2")
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE,
                             weight_decay=0.01)
    rejected = 0
    for _ in range(STEPS):
        model.train()
        indices = torch.randint(len(train) - core.BLOCK - 1, (4,))
        x = torch.stack([train[i:i+core.BLOCK] for i in indices])
        y = torch.stack([train[i+1:i+core.BLOCK+1] for i in indices])
        opt.zero_grad(set_to_none=True)
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(
            logits.reshape(-1, 256), y.reshape(-1))
        if not bool(torch.isfinite(loss)):
            rejected += 1
            continue
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
            rejected += 1
            opt.zero_grad(set_to_none=True)
            continue
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if not math.isfinite(float(norm)):
            rejected += 1
            opt.zero_grad(set_to_none=True)
            continue
        opt.step()
    final, _ = previous.weight_bytes(torch, model)
    require(hashlib.sha256(final).hexdigest() != start_hash,
            "G3_HAS_NO_WEIGHT_CHANGES")
    validation_loss = core.val_loss(torch, model, val)
    checkpoint = previous.save_checkpoint(
        checkpoint_dir, torch, model, generation="g3", freeze=freeze,
        initial_weights_sha256=start_hash,
        parent_manifest_sha256=g2["manifest_sha256"],
        trained_steps=STEPS, rejected=rejected)
    return sealed({
        "schema": SCHEMA, "generation": "g3",
        "g2_manifest_sha256": g2["manifest_sha256"],
        "g2_weights_sha256": g2["weights_sha256"],
        "g3_start_weights_sha256": start_hash,
        "g3_manifest_sha256": checkpoint["manifest_sha256"],
        "g3_weights_sha256": checkpoint["weights_sha256"],
        "g2_freeze_receipt_sha256": freeze["receipt_sha256"],
        "g3_lock_sha256": previous.sha(lock),
        "train_steps": STEPS,
        "gradients_rejected": rejected,
        "development_validation_loss": validation_loss,
        "optimizer_state_inherited": False,
        "actual_parent_weights_inherited": True,
        "external_test_bytes_fetched_in_training": False,
        "external_test_seen_during_training": False,
        "persistent_durable_storage_done_in_this_step": False,
        "independent_scientific_validation": False,
        "production_weights_changed": False,
        "production_authority": False
    })


def git_blob_sha1(raw):
    return previous.blob_sha1(raw)


def verify_external_bytes(raw, entry, training_digests):
    require(type(raw) is bytes and 2048 <= len(raw) <= 100000,
            "EXTERNAL_SOURCE_NOT_BOUNDED")
    require(git_blob_sha1(raw) == entry["git_blob_sha1"],
            "EXTERNAL_GIT_SOURCE_HASH_MISMATCH")
    h = hashlib.sha256(raw).hexdigest()
    require(h not in training_digests, "EXTERNAL_SOURCE_TRAIN_LEAKAGE")
    return h


def github_fetch_pinned(entry):
    """No unpinned floating branches: immutable commit and blob hash required."""
    require(entry["repo"] in SOURCE_REPOS, "UNEXPECTED_GITHUB_REPOSITORY")
    url = ("https://raw.githubusercontent.com/" + entry["repo"] + "/" +
           entry["commit"] + "/" + entry["path"])
    req = Request(url, headers={
        "User-Agent": "JANUS-ESSENCE-ExternalCorpus-BlindG3",
        "Accept": "application/octet-stream"})
    with urlopen(req, timeout=25) as response:
        raw = response.read(100001)
    return raw


def file_loss(torch, model, raw):
    tokens = torch.tensor(list(raw), dtype=torch.long)
    return core.val_loss(torch, model, tokens)


def exam_g3(lock, g2_directory, g3_directory, freeze_path, fetch=github_fetch_pinned):
    examine_lock(lock)
    import torch
    torch.set_num_threads(1)
    freeze, g2_model, g2 = check_g2(g2_directory, freeze_path, lock)
    g3_model, g3 = previous.load_checkpoint(g3_directory, torch, freeze)
    require(g3.get("generation") == "g3" and
            g3["parent_manifest_sha256"] == g2["manifest_sha256"] and
            g3["inherited_initial_weights_sha256"] == g2["weights_sha256"] and
            g3["trained_steps"] == STEPS and
            g3["weights_sha256"] != g2["weights_sha256"],
            "FORGED_G2_TO_G3_WEIGHT_INHERITANCE")
    witness = exact.field_search([[1, 2], [-1, 3], [2, -3]], 80)
    require(witness["exact_verifier_has_veto"] is True and
            witness["coverage_ratio"] == 1.0 and
            witness["production_authority"] is False,
            "JUXTAPOSE_EXACT_VETO_LOST")
    # Critically no external content until both full checkpoint lineages checked.
    used = set()
    per_file = []
    per_repo = {repo: [] for repo in SOURCE_REPOS}
    for item in lock["external_files"]:
        raw = fetch(item)
        digest = verify_external_bytes(raw, item, {
            v["source_sha256"] for role in ("train", "val")
            for v in freeze["roles"][role]})
        require(digest not in used, "REPEATED_EXTERNAL_CONTENT")
        used.add(digest)
        p = file_loss(torch, g2_model, raw)
        c = file_loss(torch, g3_model, raw)
        row = {"repository": item["repo"], "path": item["path"],
               "source_commit": item["commit"],
               "source_blob_sha1": item["git_blob_sha1"],
               "source_sha256": digest, "bytes": len(raw),
               "g2_loss": p, "g3_loss": c, "loss_decrease": p - c}
        per_file.append(row)
        per_repo[item["repo"]].append(row)
    require(len(per_file) == 4 and
            all(len(per_repo[repo]) == 2 for repo in SOURCE_REPOS),
            "INCOMPLETE_EXTERNAL_EXAM")
    parent_mean = sum(v["g2_loss"] for v in per_file) / len(per_file)
    child_mean = sum(v["g3_loss"] for v in per_file) / len(per_file)
    family = [{
        "repository": repo,
        "g2_mean": sum(v["g2_loss"] for v in per_repo[repo]) / 2,
        "g3_mean": sum(v["g3_loss"] for v in per_repo[repo]) / 2,
    } for repo in SOURCE_REPOS]
    permitted = all(
        v["g3_mean"] - v["g2_mean"] <= MAX_FAMILY_REGRESSION
        for v in family)
    better = (parent_mean - child_mean >= MIN_MEAN_GAIN) and permitted
    return sealed({
        "schema": EXAM,
        "status": ("PASS_EXTERNAL_SOURCE_BLIND_INTERNAL_G3_GAIN"
                   if better else "NO_G3_GAIN_ON_PREDECLARED_EXTERNAL_COHORT"),
        "g3_lock_sha256": previous.sha(lock),
        "g2_manifest_sha256": g2["manifest_sha256"],
        "g3_manifest_sha256": g3["manifest_sha256"],
        "g3_inherited_exact_g2_bytes": True,
        "juxtapose_verifier_receipt_sha256": witness["receipt_sha256"],
        "g2_external_mean_file_loss": parent_mean,
        "g3_external_mean_file_loss": child_mean,
        "external_mean_loss_decrease": parent_mean - child_mean,
        "repo_family_results": family, "file_results": per_file,
        "four_independently_authored_external_source_tasks": True,
        "same_frozen_examination_for_both_generations": True,
        "holdout_bytes_opened_only_after_g3_weights_sealed": True,
        "third_party_source_not_external_researcher": True,
        "external_scientific_replication": False,
        "blind_custodian": False,
        "exam_after_frozen_commit": True,
        "automatic_weight_or_model_promotion": False,
        "production_authority": False
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("freeze", "train", "exam"))
    p.add_argument("--repo-root", default=".")
    p.add_argument("--lock", default=LOCK_PATH)
    p.add_argument("--g2-dir")
    p.add_argument("--g3-dir")
    p.add_argument("--g2-freeze")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    lock = load_lock(args.lock)
    if args.mode == "freeze":
        output = sealed({
            "schema": "janus.essence.g3_source_frozen_before_training/3.9",
            "g3_lock_sha256": previous.sha(lock),
            "g2_source_run": G2_RUN_ID,
            "external_files_locked": len(lock["external_files"]),
            "holdout_bytes_read": False,
            "production_authority": False,
        })
    elif args.mode == "train":
        require(bool(args.g2_dir and args.g2_freeze and args.g3_dir),
                "MISSING_G2_TRAINING_LINEAGE")
        output = train_g3(args.repo_root, lock, args.g2_dir,
                          args.g2_freeze, args.g3_dir)
    else:
        require(bool(args.g2_dir and args.g2_freeze and args.g3_dir),
                "MISSING_G3_EXAM_LINEAGE")
        output = exam_g3(lock, args.g2_dir, args.g3_dir, args.g2_freeze)
    previous.immutable_json(args.out, output)
    print(json.dumps({
        "mode": args.mode, "status": output.get("status", "SEALED"),
        "receipt_sha256": output["receipt_sha256"],
        "production_authority": False}, sort_keys=True))


if __name__ == "__main__":
    main()
