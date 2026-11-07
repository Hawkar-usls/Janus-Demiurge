#!/usr/bin/env python3
"""JANUS joint-early-witness tests: detect planted interaction; reject claims.

These tests exercise a classical statistical detector on synthetic data.
They do NOT establish a physically retrocausal resource.
"""
import random
import unittest

import janus_retro_early_joint_witness_r1 as jw


class EarlyJointWitnessTests(unittest.TestCase):
    def test_exact_xor_only_joint_witness(self):
        a=[i&1 for i in range(256)]
        c=[(i>>1)&1 for i in range(256)]
        b=[x^y for x,y in zip(a,c)]
        out=jw.score(a,c,b)
        self.assertEqual(out["A_marginal_tv"],0.)
        self.assertEqual(out["C_marginal_tv"],0.)
        self.assertEqual(out["A_C_joint_tv"],1.)
        self.assertEqual(out["joint_excess_over_largest_marginal"],1.)
        # This is an intentionally leaked synthetic B, not an actual future.
        p=jw.permutation_pvalue([(a,c,b)],iterations=999,seed=16)
        self.assertLessEqual(p["permutation_p_joint_interaction_within_trial"],.002)
        self.assertLessEqual(p["bonferroni_adjusted_min_p_two_views"],.004)

    def test_no_leak_fixed_random_control_is_not_synthetic_physical_proof(self):
        r=random.Random(18001)
        a=[r.getrandbits(1) for _ in range(256)]
        c=[r.getrandbits(1) for _ in range(256)]
        b=[r.getrandbits(1) for _ in range(256)]
        z=jw.permutation_pvalue([(a,c,b)],iterations=199,seed=99)
        self.assertGreaterEqual(z["permutation_p_joint_interaction_within_trial"],.005)
        self.assertLessEqual(z["permutation_p_joint_interaction_within_trial"],1.)
        self.assertTrue(z["exploratory_not_prospective"])

    def test_two_complete_trials_reproducible_permutations(self):
        a=[i%2 for i in range(256)]
        c=[(i//2)%2 for i in range(256)]
        b=[(i*37+23)%2 for i in range(256)]
        t=[(a,c,b),(list(reversed(a)),c,b)]
        r1=jw.permutation_pvalue(t,iterations=199,seed=20261107)
        r2=jw.permutation_pvalue(t,iterations=199,seed=20261107)
        self.assertEqual(r1,r2)
        self.assertEqual(r1["permutations"],199)
        self.assertTrue(r1["conditional_exchangeability_not_externally_verified"])

    def test_refuse_degenerate_late_target(self):
        with self.assertRaisesRegex(ValueError,"DEGENERATE_FUTURE_SETTINGS"):
            jw.total_variation([0,0,0],[1,1,1],2)

    def test_refuse_bad_category_and_mismatched_lengths(self):
        with self.assertRaisesRegex(ValueError,"BAD_INPUT_LENGTHS"):
            jw.total_variation([0,1],[0],2)
        with self.assertRaisesRegex(ValueError,"BAD_CATEGORY"):
            jw.total_variation([0,7],[0,1],2)
        with self.assertRaisesRegex(ValueError,"BAD_FUTURE_BIT"):
            jw.total_variation([0,1],[0,2],2)

    def test_refuse_bad_permutation_budget(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PERMUTATION_BUDGET"):
            jw.permutation_pvalue([([0,1],[0,1],[0,1])],iterations=2)

    def test_excess_cannot_exceed_joint(self):
        r=jw.score([0,1,0,1],[1,0,1,0],[0,1,1,0])
        self.assertGreaterEqual(r["joint_excess_over_largest_marginal"],0)
        self.assertLessEqual(r["joint_excess_over_largest_marginal"],r["A_C_joint_tv"])

    def test_two_view_adjustment_is_conservative(self):
        a=[i%2 for i in range(256)]
        c=[(i//2)%2 for i in range(256)]
        b=[(i//4)%2 for i in range(256)]
        r=jw.permutation_pvalue([(a,c,b)],iterations=199,seed=5)
        self.assertAlmostEqual(
            r["bonferroni_adjusted_min_p_two_views"],
            min(1.,2*min(r["permutation_p_joint_tv_within_trial"],
                         r["permutation_p_joint_interaction_within_trial"]))
        )


if __name__=="__main__":
    unittest.main(verbosity=2)
