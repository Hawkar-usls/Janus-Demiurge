#!/usr/bin/env python3
"""Adversarial unit tests for LIGHT-007. No IBM, Qiskit, or physical apparatus."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import light_controls_007 as c


class SpectralEnergyTests(unittest.TestCase):
    def test_energy_inversely_proportional_to_wavelength(self):
        score = c.spectral_energy_control()
        self.assertEqual(score["status"], "PASS_ANALYTICAL_FORMULA_ONLY")
        self.assertGreater(score["photon_energy_eV"]["blue"], score["photon_energy_eV"]["red"])
        self.assertGreater(score["photon_energy_eV"]["red"], score["photon_energy_eV"]["far_red"])

    def test_energy_ratio_from_planck_relation(self):
        self.assertAlmostEqual(c.photon_energy_eV(450) / c.photon_energy_eV(660), 660 / 450)

    def test_bad_wavelength_and_physical_claim_refused(self):
        for wavelength in (0, -1, 20000):
            with self.assertRaisesRegex(ValueError, "INVALID_LIGHT_WAVELENGTH_NM"):
                c.photon_energy_eV(wavelength)
        self.assertFalse(c.spectral_energy_control()["detector_or_plant_data_used"])


class PhotonCountingTests(unittest.TestCase):
    def test_count_streams_deterministic(self):
        self.assertEqual(c.count_streams(), c.count_streams())

    def test_count_model_rejects_invalid_rate(self):
        import random
        with self.assertRaisesRegex(ValueError, "POISSON_RATE_OUT_OF_RANGE"):
            c.poisson(-3, random.Random(0))

    def test_higher_intensity_and_poisson_fano(self):
        result = c.shot_noise_control()
        self.assertEqual(result["status"], "PASS_SYNTHETIC_ONLY")
        self.assertGreater(result["high"]["mean"], 2 * result["low"]["mean"])
        for band in ("low", "high"):
            self.assertGreater(result[band]["fano_sample"], .8)
            self.assertLess(result[band]["fano_sample"], 1.2)
        self.assertEqual(result["actual_photon_counts_collected"], 0)

    def test_frozen_window_number(self):
        for band, counts in c.count_streams().items():
            self.assertEqual(len(counts), 2048)
            self.assertTrue(all(type(x) is int and x >= 0 for x in counts))


class CausalLightTimingTests(unittest.TestCase):
    def test_forward_waveform_reproducible(self):
        self.assertEqual(c.light_timeline(), c.light_timeline())
        self.assertEqual(len(c.light_timeline()["source"]), 1024)

    def test_recover_positive_delay_from_train_only(self):
        fit = c.fit_forward_lag(c.light_timeline())
        self.assertEqual(fit["estimated_positive_delay_bins"], 3)
        self.assertEqual(fit["train_ends_before"], c.TRAIN_END)
        self.assertIn("-1", fit["negative_lags_diagnostic_only"])

    def test_precommit_before_scoring_and_only_predictor_fields(self):
        entry = c.prepare_forecasts()
        self.assertEqual(entry, c.prepare_forecasts())
        self.assertFalse(entry["independent_timestamp_attestation"])
        self.assertFalse(entry["payload"]["labels_in_precommit"])
        self.assertEqual(len(entry["payload"]["predictions"]), 384)
        self.assertEqual(entry["payload_sha256"], c.digest(entry["payload"]))
        self.assertTrue(all("target" not in row for row in entry["payload"]["predictions"]))

    def test_out_of_order_and_future_source_rejected(self):
        timeline = c.light_timeline()
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_MISALIGNED_LIGHT_INPUT_REFUSED"):
            c.forward_prediction(timeline["source"], t=50, source_t=51,
                                 lag=-1, learned_levels=(0, 4))
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_MISALIGNED_LIGHT_INPUT_REFUSED"):
            c.forward_prediction(timeline["source"], t=50, source_t=50,
                                 lag=3, learned_levels=(0, 4))

    def test_corrupted_forecast_refused(self):
        p = c.prepare_forecasts()
        p["payload"]["predictions"][0]["prediction"] += 1
        with self.assertRaisesRegex(ValueError, "LIGHT_FORECAST_PRECOMMIT_MUTATED"):
            c.score_forecasts(p)

    def test_forward_model_outperforms_constant_baseline(self):
        report = c.score_forecasts(c.prepare_forecasts())
        self.assertEqual(report["status"], "PASS_SYNTHETIC_ONLY")
        self.assertEqual(report["recovered_delay_bins"], 3)
        self.assertLess(report["causal_test_mae"],
                        report["constant_train_mean_baseline_mae"])
        self.assertFalse(report["physical_speed_of_light_measured"])

    def test_results_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "example.json"
            c.write_once(path, c.prepare_forecasts())
            with self.assertRaisesRegex(ValueError, "LIGHT007_REFUSE_OVERWRITE"):
                c.write_once(path, c.prepare_forecasts())


class PostselectionAntiPatternTests(unittest.TestCase):
    def test_unconditional_independent_even_if_selected_correlation(self):
        report = c.postselection_control()
        self.assertEqual(report["status"], "PASS_SYNTHETIC_ONLY")
        self.assertEqual(report["total_raw_shots"], 4096)
        self.assertEqual(report["predeclared_unselected_table"],
                         [[1024, 1024], [1024, 1024]])
        self.assertEqual(report["unselected_fisher_p"], 1)
        self.assertLess(report["forbidden_selected_p"], 1e-20)

    def test_intentional_selection_creates_false_association(self):
        result = c.postselection_control()
        self.assertEqual(result["forbidden_selected_table_for_demonstration_only"],
                         [[900, 100], [100, 900]])
        self.assertTrue(result["primary_ignores_late_B"])

    def test_selection_fails_006_full_shot_guard(self):
        rows = c.postselection_rows()
        with self.assertRaisesRegex(ValueError, "ALL_4096_RAW_SHOTS_REQUIRED"):
            c.ctrl006.score_qpu_fixture([r for r in rows if r[2] == 1])

    def test_later_B_inversion_does_not_change_primary(self):
        rows = c.postselection_rows()
        a = c.ctrl006.score_qpu_fixture(rows)
        b = c.ctrl006.score_qpu_fixture([[x, y, 1-z] for x, y, z in rows])
        self.assertEqual(a["table"], b["table"])
        self.assertEqual(a["primary_fisher_two_sided_p"], b["primary_fisher_two_sided_p"])

    def test_synthetic_no_real_job_id(self):
        report = c.postselection_control()
        self.assertEqual(report["real_qpu_shots"], 0)
        self.assertIsNone(report["provider_job_id"])


class HistoricalLightProvenanceTests(unittest.TestCase):
    def test_original_fenced_file_and_current_snapshot(self):
        report = c.provenance_control()
        self.assertTrue(report["original_wrapped_in_markdown_code_fence"])
        self.assertTrue(report["normalized_semantic_content_equal"])
        self.assertEqual(report["git_blobs"]["light_20260127_original_with_fence.json"],
                         c.LIGHT_ORIGINAL_BLOB)
        self.assertEqual(report["git_blobs"]["light_current_normalized.json"],
                         c.LIGHT_NORMALIZED_BLOB)

    def test_mutated_historical_hash_causes_failure(self):
        with patch.object(c, "LIGHT_ORIGINAL_BLOB", "0" * 40):
            with self.assertRaisesRegex(ValueError, "LIGHT_ORIGINAL_OR_NORMALIZED_SHA_MISMATCH"):
                c.provenance_control()

    def test_006_previous_chain_still_valid(self):
        report = c.provenance_control()
        self.assertEqual(report["banana_qpu006_provenance_status"],
                         "PASS_HISTORICAL_SNAPSHOTS_AND_CURRENT_QPU_SOURCE")

    def test_combined_report_no_physical_claims(self):
        report = c.combined_report()
        self.assertTrue(report["all_controls_pass"])
        self.assertEqual(len(report["controls"]), 5)
        self.assertEqual([x["control"] for x in report["controls"]], [
            "LIGHT-CTRL-00-SPECTRAL-ENERGY",
            "LIGHT-CTRL-01-COUNTING-NOISE",
            "LIGHT-CTRL-02-FORWARD-DELAYS",
            "LIGHT-CTRL-03-NO-POSTSELECTION",
            "LIGHT-CTRL-04-HISTORICAL-PROVENANCE"])
        self.assertEqual(report["actual_photon_measurements"], 0)
        self.assertFalse(report["IBM_provider_called"])
        self.assertFalse(report["retrocausality_proven"])
        self.assertEqual(report, c.combined_report())


if __name__ == "__main__":
    unittest.main(verbosity=2)
