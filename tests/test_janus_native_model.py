import json
import tempfile
import unittest
from pathlib import Path

import torch

from janus_model.cli import _augment_prompt
from janus_model.model import ByteTokenizer, JanusModelConfig, JanusTinyTransformer, parameter_count
from janus_model.organs import build_bicameral_context


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


if __name__ == "__main__":
    unittest.main()
