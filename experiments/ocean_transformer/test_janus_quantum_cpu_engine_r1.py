#!/usr/bin/env python3
"""JANUS CPU quantum architecture tests — mathematics only, NO retrocausality."""
import math
import unittest

import janus_quantum_cpu_engine_r1 as q


class JANUSCPUEngineR1Tests(unittest.TestCase):

    def test_bloch_for_single_qubit_known_states(self):
        self.assertEqual(q.run(1,[],[0])["bloch"]["0"],[0.,0.,1.])
        self.assertEqual(q.run(1,[q.gate("X",0)],[0])["bloch"]["0"],[0.,0.,-1.])
        self.assertEqual(q.run(1,[q.gate("H",0)],[0])["bloch"]["0"],[1.,0.,0.])
        self.assertEqual(q.run(1,[q.gate("H",0),q.gate("S",0)],[0])["bloch"]["0"],[0.,1.,0.])

    def test_dense_bloch_for_nonclifford_T_phase(self):
        x=q.run(1,[q.gate("H",0),q.gate("T",0)],[0])
        self.assertEqual(x["backend"],"numpy")
        self.assertAlmostEqual(x["bloch"]["0"][0],1/math.sqrt(2))
        self.assertAlmostEqual(x["bloch"]["0"][1],1/math.sqrt(2))
        self.assertAlmostEqual(x["bloch"]["0"][2],0.)

    def test_stabilizer_backend_handles_256_qubits_without_statevector(self):
        g=[q.gate("H",0)]+[q.gate("CX",0,i) for i in range(1,256)]
        x=q.run(256,g,[0,1,127,255])
        self.assertEqual(x["backend"],"stim")
        self.assertIsNone(x["dense_amplitude_count"])
        for p in x["bloch"].values():
            self.assertEqual(p,[0.,0.,0.])

    def test_backend_independence_on_compound_6_qubit_circuit(self):
        gates=[q.gate("H",0),q.gate("CX",0,1),q.gate("S",2),
               q.gate("H",3),q.gate("CZ",1,3),q.gate("SWAP",0,4),
               q.gate("H",2),q.gate("CX",4,5)]
        r=q.compare_backends(6,gates,list(range(6)))
        self.assertLess(r["maximum_bloch_difference"],1e-10)

    def test_numpy_swap_and_controlled_gate_semantics(self):
        g=[q.gate("X",0),q.gate("CX",0,1),q.gate("SWAP",1,2)]
        z=q.run(3,g,[0,1,2],backend="numpy")["bloch"]
        self.assertAlmostEqual(z["0"][2],-1.)
        self.assertAlmostEqual(z["1"][2],1.)
        self.assertAlmostEqual(z["2"][2],-1.)

    def test_choice_on_late_system_does_not_signal_early(self):
        early=[q.gate("H",0),q.gate("CX",0,1)]
        report=q.audit_late_choice(2,early,[],[q.gate("X",1)],[0],[1])
        self.assertLess(report["maximum_one_qubit_trace_distance"],1e-10)
        self.assertFalse(report["genuine_independent_late_free_choice"])
        self.assertFalse(report["operational_retrocausal_channel"])

    def test_eight_bell_pairs_late_choice_no_local_signal(self):
        early=[]
        for k in range(8):
            early += [q.gate("H",2*k),q.gate("CX",2*k,2*k+1)]
        report=q.audit_late_choice(16,early,[],
            [q.gate("X",2*k+1) for k in range(8)],
            [2*k for k in range(8)], [2*k+1 for k in range(8)])
        self.assertLess(report["maximum_one_qubit_trace_distance"],1e-10)
        self.assertEqual(len(report["trace_distance_each_early_one_qubit"]),8)

    def test_forged_future_to_early_gate_is_denied(self):
        with self.assertRaisesRegex(ValueError,
                                    "ILLEGAL_LATE_CONTROL_OF_EARLY_REGISTER"):
            q.audit_late_choice(2,[q.gate("H",0)],[],[q.gate("X",0)],[0],[1])

    def test_extra_fields_bypass_attempt_is_denied(self):
        with self.assertRaisesRegex(ValueError,"GATE_FORMAT_UNEXPECTED_FIELDS"):
            q.run(2,[{"name":"H","qubits":[0],"future_choice":1}],[0])

    def test_illegal_qubits_and_wrong_arity(self):
        with self.assertRaisesRegex(ValueError,"INVALID_QUBIT_INDEX"):
            q.run(2,[q.gate("H",3)],[0])
        with self.assertRaisesRegex(ValueError,"REPEATED_QUBIT_INDEX"):
            q.run(2,[q.gate("CX",0,0)],[0])
        with self.assertRaisesRegex(ValueError,"GATE_ARITY"):
            q.run(2,[q.gate("SWAP",0)],[0])

    def test_backend_rejects_unsupported_or_too_big(self):
        with self.assertRaisesRegex(ValueError,"NON_CLIFFORD_CANNOT_USE"):
            q.run(2,[q.gate("T",0)],[0],backend="stim")
        with self.assertRaisesRegex(ValueError,"DENSE_MEMORY_BUDGET_EXCEEDED"):
            q.run(21,[q.gate("T",0)],[0])
        with self.assertRaisesRegex(ValueError,"CROSSCHECK_DENSE_PROHIBITED_ABOVE_12"):
            q.compare_backends(13,[],[0])

    def test_research_report_gates(self):
        x=q.standard_report()
        self.assertLess(x["cross_backend_6q_max_difference"],1e-10)
        self.assertEqual(x["large_clifford_case"]["qubits"],256)
        self.assertEqual(x["large_clifford_case"]["backend"],"stim")
        self.assertEqual(x["nonclifford_case"]["backend"],"numpy")
        self.assertLess(x["bell_future_local_choice"]["maximum_one_qubit_trace_distance"],1e-10)
        self.assertFalse(x["external_precommit_or_late_rng_connected"])
        self.assertFalse(x["physical_past_directed_signal"])
        self.assertFalse(x["promotion_to_production"])


if __name__=="__main__":
    unittest.main(verbosity=2)
