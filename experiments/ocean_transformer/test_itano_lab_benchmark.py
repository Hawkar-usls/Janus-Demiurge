#!/usr/bin/env python3
"""External Itano (1990) Zeno benchmark regression, no fabricated physics."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

import itano_lab_benchmark as bench

DATA=Path(__file__).parent/"data/itano1990_pra_table1.json"


class ItanoLabTests(unittest.TestCase):
    def test_published_table_has_14_real_laboratory_estimates(self):
        data,sha=bench.load_locked_table(str(DATA))
        self.assertEqual(data["n_pulses"],[1,2,4,8,16,32,64])
        self.assertEqual(len(sha),64)
        self.assertEqual(len(data["observed_forward_1_to_2"])+len(data["observed_reverse_2_to_1"]),14)
        self.assertEqual(data["observed_forward_1_to_2"][-1],-.006)
        self.assertEqual(data["doi"],"10.1103/PhysRevA.41.2295")

    def test_ideal_transition_matches_published_rounded_reference(self):
        data,_=bench.load_locked_table(str(DATA))
        for n,published in zip(data["n_pulses"],data["published_ideal_rounded"]):
            analytic=.5*(1-math.cos(math.pi/n)**n)
            self.assertLess(abs(analytic-published),.000055)

    def test_no_fit_and_author_model_stronger(self):
        r=bench.assess(str(DATA))
        self.assertFalse(r["model"]["fitted_using_published_observations"])
        self.assertEqual(len(r["individual_rows"]),14)
        self.assertTrue(r["interpretation"]["paper_apparatus_model_has_smaller_rmse_both_directions"])
        self.assertFalse(r["interpretation"]["physical_retrocausality_established"])
        self.assertFalse(r["interpretation"]["formal_pvalue_computed"])
        self.assertFalse(r["interpretation"]["uncertainty_interpreted_as_independent_identical_sigma"])
        self.assertAlmostEqual(r["metrics"]["level_1_to_2"]["observed_vs_frozen_ideal"]["rmse"],.03681733884457128,places=11)
        self.assertAlmostEqual(r["metrics"]["level_2_to_1"]["observed_vs_frozen_ideal"]["rmse"],.021107698462810378,places=11)

    def test_negative_noisy_estimate_unclipped_in_all_report_rows(self):
        r=bench.assess(str(DATA))
        row=next(x for x in r["individual_rows"]
                 if x["direction"]=="level_1_to_2" and x["n_measurement_pulses"]==64)
        self.assertEqual(row["published_observed_transition_estimate"],-.006)
        self.assertGreater(row["frozen_ideal_cpu_transition"],0)
        self.assertTrue(r["interpretation"]["negative_observation_is_noisy_estimate_not_negative_probability"])

    def test_modified_table_refused_even_if_metadata_is_same(self):
        d=json.loads(DATA.read_text())
        d["observed_forward_1_to_2"][-1]=0
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"fake.json"
            path.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"LOCKED_TABLE_CHANGED"):
                bench.load_locked_table(str(path))

    def test_single_significance_pvalue_not_inferred(self):
        r=bench.assess(str(DATA))
        self.assertFalse(r["interpretation"]["formal_pvalue_computed"])
        self.assertEqual(r["source"]["approximate_observation_uncertainty"],.02)
        self.assertFalse(r["interpretation"]["data_pretended_independent_blind_hidden_set"])

    def test_score_rejects_unpaired_values(self):
        with self.assertRaises(ValueError):
            bench.score([1,2],[1])
        with self.assertRaises(ValueError):
            bench.score([],[])

    def test_no_network_or_wolfram_as_science_data(self):
        r=bench.assess(str(DATA))
        self.assertEqual(r["scope"]["network_queries_during_benchmark"],0)
        self.assertEqual(r["scope"]["provider_wolfram_queries"],0)
        self.assertFalse(r["scope"]["physical_measurements_performed_by_janus"])
        self.assertTrue(r["scope"]["real_external_lab_measurements_used"])


if __name__=="__main__":
    unittest.main(verbosity=2)
