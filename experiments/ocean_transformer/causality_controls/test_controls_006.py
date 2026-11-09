#!/usr/bin/env python3
"""Adversarial, deterministic offline unit tests; never use actual QPU/plant data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import controls_006 as c


class BananaForwardCausalTests(unittest.TestCase):
    def test_synthetic_reproducible(self):
        self.assertEqual(c.synthetic_ripening(), c.synthetic_ripening())
        self.assertEqual(len(c.synthetic_ripening()), c.EPISODES * c.STEPS)

    def test_episode_splits_disjoint(self):
        rows = c.synthetic_ripening()
        train = {r["episode"] for r in rows if r["episode"] < c.TRAIN_END}
        test = {r["episode"] for r in rows if r["episode"] >= c.VALID_END}
        val = set(range(c.TRAIN_END, c.VALID_END))
        self.assertFalse(train & test or train & val or val & test)
        self.assertEqual(len(train), 24)
        self.assertEqual(len(test), 8)

    def test_predict_uses_only_present_fields(self):
        row = c.synthetic_ripening()[0]
        coeffs = c.fit_forward_model(c.synthetic_ripening())
        self.assertIsInstance(c.predict_next(c.observation(row), coeffs), float)
        compromised = c.observation(row)
        compromised["target"] = row["target"]
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_UNDECLARED_FEATURE"):
            c.predict_next(compromised, coeffs)

    def test_precommit_deterministic(self):
        first = c.make_forecast_commit()
        self.assertEqual(first, c.make_forecast_commit())
        self.assertEqual(c.sha256(first["payload"]), first["payload_sha256"])
        self.assertFalse(first["external_independent_witness"])
        self.assertEqual(len(first["payload"]["predictions"]), 96)

    def test_score_rejects_corrupt_precommit(self):
        entry = c.make_forecast_commit()
        entry["payload"]["predictions"][0]["prediction"] += .25
        with self.assertRaisesRegex(ValueError, "FORECAST_PRECOMMIT"):
            c.score_forecast_commit(entry)

    def test_synthetic_forward_prediction_better_than_persistence(self):
        score = c.score_forecast_commit(c.make_forecast_commit())
        self.assertEqual(score["status"], "PASS_SYNTHETIC_ONLY")
        self.assertLess(score["model_mae"], score["persistence_mae"])
        self.assertEqual(score["true_future_measurements_collected"], False)

    def test_evidence_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "precommit.json"
            c.write_once(path, c.make_forecast_commit())
            with self.assertRaisesRegex(ValueError, "REFUSE_TO_OVERWRITE"):
                c.write_once(path, {"changed": True})


class QPUNoSignallingTests(unittest.TestCase):
    def test_null_is_balanced_and_not_significant(self):
        score = c.score_qpu_fixture(c.make_qpu_fixture())
        self.assertEqual(score["table"], [[1024, 1024], [1024, 1024]])
        self.assertEqual(score["number_of_shots"], 4096)
        self.assertEqual(score["primary_fisher_two_sided_p"], 1.0)
        self.assertFalse(score["threshold_crossed"])
        self.assertEqual(score["diagnostic_a_equal_b_if_c0"], 1.0)
        self.assertEqual(score["diagnostic_a_equal_b_if_c1"], .5)

    def test_deliberate_association_detected_but_not_as_physics(self):
        score = c.score_qpu_fixture(c.make_qpu_fixture(injected=True))
        self.assertTrue(score["threshold_crossed"])
        self.assertGreater(score["primary_delta_a1_c1_minus_c0"], .1)
        self.assertTrue(score["synthetic"])

    def test_qpu_control_declares_zero_real_measurements(self):
        result = c.qpu_offline_control()
        self.assertEqual(result["status"], "PASS_SYNTHETIC_ONLY")
        self.assertTrue(result["counterfactual_late_B_does_not_change_primary"])
        self.assertEqual(result["real_qpu_shots"], 0)
        self.assertIsNone(result["real_ibm_job_id"])

    def test_later_B_cannot_change_primary(self):
        rows = c.make_qpu_fixture()
        base = c.score_qpu_fixture(rows)
        flipped = c.score_qpu_fixture([[a, setting, 1 - b] for a, setting, b in rows])
        self.assertEqual(base["table"], flipped["table"])
        self.assertEqual(base["primary_fisher_two_sided_p"],
                         flipped["primary_fisher_two_sided_p"])

    def test_missing_and_malformed_shots_refused(self):
        rows = c.make_qpu_fixture()
        with self.assertRaisesRegex(ValueError, "ALL_4096_RAW_SHOTS_REQUIRED"):
            c.score_qpu_fixture(rows[1:])
        damaged = copy.deepcopy(rows)
        damaged[17][0] = 2
        with self.assertRaisesRegex(ValueError, "INVALID_RAW_SHOT"):
            c.score_qpu_fixture(damaged)

    def test_no_selection_of_lucky_shots(self):
        rows = c.make_qpu_fixture()
        selective = [r for r in rows if r[2] == 1]
        with self.assertRaisesRegex(ValueError, "ALL_4096_RAW_SHOTS_REQUIRED"):
            c.score_qpu_fixture(selective)

    def test_causal_control_uses_frozen_fisher_function(self):
        self.assertEqual(c.qpu005.SHOTS, 4096)
        self.assertEqual(c.qpu005.SIGNIFICANCE_THRESHOLD, .001)
        self.assertEqual(c.qpu005.fisher_exact_two_sided(2, 0, 0, 2), 1/3)


class HistoricalProvenanceTests(unittest.TestCase):
    def test_original_blob_hashes_and_bridge_compatible(self):
        score = c.provenance_control()
        self.assertEqual(score["status"],
                         "PASS_HISTORICAL_SNAPSHOTS_AND_CURRENT_QPU_SOURCE")
        self.assertEqual(score["verified_git_blob_sha"], c.EXPECTED_BLOBS)

    def test_mutated_historical_blob_refused(self):
        with patch.dict(c.EXPECTED_BLOBS,
                        {"banana_20260126_original.json": "0" * 40}):
            with self.assertRaisesRegex(ValueError, "HISTORICAL_GIT_BLOB_MISMATCH"):
                c.provenance_control()

    def test_report_has_three_independent_offline_controls(self):
        report = c.run_all()
        self.assertEqual(len(report["controls"]), 3)
        self.assertEqual(
            [x["control"] for x in report["controls"]],
            ["BRIDGE-CTRL-01-FORWARD-BANANA",
             "BRIDGE-CTRL-02-QPU005", "BRIDGE-CTRL-03-TRACEABILITY"])
        self.assertTrue(all(x["status"].startswith("PASS") for x in report["controls"]))
        self.assertFalse(report["hardware_provider_called"])
        self.assertFalse(report["new_physical_qpu_results"])
        self.assertFalse(report["retrocausality_proven"])
        self.assertEqual(report, c.run_all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
