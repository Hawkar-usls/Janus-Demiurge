#!/usr/bin/env python3
"""JANUS Ocean/Wolfram council source-binding and scientific claims gates."""
import copy
import unittest

import measurement_priors as p
import wolfram_alpha_bridge as w
import ocean_wolfram_council as c


def fixtures():
    return p.report(), w.check(live=False)


def synthetic_training():
    return {
        "schema": c.TRAIN_SCHEMA,
        "model": "JanusTinyTransformer",
        "dataset_type": "SYNTHETIC_STANDARD_QUANTUM_MEASUREMENT",
        "production_checkpoint_changed": False,
        "future_labels_seen_at_training": False,
        "postselection_on_test_results": False,
        "physically_triggered_wavefunction_collapse": False,
        "proven_tachyons_or_retrocausal_communication": False,
        "untrained_holdout": {
            "cases": 2048, "brier": 0.253, "analytic_born_oracle_brier": 0.154, "logloss": 0.7
        },
        "trained_holdout": {
            "cases": 2048, "brier": 0.155, "analytic_born_oracle_brier": 0.154, "logloss": 0.48
        },
        "independent_future_random_negative_control": {"cases": 2048, "accuracy": .50},
        "assessment": "SYNTHETIC_BORN_RULE_LEARNING_GAIN_ONLY",
        "video_source": c.video.VIDEO_URL,
        "video_hypothesis_card_sha256": c.video.card_sha256(),
        "independent_validation_seed": 20269110,
        "independent_test_seed": 20270110,
        "calibration_training_test_seeds_disjoint": True,
        "video_measurement_calibration": {
            "schema": c.video.SCHEMA,
            "video_card_sha256": c.video.card_sha256(),
            "chosen_temperature": 1.25,
            "allowed_temperatures": list(c.video.TEMPERATURES),
            "calibration_rows": 2048,
            "test_rows": 2048,
            "validation_nll_raw": .49,
            "validation_nll_calibrated": .47,
            "test_raw": {"n":2048,"brier":.155,"nll":.48},
            "test_calibrated": {"n":2048,"brier":.15,"nll":.47},
            "test_analytic_born": {"n":2048,"brier":.154,"nll":.46},
            "calibration_selection_used_test_labels": False,
            "hypothesis_training_labels_from_video": False,
            "future_signal_or_quantum_collapse_proven": False,
            "source":"SYNTHETIC_BORN_RULE_WITH_INDEPENDENT_SPLITS",
            "status":"TEMPERATURE_CALIBRATION_IMPROVED_HELDOUT_NLL_ONLY"
        }
    }


class Tests(unittest.TestCase):
    def test_offline_verified_math_not_claimed_external(self):
        priors, bridge = fixtures()
        council = c.council(priors, bridge)
        self.assertEqual(council["research_admission"], "OFFLINE_MATH_ONLY")
        self.assertFalse(council["verified_external_provider"])
        self.assertFalse(council["claims"]["physical_retrocausal_communication_proven"])
        self.assertFalse(council["authority"]["edit_production_weights"])

    def test_actual_transformer_report_bound_and_no_promotion(self):
        p0, w0 = fixtures()
        result = c.council(p0, w0, synthetic_training())
        self.assertEqual(result["training_assessment"], "SYNTHETIC_BORN_RULE_LEARNING_GAIN_ONLY")
        self.assertAlmostEqual(result["measured_synthetic_brier_gain"], .098)
        self.assertIsNotNone(result["source_binding"]["training_report_sha256"])
        self.assertFalse(result["authority"]["spend_wolfram_credits_automatically"])

    def test_provider_liveness_is_truthful_with_no_caching(self):
        priors, bridge = fixtures()
        bridge["mode"] = "LIVE_READ_ONLY_WOLFRAM_ALPHA"
        bridge["status"] = "EXTERNAL_ARITHMETIC_CHECK_PASS"
        bridge["upstream"]["authenticated"] = True
        for row in bridge["queries"]:
            row["external_checked"] = True
            row["agrees_with_standard_arithmetic"] = True
        council = c.council(priors, bridge)
        self.assertTrue(council["verified_external_provider"])
        self.assertEqual(council["research_admission"], "EXTERNAL_MATH_CHECKED")
        self.assertFalse(council["claims"]["physical_quantum_collapse_proven"])

    def test_tampered_dataset_is_rejected(self):
        priors, bridge = fixtures()
        priors["grid"][0]["p_readout_one"] = .9
        with self.assertRaisesRegex(c.CouncilHold, "PRIOR_GRID_OR_BELL_CONTROL_DRIFT"):
            c.council(priors, bridge)

    def test_provider_source_sha_is_rejected(self):
        priors, bridge = fixtures()
        bridge["source_binding"]["canonical_dataset_sha256"] = "0"*64
        with self.assertRaisesRegex(c.CouncilHold, "WOLFRAM_SOURCE_BINDING_DRIFT"):
            c.council(priors, bridge)

    def test_provider_raw_output_caching_is_refused(self):
        priors, bridge = fixtures()
        bridge["queries"][0]["wolfram_numeric_result"] = 0.5
        with self.assertRaisesRegex(c.CouncilHold, "WOLFRAM_PROVIDER_CONTENT_MUST_NOT_BE_CACHED"):
            c.council(priors, bridge)

    def test_fake_external_confirmation_fails(self):
        priors, bridge = fixtures()
        bridge["status"] = "EXTERNAL_ARITHMETIC_CHECK_PASS"
        with self.assertRaisesRegex(c.CouncilHold, "WOLFRAM_MODE_STATUS_INCONSISTENT"):
            c.council(priors, bridge)

    def test_model_claim_escalation_fails(self):
        priors, bridge = fixtures()
        training = synthetic_training()
        training["proven_tachyons_or_retrocausal_communication"] = True
        with self.assertRaisesRegex(c.CouncilHold, "TRAINING_SAFETY_BOUNDARY_VIOLATION"):
            c.council(priors, bridge, training)

    def test_model_brier_claim_contradiction_fails(self):
        priors, bridge = fixtures()
        training = synthetic_training()
        training["trained_holdout"]["brier"] = .252
        with self.assertRaisesRegex(c.CouncilHold, "VIDEO_CALIBRATION_NOT_BOUND_TO_OCEAN_TEST"):
            c.council(priors, bridge, training)

    def test_video_calibration_claim_escalation_fails(self):
        priors, bridge = fixtures()
        training = synthetic_training()
        training["video_measurement_calibration"]["future_signal_or_quantum_collapse_proven"] = True
        with self.assertRaisesRegex(c.CouncilHold, "VIDEO_CALIBRATION_AUTHORITY_ESCALATION"):
            c.council(priors, bridge, training)

    def test_video_card_sha_tamper_fails(self):
        priors, bridge = fixtures()
        training = synthetic_training()
        training["video_hypothesis_card_sha256"] = "0"*64
        with self.assertRaisesRegex(c.CouncilHold, "VIDEO_HYPOTHESIS_CARD_DRIFT"):
            c.council(priors, bridge, training)

    def test_outside_query_in_research_packet_fails(self):
        priors, bridge = fixtures()
        bridge["queries"][0]["public_expression"] = "what will happen tomorrow"
        with self.assertRaisesRegex(c.CouncilHold, "UNAPPROVED_WOLFRAM_QUERY"):
            c.council(priors, bridge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
