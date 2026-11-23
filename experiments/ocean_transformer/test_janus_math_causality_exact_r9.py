#!/usr/bin/env python3
"""Exact algebraic JANUS R9 proof tests. No external QPU or lab."""
from fractions import Fraction as F
import unittest

import janus_math_causality_exact_r9 as m


class ExactCausalTheoremTests(unittest.TestCase):
    def test_field_arithmetic_exact_without_float(self):
        a=m.E(F(1,2),F(1,3))
        b=m.E(F(1,4),F(-2,3))
        self.assertEqual(a*b,m.E(F(1,8)-F(4,9),F(-1,4)))
        self.assertEqual(a+b,m.E(F(3,4),F(-1,3)))
        self.assertTrue(m.E(F(-1,4),F(1,4)).is_positive())
        self.assertFalse(m.E(F(1,4),F(-1,4)).is_positive())
        self.assertFalse(m.E(F(0)).is_positive())

    def test_pauli_square_and_anticommutation_exact(self):
        self.assertTrue(m.validate_ocb_algebra())
        self.assertEqual(m.matmul(m.P,m.P),m.II)
        self.assertEqual(m.matmul(m.Q,m.Q),m.II)
        self.assertTrue(m.matzero(m.matsum(m.matmul(m.P,m.Q),
                                          m.matmul(m.Q,m.P))))

    def test_process_trace_and_positive_eigenvalues_exact(self):
        for v in (F(0),F(1,2),F(3,4),F(1)):
            w=m.algebraic_process(v)
            self.assertEqual(sum(w[i][i] for i in range(16)),m.E(F(4)))
            self.assertGreaterEqual((1-v)/4,0)
            self.assertGreaterEqual((1+v)/4,0)

    def test_all_128_born_branches_and_exact_analytic_are_identical(self):
        for v in (F(0),F(1,2),F(3,4),F(1)):
            w=m.algebraic_process(v)
            for a in (0,1):
                for b in (0,1):
                    for task in (0,1):
                        ps=[]
                        for x in (0,1):
                            for y in (0,1):
                                p=m.generalized_born(w,m.local_A(a,x),
                                                      m.local_B(b,task,y))
                                self.assertEqual(p,m.analytic_probability(
                                    v,a,b,task,x,y))
                                self.assertTrue(p.is_positive())
                                ps.append(p)
                        self.assertEqual(sum(ps),m.E(F(1)))

    def test_exact_causal_inequality_and_positive_advantage(self):
        a=m.prove_causal_game()
        self.assertEqual(len(a),4)
        self.assertEqual([x["violates_definite_order"] for x in a],
                         [False,False,True,True])
        self.assertEqual(a[-1]["exact_score"],
                         m.E(F(1,2),F(1,4)).encoded())
        self.assertEqual(a[-1]["exact_advantage"],
                         m.E(F(-1,4),F(1,4)).encoded())
        self.assertTrue(m.E(F(-1,4),F(1,4)).is_positive())

    def test_visibility_parameter_must_be_exact_rational_and_physical(self):
        for v in (F(-1,100),F(101,100),.5,1):
            with self.assertRaisesRegex(ValueError,
                                        "VISIBILITY_OUTSIDE_PROVED_PROCESS_RANGE"):
                m.algebraic_process(v)

    def test_forward_independence_theorem_and_all_256_pairs(self):
        r=m.prove_independent_future_no_go()
        self.assertEqual(r["finite_exact_cross_checks"],256)
        self.assertIn("P(X,Z|B)=P(X,Z)",r["theorem"])
        self.assertFalse(r["quantum_CPU_simulator_exemption"])

    def test_late_postselection_produces_fake_perfect_correlation(self):
        s=m.prove_postselection_counterexample()
        self.assertEqual(s["selected_fraction_of_original_attempts"],"1/2")
        self.assertTrue(s["postselected_conditional_equals_ideal_jamming_table"])
        self.assertFalse(s["unconditional_past_message"])

    def test_final_certificate_is_math_only_not_physical_proof(self):
        r=m.report()
        self.assertFalse(r["physical_retrocausal_channel_deduced"])
        self.assertTrue(r["no_quantum_hardware_used"])
        self.assertFalse(r["production_promotion"])
        self.assertIn("UNDETERMINED",r["scientific_verdict"])
        self.assertEqual(r["process_trace"],4)
        self.assertEqual(r["fixed_causal_bound"],"3/4")
        self.assertEqual(r["standard_forward_cpu_no_go"]
                         ["finite_exact_cross_checks"],256)


if __name__=="__main__":
    unittest.main(verbosity=2)
