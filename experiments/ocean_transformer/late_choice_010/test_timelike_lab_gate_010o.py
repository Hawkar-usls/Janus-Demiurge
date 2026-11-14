import unittest
import timelike_lab_gate_010o as p

def valid_trial(i):
    t=10_000_000+i*1_000_000
    return {"trial_id":i,"A":i%2,"C":(i//2)%2,
            "A_commit":{"t_ns":t,"u_ns":10},
            "C_entropy_generation":{"t_ns":t+10000,"u_ns":20},
            "C_basis_latch":{"t_ns":t+20000,"u_ns":20},
            "B_detection":{"t_ns":t+40000,"u_ns":10}}

def manifest(trials):
    return {"schema":p.SCHEMA,"expected_n":p.EXPECTED_N,"trials":trials}

class PhysicalOrderFailClosed(unittest.TestCase):
    def test_default_no_hardware(self):
        r=p.assess(manifest([]))
        self.assertEqual(r["status"],"BLOCKED_NO_PHYSICAL_TRIALS")
        self.assertFalse(r["physically_late_choice_proven"])

    def test_numeric_valid_not_real_physics(self):
        r=p.assess(manifest([valid_trial(0),valid_trial(1)]))
        self.assertEqual(r["status"],"BLOCKED_MISSING_PREREGISTERED_TRIALS")
        self.assertFalse(r["early_A_WORM_external_signature_and_order_verified"])
        self.assertFalse(r["lab_independent_clock_path_calibration_and_uncertainties_verified"])

    def test_c_generated_too_early_no_promotion(self):
        x=valid_trial(0)
        x["C_entropy_generation"]["t_ns"]=x["A_commit"]["t_ns"]+5
        r=p.assess(manifest([x]))
        self.assertEqual(r["numeric_chronology_failures"],1)
        self.assertLess(r["minimum_numeric_timing_margin_ns"],0)

    def test_uncertainty_overlap_is_not_strict_future(self):
        x=valid_trial(0)
        x["C_entropy_generation"]["t_ns"]=x["A_commit"]["t_ns"]+25
        x["C_entropy_generation"]["u_ns"]=20
        res=p.chronology(x)
        self.assertFalse(res["chronological_order_robust_given_claimed_common_time"])

    def test_missing_actuator_latch_rejected(self):
        x=valid_trial(0)
        del x["C_basis_latch"]
        with self.assertRaisesRegex(ValueError,"MISSING_PHYSICAL_STAGE"):
            p.chronology(x)

    def test_ordered_ids_required(self):
        x=valid_trial(1)
        with self.assertRaisesRegex(ValueError,"MISSING_DUPLICATE_OR_REORDERED_TRIAL"):
            p.assess(manifest([x]))

    def test_wrong_sealed_sample_count_rejected(self):
        m=manifest([])
        m["expected_n"]=64
        with self.assertRaisesRegex(ValueError,"SEALED_TRIAL_COUNT_CHANGED"):
            p.assess(m)

    def test_fake_self_attestation_does_not_unlock(self):
        m=manifest([valid_trial(0)])
        m["lab_signature"]="I hereby certify true causality"
        m["NIST_authorized_hardware"]=True
        r=p.assess(m)
        self.assertFalse(r["independent_lab_custody_verified"])
        self.assertFalse(r["ready_to_apply_original_sealed_Fisher_alpha_0_001"])
        self.assertFalse(r["retrocausal_channel_proven"])

if __name__=="__main__":unittest.main()
