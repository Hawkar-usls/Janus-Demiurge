"""Bounded historical All Star SAT occupancy heuristic: no universal solver claim."""
import unittest
import numpy as np
from restored import experimental_sat_profile as m


class ExperimentalSatProfileIntake(unittest.TestCase):
    def test_small_occurrence_histogram_exact(self):
        profile = m.clause_occupancy_profile(2, [[1], [2]])
        self.assertEqual(profile.universe_size, 4)
        self.assertEqual(profile.distinct_vested_clauses, 3)
        self.assertEqual(profile.multiplicity_histogram, {1: 2, 2: 1})
        self.assertEqual(profile.saturation_ratio, 0.75)
        self.assertEqual(profile.power_sums, [4, 6])
        self.assertTrue(profile.open_space)

    def test_invalid_and_out_of_range_literals_rejected(self):
        for clause in ([0], [1, -1], [3]):
            with self.assertRaises(ValueError):
                m.clause_to_vested_indices(2, clause)

    def test_strict_exponential_complexity_caps(self):
        with self.assertRaisesRegex(ValueError, "VARIABLE_LIMIT_HOLD"):
            m.clause_occupancy_profile(9, [])
        with self.assertRaisesRegex(ValueError, "CLAUSE_LIMIT_HOLD"):
            m.clause_occupancy_profile(2, [[1]] * 33)
        with self.assertRaisesRegex(ValueError, "POWER_ORDER_HOLD"):
            m.power_sums(np.array([15], dtype=np.int64))
        with self.assertRaisesRegex(ValueError, "RECOVERY_ORDER_HOLD"):
            m.recover_histogram_from_power_sums([1], 13)

    def test_python_integer_power_sums_do_not_overflow_int64(self):
        nums = np.array([2 ** 30, 2 ** 30, 2 ** 30], dtype=np.int64)
        self.assertEqual(m.power_sums(nums, 3)[2], 3 * (2 ** 30) ** 3)

    def test_graph_projection_is_explicitly_toy_and_bounded(self):
        children = [{"type": "ally", "score": 0.6}] * 40
        n_vars, clauses = m.graph_fragment_to_clauses(children)
        self.assertEqual(n_vars, 8)
        self.assertTrue(clauses)
        self.assertLessEqual(len(clauses), m.MAX_CLAUSES)

if __name__ == "__main__":
    unittest.main()
