#!/usr/bin/env python3
"""JANUS exact rational jamming/parity contrast regression tests."""
from fractions import Fraction
import unittest
import janus_jamming_parity_counterfactual_r2 as q


class CounterfactualJammingTests(unittest.TestCase):
    def test_causal_eight_cells_are_uniform(self):
        d=q.distribution("normal")
        self.assertEqual(len(d),8)
        self.assertTrue(all(p==Fraction(1,8) for p in d.values()))
        self.assertEqual(sum(d.values()),1)

    def test_normal_future_cannot_be_predicted_from_early_parity(self):
        r=q.summarize("normal")
        self.assertEqual(r["joint_XZ_TV_between_B_choices"],0.)
        self.assertEqual(r["marginal_X_TV_between_B_choices"],0.)
        self.assertEqual(r["marginal_Z_TV_between_B_choices"],0.)
        self.assertEqual(r["parity_predicts_B_if_scored_on_distribution"],"1/2")

    def test_mathematical_jamming_preserves_single_marginals(self):
        r=q.summarize("ideal_jamming_requires_future_parameter")
        self.assertEqual(r["joint_XZ_TV_between_B_choices"],1.)
        self.assertEqual(r["marginal_X_TV_between_B_choices"],0.)
        self.assertEqual(r["marginal_Z_TV_between_B_choices"],0.)
        self.assertTrue(r["future_B_needed_to_sample_prior_XZ"])
        self.assertFalse(r["physical_backward_transport_implemented"])

    def test_postselection_fakes_perfect_parity_at_half_acceptance(self):
        r=q.summarize("late_selected_normal")
        self.assertEqual(r["joint_XZ_TV_between_B_choices"],1.)
        self.assertEqual(r["parity_predicts_B_if_scored_on_distribution"],"1")
        self.assertEqual(r["fraction_of_all_original_attempts_retained"],"1/2")
        self.assertTrue(r["late_herald_required"])
        self.assertFalse(r["earlier_receiver_has_operational_future_B"])

    def test_postselected_and_hypothetical_conditionals_are_identical(self):
        a=q.summarize("ideal_jamming_requires_future_parameter")
        b=q.summarize("late_selected_normal")
        self.assertEqual(a["fraction_joint_conditional_on_B"],
                         b["fraction_joint_conditional_on_B"])
        self.assertNotEqual(a["fraction_of_all_original_attempts_retained"],
                            b["fraction_of_all_original_attempts_retained"])

    def test_invalid_model_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_HYPOTHETICAL_MODEL"):
            q.distribution("actual_time_machine")

    def test_report_fail_closed_no_physical_claim(self):
        r=q.report()
        self.assertFalse(r["no_backward_in_time_classical_bit_implemented"])
        self.assertTrue(r["no_external_physical_implementation"])
        self.assertTrue(r["no_postselection_for_primary_proof"])
        self.assertTrue(r["no_production_promotion"])
        self.assertIn("PHYSICAL_RETROCAUSALITY_NOT_ESTABLISHED",
                      r["scientific_verdict"])


if __name__=="__main__":
    unittest.main(verbosity=2)
