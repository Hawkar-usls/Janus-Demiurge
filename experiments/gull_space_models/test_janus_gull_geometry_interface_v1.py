#!/usr/bin/env python3
"""Independent stdlib regressions for JANUS gull optics vs perception toy."""
from __future__ import annotations
import copy
from fractions import Fraction as F
import json
from pathlib import Path
import tempfile
import unittest

import janus_gull_geometry_interface_v1 as g

SRC=Path(__file__).with_name("laridae_visual_measurements_v1.json")


class LiteratureCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src,cls.sha=g.source_data(SRC)

    def test_three_gull_species_ten_real_birds_without_fabrication(self):
        self.assertEqual(sum(x["sample_size_individuals"]
                              for x in self.src["studied_species"]),10)
        self.assertEqual(set(x["scientific_name"]
                             for x in self.src["studied_species"]),
                         set(g.EXPECTED_SAMPLE_COUNTS))
        self.assertFalse(self.src["provenance"][
            "individual_measurement_table_verified_and_imported"])

    def test_max_binocular_width_applied_only_at_reference_peak_plane(self):
        self.assertTrue(g.frontal_binocular_peak_proxy(12,self.src))
        self.assertTrue(g.frontal_binocular_peak_proxy(-17,self.src))
        self.assertFalse(g.frontal_binocular_peak_proxy(18,self.src))

    def test_head_down_pitch_is_qualitatively_consistent_with_published_blind_sector(self):
        rest=g.sagittal_midline_flight_proxy(0,0,self.src)
        flight=g.sagittal_midline_flight_proxy(0,50,self.src)
        self.assertFalse(rest["anterior_midline_blind_sector_proxy"])
        self.assertTrue(flight["anterior_midline_blind_sector_proxy"])
        self.assertEqual(flight["head_relative_elevation_deg"],50)
        self.assertTrue(flight["assumes_static_head_and_1d_projection"])

    def test_falsified_group_mean_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data=copy.deepcopy(self.src)
            data["published_cross_species_summaries"][
                "max_binocular_width_degrees"]["mean"]=44.0
            p=Path(d)/"fabricated.json"
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,
                                       "PUBLISHED_FIELD_VALUE_CHANGED"):
                g.source_data(p)

    def test_fake_individual_gull_neural_measurement_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            data=copy.deepcopy(self.src)
            data["provenance"]["individual_measurement_rows_reconstructed"]=True
            p=Path(d)/"unverified_individuals.json"
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,
                                       "MISSING_PUBLISHED_ORIGINAL_DATA_LIMIT"):
                g.source_data(p)


class FormalCompressionTests(unittest.TestCase):
    def test_only_127_nontrivial_binary_encodings_and_same_inputs(self):
        options=list(g.partitions())
        self.assertEqual(len(options),127)
        self.assertEqual(len(set(options)),127)
        self.assertTrue(all(len(c)==8 and set(c)=={0,1}
                            and c[0]==0 for c in options))
        self.assertTrue(all(abs(s[1])<35.1/2 for s in g.FROZEN_STATES))

    def test_geometry_bottleneck_optimal_angle_mse_exact(self):
        x=g.exhaustive_comparison("hazard_costly")
        self.assertEqual(x["geometry_angle_MSE_optimized"][
                         "angle_mse_deg2_exact"],"16")
        self.assertEqual(x["possible_encoders_exhaustively_checked"],127)

    def test_interface_optimizes_action_payoff_on_same_information_capacity(self):
        x=g.exhaustive_comparison("hazard_costly")
        a=F(x["geometry_angle_MSE_optimized"][
            "action_expected_reward_exact"])
        b=F(x["fitness_action_reward_optimized"][
            "action_expected_reward_exact"])
        self.assertEqual(a,F(21,20))
        self.assertEqual(b,F(71,40))
        self.assertEqual(b-a,F(29,40))
        self.assertEqual(x["interface_minus_geometry_reward_exact"],"29/40")

    def test_data_processing_uncompressed_optimum_dominates(self):
        for world in ("hazard_costly","all_safe"):
            x=g.exhaustive_comparison(world)
            full=F(x["full_input_optimal_action_reward_upper_bound"])
            interface=F(x["fitness_action_reward_optimized"][
                "action_expected_reward_exact"])
            geometry=F(x["geometry_angle_MSE_optimized"][
                "action_expected_reward_exact"])
            self.assertGreaterEqual(full,interface)
            self.assertGreaterEqual(interface,geometry)

    def test_utility_changes_without_changing_gull_eyes(self):
        a=g.exhaustive_comparison("hazard_costly")
        b=g.exhaustive_comparison("all_safe")
        self.assertEqual(a["geometry_angle_MSE_optimized"][
                         "angle_mse_deg2_exact"],
                         b["geometry_angle_MSE_optimized"][
                         "angle_mse_deg2_exact"])
        self.assertNotEqual(a["fitness_action_reward_optimized"]["codes"],
                            b["fitness_action_reward_optimized"]["codes"])

    def test_behavior_is_synthetic_and_hypothesis_remains_unidentified(self):
        src,sha=g.source_data(SRC)
        x=g.report(src,sha)
        self.assertEqual(x["real_birds_total"],10)
        self.assertFalse(x["empirical_calibration"][
            "actual_gull_behavior_or_fitness_measured"])
        self.assertFalse(x["empirical_calibration"][
            "independent_species_holdout_available"])
        self.assertFalse(x["model_is_real_seagull_neural_connectome"])
        self.assertFalse(x["trained_transformer_or_production_model_modified"])
        self.assertIn("NOT_IDENTIFIABLE",
                      x["physical_vision_theory_identification"])
        self.assertEqual(len(x["synthetic_exhaustive_worlds"]),2)

    def test_research_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            source,sha=g.source_data(SRC)
            dest=Path(d)/"already_used.json"
            dest.write_text("evidence already recorded")
            self.assertTrue(dest.exists())
            with self.assertRaisesRegex(ValueError,
                                        "REFUSE_TO_OVERWRITE_RESEARCH_EVIDENCE"):
                # Contract is checked by the entrypoint's guard.
                g.check(not dest.exists(),
                        "REFUSE_TO_OVERWRITE_RESEARCH_EVIDENCE")


if __name__=="__main__":
    unittest.main(verbosity=2)
