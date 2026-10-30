"""Real PyTorch checkpoint admission fixture; not a production champion.

Trains a genuine JANUS Transformer on an isolated, deterministic *synthetic*
distribution and verifies held-out loss, serialised weights, CAS publication
and compensating rollback in a temporary Git repository. This tests
mechanics, not a superiority claim for the real canonical checkpoint.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import torch

from daddy_keymaster.broker import sha
from daddy_keymaster.champion_release import (
    CHECKPOINT, ROLLBACK, STATE, Hold, assess, authoritative_state,
    hash_file, publish, rollback_latest,
)
from janus_model.eval_contract import contract_identity
from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer
from janus_model.train_registry import batch_from, save_checkpoint


def git(root, *args):
    return subprocess.check_output(
        ["git", *args], cwd=root, stderr=subprocess.STDOUT, text=True
    ).strip()


def make_text(tag, n):
    # Different documents, reproducible and source-separated by tag.
    # Common grammar is intentionally learnable by the small model.
    lines = [f"JANUS: A B C D E F G H | {tag}-{i:04d}\n" for i in range(n)]
    return "".join(lines)


@contextmanager
def tiny_git_repo(base):
    remote = base / "remote.git"
    root = base / "writer"
    git(base, "init", "--bare", "--initial-branch=main", str(remote))
    git(base, "clone", str(remote), str(root))
    git(root, "switch", "-c", "main")
    git(root, "config", "user.name", "JANUS synthetic test")
    git(root, "config", "user.email", "janus-test@example.invalid")
    yield root
    # TemporaryDirectory removes local repositories automatically.


class RealTorchChampionE2E(unittest.TestCase):
    def test_actual_transformer_gate_publish_rollback(self):
        torch.set_num_threads(2)
        torch.manual_seed(123)
        with tempfile.TemporaryDirectory(prefix="janus-r2-real-torch-") as tmp:
            base = Path(tmp)
            files = base / "data"
            files.mkdir()
            train = files / "train.txt"
            adaptive = files / "holdout.txt"
            final = files / "final.txt"
            anchor = files / "anchor.txt"
            train.write_text(make_text("training", 1100), encoding="utf-8")
            adaptive.write_text(make_text("adaptive", 500), encoding="utf-8")
            final.write_text(make_text("unseen", 170), encoding="utf-8")
            anchor.write_text(make_text("sentinel", 230), encoding="utf-8")
            self.assertNotEqual(hash_file(final), hash_file(train))
            self.assertNotEqual(hash_file(final), hash_file(adaptive))
            self.assertNotEqual(hash_file(final), hash_file(anchor))

            config = JanusModelConfig(
                vocab_size=258, context_length=32, d_model=32,
                n_heads=4, n_layers=1, ff_mult=2, dropout=0.0)
            with tiny_git_repo(base) as root:
                (root / CHECKPOINT).parent.mkdir(parents=True, exist_ok=True)
                (root / STATE).parent.mkdir(parents=True, exist_ok=True)
                baseline = JanusTinyTransformer(config)
                save_checkpoint(root / CHECKPOINT, baseline, {"kind": "synthetic-incumbent"})
                incumbent_sha = hash_file(root / CHECKPOINT)
                (root / STATE).write_text(json.dumps({
                    "schema": "janus.model.state.v1",
                    "checkpoint_sha256": incumbent_sha,
                    "config": config.to_dict(), "promotion_count": 0,
                    "attempt_count": 1, "history": []}), encoding="utf-8")
                git(root, "add", ".")
                git(root, "commit", "-m", "synthetic initial weights")
                git(root, "push", "origin", "HEAD:main")
                old_head = git(root, "rev-parse", "HEAD")

                # Train an ACTUAL JANUS model from the incumbent state.
                challenger = JanusTinyTransformer(config)
                challenger.load_state_dict(baseline.state_dict())
                challenger.train()
                stream = torch.tensor(ByteTokenizer.encode(
                    train.read_text(encoding="utf-8"), bos=True, eos=True),
                    dtype=torch.long)
                rng = torch.Generator().manual_seed(456)
                optimizer = torch.optim.AdamW(challenger.parameters(), lr=0.006)
                last = None
                for i in range(65):
                    x, y = batch_from(stream, 8, config.context_length, rng)
                    _, loss = challenger(x, y)
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(challenger.parameters(), 1)
                    optimizer.step()
                    last = float(loss.item())
                checkpoint = base / "candidate.pt"
                save_checkpoint(checkpoint, challenger, {
                    "kind": "trained-real-PyTorch-weights",
                    "steps": 65, "training_only": True,
                })
                candidate_sha = hash_file(checkpoint)
                self.assertNotEqual(incumbent_sha, candidate_sha)

                with patch("janus_model.eval_contract.DEFAULT_ANCHOR", anchor):
                    contract = contract_identity()
                    source_digest = hashlib.sha256(b"isolated-synthetic-janus-r2").hexdigest()
                    corpus = {
                        "source_digest": source_digest,
                        "evaluation_contract_sha256": contract["contract_sha256"],
                        "anchor_is_training_source": False,
                        "holdout_bytes": adaptive.stat().st_size,
                    }
                    corpus_manifest = files / "corpus_manifest.json"
                    corpus_manifest.write_text(json.dumps(corpus), encoding="utf-8")
                    audit = {
                        "schema": "janus.daddy_keymaster.native_calibration_audit.v1",
                        "status": "BEST_CANDIDATE_REVIEW_ONLY",
                        "main_checkpoint_mutated": False,
                        "automatic_production_promotion": False,
                        "incumbent_checkpoint_sha256": incumbent_sha,
                        "commit": old_head,
                        "source_digest": source_digest,
                        "evaluation_contract_sha256": contract["contract_sha256"],
                        "run_id": "99999900001",
                        "attempt": "1",
                        "workers": [
                            {
                                "architecture": "X64",
                                "verdict": "INDEPENDENTLY_VERIFIED_BETTER",
                                "candidate_checkpoint_sha256": candidate_sha,
                            },
                            {
                                "architecture": "ARM64",
                                "verdict": "REJECTED_BY_ORIGINAL_GATE",
                            },
                        ],
                        "winner": {
                            "architecture": "X64",
                            "candidate_checkpoint_sha256": candidate_sha,
                        },
                    }
                    audit["receipt_sha256"] = sha(audit)
                    audit_path = files / "AUDIT.json"
                    audit_path.write_text(json.dumps(audit), encoding="utf-8")
                    fmanifest = {
                        "schema": "janus.daddy_keymaster.blind_final.v1",
                        "training_excluded": True, "selection_excluded": True,
                        "checkpoint_source_sha256": incumbent_sha,
                        "corpus_source_digest": source_digest,
                        "sha256": hash_file(final),
                    }
                    fmanifest_path = files / "final_manifest.json"
                    fmanifest_path.write_text(json.dumps(fmanifest), encoding="utf-8")
                    report = assess(root, checkpoint, audit_path, corpus_manifest,
                                    adaptive, final, fmanifest_path)
                    self.assertTrue(report["original_promotion_gate"]["promote"])
                    self.assertTrue(report["final_gate_pass"])
                    for metric in ("adaptive_losses", "anchor_losses", "final_losses"):
                        self.assertLess(report[metric]["candidate"],
                                        report[metric]["incumbent"],
                                        metric)
                    print("REAL_TORCH_PASS", json.dumps({
                        "steps": 65, "train_loss": last,
                        "sha_initial": incumbent_sha[:16],
                        "sha_candidate": candidate_sha[:16],
                        "adaptive": report["adaptive_losses"],
                        "anchor": report["anchor_losses"],
                        "final": report["final_losses"]}, sort_keys=True))
                    # TRUSTED_WORKFLOW_VERIFIED is MOCKED here ONLY to exercise
                    # the publishing mechanism in an isolated fake Git remote.
                    simulated_issuer = dict(report)
                    simulated_issuer["source_authentication"] = "TRUSTED_WORKFLOW_VERIFIED"
                    promoted_head = publish(root, checkpoint, simulated_issuer,
                                            old_head, enable=True)
                    new_state, promoted_sha = authoritative_state(root)
                    self.assertEqual(promoted_sha, candidate_sha)
                    self.assertEqual(new_state["promotion_count"], 1)
                    self.assertEqual(git(root, "rev-parse", "origin/main"), promoted_head)
                    rollback_head = rollback_latest(root, promoted_head, enable=True)
                    old_state, restored_sha = authoritative_state(root)
                    self.assertEqual(restored_sha, incumbent_sha)
                    self.assertEqual(old_state["rollback_count"], 1)
                    self.assertEqual(git(root, "rev-parse", "origin/main"), rollback_head)
                    self.assertEqual(json.loads((root / ROLLBACK).read_text())
                                     ["status"], "CONSUMED")
                    self.assertEqual(git(root, "rev-parse", "HEAD^^"), old_head)
                    with self.assertRaisesRegex(Hold, "ROLLBACK_NOT_APPLICABLE"):
                        rollback_latest(root, rollback_head, enable=True)


if __name__ == "__main__":
    unittest.main()
