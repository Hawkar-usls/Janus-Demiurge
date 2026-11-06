#!/usr/bin/env python3
"""Independent CPU regression tests; mathematical results != physical retrocausality."""
import math
import unittest
import janus_temporal_signal_search as j


class IndependentTemporalNoSignalTests(unittest.TestCase):
    def test_every_allowed_channel_is_trace_preserving(self):
        for name,choices in j.channels().items():
            for k in choices:
                with self.subTest(name=name):
                    self.assertTrue(j.cptp_valid(k))

    def test_all_77_candidate_circuits_have_no_raw_future_signal(self):
        states=j.make_states()
        channels=j.channels()
        self.assertEqual(len(states)*len(channels),77)
        for name,(state,late) in states.items():
            for channel,pair in channels.items():
                with self.subTest(state=name,channel=channel):
                    score=j.candidate(state,late,channel,pair)
                    self.assertLess(score["unconditional_trace_distance"],1e-10)
                    self.assertLess(score["max_independent_backend_abs_difference"],1e-10)
                    self.assertLess(max(score["unconditional_early_TV_ZXY"].values()),1e-10)
                    self.assertFalse(score["physical_retrocause_proven"])

    def test_late_conditioning_succeeds_for_bell_but_not_early_available(self):
        state,late=j.make_states()["bell_phi_plus"]
        x=j.candidate(state,late,"I_vs_X",j.channels()["I_vs_X"])
        self.assertEqual(x["unconditional_trace_distance"],0.)
        self.assertAlmostEqual(x["postselected_conditional_trace_distance"],1.,places=10)
        self.assertAlmostEqual(x["later_herald_probability_by_choice"][0],.5,places=10)
        self.assertFalse(x["postselected_information_accessible_early"])

    def test_independent_kraus_and_wavefunction_path_for_amplitude_damping(self):
        state,late=j.make_states()["ghz_3"]
        x=j.candidate(state,late,"I_vs_amplitude_damping",
                      j.channels()["I_vs_amplitude_damping"])
        self.assertLess(x["max_independent_backend_abs_difference"],1e-11)

    def test_injected_leakage_detected_but_rejected(self):
        x=j.leakage_positive_control()
        self.assertEqual(x["unconditional_trace_distance"],1.)
        self.assertTrue(x["set_early_X_based_on_future_bit"])
        self.assertFalse(x["accepted_as_physical_channel"])

    def test_random_early_late_trial_is_only_a_control(self):
        x=j.all_attempts_early_late_control(20000,20261106)
        self.assertLess(abs(x["accuracy"]-.5),.02)
        self.assertEqual(x["shots"],20000)

    def test_all_candidates_recorded_and_fail_closed(self):
        x=j.run(2000,20261106)
        self.assertEqual(x["candidate_count"],77)
        self.assertEqual(len(x["all_candidates"]),77)
        self.assertLess(x["maximum_unconditional_early_trace_distance"],1e-10)
        self.assertEqual(x["maximum_later_postselected_trace_distance"],1.)
        self.assertFalse(x["operational_early_message_observed"])
        self.assertEqual(x["promotion_to_production"],"REFUSED_NO_OPERATIONAL_SIGNAL")


if __name__=="__main__":
    unittest.main(verbosity=2)
