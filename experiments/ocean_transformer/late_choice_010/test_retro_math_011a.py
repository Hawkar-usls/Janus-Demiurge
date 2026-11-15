#!/usr/bin/env python3
"""No empirical retrocausal claims: exact toy theorems and power unit tests."""
import math
import unittest
from fractions import Fraction

import retro_math_011a as m


class MathematicalRetroCandidateTests(unittest.TestCase):
    def test_bell_normalization_and_unconditional_no_signal(self):
        result=m.quantum_bell()
        self.assertEqual(result["unconditional_later_C_effect"],0)
        self.assertEqual(result["earlier_A_unconditional_P_A0_by_later_choice"],{"0":.5,"1":.5})
        self.assertEqual(result["after_B_outcome_selection_P_A0_given_B0_by_choice"],{"0":1.,"1":.5})
        self.assertTrue(all(abs(sum(d.values())-1)<1e-12 for d in result["joint_distributions"].values()))

    def test_full_no_selection_count_in_PCTC(self):
        for r in m.CTC_POST_RATES:
            q=m.postselect(r)
            self.assertEqual(q["unconditional_signal_delta"],0)
            self.assertAlmostEqual(q["selected_P_A1_given_C1"]+q["selected_P_A1_given_C0"],1)
        self.assertAlmostEqual(m.postselect(Fraction(1,20))["apparent_selected_signal_delta"],19/21)
        self.assertAlmostEqual(m.postselect(Fraction(1,20))["success_fraction"],.525)

    def test_postselection_no_false_usable_signal(self):
        q=m.postselect(Fraction(0,1))
        self.assertEqual(q["apparent_selected_signal_delta"],1)
        self.assertFalse(q["precommitted_early_A_records_affected"])
        self.assertTrue(q["selection_is_not_a_backwards_usable_channel"])

    def test_ontic_future_retro_information_can_be_unobservable(self):
        q=m.latent_retro_model(Fraction(1,10))
        self.assertAlmostEqual(q["latent_lambda_future_C_mutual_information_bits"],.5310044064107188)
        self.assertEqual(q["accessible_A_future_C_mutual_information_bits"],0)
        self.assertEqual(q["unconditional_signal_delta"],0)

    def test_prior_common_cause_mimics_future_signal(self):
        q=m.common_cause_model(Fraction(11,20))
        self.assertAlmostEqual(q["observational_apparent_future_past_delta"],.1)
        self.assertEqual(q["interventional_do_C_effect_on_early_A"],0)

    def test_exact_power_scaling_and_sealed_010(self):
        q=m.power_calculation()
        self.assertEqual(q["N_previously_sealed_010"],16_384)
        self.assertEqual(q["statistical_alpha_two_sided"],.001)
        assert q["delta_probability_difference_for_90_percent_power_given_N_16384_approx"]>.035
        assert q["delta_probability_difference_for_90_percent_power_given_N_16384_approx"]<.036
        by={s["absolute_delta"]:s for s in q["N_required_by_hypothetical_probability_difference"]}
        self.assertGreater(by[.01]["total_N_for_90_percent_power_approx"],200000)
        self.assertLess(by[.01]["total_N_for_90_percent_power_approx"],220000)
        self.assertGreater(by[.04]["power_with_N_16384_approx"],.9)

    def test_no_physical_promotion_even_for_hypothetical_signal(self):
        o=m.evaluate()
        self.assertEqual(o["empirical_new_physical_trials"],0)
        self.assertFalse(o["retrocausality_proven"])
        self.assertFalse(o["falsifiable_candidate_map"][-1]["theoretical_mechanism_identified"])
        self.assertFalse(o["falsifiable_candidate_map"][-1]["currently_physically_observed"])

    def test_out_of_domain_inputs_fail(self):
        with self.assertRaises(ValueError):
            m.born_joint(5,0,0)
        with self.assertRaises(ValueError):
            m.postselect(Fraction(2,1))
        with self.assertRaises(ValueError):
            m.latent_retro_model(Fraction(-1,2))

if __name__=="__main__":
    unittest.main()
