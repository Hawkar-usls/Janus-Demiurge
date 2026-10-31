"""Adversarial tests: all-n exact polynomial identity and frozen Policy-0A scope."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import pnp_policy0a_asymptotic_transfer_witness as witness

class AsymptoticTransferTests(unittest.TestCase):
    def test_exact_all_n_symbolic_certificate(self):
        report=witness.verify_algebra()
        self.assertEqual(report["status"],"ALL_N_ALGEBRA_CERTIFIED__GT_THEOREM_DEPENDENCY_EXPLICIT")
        c=report["exact_polynomials_coefficients_ascending_degree"]
        self.assertEqual(c["L0"],[0,3,378,-509,512])
        self.assertEqual(c["p_squared_minus_4L0"],[0,-12,-1512,2036,2048])
        self.assertGreater(c["strict_slack_substitute_n_equals_m_plus_3"][0],0)
        self.assertTrue(all(v>=0 for v in c["strict_slack_substitute_n_equals_m_plus_3"]))
        self.assertEqual(c["core_frequency_minus_sink_frequency"],[0,0,128])
        self.assertTrue(report["root_affine_preemption_excluded_by_non_affine_private_booster_scope"])
        self.assertFalse(report["external_GT_theorem_independently_reproved"])
        self.assertFalse(report["machine_checked_general_projection_induction"])
        self.assertFalse(report["unrestricted_SAT_lower_bound"])
        self.assertEqual(report["P_VS_NP"],"OPEN")

    def test_clean_room_directed_GT_n_clause_enumeration(self):
        for n in range(3,7):
            clauses,literals,variables=witness.source_gt_n(n)
            self.assertEqual(clauses,n*((n-1)**2+1))
            self.assertEqual(literals,3*n*(n-1)**2)
            self.assertEqual(variables,n*(n-1))
        with self.assertRaises(witness.TransferHold):
            witness.source_gt_n(100)

    def test_policy_parameter_mutations_fail_closed(self):
        for kwargs in ({"b_factor":255},{"p_factor":63},{"attempt_factor":5},
                       {"b_factor":512},{"p_factor":128}):
            with self.subTest(kwargs=kwargs), self.assertRaises(witness.TransferHold):
                witness.verify_algebra(**kwargs)

    def test_symbolic_slack_not_confused_with_samples(self):
        obj=witness.verify_algebra()
        polynomial=obj["exact_polynomials_coefficients_ascending_degree"]["p_squared_minus_4L0"]
        shifted=witness.shift(polynomial,3)
        self.assertGreater(shifted[0],0)
        self.assertTrue(all(v>=0 for v in shifted))
        for n in (3,4,7,11,31,99):
            lhs=witness.value(polynomial,n)
            rhs=witness.value(shifted,n-3)
            self.assertEqual(lhs,rhs)
            self.assertGreater(lhs,0)

    def test_independent_GT_source_change_rejected(self):
        with patch.object(witness,"source_gt_n",return_value=(0,0,0)):
            with self.assertRaises(witness.TransferHold):
                witness.verify_algebra()

    def test_external_theorem_premise_not_promoted_to_self_proof(self):
        report=witness.verify_algebra()
        premise=report["conditional_transfer"]
        self.assertEqual(premise["source_lower_bound"],
                         "FCWS_GT_n_nodes_at_least_2^(n-2)")
        self.assertTrue(premise["assumes_peer_reviewed_FCWS_theorem"])
        self.assertEqual(premise["conditional_residual_count_lower_bound"],
                         "S(H_n)>=2^(n-2)")
        self.assertFalse(report["external_GT_theorem_independently_reproved"])

if __name__=="__main__":
    unittest.main()
