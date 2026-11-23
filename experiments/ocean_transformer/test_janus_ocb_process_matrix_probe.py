#!/usr/bin/env python3
"""OCB mathematical noncausality checks; never a physical time-machine test."""
import math
import unittest
import janus_ocb_process_matrix_probe as q


class OCBTests(unittest.TestCase):
    def test_both_local_instruments_are_trace_preserving(self):
        self.assertTrue(q.check_trace_preserving())

    def test_process_trace_and_positive_spectrum(self):
        for v in (0., .5, .75, 1.):
            self.assertAlmostEqual(q.trace(q.ocb_matrix(v)), 4.)
            self.assertGreaterEqual((1-v)/4, 0.)

    def test_full_matrix_vs_factor_contraction_vs_closed_formula(self):
        for v in (0., .5, .75, 1.):
            w = q.ocb_matrix(v)
            for a in (0,1):
                for b in (0,1):
                    for task in (0,1):
                        for x in (0,1):
                            for y in (0,1):
                                p=q.probability_full(w,a,b,task,x,y)
                                self.assertAlmostEqual(p,
                                    q.probability_pauli(v,a,b,task,x,y),places=12)
                                self.assertAlmostEqual(p,
                                    q.probability_analytic(v,a,b,task,x,y),places=12)

    def test_ocb_causes_game_inequality_violation_not_past_signal(self):
        r=q.run()
        self.assertAlmostEqual(r["all_visibilities"][-1]["score"],
                               (2+math.sqrt(2))/4,places=12)
        self.assertAlmostEqual(
            r["all_visibilities"][-1]["ocb_model_B_input_to_A_marginal_TV"],
            1/math.sqrt(2),places=12)
        self.assertEqual(r["production_promotion"],"REFUSED_RESEARCH_ONLY")
        self.assertFalse(r["earlier_physical_clock_recording"])
        self.assertFalse(r["past_directed_message_detected"])

    def test_visibility_controls_and_threshold(self):
        r=q.run()
        self.assertEqual([z["causal_inequality_violated"] for z in
                          r["all_visibilities"]],[False,False,True,True])
        self.assertAlmostEqual(r["all_visibilities"][0]["score"],.5)
        self.assertAlmostEqual(r["causal_inequality_visibility_threshold"],
                               1/math.sqrt(2))

    def test_invalid_visibility_rejected(self):
        for v in (-.01,1.01):
            with self.assertRaises(ValueError):
                q.ocb_matrix(v)

    def test_no_hidden_future_and_all_outcomes_used(self):
        r=q.run()
        self.assertTrue(r["all_outcomes_retained"])
        self.assertFalse(r["late_postselection_used"])
        self.assertFalse(r["independently_generated_late_choice"])
        self.assertFalse(r["physical_OCB_process_implemented"])


if __name__=="__main__":
    unittest.main(verbosity=2)
