#!/usr/bin/env python3
"""Unit tests for hypothetical D-CTC SWAP; no physical channel claimed."""
import unittest
import janus_deutsch_ctc_swap_probe as m


class DeutschHypotheticalTests(unittest.TestCase):
    def test_density_swap_for_every_classical_future_bit(self):
        sigma=[[.6+0j,.2+0j],[.2+0j,.4+0j]]
        for bit in (0,1):
            rho=[[1.+0j,0j],[0j,0j]] if bit==0 else [[0j,0j],[0j,1.+0j]]
            self.assertLess(m.maxdiff(m.deutsch_map_swap(rho,sigma),rho),1e-12)

    def test_idealized_fixed_point_depends_on_late_bit(self):
        a,b=(m.solve_future_bit(z) for z in (0,1))
        self.assertEqual(a["iterated_matrix_fixed_point_early_p1"],0.)
        self.assertEqual(b["iterated_matrix_fixed_point_early_p1"],1.)
        self.assertTrue(a["uses_future_bit_as_input_to_cpu_solver"])
        self.assertTrue(b["uses_future_bit_as_input_to_cpu_solver"])
        self.assertTrue(a["early_receiver_did_not_get_this_state_before_input"])

    def test_true_forward_chronology_remains_random(self):
        x=m.real_ordered_control(20000,20261106)
        self.assertLess(abs(x["accuracy"]-.5),.02)
        self.assertTrue(x["future_input_hidden_from_early_algorithm"])

    def test_no_physical_ctc_or_promotion(self):
        x=m.run(4000,20261106)
        self.assertEqual(x["hypothetical_early_state_trace_distance_by_late_choice"],1.)
        self.assertFalse(x["physical_CTC_created"])
        self.assertFalse(x["early_blind_message_receiver_operational"])
        self.assertFalse(x["promotion_allowed"])
        self.assertFalse(x["CPU_simulated_backward_message_proven"])
        self.assertEqual(x["verdict"],"MATHEMATICALLY_POSITIVE_DCTC_ASSUMPTION__PHYSICALLY_UNREALIZED__BLIND_CPU_NULL")


if __name__=="__main__":
    unittest.main(verbosity=2)
