#!/usr/bin/env python3
"""Unit tests of CPU classical QM emulation, not a retrocausal experiment."""
import math
import unittest
import janus_cpu_quantum_emulator as q


class CPUQuantumEmulatorTests(unittest.TestCase):
    def test_bell_marginal_never_depends_on_future_bit(self):
        a,b=(q.bell_late_message(i) for i in (0,1))
        for trial in (a,b):
            self.assertAlmostEqual(trial["early_marginal_before_late_choice"][0],.5)
            self.assertAlmostEqual(trial["early_marginal_after_late_choice"][1],.5)
            self.assertAlmostEqual(trial["late_zero_herald_probability"],.5)
            self.assertFalse(trial["unconditioned_early_readout_contains_future_bit"])
        self.assertEqual(a["early_distribution_given_LATER_herald"],[1.,0.])
        self.assertEqual(b["early_distribution_given_LATER_herald"],[0.,1.])

    def test_real_16_qubit_statevector_conditional_byte(self):
        for message in (0,0xA5,255):
            r=q.bell_byte(message)
            self.assertEqual(r["early_byte_given_later_herald"],f"{message:02x}")
            self.assertAlmostEqual(r["late_herald_all_zero_probability"],1/256,places=10)
            self.assertEqual(r["unconditional_early_byte_correct_probability"],1/256)
            self.assertFalse(r["operational_early_decoding_available"])
            for p in r["unconditioned_early_marginal_each_bit"]:
                self.assertAlmostEqual(p[0],.5,places=10)

    def test_unitaries_reversible_without_time_reversal(self):
        st=q.StateVector(3)
        st.h(0).t(0).s(1).cx(0,1).cz(0,2).swap(1,2)
        self.assertAlmostEqual(st.norm(),1.,places=12)
        st.swap(1,2).cz(0,2).cx(0,1).s(1).s(1).s(1).t(0)
        # Three S gates invert S; seven T gates invert T.
        for _ in range(6):st.t(0)
        st.h(0)
        self.assertAlmostEqual(st.norm(),1.,places=12)
        self.assertAlmostEqual(abs(st.a[0]),1.,places=10)

    def test_projection_keeps_probability_and_rejects_impossible(self):
        st=q.StateVector(2).h(0).cx(0,1)
        p,out=st.project(1,0)
        self.assertAlmostEqual(p,.5)
        self.assertAlmostEqual(out.norm(),1.)
        p2,nothing=out.project(1,1)
        self.assertEqual(p2,0.)
        self.assertIsNone(nothing)

    def test_pctc_nonunitary_conditional_map_is_not_real_channel(self):
        x=q.pctc_consistency_map()
        self.assertEqual(x["K_real"],[[1.,0.],[0.,0.]])
        self.assertEqual(x["input_examples"]["one"]["acceptance_probability"],0.)
        self.assertAlmostEqual(x["input_examples"]["plus"]["acceptance_probability"],.5)
        self.assertEqual(x["input_examples"]["plus"]["final_conditional_probabilities"],[1.,0.])
        self.assertFalse(x["physical_CTC_supplied"])

    def test_large_emulated_qubit_count_is_rejected(self):
        with self.assertRaises(ValueError):
            q.StateVector(17)

    def test_all_attempts_noise_controls_not_physical_messages(self):
        for noise in (0.,.20):
            x=q.byte_monte_carlo(32768,42+round(noise*100),noise)
            self.assertAlmostEqual(x["all_shots_bit_accuracy"],.5,delta=.012)
            self.assertAlmostEqual(x["all_shots_exact_byte_accuracy"],1/256,delta=.002)
            self.assertAlmostEqual(x["late_postselection_acceptance"],1/256,delta=.002)
            self.assertAlmostEqual(x["accepted_exact_byte_accuracy"],(1-noise)**8,delta=.10)
            self.assertFalse(x["physical_backward_channel_connected"])

    def test_no_retrocausal_claim_or_production_promotion(self):
        x=q.run(2048,92026)
        self.assertEqual(x["verdict"],"SIMULATION_VERIFIED__LATE_POSTSELECTION_CORRELATION__NO_EARLY_MESSAGE")
        self.assertFalse(x["physical_channel_safety_gate"]["promote_to_JANUS"])
        self.assertFalse(x["real_future_to_past_channel"])
        self.assertFalse(x["production_checkpoint_changed"])


if __name__=="__main__":
    unittest.main(verbosity=2)
