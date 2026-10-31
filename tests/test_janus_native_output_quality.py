"""Native tiny-LM output witness: structural-only, no truth promotion."""
import hashlib
import unittest

from janus_model.output_quality import assess


class NativeOutputQualityTests(unittest.TestCase):
    def test_structural_candidate_is_still_unverified(self):
        text = "Q: What changed?\nC:HRAIN\nJANUS: The repository snapshot reports a newer commit and a changed contract file."
        result = assess(text)
        self.assertEqual(result["status"], "STRUCTURAL_CANDIDATE_UNVERIFIED")
        self.assertFalse(result["semantic_quality_verified"])
        self.assertFalse(result["model_truth"])
        self.assertFalse(result["eligible_for_autonomous_merge"])
        self.assertFalse(result["eligible_for_training"])
        self.assertEqual(result["native_output_sha256"],
                         hashlib.sha256(text.encode()).hexdigest())

    def test_real_prior_native_garbled_output_is_held(self):
        text = ('Q: from your own checkpoint.\nC:M17|Habc|Idef\nJANUS:\n'
                'python toools/janus_tresearch_stative_role_narate_operator_model_inear_eal_required_before": false,\n')
        result = assess(text)
        self.assertEqual(result["status"], "LOW_SIGNAL_HOLD")
        self.assertIn("UNBALANCED_DOUBLE_QUOTE", result["reasons"])

    def test_prompt_only_or_empty_output_is_held(self):
        for text in ("", "Q: test prompt", "Q: test\nJANUS:", "JANUS: hello"):
            with self.subTest(text=text):
                self.assertEqual(assess(text)["status"], "LOW_SIGNAL_HOLD")

    def test_invalid_json_and_context_echo_are_held(self):
        self.assertIn("TRUNCATED_OR_INVALID_JSON",
                      assess('Q: test\nJANUS: {"alpha": "open"')["reasons"])
        repeated = "The same long sentence is repeated without independent analysis."
        self.assertIn("ECHO_OF_INPUT_CONTEXT",
                      assess("Q: " + repeated + "\nJANUS: " + repeated)["reasons"])

    def test_report_deterministic_and_zero_authority(self):
        text = "Q: task\nJANUS: An observation is unverified until independent tests reproduce it."
        a, b = assess(text), assess(text)
        self.assertEqual(a, b)
        self.assertFalse(a["model_output_is_independent_evidence"])
        self.assertFalse(a["eligible_for_training"])


if __name__ == "__main__":
    unittest.main()
