#!/usr/bin/env python3
"""No-signalling, raw-data, non-post-selection and chronology tests."""
import copy
import json
import unittest

import late_choice_010 as lc


class PhysicalProtocolContract(unittest.TestCase):
    def make(self,counts=None):
        counts=counts or [[32,32],[32,32]]
        early,late=[],[]
        for c in (0,1):
            for a in (0,1):
                for _ in range(counts[c][a]):
                    i=len(early)
                    early.append({"trial":i,"a":a,"t_a_ns":1000000*i,"u_a_ns":10})
                    late.append({"trial":i,"c":c,"t_c_ns":1000000*i+200000,
                                 "u_c_ns":10,"t_b_ns":1000000*i+400000,"u_b_ns":10,
                                 "choice_origin":lc.REQUIRED_ORIGIN,"b":a^c})
        pre={"schema":lc.SCHEMA,"protocol_version":lc.PROTOCOL_VERSION,
             "alpha":lc.ALPHA,"n":len(early),"primary_test":lc.MODEL_TEST,
             "postselection_allowed":False,"required_choice_origin":lc.REQUIRED_ORIGIN}
        return pre,early,late

    def test_unconditional_uniform_independence(self):
        pre,e,l=self.make()
        r=lc.analyze(pre,e,l,"SIMULATION_ONLY")
        self.assertAlmostEqual(r["primary_unconditional"]["fisher_exact_two_sided_p"],1.)
        self.assertAlmostEqual(r["primary_unconditional"]["delta_p_a1"],0.)
        self.assertTrue(r["all_trials_in_primary"])
        self.assertFalse(r["eligible_to_claim_retrocausality"])

    def test_postselection_produces_false_p(self):
        pre,e,l=self.make()
        r=lc.analyze(pre,e,l,"SIMULATION_ONLY")
        self.assertEqual(r["primary_unconditional"]["fisher_exact_two_sided_p"],1.)
        self.assertLess(r["postselection_diagnostic_exploratory"]["p_two_sided_postselected_NOT_PRIMARY"],0.001)

    def test_large_raw_correlation_is_detected_not_promoted(self):
        pre,e,l=self.make([[60,4],[4,60]])
        r=lc.analyze(pre,e,l,"SIMULATION_ONLY")
        self.assertLess(r["primary_unconditional"]["fisher_exact_two_sided_p"],1e-10)
        self.assertFalse(r["eligible_to_claim_retrocausality"])

    def test_any_missing_record_refused(self):
        pre,e,l=self.make()
        with self.assertRaisesRegex(ValueError,"ALL_PREDECLARED_TRIALS_REQUIRED"):
            lc.analyze(pre,e,l[:-1],"SIMULATION_ONLY")

    def test_reordering_refused(self):
        pre,e,l=self.make()
        e[1],e[2]=e[2],e[1]
        with self.assertRaisesRegex(ValueError,"MISSING_DUPLICATED_OR_REORDERED"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_timelike_order_uncertainty_refused(self):
        pre,e,l=self.make()
        e[0]["u_a_ns"]=250000
        with self.assertRaisesRegex(ValueError,"EVENT_ORDER_NOT_PROVEN"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_nonphysical_choice_refused(self):
        pre,e,l=self.make()
        l[0]["choice_origin"]="PSEUDORANDOM_FROM_PRECOMMITTED_SEED"
        with self.assertRaisesRegex(ValueError,"LATE_CHOICE_NOT_DECLARED_PHYSICAL"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_false_postselection_precommit_refused(self):
        pre,e,l=self.make()
        pre["postselection_allowed"]=True
        with self.assertRaisesRegex(ValueError,"PREDECLARED_PRIMARY_CHANGED"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_external_sample_size_gate(self):
        pre,e,l=self.make()
        with self.assertRaisesRegex(ValueError,"PHYSICAL_N_DIFFERS"):
            lc.analyze(pre,e,l,"EXTERNAL_DATA_UNVERIFIED")

    def test_zero_late_choice_variation_refused(self):
        pre,e,l=self.make([[64,64],[0,0]])
        with self.assertRaisesRegex(ValueError,"NO_VARIATION_IN_LATE_SETTING"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_exact_fisher_symmetry(self):
        self.assertAlmostEqual(lc.fisher_two_sided([[10,20],[30,40]]),
                               lc.fisher_two_sided([[30,40],[10,20]]))
        self.assertEqual(lc.fisher_two_sided([[10,10],[10,10]]),1.)

    def test_no_boolean_as_a_detector_outcome(self):
        pre,e,l=self.make()
        e[0]["a"]=True
        with self.assertRaisesRegex(ValueError,"REQUIRED_INTEGER"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")

    def test_uncertain_clock_mismatch_refused(self):
        pre,e,l=self.make()
        l[2]["t_c_ns"]=e[2]["t_a_ns"]
        with self.assertRaisesRegex(ValueError,"EVENT_ORDER_NOT_PROVEN"):
            lc.analyze(pre,e,l,"SIMULATION_ONLY")


if __name__=="__main__":
    unittest.main()
