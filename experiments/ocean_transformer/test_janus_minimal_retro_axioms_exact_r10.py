#!/usr/bin/env python3
"""JANUS R10: formal observational non-identifiability vs do(B) tests."""
import unittest
from fractions import Fraction as F
import janus_minimal_retro_axioms_exact_r10 as j


class MinimalAxiomExactTests(unittest.TestCase):
    def test_all_joint_probability_tables_normalize(self):
        for e in j.ETA_GRID:
            p=j.joint(e)
            self.assertEqual(sum(p.values()),F(1))
            self.assertEqual(len(p),8)
            self.assertTrue(all(type(v) is F and 0 <= v <= 1
                                for v in p.values()))

    def test_forward_and_backward_generators_match_every_observable_cell(self):
        for e in j.ETA_GRID:
            self.assertEqual(j.forward_generator_distribution(e),j.joint(e))
            self.assertEqual(j.backward_formal_distribution(e),j.joint(e))
            self.assertEqual(j.forward_generator_distribution(e),
                             j.backward_formal_distribution(e))

    def test_local_marginals_never_reveal_late_b(self):
        for e in j.ETA_GRID:
            for b in (0,1):
                pair=j.early_given_b_from_joint(e,b)
                self.assertEqual(j.marginal_xz(pair,0),{0:F(1,2),1:F(1,2)})
                self.assertEqual(j.marginal_xz(pair,1),{0:F(1,2),1:F(1,2)})

    def test_observational_total_variation_exactly_eta(self):
        for e in j.ETA_GRID:
            self.assertEqual(j.total_variation(
                j.early_given_b_from_joint(e,0),
                j.early_given_b_from_joint(e,1)),e)

    def test_intervening_on_B_discriminates_opposite_causal_models(self):
        for e in j.ETA_GRID:
            self.assertEqual(j.total_variation(j.forward_do_b(e,0),
                                               j.forward_do_b(e,1)),F(0))
            self.assertEqual(j.total_variation(j.backward_do_b(e,0),
                                               j.backward_do_b(e,1)),e)

    def test_perfect_prediction_can_be_entirely_forward_causal(self):
        p=j.forward_generator_distribution(F(1))
        self.assertTrue(all(prob==F(0) for (x,z,b),prob in p.items()
                            if b != (x^z)))
        self.assertEqual(sum(prob for (x,z,b),prob in p.items()
                             if b==(x^z)),F(1))
        self.assertEqual(j.total_variation(
            j.forward_do_b(F(1),0),j.forward_do_b(F(1),1)),F(0))

    def test_independent_future_axiom_is_compatible_only_with_eta_zero(self):
        for e in j.ETA_GRID:
            p=j.joint(e)
            factors=all(p[(x,z,b)]==F(1,8)
                        for x in (0,1) for z in (0,1) for b in (0,1))
            self.assertEqual(factors,(e==0))

    def test_parity_prediction_success_exact_formula(self):
        for e in j.ETA_GRID:
            p=j.joint(e)
            success=sum((prob for (x,z,b),prob in p.items()
                         if (x^z)==b),F(0))
            self.assertEqual(success,(1+e)/2)

    def test_time_symmetric_postselection_recovers_same_observational_table(self):
        for e in j.ETA_GRID:
            c=j.postselected_global_consistency(e)
            self.assertEqual(c["acceptance_mass"],F(1,2))
            self.assertEqual(c["distribution"],j.joint(e))

    def test_exact_endpoints_no_approximate_float(self):
        self.assertEqual(j.certificate_one_eta(F(0))[
                         "observational_joint_TV_given_B"],"0")
        self.assertEqual(j.certificate_one_eta(F(1))[
                         "observational_joint_TV_given_B"],"1")
        self.assertEqual(j.certificate_one_eta(F(1,2))[
                         "parity_guesses_B_success_under_observation"],"3/4")
        for row in j.report()["all_exact_eta_cases"]:
            self.assertNotIn("0.5",str(row["observational_joint_TV_given_B"]))

    def test_inexact_eta_or_out_of_range_rejected(self):
        for e in (-.01,.5,F(-1,2),F(5,4),1):
            with self.assertRaisesRegex(ValueError,"ETA_OUT_OF_RANGE_OR_NOT_EXACT"):
                j.joint(e)

    def test_symbolic_Q_eta_all_eight_cells_not_just_grid(self):
        result=j.symbolic_all_real_eta_proof()
        self.assertTrue(result[
            "observational_equivalence_all_real_eta_in_closed_interval"])
        self.assertTrue(result[
            "all_eight_joint_cells_verified_as_polynomial_identities"])
        self.assertEqual(len(result["eight_exact_polynomial_coefficients"]),8)
        self.assertEqual(result["backward_doB_total_variation_exact"],"eta")
        self.assertEqual(result["forward_doB_total_variation_exact"],"0")
        self.assertFalse(result["physical_retrocausal_resource_derived"])
        self.assertEqual({v["joint_eta_coeff"] for v in
                          result["eight_exact_polynomial_coefficients"]},
                         {"1/8","-1/8"})

    def test_deduction_does_not_claim_physical_retrocausality(self):
        r=j.report()
        self.assertTrue(r["cpu_only"])
        self.assertFalse(r["physical_retrocausality_deduced"])
        self.assertFalse(r["novel_physical_mechanism_constructed"])
        self.assertFalse(r["production_promotion"])
        self.assertEqual(len(r["all_exact_eta_cases"]),5)
        self.assertIn("intervention",r["proof_status"].lower())


if __name__=="__main__":
    unittest.main(verbosity=2)
