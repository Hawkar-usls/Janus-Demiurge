"""CPU-only security and compatibility tests for Demiurge's native weights."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from janus_model import train_registry as registry
from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer


def _unexpected_checkpoint_code_execution(marker):
    Path(marker).write_text("unsafe unpickler executed", encoding="utf-8")
    return {}


class _MaliciousCheckpoint:
    def __init__(self, marker):
        self.marker = str(marker)

    def __reduce__(self):
        return (_unexpected_checkpoint_code_execution, (self.marker,))


class JanusCheckpointSecurityTests(unittest.TestCase):
    def test_real_promoted_checkpoint_matches_committed_digest(self):
        path = registry.PROMOTED_CHECKPOINT
        state = json.loads(registry.PROMOTED_STATE.read_text(encoding="utf-8"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(digest, state["checkpoint_sha256"])
        model, obj = registry.load_checkpoint(path)
        self.assertEqual(model.config.to_dict(), obj["config"])
        self.assertGreater(len(obj["model_state"]), 10)

    def test_real_promoted_model_generates_tokens_on_cpu(self):
        model, _ = registry.load_checkpoint(registry.PROMOTED_CHECKPOINT)
        prompt = torch.tensor([ByteTokenizer.encode("JANUS:", bos=True)], dtype=torch.long)
        torch.manual_seed(20261020)
        output = model.generate(prompt, max_new_tokens=8, temperature=0.75, top_k=16)
        self.assertEqual(output.device.type, "cpu")
        self.assertGreater(output.shape[1], prompt.shape[1])
        self.assertLessEqual(output.shape[1], prompt.shape[1] + 8)

    def test_hash_mismatch_fails_before_deserialization(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.pt"
            path.write_bytes(b"not valid pickle")
            with patch.object(registry.torch, "load", side_effect=AssertionError("must not deserialize")):
                with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_SHA256_MISMATCH"):
                    registry.load_checkpoint(path, expected_sha256="0" * 64)

    def test_promoted_checkpoint_cannot_diverge_from_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "promoted.pt"
            path.write_bytes(b"wrong promoted weights")
            state = root / "state.json"
            state.write_text(json.dumps({"checkpoint_sha256": "f" * 64}), encoding="utf-8")
            with patch.object(registry, "PROMOTED_CHECKPOINT", path), patch.object(registry, "PROMOTED_STATE", state):
                with patch.object(registry.torch, "load", side_effect=AssertionError("must not deserialize")):
                    with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_SHA256_MISMATCH"):
                        registry.load_checkpoint(path)

    def test_unsafe_pickle_payload_is_not_executed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "malicious.pt"
            marker = root / "untrusted-execution.txt"
            torch.save(_MaliciousCheckpoint(marker), path)
            with self.assertRaises(Exception):
                registry.load_checkpoint(path)
            self.assertFalse(marker.exists(), "unsafe pickle code must not execute")

    def test_roundtrip_rejects_bad_config_and_parameter_shapes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model = JanusTinyTransformer(JanusModelConfig())
            valid = root / "valid.pt"
            registry.save_checkpoint(valid, model, {"test": True})
            restored, obj = registry.load_checkpoint(valid, expected_sha256=registry.sha256_file(valid))
            self.assertEqual(restored.config.to_dict(), model.config.to_dict())

            bad_config = root / "bad_config.pt"
            torch.save({**obj, "config": {**obj["config"], "n_layers": 10_000}}, bad_config)
            with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_CONFIG_INVALID"):
                registry.load_checkpoint(bad_config)

            huge_model = root / "huge_model.pt"
            torch.save({**obj, "config": {**obj["config"], "d_model": 1024, "n_layers": 32, "ff_mult": 32}}, huge_model)
            with patch.object(registry, "JanusTinyTransformer", side_effect=AssertionError("must reject before allocation")):
                with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_PARAMETER_LIMIT_REJECTED"):
                    registry.load_checkpoint(huge_model)

            bad_state = root / "bad_state.pt"
            state = dict(obj["model_state"])
            state["token.weight"] = torch.zeros(1, 1)
            torch.save({**obj, "model_state": state}, bad_state)
            with self.assertRaises(RuntimeError):
                registry.load_checkpoint(bad_state)

            nonfinite_state = root / "nonfinite_state.pt"
            state = dict(obj["model_state"])
            state["token.weight"] = state["token.weight"].clone()
            state["token.weight"][0, 0] = float("nan")
            torch.save({**obj, "model_state": state}, nonfinite_state)
            with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_NONFINITE_WEIGHTS"):
                registry.load_checkpoint(nonfinite_state)

    def test_oversize_and_unbounded_archive_fail_before_torch_load(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "candidate.pt"
            registry.save_checkpoint(path, JanusTinyTransformer(JanusModelConfig()), {})
            with patch.object(registry, "MAX_CHECKPOINT_BYTES", 10):
                with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_SIZE_REJECTED"):
                    registry.load_checkpoint(path)
            with patch.object(registry, "MAX_CHECKPOINT_UNCOMPRESSED_BYTES", 10):
                with self.assertRaisesRegex(RuntimeError, "JANUS_CHECKPOINT_ARCHIVE_LIMIT_REJECTED"):
                    registry.load_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
