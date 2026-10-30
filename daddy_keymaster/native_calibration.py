"""JANUS DADDY_KEYMASTER: bounded own-weight cloud calibration, fail-closed.

Two standard GitHub CPU workers train separate low-budget variants from the
same canonical native checkpoint. A third worker independently evaluates both
against the existing frozen anchor and adaptive holdout. No automatic main
checkpoint mutation or external model replaces JANUS's canonical trained one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from daddy_keymaster.broker import canonical, sha
from janus_model.eval_contract import contract_identity, sha256_file

PROFILES = {
    "X64": {"steps": 32, "batch_size": 8, "lr": 0.00010, "seed": 4321},
    "ARM64": {"steps": 48, "batch_size": 8, "lr": 0.00015, "seed": 8765},
}
STATE_FILE = Path("janus_model/state/JANUS_MODEL_STATE.json")
CANONICAL = Path("janus_model/checkpoints/promoted.pt")
SCHEMA = "janus.daddy_keymaster.native_calibration_worker.v1"
AUDIT = "janus.daddy_keymaster.native_calibration_audit.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def check_source(root, env):
    if (env.get("GITHUB_ACTIONS") != "true" or
        env.get("GITHUB_REPOSITORY") != "Hawkar-usls/Janus-Demiurge" or
        env.get("GITHUB_EVENT_NAME") not in
            ("pull_request", "push", "schedule", "workflow_dispatch") or
        not HEX40.fullmatch(env.get("GITHUB_SHA", "")) or
        not re.fullmatch(r"[0-9]{5,}", env.get("GITHUB_RUN_ID", "")) or
        not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", ""))):
        raise ValueError("NATIVE_SWARM_RUN_CONTEXT_REFUSED")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                     text=True).strip()
    if actual != env["GITHUB_SHA"]:
        raise ValueError("NATIVE_SWARM_SOURCE_SHA_DRIFT")


def canonical_checkpoint(root):
    state = json.loads((root / STATE_FILE).read_text())
    current = root / CANONICAL
    real_sha = sha256_file(current)
    if (state.get("schema") != "janus.model.state.v1" or
        not HEX64.fullmatch(state.get("checkpoint_sha256", "")) or
        state["checkpoint_sha256"] != real_sha):
        raise ValueError("NATIVE_SWARM_INCUMBENT_SHA_MISMATCH")
    return real_sha


def corpus_identity(root):
    corpus = json.loads((root / "runtime/corpus/corpus_manifest.json").read_text())
    contract = contract_identity()
    if (corpus.get("source_repository") != "Hawkar-usls/janus-meta-registry" or
        not HEX40.fullmatch(corpus.get("source_commit", "")) or
        not HEX64.fullmatch(corpus.get("source_digest", "")) or
        corpus.get("evaluation_contract_sha256") != contract["contract_sha256"] or
        corpus.get("anchor_is_training_source") is not False or
        (root / "runtime/corpus/train.txt").stat().st_size < 50000 or
        (root / "runtime/corpus/holdout.txt").stat().st_size < 10000):
        raise ValueError("NATIVE_SWARM_CORPUS_INVALID")
    return corpus, contract


def worker(root, env):
    if env.get("RUNNER_OS") != "Linux" or env.get("RUNNER_ARCH") not in PROFILES:
        raise ValueError("NATIVE_SWARM_UNADMITTED_WORKER")
    check_source(root, env)
    parent_sha = canonical_checkpoint(root)
    corpus, contract = corpus_identity(root)
    profile = PROFILES[env["RUNNER_ARCH"]]
    # Genuine native JANUS inference, even if every candidate gets rejected.
    import torch
    from janus_model.model import ByteTokenizer
    from janus_model.train_registry import load_checkpoint
    torch.set_num_threads(2)
    model, checkpoint = load_checkpoint(root / CANONICAL)
    if checkpoint.get("config") != model.config.to_dict():
        raise ValueError("NATIVE_SWARM_NATIVE_CONFIG_DRIFT")
    model.eval()
    torch.manual_seed(20261031)
    prompt = torch.tensor([ByteTokenizer.encode("JANUS:", bos=True)], dtype=torch.long)
    with torch.no_grad():
        generated = model.generate(prompt, max_new_tokens=12, temperature=0.75)[0].tolist()
    inference_hash = hashlib.sha256(bytes([int(x) & 255 for x in generated])).hexdigest()

    out_dir = root / "runtime/native-calibration" / env["RUNNER_ARCH"]
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_file, candidate_file = out_dir / "TRAINING.json", out_dir / "CANDIDATE.pt"
    cmd = [sys.executable, "-m", "janus_model.train_registry",
           "--train", "runtime/corpus/train.txt",
           "--holdout", "runtime/corpus/holdout.txt",
           "--corpus-manifest", "runtime/corpus/corpus_manifest.json",
           "--incumbent", str(CANONICAL), "--out", str(candidate_file),
           "--receipt", str(receipt_file),
           "--steps", str(profile["steps"]),
           "--batch-size", str(profile["batch_size"]),
           "--lr", str(profile["lr"]), "--seed", str(profile["seed"])]
    # Fixed command, no shell, no arbitrary Rex/source instructions.
    clean_env = {k:v for k,v in os.environ.items() if not any(
        s in k.upper() for s in ("TOKEN", "PASSWORD", "SECRET", "PRIVATE_KEY"))}
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=720,
                       env=clean_env, check=False)
    if p.returncode not in (0, 2) or not receipt_file.is_file():
        raise RuntimeError("NATIVE_SWARM_TRAINING_ENGINE_ERROR")
    receipt = json.loads(receipt_file.read_text())
    status = receipt.get("status")
    if status not in ("PROMOTED", "REJECTED") or (status == "PROMOTED") != (p.returncode == 0):
        raise ValueError("NATIVE_SWARM_WORKER_TRAINING_VERDICT")
    candidate_sha = sha256_file(candidate_file) if candidate_file.exists() else None
    if ((status == "PROMOTED") != (candidate_sha is not None) or
        receipt.get("candidate_checkpoint_sha256") != candidate_sha or
        receipt.get("parent_checkpoint_sha256") != parent_sha or
        receipt.get("evaluation_contract_sha256") != contract["contract_sha256"] or
        receipt.get("source_digest") != corpus["source_digest"] or
        receipt.get("steps") != profile["steps"] or
        receipt.get("seed") != profile["seed"]):
        raise ValueError("NATIVE_SWARM_WORKER_RECEIPT_MISMATCH")
    result = {
        "schema": SCHEMA, "status": "EXECUTED_NATIVE_WEIGHT_CALIBRATION",
        "repository": env["GITHUB_REPOSITORY"], "commit": env["GITHUB_SHA"],
        "run_id": env["GITHUB_RUN_ID"], "attempt": env["GITHUB_RUN_ATTEMPT"],
        "architecture": env["RUNNER_ARCH"], "profile": profile,
        "parent_checkpoint_sha256": parent_sha, "native_inference_sha256": inference_hash,
        "candidate_status": status, "candidate_checkpoint_sha256": candidate_sha,
        "candidate_adaptive_loss": receipt["candidate_eval_loss"],
        "candidate_anchor_loss": receipt["candidate_anchor_eval_loss"],
        "worker_receipt_sha256": sha(receipt),
        "source_digest": corpus["source_digest"],
        "evaluation_contract_sha256": contract["contract_sha256"],
        "authority_delta": 0, "auto_write_main": False, "paid_resources_used": False,
        "external_model_used": False,
    }
    result["receipt_sha256"] = sha(result)
    (out_dir / "WORKER.json").write_bytes(canonical(result) + b"\n")
    return result


def evaluate_independent(root, env, sources):
    check_source(root, env)
    parent_sha = canonical_checkpoint(root)
    corpus, contract = corpus_identity(root)
    import torch
    from janus_model.train_registry import (
        load_checkpoint, eval_loss, tokens, promotion_gate
    )
    from janus_model.eval_contract import EVAL_BATCHES, EVAL_BATCH_SIZE, DEFAULT_ANCHOR
    torch.set_num_threads(2)
    baseline, _ = load_checkpoint(root / CANONICAL)
    holdout = tokens(root / "runtime/corpus/holdout.txt")
    anchor = tokens(DEFAULT_ANCHOR)
    seed_a = contract["adaptive"]["seed"]
    seed_b = contract["anchor"]["seed"]
    baseline_adaptive = eval_loss(baseline, holdout, EVAL_BATCHES, EVAL_BATCH_SIZE, seed_a)
    baseline_anchor = eval_loss(baseline, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, seed_b)

    evaluated = []
    verified_candidates = []
    seen = set()
    for folder in sources:
        if (folder / "WORKER.json").stat().st_size > 30000 or (folder / "TRAINING.json").stat().st_size > 100000:
            raise ValueError("NATIVE_SWARM_INPUT_TOO_BIG")
        worker_receipt = json.loads((folder / "WORKER.json").read_text())
        training_receipt = json.loads((folder / "TRAINING.json").read_text())
        body = {k:v for k,v in worker_receipt.items() if k != "receipt_sha256"}
        arch = worker_receipt.get("architecture")
        if (arch not in PROFILES or arch in seen or
            worker_receipt.get("schema") != SCHEMA or
            worker_receipt.get("receipt_sha256") != sha(body) or
            worker_receipt.get("status") != "EXECUTED_NATIVE_WEIGHT_CALIBRATION" or
            worker_receipt.get("commit") != env["GITHUB_SHA"] or
            worker_receipt.get("run_id") != env["GITHUB_RUN_ID"] or
            worker_receipt.get("attempt") != env["GITHUB_RUN_ATTEMPT"] or
            worker_receipt.get("repository") != env["GITHUB_REPOSITORY"] or
            worker_receipt.get("profile") != PROFILES[arch] or
            worker_receipt.get("parent_checkpoint_sha256") != parent_sha or
            worker_receipt.get("source_digest") != corpus["source_digest"] or
            worker_receipt.get("evaluation_contract_sha256") != contract["contract_sha256"] or
            worker_receipt.get("worker_receipt_sha256") != sha(training_receipt) or
            worker_receipt.get("auto_write_main") is not False or
            worker_receipt.get("external_model_used") is not False or
            worker_receipt.get("paid_resources_used") is not False or
            worker_receipt.get("authority_delta") != 0):
            raise ValueError("NATIVE_SWARM_INVALID_OR_FORGED_WORKER")
        seen.add(arch)
        status = worker_receipt.get("candidate_status")
        if status not in ("PROMOTED", "REJECTED") or training_receipt.get("status") != status:
            raise ValueError("NATIVE_SWARM_INCONSISTENT_TRAINING_STATUS")
        if (training_receipt.get("parent_checkpoint_sha256") != parent_sha or
            training_receipt.get("source_digest") != corpus["source_digest"] or
            training_receipt.get("evaluation_contract_sha256") != contract["contract_sha256"] or
            training_receipt.get("seed") != PROFILES[arch]["seed"] or
            training_receipt.get("steps") != PROFILES[arch]["steps"]):
            raise ValueError("NATIVE_SWARM_TRAINING_MISMATCH")
        candidate_file = folder / "CANDIDATE.pt"
        if status == "REJECTED":
            if candidate_file.exists() or worker_receipt.get("candidate_checkpoint_sha256") is not None:
                raise ValueError("NATIVE_SWARM_REJECTED_CHECKPOINT_SHOULD_NOT_EXIST")
            evaluated.append({"architecture": arch, "verdict": "REJECTED_BY_ORIGINAL_GATE"})
            continue
        candidate_sha = worker_receipt.get("candidate_checkpoint_sha256")
        if (not isinstance(candidate_sha, str) or not HEX64.fullmatch(candidate_sha) or
            candidate_file.stat().st_size > 5000000 or
            sha256_file(candidate_file) != candidate_sha or
            training_receipt.get("candidate_checkpoint_sha256") != candidate_sha):
            raise ValueError("NATIVE_SWARM_CANDIDATE_HASH_INVALID")
        candidate, _ = load_checkpoint(candidate_file)
        if candidate.config != baseline.config:
            raise ValueError("NATIVE_SWARM_CONFIG_ESCALATION")
        a = eval_loss(candidate, holdout, EVAL_BATCHES, EVAL_BATCH_SIZE, seed_a)
        b = eval_loss(candidate, anchor, EVAL_BATCHES, EVAL_BATCH_SIZE, seed_b)
        gate = promotion_gate(candidate_loss=a, incumbent_loss=baseline_adaptive,
                              candidate_anchor_loss=b, incumbent_anchor_loss=baseline_anchor)
        if (abs(a-training_receipt["candidate_eval_loss"]) > 0.002 or
            abs(b-training_receipt["candidate_anchor_eval_loss"]) > 0.002):
            raise ValueError("NATIVE_SWARM_INDEPENDENT_EVALUATION_MISMATCH")
        if not gate["promote"]:
            evaluated.append({"architecture": arch, "verdict": "REJECTED_BY_INDEPENDENT_GATE"})
            continue
        evaluated.append({"architecture": arch, "verdict": "INDEPENDENTLY_VERIFIED_BETTER",
                          "candidate_checkpoint_sha256": candidate_sha,
                          "adaptive_loss": a, "anchor_loss": b})
        verified_candidates.append((a, b, arch, candidate_sha))
    if seen != set(PROFILES):
        raise ValueError("NATIVE_SWARM_NOT_TWO_DISTINCT_WORKERS")
    winner = min(verified_candidates) if verified_candidates else None
    result = {
        "schema": AUDIT, "status": "BEST_CANDIDATE_REVIEW_ONLY" if winner else "INCUMBENT_RETAINED",
        "run_id": env["GITHUB_RUN_ID"], "attempt": env["GITHUB_RUN_ATTEMPT"],
        "commit": env["GITHUB_SHA"],
        "incumbent_checkpoint_sha256": parent_sha,
        "incumbent_adaptive_loss": baseline_adaptive,
        "incumbent_anchor_loss": baseline_anchor,
        "source_digest": corpus["source_digest"],
        "evaluation_contract_sha256": contract["contract_sha256"],
        "workers": sorted(evaluated, key=lambda x:x["architecture"]),
        "winner": ({"architecture": winner[2], "candidate_checkpoint_sha256": winner[3],
                    "adaptive_loss": winner[0], "anchor_loss": winner[1]} if winner else None),
        "local_model_execution": True,
        "main_checkpoint_mutated": False,
        "automatic_production_promotion": False,
        "best_model_in_canonical_runtime": "EXISTING_PROMOTED_CHECKPOINT",
        "claim_ceiling": "MEASURED_HOLDOUT_LOSS_NOT_GENERAL_INTELLIGENCE",
        "paid_resources": False, "authority_delta": 0,
    }
    result["receipt_sha256"] = sha(result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("operation", choices=("worker", "audit"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--inputs", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    if args.operation == "worker":
        report = worker(root, os.environ)
    else:
        if args.inputs is None:
            ap.error("audit needs --inputs")
        files = [args.inputs / ("native-calibration-" + arch.lower()) for arch in PROFILES]
        report = evaluate_independent(root, os.environ, files)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(canonical(report) + b"\n")
    print(json.dumps({"status": report["status"], "receipt_sha256": report["receipt_sha256"],
                      "authority_delta": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
