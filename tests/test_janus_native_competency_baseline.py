"""Fixed public native-model baseline scorer; no LLM/candidate is promoted."""
import hashlib
import unittest
from janus_model.competency_baseline import (
    SCHEMA, TASKS, MAX_NEW_TOKENS, canonical, score_response, suite_digest,
)


class NativeCompetencyBaselineTests(unittest.TestCase):
    def test_frozen_suite_and_finite_inference_budget(self):
        self.assertEqual(len(TASKS), 4)
        self.assertEqual(len(set(t[0] for t in TASKS)), 4)
        self.assertEqual(MAX_NEW_TOKENS, 48)
        self.assertEqual(len(suite_digest()), 64)
        self.assertTrue(all(0 < len(question) <= 96 for _, question, _ in TASKS))

    def test_exact_answer_requires_generated_suffix_not_prompt_echo(self):
        prompt = "What is two plus two? Reply one numeral."
        good = score_response(prompt, "4", f"Q: {prompt}\nJANUS:4")
        self.assertTrue(good["exact_match"])
        for bad in ("Q: 4", "4 and five", "42", "question repeated"):
            with self.subTest(output=bad):
                record = score_response(prompt, "4", f"Q: {prompt}\nJANUS:{bad}")
                self.assertFalse(record["exact_match"])
                self.assertFalse(record["raw_output_recorded"])

    def test_does_not_accept_missing_model_prefix(self):
        with self.assertRaisesRegex(ValueError, "PROMPT_PREFIX_MISMATCH"):
            score_response("What is two plus two?", "4", "4")
        with self.assertRaisesRegex(ValueError, "GENERATED_TEXT_REQUIRED"):
            score_response("What?", "4", None)

    def test_sha_receipt_contract_is_deterministic(self):
        self.assertEqual(suite_digest(), suite_digest())
        example = {"schema": SCHEMA, "result": False}
        self.assertEqual(hashlib.sha256(canonical(example)).hexdigest(),
                         hashlib.sha256(canonical(example)).hexdigest())


if __name__ == "__main__":
    unittest.main()
