#!/usr/bin/env python3
"""011C reproducibility: no synthetic retro signal is promoted to physics."""
from fractions import Fraction as F
import unittest
import retro_fixedpoint_011c as q

class LoopAndChronologyTests(unittest.TestCase):
    def test_exact_stationary_solution_and_normalization(self):
        self.assertEqual(q.fixed_point(F(1,5),F(3,10)),(F(3,5),F(2,5)))
        self.assertEqual(q.fixed_point(F(3,10),F(1,5)),(F(2,5),F(3,5)))
        for u,v in q.BASE.values():
            self.assertEqual(tuple(sum(row) for row in q.transition(u,v)),(1,1))
            self.assertTrue(all(0<=x<=1 for row in q.transition(u,v) for x in row))

    def test_fixed_point_is_eigenvector_not_late_filter(self):
        for c in (0,1):
            s=q.future_control(c)
            T=q.transition(s["u"],s["v"])
            p=s["p"]
            self.assertEqual(p[1],p[0]*T[0][1]+p[1]*T[1][1])
            self.assertEqual(sum(p),1)

    def test_formal_channel_is_binary_symmetric(self):
        a=q.future_control(0)["p"][1]
        b=q.future_control(1)["p"][1]
        self.assertEqual(a,F(2,5))
        self.assertEqual(b,F(3,5))
        self.assertEqual(b-a,F(1,5))
        self.assertAlmostEqual(q.capacity_for_symmetric_pair(a,b),.02904940554533142)

    def test_control_noise_at_half_erases_formal_retro_channel(self):
        d=q.cyclic_family()
        self.assertEqual(len(d),4)
        self.assertAlmostEqual(d[1]["operational_delta_with_ASSUMED_future_loop"],.16)
        self.assertAlmostEqual(d[2]["operational_delta_with_ASSUMED_future_loop"],.1)
        self.assertEqual(d[3]["operational_delta_with_ASSUMED_future_loop"],0)
        self.assertEqual(d[3]["SHANNON_capacity_bits_per_use_UNREALIZED_PHYSICALLY"],0)

    def test_math_constraint_cannot_identify_which_channel_exists(self):
        a=q.unconstrained_capacity()
        self.assertEqual(a["no_signal_symmetric_loop"]["capacity_bits_per_use_in_toy"],0)
        self.assertGreater(a["near_one_bit_symmetric_loop"]["capacity_bits_per_use_in_toy"],.9)
        self.assertFalse(a["near_one_bit_symmetric_loop"]["physical_backward_channel_proven"])
        self.assertTrue(a["near_one_bit_symmetric_loop"]["full_stochastic_matrix_rows_positive"])

    def test_forward_chronology_no_signalling(self):
        baseline=q.forward_no_go()
        self.assertEqual(baseline["interventional_delta"],0)
        self.assertEqual([x["P_committed_early_A1"] for x in baseline["late_intervention_distributions"]],[.5,.5])

    def test_late_input_not_known_when_early_record_is_committed(self):
        a=q.chronology_audit()
        self.assertFalse(a["can_online_early_record_be_computed_by_this_formula_without_future_input"])
        self.assertTrue(a["mathematical_loop_was_assumed_not_derived"])
        self.assertFalse(a["physically_authenticated_early_record_created"])

    def test_approximate_trial_power_only_not_physical(self):
        p=q.sample_size()
        self.assertEqual(p["total_trials_for_90_percent_power_iid_gaussian_approx"],523)
        self.assertEqual(p["previously_frozen_010_total_trials_unmodified"],16384)
        self.assertTrue(p["these_are_not_actual_physical_trials"])

    def test_out_of_domain_parameters_and_nonunique_loop_rejected(self):
        with self.assertRaisesRegex(ValueError,"NONUNIQUE"):
            q.fixed_point(F(0),F(0))
        with self.assertRaisesRegex(ValueError,"INVALID_OR_NONUNIQUE"):
            q.transition(F(-1,10),F(1,2))
        with self.assertRaisesRegex(ValueError,"CONTROL_NOISE"):
            q.future_control(1,F(3,4))
        with self.assertRaisesRegex(ValueError,"CHOICE_MUST_BE_BINARY"):
            q.future_control(2)

    def test_no_physical_retrocausality_claim(self):
        r=q.result()
        self.assertFalse(r["operational_retrocausal_signal_proven"])
        self.assertFalse(r["source_time_loop_observed"])
        self.assertEqual(r["real_physical_trials"],0)
        self.assertEqual(r["status"],"EXACT_NORMALIZED_CYCLIC_TOY__PHYSICAL_MECHANISM_UNKNOWN")

if __name__=="__main__":
    unittest.main()
