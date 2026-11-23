#!/usr/bin/env python3
"""Synthetic data contract tests, NOT an experiment in physical retrocausality."""
import copy
import math
import unittest
import janus_delayed_choice_clock_audit as d


class ClockAuditTests(unittest.TestCase):
    def setUp(self):
        self.m, self.e, self.l = d.deterministic_mock(64)

    def test_all_early_outcomes_and_no_clicks_retained(self):
        r = d.audit(self.m, self.e, self.l)
        self.assertEqual(r["completed_trials"], 64)
        self.assertTrue(r["fixed_n_primary_valid"])
        self.assertEqual(sum(sum(v) for v in
                             r["unconditional_A_by_late_B_counts"].values()),64)
        self.assertGreater(sum(r["unconditional_A_by_late_B_counts"]["NO_CLICK"]), 0)
        self.assertIsNotNone(r["unconditional_early_A_total_variation"])

    def test_sha_tamper_fails_closed(self):
        e = copy.deepcopy(self.e)
        e[0]["predict_b"] ^= 1
        with self.assertRaisesRegex(ValueError, "EARLY_DIGEST_MISMATCH"):
            d.audit(self.m, e, self.l)

    def test_future_information_in_early_record_rejected(self):
        e = copy.deepcopy(self.e)
        e[0]["late_b"] = self.l[0]["late_b"]
        m = dict(self.m, early_log_sha256=d.canonical_digest(e))
        with self.assertRaisesRegex(ValueError, "UNEXPECTED_EARLY_FIELD"):
            d.audit(m, e, self.l)

    def test_late_clock_before_A_closes_rejected(self):
        l = copy.deepcopy(self.l)
        l[0]["late_qrng_ns"] = self.e[0]["early_window_closed_ns"]
        with self.assertRaisesRegex(ValueError, "CLOCK_ORDER_FAIL"):
            d.audit(self.m, self.e, l)

    def test_duplicate_or_missing_late_record_rejected(self):
        l = copy.deepcopy(self.l)
        l[0]["trial_id"] = l[1]["trial_id"]
        with self.assertRaisesRegex(ValueError, "LATE_TRIAL_DUPLICATE"):
            d.audit(self.m, self.e, l)
        with self.assertRaisesRegex(ValueError, "TRIALS_MISSING"):
            d.audit(self.m, self.e, self.l[:-1])

    def test_abort_is_retained_but_voids_fixed_n_primary(self):
        l = copy.deepcopy(self.l)
        l[0]["status"] = "INFRA_ABORT"
        l[0]["late_b"] = None
        l[0]["late_qrng_ns"] = None
        r=d.audit(self.m, self.e, l)
        self.assertEqual(r["infra_abort_trial_ids"], [0])
        self.assertEqual(r["completed_trials"], 63)
        self.assertFalse(r["fixed_n_primary_valid"])
        self.assertIsNone(r["one_sided_exact_binomial_p"])
        self.assertIsNone(r["unconditional_early_A_total_variation"])

    def test_perfect_future_leak_control_is_detected_not_promoted(self):
        l = copy.deepcopy(self.l)
        for i in range(64):
            l[i]["late_b"] = self.e[i]["predict_b"]
        r=d.audit(self.m, self.e, l)
        self.assertEqual(r["matched_predictions"],64)
        self.assertAlmostEqual(r["one_sided_exact_binomial_p"], 2**(-64))
        self.assertTrue(r["apparent_significance_under_fair_independent_B_assumption"])
        self.assertFalse(r["physical_retro_signal_detected"])
        self.assertFalse(r["hardware_QRNG_independence_verified"])
        self.assertEqual(r["production_promotion"], "REFUSED_NO_INDEPENDENT_LAB_EVIDENCE")

    def test_exact_binomial_boundaries(self):
        self.assertEqual(d.exact_right_binomial_tail(64,0),1.)
        self.assertAlmostEqual(d.exact_right_binomial_tail(8,8), 1/256)
        self.assertAlmostEqual(d.exact_right_binomial_tail(8,4), 163/256)

    def test_bogus_timestamps_and_nonbinary_setting_rejected(self):
        l = copy.deepcopy(self.l)
        l[0]["late_b"] = True
        with self.assertRaisesRegex(ValueError, "INVALID_LATE_BIT"):
            d.audit(self.m, self.e, l)
        e=copy.deepcopy(self.e)
        e[0]["early_a"] = True
        m = dict(self.m, early_log_sha256=d.canonical_digest(e))
        with self.assertRaisesRegex(ValueError, "INVALID_EARLY_OUTCOME"):
            d.audit(m, e, self.l)

    def test_sha_does_not_equal_external_attestation(self):
        r=d.audit(self.m,self.e,self.l)
        self.assertTrue(r["early_log_sha256_verified_against_manifest"])
        self.assertFalse(r["external_sha_timestamp_signature_verified"])
        self.assertFalse(r["hardware_clock_calibration_verified"])
        self.assertFalse(r["physical_A_before_B_proven"])


if __name__=="__main__":
    unittest.main(verbosity=2)
