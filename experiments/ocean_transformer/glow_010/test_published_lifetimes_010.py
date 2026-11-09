import math
import unittest

import published_lifetimes_010 as m


class PublishedLifetimeCalculations(unittest.TestCase):
    def test_original_six_wavelengths_and_four_exponents(self):
        result = m.compute()
        self.assertEqual(len(result["published_rows"]), 6)
        self.assertEqual([x["excitation_nm"] for x in result["published_rows"]],
                         [300, 310, 320, 330, 340, 350])
        self.assertEqual(result["published_rows"][-1]["tau_slow_4_s"], 1167.0)

    def test_slow_mode_decay_is_not_total_afterglow(self):
        result = m.compute()
        row = result["published_rows"][-1]
        self.assertAlmostEqual(row["slow_component_exponential_survival_at_600s"],
                               math.exp(-600 / 1167), places=7)
        self.assertNotIn("total_afterglow_power_microwatt", result)

    def test_prior_900_second_tau_deviation(self):
        result = m.compute()
        self.assertAlmostEqual(result["prior_900s_mae_vs_published_condition_means_s"],
                               245.6666667, places=5)
        self.assertGreater(result["prior_900s_mape_vs_published_condition_means_percent"], 20)

    def test_do_not_fabricate_three_model_real_holdout_scores(self):
        result = m.compute()
        self.assertFalse(result["raw_measurement_pairs_available_here"])
        self.assertIsNone(result["monoexp_vs_biexp_vs_powerlaw_out_of_sample_MAE"])
        self.assertIsNone(result["monoexp_vs_biexp_vs_powerlaw_model_winner"])
        self.assertFalse(result["sunlu_composite_emission_measured"])

    def test_pub_lifetimes_range(self):
        result = m.compute()
        self.assertEqual(result["slow_component_tau_range_s"], [1089.0, 1955.0])
        self.assertEqual(result["reported_mean_lifetime_range_s"], [719.85, 1776.99])
        self.assertTrue(result["published_4exp_had_better_fit_than_3exp_by_reported_chi_squared"])
        self.assertTrue(result["no_retrocausal_conclusion"])


if __name__ == "__main__":
    unittest.main()
