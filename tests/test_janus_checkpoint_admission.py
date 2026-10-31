"""Adversarial SHA-bound JANUS native PyTorch checkpoint admission."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from janus_model.checkpoint_admission import (
    PROMOTED, PROMOTED_STATE, checked_config, preflight, sha256_file,
)
from janus_model.model import JanusModelConfig, JanusTinyTransformer
from janus_model.train_registry import load_checkpoint, save_checkpoint


class NativeCheckpointAdmissionTests(unittest.TestCase):
    def fixture(self, target: Path):
        torch.manual_seed(9)
        model = JanusTinyTransformer(JanusModelConfig())
        save_checkpoint(target, model, {"source": "synthetic-test"})
        return sha256_file(target)

    def test_real_committed_promoted_checkpoint_bound_before_load(self):
        actual = sha256_file(PROMOTED)
        committed = json.loads(PROMOTED_STATE.read_text(encoding="utf-8"))["checkpoint_sha256"]
        self.assertEqual(actual, committed)
        self.assertEqual(preflight(PROMOTED), actual)
        model, obj = load_checkpoint(PROMOTED)
        self.assertEqual(model.config.vocab_size, 258)
        self.assertEqual(obj["config"]["context_length"], 128)

    def test_custom_valid_checkpoint_load_with_explicit_digest(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "candidate.pt"
            digest = self.fixture(file)
            self.assertEqual(preflight(file, expected_sha256=digest), digest)
            model, _ = load_checkpoint(file, expected_sha256=digest)
            self.assertEqual(model.config.n_heads, 4)

    def test_wrong_digest_refused_before_unpickler(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "candidate.pt"
            self.fixture(file)
            with patch("janus_model.train_registry.torch.load") as loader:
                with self.assertRaisesRegex(RuntimeError, "SHA_MISMATCH"):
                    load_checkpoint(file, expected_sha256="f" * 64)
                loader.assert_not_called()

    def test_invalid_zip_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "garbled.pt"
            bad.write_bytes(b"unsafe not a zip")
            with self.assertRaisesRegex(RuntimeError, "ZIP_INVALID"):
                preflight(bad)
            linked = Path(td) / "linked.pt"
            try:
                linked.symlink_to(bad)
            except (OSError, NotImplementedError):
                return
            with self.assertRaisesRegex(RuntimeError, "PATH_HOLD"):
                preflight(linked)

    def test_unbounded_config_refused_before_allocation(self):
        config = JanusModelConfig().to_dict()
        for delta in ({"context_length": 1000000}, {"d_model": 65536},
                      {"n_layers": 900}, {"vocab_size": 999}, {"dropout": float("nan")},
                      {"n_heads": 3}):
            with self.subTest(delta=delta), self.assertRaises(RuntimeError):
                checked_config({**config, **delta})
        self.assertEqual(checked_config(config)["vocab_size"], 258)

    def test_nonfinite_weights_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "bad-weights.pt"
            self.fixture(file)
            obj = torch.load(file, weights_only=True, map_location="cpu")
            obj["model_state"]["token.weight"][0, 0] = float("nan")
            torch.save(obj, file)
            with self.assertRaisesRegex(RuntimeError, "NONFINITE_WEIGHTS"):
                load_checkpoint(file, expected_sha256=sha256_file(file))

    def test_custom_cli_requires_digest_before_loading(self):
        from janus_model import cli
        import sys
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "custom.pt"
            self.fixture(file)
            with patch.object(sys, "argv", ["janus", "inspect", "--checkpoint", str(file)]):
                with self.assertRaisesRegex(SystemExit, "CUSTOM_CHECKPOINT_REQUIRES_DIGEST"):
                    cli.main()


if __name__ == "__main__":
    unittest.main()
