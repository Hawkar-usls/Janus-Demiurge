#!/usr/bin/env python3
"""LBBG R12c exact metadata and efficient model/heldout smoke tests."""
import unittest

import janus_gull_human_gps_holdout_v2 as slow
import janus_lbbg_real_human_holdout_v3 as v


class RealLBBGGroupedControls(unittest.TestCase):
    def test_publisher_check_sum_set_all_three_years(self):
        self.assertEqual(set(v.PUBLISHED),{2012,2013,2014})
        self.assertEqual(v.DOI,"10.5281/zenodo.23942209")
        for year in v.PUBLISHED:
            for value in v.PUBLISHED[year].values():
                self.assertEqual(len(value),32)
                self.assertTrue(all(c in "0123456789abcdef" for c in value))

    def test_fast_and_original_1bit_encoders_same_on_basic_fixture(self):
        data=[{"bird":"a","speed":float(speed),"label":int(speed>=5)}
              for speed in (0,1,2,8,9,11)]
        for objective in ("metric","task"):
            original=slow.fit(data,objective)
            fast=v.fit_fast(data,objective)
            self.assertEqual(fast["threshold"],original["threshold"])
            self.assertEqual(fast["codebook"],original["codebook"])

    def test_fast_optimized_threshold_spans_correct_class_types(self):
        data=[{"bird":"b","speed":float(speed),"label":label}
              for speed,label in ((0,0),(1,0),(4,0),(9,1),(10,1),(12,1))]
        task=v.fit_fast(data,"task")
        p=[slow.predict(task["codebook"],task["threshold"],x["speed"])
           for x in data]
        self.assertEqual(p,[x["label"] for x in data])

    def test_four_bird_realistic_grouped_holdout(self):
        data=[{"bird":f"bird_{bird}","speed":float(s),
               "label":int(s>8)}
              for bird in range(4) for s in (1,3,11,12,14,20)]
        r=v.leave_bird_out(data)
        self.assertEqual(r["status"],
                         "REAL_HUMAN_BEHAVIOR_CROSS_BIRD_HOLDOUT_COMPLETE")
        self.assertEqual(r["complete_held_out_birds"],4)
        self.assertEqual(r["evaluated_rows"],24)
        self.assertEqual(r["models"]["task"]["balanced_accuracy"],1)
        self.assertFalse(r["Hoffman_theory_proven"])

    def test_single_bird_is_scientifically_not_scorable(self):
        data=[{"bird":"one","speed":float(k),"label":k%2}
              for k in range(124)]
        r=v.leave_bird_out(data)
        self.assertIn("NOT_SCORABLE",r["status"])
        self.assertEqual(r["matched_individuals"],1)
        self.assertFalse(r["physical_Hoffman_theory_test"])

    def test_missing_two_classes_rejected(self):
        data=[{"bird":f"b{i%3}","speed":float(i),"label":0}
              for i in range(60)]
        r=v.leave_bird_out(data)
        self.assertIn("NOT_SCORABLE",r["status"])

    def test_out_of_scope_source_year_refused_before_download(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_PUBLISHED_SOURCE"):
            v.official_data(2026,"gps")


if __name__=="__main__":
    unittest.main(verbosity=2)
