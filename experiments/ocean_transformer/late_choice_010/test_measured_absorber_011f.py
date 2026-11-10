#!/usr/bin/env python3
"""JANUS-011F: material spectral calculations and causal timing controls."""
import math
import unittest
import measured_absorber_011f as q

class RealMaterialSpectraAndCausalControls(unittest.TestCase):
    def test_pinned_original_snapshot_and_comparison_points(self):
        self.assertEqual(q.COMMIT,"e6d15e364f70de1cad8a96a20f75689f2fba8b21")
        self.assertEqual(q.MATERIALS,("Au","Ag"))
        self.assertEqual(q.WAVELENGTHS,(.4509,.5486,.7045,.8920))
        self.assertEqual(q.THICKNESS_UM,.04)

    def test_vacuum_has_no_absorption_or_reflection(self):
        for wl in (.4509,.7045):
            r=q.slab(wl,1,0,.04)
            self.assertAlmostEqual(r["R_model"],0,places=14)
            self.assertAlmostEqual(r["T_model"],1,places=14)
            self.assertEqual(r["A_model"],0)

    def test_finite_slab_zero_thickness_is_transparent(self):
        for n,k in ((.43,2.455),(1.44,0),(1.1,5.2)):
            r=q.slab(.5486,n,k,0)
            self.assertAlmostEqual(r["R_model"],0,places=14)
            self.assertAlmostEqual(r["T_model"],1,places=14)

    def test_gold_measured_sample_passive_energy_balanced(self):
        r=q.slab(.5486,.43,2.455,.04)
        self.assertGreater(r["R_model"],0)
        self.assertGreater(r["T_model"],0)
        self.assertGreater(r["A_model"],0)
        self.assertAlmostEqual(r["R_model"]+r["T_model"]+r["A_model"],1,places=12)

    def test_silver_measured_sample_passive_energy_balanced(self):
        r=q.slab(.7045,.04,4.838,.04)
        self.assertTrue(all(0<=r[name]<=1 for name in ("R_model","T_model","A_model")))
        self.assertAlmostEqual(r["R_model"]+r["T_model"]+r["A_model"],1,places=12)

    def test_material_negative_k_or_bad_thickness_fails(self):
        with self.assertRaisesRegex(ValueError,"INVALID_IDEAL_FILM_INPUT"):
            q.slab(.5486,1,-.1,.04)
        with self.assertRaisesRegex(ValueError,"INVALID_IDEAL_FILM_INPUT"):
            q.slab(.5486,1,.1,-.04)

    def test_published_format_custody_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"ORIGINAL_JOHNSON_CHRISTY"):
            q.parse_original_nk(b"0.4509 1.0 1.0")
        with self.assertRaisesRegex(ValueError,"UNKNOWN_MEASURED_MATERIAL"):
            q.load_pinned_file("FakeMetal")

    def test_finite_band_inverse_pulse_has_fake_early_tail(self):
        p=q.temporal_false_positives()
        self.assertEqual(p["true_exact_early_pre_impulse_nonzero_samples"],[])
        self.assertIn(4,p["bandlimited_reconstruction_nonzero_before_true_delay"])
        self.assertAlmostEqual(p["bandlimited_reconstructed_amplitude_at_t4"],1/math.pi)
        self.assertTrue(p["bandlimited_artifact_is_not_physical_advanced_response"])

    def test_centered_filter_looks_ahead_but_trailing_is_causal(self):
        p=q.temporal_false_positives()
        self.assertEqual(p["centered_filter_nonzero_before_true_delay"],[3,4])
        self.assertEqual(p["causal_trailing_filter_nonzero_before_true_delay"],[])
        self.assertEqual(p["centered_filter_at_t3"],.2)
        self.assertEqual(p["causal_trailing_filter_at_t3"],0)
        self.assertTrue(p["centered_five_sample_filter_reads_future_samples"])

    def test_wrong_clock_reports_fake_negative_time(self):
        p=q.temporal_false_positives()
        self.assertEqual(p["wrong_displayed_impulse_t"],-1)
        self.assertEqual(p["correct_physical_impulse_t_unchanged"],5)

    def test_local_group_delay_is_only_descriptive(self):
        # Synthetic samples; no physical early-front claims.
        rows=[(.4,1.2,.1),(.5,1.1,.3),(.6,.9,.4)]
        fs=q.group_delay_local(rows,1,.04)
        self.assertTrue(math.isfinite(fs))
        self.assertLess(abs(fs),1000)

    def test_original_measurement_range_without_relabeling(self):
        self.assertEqual(q.WAVELENGTH_RANGE_EXPECTED,(.1879,1.937))
        self.assertEqual(len(q.TIME_SAMPLES),21)
        self.assertEqual(q.DELAY,5)

if __name__=="__main__":unittest.main()
