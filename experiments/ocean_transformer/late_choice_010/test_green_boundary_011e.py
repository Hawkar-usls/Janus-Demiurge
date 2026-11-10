#!/usr/bin/env python3
"""011E regression: do not confuse future-conditioned reconstruction with observed past."""
import unittest
from fractions import Fraction as F
import green_boundary_011e as q

class AdvancedRetardedFieldContracts(unittest.TestCase):
    def test_later_source_does_not_emit_before_future_choice(self):
        for c in (0,1):
            self.assertTrue(all(q.src_at(t,c)==0 for t in range(q.T_SOURCE)))
        self.assertEqual(q.src_at(q.T_SOURCE,1),1)
        self.assertEqual(q.src_at(q.T_SOURCE+1,1),F(1,2))
        self.assertEqual(q.src_at(q.T_SOURCE+2,1),F(1,4))

    def test_retarded_wave_has_only_delayed_support(self):
        self.assertEqual([t for t in range(q.LAST_T+1) if q.ret_at(t,1)], [21,22,23])
        self.assertEqual(q.ret_at(q.EARLY_T,1),0)
        self.assertEqual(q.ret_at(q.LATE_RET_T,1),1)

    def test_advanced_wave_has_pre_future_support_ONLY_BY_BOUNDARY(self):
        self.assertEqual([t for t in range(q.LAST_T+1) if q.adv_at(t,1)],[11,12,13])
        self.assertEqual(q.adv_at(q.EARLY_T,1),1)
        self.assertEqual(q.adv_at(q.LATE_RET_T,1),0)

    def test_all_predeclared_boundaries_and_early_contrasts(self):
        models=q.all_model_results()
        self.assertEqual([m["boundary"] for m in models],["retarded","symmetric","advanced"])
        self.assertEqual([m["full_unselected_early_model_amplitude_delta"] for m in models],["0","1/2","1"])
        self.assertEqual([m["full_unselected_late_model_amplitude_delta"] for m in models],["1","1/2","0"])
        self.assertTrue(all(not m["boundary_law_independently_deduced_from_wave_equation"] for m in models))

    def test_linear_mixtures_of_same_sources_and_no_outcome_filter(self):
        for t in range(q.LAST_T+1):
            for c in (0,1):
                self.assertEqual(q.field_at(t,c,F(1,2)),(q.ret_at(t,c)+q.adv_at(t,c))/2)
                self.assertEqual(q.field_at(t,c,F(0)),q.ret_at(t,c))
                self.assertEqual(q.field_at(t,c,F(1)),q.adv_at(t,c))

    def test_every_timestamp_accounted_and_source_amplitude_sum_is_not_energy(self):
        for m in q.all_model_results():
            for row in m["traces"]:
                self.assertEqual(len(row["receiver_trace_fraction_strings"]),q.LAST_T+1)
                self.assertEqual(row["sum_of_all_discrete_receiver_amplitudes_not_an_energy"],
                                 "0" if row["do_C"]==0 else "7/4")

    def test_compensated_advanced_past_term_needs_assumed_absorber(self):
        a=q.false_controls()["absorber_compensator_ALGEBRA_ONLY"]
        self.assertEqual(a["advanced_past_precursor_after_compensator"],"0")
        self.assertTrue(a["equals_retarded_trace_all_steps"])
        self.assertFalse(a["absorber_material_response_or_boundary_derived_from_theory"])

    def test_centered_digital_filter_creates_fake_future_signal(self):
        a=q.false_controls()["noncausal_digital_filter_artifact"]
        self.assertEqual(a["centered_nonzero_before_source"],[14,15])
        self.assertEqual(a["trailing_nonzero_before_source"],[])
        self.assertEqual(a["centered_source_pre_event_t14_amplitude"],"1/5")
        self.assertEqual(a["trailing_source_pre_event_t14_amplitude"],"0")
        self.assertTrue(a["reading_future_raw_samples_required_for_centered_filter"])

    def test_bad_clock_alone_fakes_past_arrival(self):
        a=q.false_controls()["instrument_timestamp_miscalibration_artifact"]
        self.assertEqual(a["true_retarded_arrival_t"],21)
        self.assertEqual(a["apparent_displayed_arrival_t"],11)
        self.assertTrue(a["ordinary_retarded_physical_timeline_unchanged"])

    def test_ordinary_forward_early_record_is_independent_of_future_choice(self):
        a=q.causal_initial_record()
        self.assertEqual(a["ordinary_forward_interventional_delta"],0)
        self.assertEqual(a["precommitted_A_distribution_by_do_C"]["0"],
                         a["precommitted_A_distribution_by_do_C"]["1"])
        self.assertFalse(a["early_witness_is_real_hardware"])

    def test_field_equation_does_not_identify_green_boundary(self):
        eq=q.theoretical_source_equivalence()
        self.assertFalse(eq["wave_law_selects_advanced_weight_without_boundary"])
        self.assertIn("Box(G_adv-G_ret)=0",eq["homogeneous_difference"])
        self.assertFalse(eq["solves_full_Wheeler_Feynman_absorber_interaction"])

    def test_false_advanced_prop_not_labelled_new_derived_physics(self):
        a=q.evaluate()
        self.assertFalse(a["scientific_admission"]["new_unconditional_physical_law_prediction_derived_without_boundary"])
        self.assertEqual(a["scientific_admission"]["physical_trials_completed"],0)
        self.assertFalse(a["scientific_admission"]["physical_retrocausal_signal_measured"])
        self.assertEqual(a["scientific_admission"]["actual_late_physically_randomized_QRNG_choices"],0)
        self.assertTrue(a["scientific_admission"]["no_postselection_and_all_time_samples_included"])

    def test_invalid_late_setting_future_time_boundary_refused(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_CHOICE"):
            q.src_at(16,2)
        with self.assertRaisesRegex(ValueError,"TIME_MUST"):
            q.src_at(16.0,1)
        with self.assertRaisesRegex(ValueError,"BOUNDARY_FRACTION"):
            q.field_at(11,1,F(-1,2))
        with self.assertRaisesRegex(ValueError,"BOUNDARY_FRACTION"):
            q.field_at(11,1,0.5)

if __name__=="__main__":unittest.main()
