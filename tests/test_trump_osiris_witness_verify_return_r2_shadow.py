import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trump"))

from trump_osiris_double_spiral_meet_r0 import (  # noqa: E402
    dense_control_formula,
    structured_holdout_formula,
)
from trump_osiris_witness_verify_return_r2_shadow import (  # noqa: E402
    PATTERN_ADMISSION_MIN_ACCURACY,
    PATTERN_ADMISSION_MIN_PROSPECTIVE_CASES,
    RULE_ID,
    prospective_pattern_admission_gate,
    witness_verify_return_r2_shadow,
)


class WitnessVerifyReturnR2ShadowTests(unittest.TestCase):
    def test_constants_frozen(self):
        self.assertEqual(RULE_ID, "TRUMP_R2_PATTERN_RULE_DENSITY_ROUTE_v1")
        self.assertEqual(PATTERN_ADMISSION_MIN_PROSPECTIVE_CASES, 24)
        self.assertEqual(PATTERN_ADMISSION_MIN_ACCURACY, 0.95)

    def test_structured_observe_preserve_verify_return(self):
        result = witness_verify_return_r2_shadow(structured_holdout_formula(301, "SAT")).as_dict()
        self.assertEqual(result["pre_verification_witness"]["payload"]["truth"], None)
        self.assertEqual(
            result["pre_verification_witness"]["payload"]["stage"],
            "PRESERVED_BEFORE_TRUTH_VERIFICATION",
        )
        self.assertTrue(result["independent_verification"]["verification_pass"])
        self.assertTrue(result["return_higher"]["experience_eligible"])
        self.assertFalse(result["return_higher"]["proof_authority"])
        self.assertFalse(result["return_higher"]["routing_authority"])

    def test_dense_pattern_predicts_skip_without_truth_prediction(self):
        result = witness_verify_return_r2_shadow(dense_control_formula(302)).as_dict()
        self.assertEqual(result["prediction"]["predicted_route_class"], "DENSITY_SKIP_TO_EXACT_FALLBACK")
        self.assertIsNone(result["prediction"]["truth_prediction"])
        self.assertTrue(result["independent_verification"]["frozen_pattern_prediction_match"])
        self.assertTrue(result["return_higher"]["pattern_support"])

    def test_pattern_gate_never_grants_truth_authority(self):
        rows = []
        for seed in range(400, 412):
            rows.append(witness_verify_return_r2_shadow(structured_holdout_formula(seed, "SAT")).as_dict())
        for seed in range(500, 512):
            rows.append(witness_verify_return_r2_shadow(dense_control_formula(seed)).as_dict())
        gate = prospective_pattern_admission_gate(rows, rule_frozen_before_holdout=True)
        self.assertTrue(gate["pass"])
        self.assertFalse(gate["truth_authority_if_pass"])
        self.assertFalse(gate["current_run_routing_authority"])

    def test_unfrozen_rule_cannot_promote(self):
        rows = []
        for seed in range(600, 624):
            rows.append(witness_verify_return_r2_shadow(dense_control_formula(seed)).as_dict())
        gate = prospective_pattern_admission_gate(rows, rule_frozen_before_holdout=False)
        self.assertFalse(gate["pass"])


if __name__ == "__main__":
    unittest.main()
