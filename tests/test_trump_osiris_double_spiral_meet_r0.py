import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trump"))

from trump_osiris_double_spiral_meet_r0 import (  # noqa: E402
    dense_control_formula,
    double_spiral_meet,
    exact_search,
    structured_holdout_formula,
    verify_root_sat,
)


class DoubleSpiralMeetR0Tests(unittest.TestCase):
    def assert_matches_exact(self, clauses):
        baseline_terminal, baseline_witness, _ = exact_search(clauses)
        candidate = double_spiral_meet(clauses, max_separator_size=2)
        self.assertEqual(candidate.terminal, baseline_terminal)
        if baseline_terminal == "SAT":
            self.assertTrue(verify_root_sat(clauses, baseline_witness))
            self.assertTrue(verify_root_sat(clauses, candidate.witness))
        else:
            self.assertIsNone(candidate.witness)
        return candidate

    def test_calibration_structured_sat_exact_meet(self):
        for seed in (101, 102, 103):
            with self.subTest(seed=seed):
                candidate = self.assert_matches_exact(structured_holdout_formula(seed, "SAT"))
                self.assertEqual(candidate.mode, "EXACT_DOUBLE_SPIRAL_MEET")
                self.assertIsNotNone(candidate.separator)
                self.assertLessEqual(len(candidate.separator), 2)

    def test_calibration_structured_unsat_exact_meet(self):
        for seed in (101, 102, 103):
            with self.subTest(seed=seed):
                candidate = self.assert_matches_exact(structured_holdout_formula(seed, "UNSAT"))
                self.assertEqual(candidate.mode, "EXACT_DOUBLE_SPIRAL_MEET")
                self.assertIsNone(candidate.witness)
                self.assertEqual(len(candidate.boundary_table), 4)
                self.assertTrue(all(row.get("blocker") in {"CENTER", "LEFT", "RIGHT"} for row in candidate.boundary_table))

    def test_dense_calibration_control_never_changes_truth(self):
        for seed in (201, 202, 203, 204):
            with self.subTest(seed=seed):
                self.assert_matches_exact(dense_control_formula(seed))

    def test_dense_201_charges_discovery_then_falls_back(self):
        candidate = self.assert_matches_exact(dense_control_formula(201))
        self.assertEqual(candidate.mode, "NO_MEET_EXACT_FALLBACK")
        self.assertGreater(candidate.structural_ops, 0)
        self.assertGreater(candidate.fallback_nodes, 0)

    def test_sat_meet_has_root_replay_row(self):
        candidate = self.assert_matches_exact(structured_holdout_formula(101, "SAT"))
        self.assertTrue(any(row.get("root_replay") is True for row in candidate.boundary_table))


if __name__ == "__main__":
    unittest.main()
