#!/usr/bin/env python3
"""Deterministic tests for retro-byte *simulation*, never physical evidence."""
import unittest
import retro_byte_channel_probe as b


class RetroByteCandidateTests(unittest.TestCase):
    def test_byte_postselection_analytic_yield(self):
        x=b.exact_model(0.)
        self.assertEqual(x["P_late_zero_byte_success"],1/256)
        self.assertEqual(x["P_early_byte_equals_future_byte_conditioned_on_late_zero"],1.)
        self.assertEqual(x["P_early_byte_equals_independent_future_byte_unconditional"],1/256)
        self.assertEqual(x["preselection_operational_information_bits"],0.)

    def test_noisy_conditional_accuracy_formula(self):
        x=b.exact_model(.2)
        self.assertAlmostEqual(x["P_early_byte_equals_future_byte_conditioned_on_late_zero"],.8**8)
        self.assertAlmostEqual(x["P_early_bit_equals_future_bit_conditioned_on_late_zero"],.8)

    def test_noiseless_sample_shows_conditional_but_not_operational_communication(self):
        x=b.simulate_byte_lane(32768,0.,5010)
        self.assertAlmostEqual(x["raw_early_equals_future_bit_rate"],.5,delta=.012)
        self.assertAlmostEqual(x["raw_early_equals_future_full_byte_rate"],1/256,delta=.002)
        self.assertAlmostEqual(x["postselection_acceptance_rate"],1/256,delta=.002)
        self.assertEqual(x["selected_early_equals_future_byte_rate"],1.)
        self.assertFalse(x["late_conditioning_can_be_used_for_future_to_past_operational_communication"])

    def test_noisy_conditional_byte_agreement(self):
        x=b.simulate_byte_lane(65536,.2,5010)
        self.assertAlmostEqual(x["raw_early_equals_future_bit_rate"],.5,delta=.01)
        self.assertAlmostEqual(x["selected_early_equals_future_byte_rate"],.8**8,delta=.09)
        self.assertLess(x["selected_early_equals_future_byte_rate"],.4)
        self.assertFalse(x["hardware_run"])

    def test_quantum_switch_interference_is_not_time_travel(self):
        x=b.switch_exact()
        self.assertEqual(x["coherent_control_minus_probability"],1.)
        self.assertEqual(x["coherent_control_plus_probability"],0.)
        self.assertFalse(x["future_to_past_single_byte_capacity_demonstrated"])

    def test_physical_candidate_requires_external_real_hardware_evidence(self):
        self.assertFalse(b.guard({})["promote"])
        self.assertFalse(b.guard({},physically_implemented=True)["promote"])

    def test_injected_information_leak_is_rejected(self):
        r=b.run(2048,20261106)
        leak=r["deliberate_leakage_detector_positive_control"]
        self.assertEqual(leak["raw_exact_byte_accuracy"],1.)
        self.assertTrue(leak["leakage_violation_flag"])
        self.assertFalse(leak["promotable"])
        self.assertFalse(r["observed_actual_physical_backward_bit_channel"])
        self.assertFalse(r["janus_production_promoted"])


if __name__=="__main__":
    unittest.main(verbosity=2)
