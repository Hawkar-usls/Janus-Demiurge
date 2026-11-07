#!/usr/bin/env python3
"""JANUS R8 ideal quantum vs synthetic future leakage and no-click protection."""
import copy
from fractions import Fraction
import unittest

import janus_ma_jamming_exact_r8 as exact
import janus_ma_jamming_full_attempt_audit_r8 as audit


class MaJammingExactTests(unittest.TestCase):
    def test_exact_four_qubit_tables_normalize(self):
        for mode in exact.SETTINGS:
            self.assertEqual(sum(exact.standard_joint(mode).values()),1)
            self.assertTrue(all(exact.early_marginal(mode)[(x,z)]==Fraction(1,4)
                                for x in exact.BITS for z in exact.BITS))

    def test_standard_qm_future_setting_does_not_change_early_joint(self):
        self.assertEqual(exact.early_marginal("SSM"),
                         exact.early_marginal("BSM"))
        self.assertEqual(exact.total_variation(exact.early_marginal("SSM"),
                                               exact.early_marginal("BSM")),0)

    def test_late_herald_changes_conditional_only(self):
        conditional=exact.late_heralded_early("BSM","PHI_PLUS")
        self.assertEqual(conditional[(0,0)],Fraction(1,2))
        self.assertEqual(conditional[(1,1)],Fraction(1,2))
        self.assertEqual(conditional[(0,1)],0)
        self.assertEqual(conditional[(1,0)],0)
        self.assertEqual(exact.early_marginal("BSM")[(0,1)],Fraction(1,4))

    def test_hypothetical_jamming_has_joint_not_single_marginal_change(self):
        zero=exact.ideal_jamming_early_given_late_bit(0)
        one=exact.ideal_jamming_early_given_late_bit(1)
        self.assertEqual(exact.total_variation(zero,one),1)
        for model in (zero,one):
            for x in (0,1):
                self.assertEqual(sum(model[(x,z)] for z in (0,1)),
                                 Fraction(1,2))

    def test_hypothetical_cannot_be_presented_as_physical_ma_experiment(self):
        result=exact.report()
        self.assertTrue(result["hypothetical_nonphysical_late_jamming_parity"]
                        ["cpu_sample_requires_future_bit_as_input_before_early_sample"])
        self.assertFalse(result["physical_experiment_performed"])
        self.assertFalse(result["physical_retrocausal_signal_observed"])
        self.assertEqual(result["postselection_trap"]
                         ["unconditional_original_attempts_kept"],"1/2")

    def test_unknown_setting_and_herald_rejected(self):
        with self.assertRaises(ValueError):
            exact.standard_joint("TIME_MACHINE")
        with self.assertRaises(ValueError):
            exact.late_heralded_early("BSM","NOT_A_REAL_HERALD")


class FullAttemptAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.early,cls.late,cls.manifest=audit.synthetic(20261107,"normal")

    def test_synthetic_normal_holds_all_attempts_and_no_clicks(self):
        self.assertTrue(audit.verify(self.early,self.late,self.manifest))
        self.assertEqual(len(self.early["records"]),audit.N)
        self.assertEqual(len(self.late["records"]),audit.N)
        self.assertGreater(sum(audit.NOC in (r["x"],r["z"])
                               for r in self.early["records"]),0)
        self.assertFalse(self.manifest["independent_external_early_timestamp_seal_verified"])

    def test_regular_random_rig_scoring_marks_not_physical(self):
        r=audit.score(self.early,self.late,self.manifest,permutations=199)
        self.assertTrue(r["all_trials_included_in_primary_endpoint"])
        self.assertFalse(r["actual_physical_retrocausal_signal_proven"])
        self.assertEqual(r["fixed_sample_N"],2048)
        self.assertIsNone(r["pass_statistical_gate"])
        self.assertTrue(0<r["p_label_permutation_one_sided"]<=1)

    def test_late_herald_does_not_enter_early_statistic(self):
        old=audit.score(self.early,self.late,self.manifest,permutations=199)
        later=copy.deepcopy(self.late)
        for r in later["records"]:
            r["late_outcome"]="ALTERNATE_HERALD"
        manifest=copy.deepcopy(self.manifest)
        manifest["late_sha256"]=audit.sha(later["records"])
        amended=audit.score(self.early,later,manifest,permutations=199)
        self.assertEqual(old["observed_joint_early_TV_between_late_choices"],
                         amended["observed_joint_early_TV_between_late_choices"])
        self.assertEqual(old["p_label_permutation_one_sided"],
                         amended["p_label_permutation_one_sided"])

    def test_missing_early_trial_fails_entire_inference(self):
        altered=copy.deepcopy(self.early)
        altered["records"].pop()
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_FIXED_N_NO_POSTSELECTION"):
            audit.verify(altered,self.late,self.manifest)

    def test_changed_no_click_fails_immutable_digest(self):
        modified=copy.deepcopy(self.early)
        modified["records"][0]["x"]=audit.NOC
        with self.assertRaisesRegex(ValueError,"LEDGER_DIGEST_CHANGED"):
            audit.verify(modified,self.late,self.manifest)

    def test_late_data_leak_inside_early_row_fails_even_if_rehashed(self):
        modified=copy.deepcopy(self.early)
        modified["records"][0]["late_b"]=0
        manifest=copy.deepcopy(self.manifest)
        manifest["early_sha256"]=audit.sha(modified["records"])
        with self.assertRaisesRegex(ValueError,"FUTURE_LEAK_INTO_EARLY"):
            audit.verify(modified,self.late,manifest)

    def test_invalid_timestamp_rejected(self):
        modified=copy.deepcopy(self.late)
        modified["records"][0]["late_epoch_ns"]=modified["records"][0]["early_epoch_ns"] if False else 0
        manifest=copy.deepcopy(self.manifest)
        manifest["late_sha256"]=audit.sha(modified["records"])
        with self.assertRaisesRegex(ValueError,"CLOCK_ORDER_VIOLATION"):
            audit.verify(self.early,modified,manifest)

    def test_preregistered_alpha_or_permutations_cannot_change(self):
        modified=copy.deepcopy(self.manifest)
        modified["primary_alpha"]=0.05
        with self.assertRaisesRegex(ValueError,"PREDECLARED_TEST_CHANGED"):
            audit.verify(self.early,self.late,modified)
        modified=copy.deepcopy(self.manifest)
        modified["primary_permutations"]=999
        with self.assertRaisesRegex(ValueError,"PREDECLARED_TEST_CHANGED"):
            audit.verify(self.early,self.late,modified)

    def test_artificially_injected_late_bit_is_detected_but_not_retrocausal(self):
        early,late,manifest=audit.synthetic(20261107,"leak_injected")
        self.assertTrue(manifest["late_B_preloaded_for_early_generation"])
        v=audit.score(early,late,manifest,permutations=4999)
        self.assertGreater(v["observed_joint_early_TV_between_late_choices"],.80)
        self.assertLess(v["p_label_permutation_one_sided"],audit.ALPHA)
        self.assertFalse(v["actual_physical_retrocausal_signal_proven"])
        self.assertTrue(v["source_preloaded_late_B"])

    def test_quantum_heralded_late_label_keeps_full_population(self):
        early,late,manifest=audit.synthetic(20261107,"quantum_heralded")
        result=audit.score(early,late,manifest,permutations=199)
        self.assertEqual(result["complete_early_attempts"],2048)
        self.assertFalse(result["fourfold_or_late_herald_postselection_in_primary"])
        self.assertFalse(result["actual_physical_retrocausal_signal_proven"])


if __name__=="__main__":
    unittest.main(verbosity=2)
