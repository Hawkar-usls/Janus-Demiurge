import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trump"))

from trump_osiris_double_spiral_meet_r0 import (  # noqa: E402
    dense_control_formula,
    exact_search,
    structured_holdout_formula,
    verify_root_sat,
)
from trump_osiris_double_spiral_meet_r1_advisory import (  # noqa: E402
    DENSITY_SKIP_THRESHOLD,
    MAX_PAIR_PROPOSALS,
    double_spiral_meet_r1,
)


class DoubleSpiralMeetR1Tests(unittest.TestCase):
    def compare(self, clauses):
        terminal, witness, _ = exact_search(clauses)
        candidate = double_spiral_meet_r1(clauses)
        self.assertEqual(candidate.terminal, terminal)
        if terminal == "SAT":
            self.assertTrue(verify_root_sat(clauses, witness))
            self.assertTrue(verify_root_sat(clauses, candidate.witness))
        return candidate

    def test_frozen_policy_constants(self):
        self.assertEqual(DENSITY_SKIP_THRESHOLD, 0.70)
        self.assertEqual(MAX_PAIR_PROPOSALS, 12)

    def test_calibration_structured_meets_exactly(self):
        for terminal in ("SAT", "UNSAT"):
            for seed in (101, 102, 103):
                with self.subTest(terminal=terminal, seed=seed):
                    candidate = self.compare(structured_holdout_formula(seed, terminal))
                    self.assertEqual(candidate.mode, "ADVISORY_PROPOSAL_EXACT_DOUBLE_SPIRAL_MEET")
                    self.assertIsNotNone(candidate.separator)
                    self.assertLessEqual(candidate.advisory["proposal_rank"], 12)

    def test_historical_R0_hard_proposal_case_still_exact(self):
        # Historical/exposed R0 seed; permitted as R1 design regression, never R1 holdout.
        candidate = self.compare(structured_holdout_formula(7205, "UNSAT"))
        self.assertEqual(candidate.mode, "ADVISORY_PROPOSAL_EXACT_DOUBLE_SPIRAL_MEET")
        self.assertLessEqual(candidate.advisory["proposal_rank"], 12)

    def test_dense_calibration_skips_advisory_meet(self):
        for seed in (201, 202, 203, 204):
            with self.subTest(seed=seed):
                candidate = self.compare(dense_control_formula(seed))
                self.assertEqual(candidate.mode, "ADVISORY_SKIP_EXACT_FALLBACK")
                self.assertEqual(candidate.advisory["decision"], "DENSITY_SKIP_TO_EXACT_FALLBACK")
                self.assertGreater(candidate.advisory["graph_density"], 0.70)


if __name__ == "__main__":
    unittest.main()
