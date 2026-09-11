import json
import tempfile
import unittest
from pathlib import Path

from janus_model.cli import _augment_prompt
from janus_model.model import ByteTokenizer


class JanusNativePromptBudgetTests(unittest.TestCase):
    def context_path(self, root: Path, compact: str) -> Path:
        path = root / "organ-context.json"
        path.write_text(
            json.dumps(
                {
                    "status": "READ_ONLY_MODULAR_ORGAN_CONTEXT",
                    "module_count": 17,
                    "native_prompt_compact": compact,
                    "native_prompt_suffix": "THIS DESCRIPTIVE SUFFIX IS INTENTIONALLY MUCH LONGER THAN THE NATIVE CONTEXT WINDOW " * 4,
                    "organs": {
                        "HRAiN": {"target_commit": "a" * 40},
                        "iNaiHR": {"target_commit": "b" * 40},
                    },
                    "trump_research": {
                        "P_VS_NP": "OPEN",
                        "native_frontier_intake": {"selected_commit": "c" * 40},
                    },
                    "firewalls": {
                        "read_only": True,
                        "terminal_authority": "VERIFY",
                        "module_observation_grants_mutation": False,
                        "raw_self_reflection_is_training_source": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_budgeted_prompt_preserves_user_tail_and_compact_verified_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            compact = "M17|Haaaaaaaa|Ibbbbbbbb|TOPEN|Fcccccccc|V1"
            path = self.context_path(root, compact)
            user_prompt = "СТАРЫЙ_ХВОСТ_" * 20 + "ВАЖНЫЙ_ВОПРОС_TRUMP"
            packed = _augment_prompt(user_prompt, str(path), context_length=128)

        ids = ByteTokenizer.encode(packed, bos=True)
        self.assertLessEqual(len(ids), 128)
        self.assertIn("ВАЖНЫЙ_ВОПРОС_TRUMP", packed)
        self.assertIn("C:" + compact, packed)
        self.assertTrue(packed.endswith("\nJANUS:"))
        self.assertNotIn("THIS DESCRIPTIVE SUFFIX", packed)

    def test_budgeted_prompt_without_organs_is_also_explicitly_bounded(self):
        prompt = "x" * 400 + "TAIL"
        packed = _augment_prompt(prompt, None, context_length=128)
        self.assertLessEqual(len(ByteTokenizer.encode(packed, bos=True)), 128)
        self.assertTrue(packed.endswith("TAIL"))

    def test_legacy_unbounded_helper_remains_compatible_for_old_callers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self.context_path(root, "M17|Haaaaaaaa|Ibbbbbbbb|TOPEN|FNONE|V1")
            augmented = _augment_prompt("QUESTION", str(path))
        self.assertIn("QUESTION", augmented)
        self.assertIn("THIS DESCRIPTIVE SUFFIX", augmented)
        self.assertTrue(augmented.endswith("\nJANUS:"))

    def test_oversized_compact_context_fails_closed_instead_of_evicting_user_intent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self.context_path(root, "C" * 120)
            with self.assertRaisesRegex(SystemExit, "JANUS_COMPACT_CONTEXT_EXCEEDS_MODEL_BUDGET"):
                _augment_prompt("QUESTION", str(path), context_length=128)


if __name__ == "__main__":
    unittest.main()
