import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import torch

from janus_model.cli import _augment_prompt
from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer, parameter_count
from janus_model.organs import build_bicameral_context
from janus_model.reflection import build_reflection


class JanusNativeModelTests(unittest.TestCase):
    def test_byte_tokenizer_roundtrip(self):
        text = "JANUS REMEMBERS THE REGISTRY"
        ids = ByteTokenizer.encode(text, bos=True, eos=True)
        self.assertEqual(ids[0], ByteTokenizer.BOS)
        self.assertEqual(ids[-1], ByteTokenizer.EOS)
        self.assertEqual(ByteTokenizer.decode(ids), text)

    def test_forward_and_loss(self):
        torch.manual_seed(7)
        model = JanusTinyTransformer(JanusModelConfig())
        x = torch.randint(0, ByteTokenizer.vocab_size, (2, 32))
        y = torch.randint(0, ByteTokenizer.vocab_size, (2, 32))
        logits, loss = model(x, y)
        self.assertEqual(tuple(logits.shape), (2, 32, ByteTokenizer.vocab_size))
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(parameter_count(model), 100_000)

    def test_bicameral_organ_context_and_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for agent_id, repo, role, commit in [
                ("SCOUT_HRAIN_02", "Hawkar-usls/Hrain", "COGNITION_RECON", "a" * 40),
                ("SCOUT_INAIHR_03", "Hawkar-usls/iNaiHR", "REVERSE_COGNITION_RECON", "b" * 40),
            ]:
                obj = {
                    "agent_id": agent_id,
                    "role": role,
                    "created_at_utc": "2026-09-01T00:00:00Z",
                    "status": "OBSERVED_REPOSITORY_STATE",
                    "target": {"repository": repo, "ref": "main"},
                    "focus": "test",
                    "repository_snapshot": {
                        "target_repo": repo,
                        "target_commit": commit,
                        "file_count": 1,
                        "recent_commits": [],
                    },
                }
                (root / f"{agent_id}.json").write_text(json.dumps(obj), encoding="utf-8")
            ctx = build_bicameral_context(root)
            self.assertEqual(ctx["firewalls"]["terminal_authority"], "VERIFY")
            self.assertFalse(ctx["firewalls"]["bicameral_agreement_is_truth"])
            path = root / "ctx.json"
            path.write_text(json.dumps(ctx), encoding="utf-8")
            augmented = _augment_prompt("QUESTION", str(path))
            self.assertIn("HRAiN@aaaaaaaa=STRUCTURE", augmented)
            self.assertIn("iNaiHR@bbbbbbbb=ASSOCIATION", augmented)
            self.assertIn("VERIFY=DECIDES", augmented)

    def test_modular_reflection_accepts_self_memory_but_never_promotes_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            checkpoint = root / "brain.pt"
            checkpoint.write_bytes(b"native-janus-checkpoint-test")
            checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            state = root / "state.json"
            state.write_text(json.dumps({
                "checkpoint_sha256": checkpoint_sha,
                "last_source_commit": "c" * 40,
                "last_source_digest": "d" * 64,
            }), encoding="utf-8")
            context = root / "context.json"
            context.write_text(json.dumps({
                "schema": "janus.model.modular_organ_context.v2",
                "status": "READ_ONLY_MODULAR_ORGAN_CONTEXT",
                "canonical_formula": "HRAIN_GROUNDS -> EYE_BRIDGES -> INAIHR_ASSOCIATES -> HRAIN_MEDIATES -> NATIVE_MODEL_DECIDES -> VERIFY_DECIDES",
                "context_sha256": "e" * 64,
                "module_count": 17,
                "module_registry_sha256": "f" * 64,
                "organs": {
                    "HRAiN": {"target_commit": "a" * 40},
                    "iNaiHR": {"target_commit": "b" * 40},
                },
                "self_memory": {
                    "status": "BOUND_READ_ONLY_SELF_MEMORY",
                    "digest_sha256": "1" * 64,
                    "file_count": 12,
                    "raw_reflections_are_training_source": False,
                },
                "firewalls": {
                    "read_only": True,
                    "module_observation_grants_mutation": False,
                    "raw_self_reflection_is_training_source": False,
                    "terminal_authority": "VERIFY",
                },
            }), encoding="utf-8")
            inference = root / "inference.txt"
            inference.write_text("JANUS native modular reflection", encoding="utf-8")
            reflection = build_reflection(checkpoint, state, context, inference, "PROMPT", "42")
            self.assertEqual(reflection["status"], "UNVERIFIED_MODEL_REFLECTION")
            self.assertFalse(reflection["authority"]["eligible_for_training"])
            self.assertFalse(reflection["authority"]["repository_mutation"])
            self.assertEqual(reflection["provenance"]["module_count"], 17)
            self.assertEqual(reflection["provenance"]["self_memory_digest_sha256"], "1" * 64)
            self.assertEqual(reflection["provenance"]["module_registry_sha256"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
