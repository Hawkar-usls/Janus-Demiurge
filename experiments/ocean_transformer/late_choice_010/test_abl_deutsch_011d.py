#!/usr/bin/env python3
"""011D: formal no-signalling ABL controls and Deutsch quantum SWAP checks."""
import math
import unittest
from fractions import Fraction as F
import abl_deutsch_011d as q

class ABLvsDeutschQuantum(unittest.TestCase):
    def test_ABL_all_early_records_independent_of_later_basis(self):
        a=q.abl_two_boundary()
        self.assertEqual(a["unconditional_early_delta_A0"],0)
        for t in a["per_choice_all_outcome"]:
            self.assertEqual(t["sum_all_outcomes"],1)
            self.assertEqual(t["unconditional_early_P_A0"],.5)
            self.assertEqual(t["postselect_B0_success_rate"],.5)

    def test_ABL_postselected_correlation_not_early_available(self):
        a=q.abl_two_boundary()
        self.assertEqual(a["per_choice_all_outcome"][0]["ABL_P_early_A0_given_late_B0"],1.)
        self.assertEqual(a["per_choice_all_outcome"][1]["ABL_P_early_A0_given_late_B0"],.5)
        self.assertEqual(a["conditional_postselection_delta_A0"],-.5)
        self.assertFalse(a["physically_late_C_changes_precommitted_A"])

    def test_ABL_reintroducing_all_B_outcomes_restores_no_signal(self):
        for t in q.abl_two_boundary()["per_choice_all_outcome"]:
            d=t["complete_joint_P_A_and_B"]
            self.assertEqual(d["A0B0"]+d["A0B1"],.5)
            self.assertAlmostEqual(sum(d.values()),1.)

    def test_SWAP_is_true_two_qubit_unitary_even_with_coherence(self):
        r=q.rho_plus()
        s=q.rho_z(0)
        joint=q.swap(r,s)
        self.assertTrue(q.same_matrix(q.partial_trace_CR(joint),r))
        self.assertTrue(q.same_matrix(q.partial_trace_CTC(joint),s))
        self.assertTrue(q.same_matrix(q.partial_trace_CR(q.swap(s,r)),s))
        self.assertTrue(q.same_matrix(q.partial_trace_CTC(q.swap(s,r)),r))

    def test_Deutsch_fixed_point_exact_noiseless_and_unique(self):
        m=q.deutsch_swap(F(0))
        assert m["all_outcomes_kept"]
        d=m["late_choice_probabilities"]
        self.assertEqual([x["fixed_point_CTC_input_P_L1"] for x in d],[0.,1.])
        self.assertEqual(m["theory_internal_early_loop_P_L1_delta"],1.)
        self.assertEqual(m["model_internal_binary_Shannon_capacity_bits_per_use"],1.)
        for c in (0,1):
            fixed=q.rho_z(c)
            self.assertTrue(q.same_matrix(q.partial_trace_CR(q.swap(fixed,q.rho_plus())),fixed))
            self.assertTrue(q.same_matrix(q.partial_trace_CR(q.swap(fixed,q.rho_mix())),fixed))

    def test_depolarized_no_selection_comparison(self):
        n=q.deutsch_swap(F(1,10))
        self.assertAlmostEqual(n["theory_internal_early_loop_P_L1_delta"],.9)
        vals=[x["fixed_point_CTC_input_P_L1"] for x in n["late_choice_probabilities"]]
        self.assertAlmostEqual(vals[0],.05)
        self.assertAlmostEqual(vals[1],.95)
        self.assertAlmostEqual(n["model_internal_binary_Shannon_capacity_bits_per_use"],1-q.h2(.05))

    def test_full_return_noise_erases_assumed_future_control(self):
        n=q.deutsch_swap(F(1))
        self.assertEqual(n["theory_internal_early_loop_P_L1_delta"],0.)
        self.assertEqual(n["model_internal_binary_Shannon_capacity_bits_per_use"],0.)
        self.assertEqual([x["fixed_point_CTC_input_P_L1"] for x in n["late_choice_probabilities"]],[.5,.5])

    def test_forward_open_loop_early_record_never_depends_on_future_C(self):
        for eps in q.NOISE:
            m=q.deutsch_swap(eps)
            self.assertEqual(m["ordinary_open_loop_early_P_L1_delta"],0.)
            for x in m["late_choice_probabilities"]:
                self.assertEqual(x["open_forward_no_CTC_early_P_L1"],.5)
                self.assertFalse(x["experimentally_early_loop_L_record_present"])

    def test_density_constraints_and_noise_input_refusal(self):
        with self.assertRaisesRegex(ValueError,"C_NOT_BINARY"):
            q.rho_z(2)
        with self.assertRaisesRegex(ValueError,"NON_HERMITIAN_DENSITY"):
            q.validate_density([[.5,1],[0,.5]])
        with self.assertRaisesRegex(ValueError,"INVALID_DENSITY_POSITIVITY_OR_TRACE"):
            q.validate_density([[1.1,0],[0,-.1]])
        with self.assertRaisesRegex(ValueError,"DEPOLARIZING_RATE"):
            q.deutsch_swap(F(11,10))
        with self.assertRaisesRegex(ValueError,"DEPOLARIZING_RATE"):
            q.noisy_return(q.rho_z(0),F(-1,10))

    def test_DCTC_is_a_postulate_not_derived_principle_of_Janus(self):
        h=q.hypotheses()
        self.assertFalse(h["Janus_Principle_mapping"]["Janus_principle_derivation_from_physical_law"])
        self.assertFalse(h["admission"]["device_return_path_backwards_time_observed"])
        self.assertFalse(h["admission"]["measured_future_to_past_information_capacity"])

    def test_main_summary_avoids_overclaiming(self):
        r=q.result()
        self.assertEqual(r["schema"],q.SCHEMA)
        self.assertEqual(r["physical_experiments_performed"],0)
        self.assertFalse(r["retrocausality_physically_proven"])
        self.assertEqual(r["source_DOIs"]["ABL_1964"],"10.1103/PhysRev.134.B1410")
        self.assertEqual(r["source_DOIs"]["Deutsch_1991"],"10.1103/PhysRevD.44.3197")

if __name__=="__main__":
    unittest.main()
