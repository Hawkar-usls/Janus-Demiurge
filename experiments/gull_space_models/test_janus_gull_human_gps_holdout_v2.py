#!/usr/bin/env python3
"""Synthetic regression controls for REAL-data gull human-only LOBO validator."""
import gzip
import json
import unittest

import janus_gull_human_gps_holdout_v2 as h


def gzip_csv(s):
    return gzip.compress(s.encode("utf8"))


class HumanBehaviorHoldoutTests(unittest.TestCase):
    def test_publisher_original_checksums_pinned(self):
        self.assertEqual(h.ORIGINAL_MD5[h.GPS],
                         "cf0af35d196b35d73461e0ba55778583")
        self.assertEqual(h.ORIGINAL_MD5[h.ACCESSORY],
                         "fa96822fc65b746b626ce9ff9a382272")

    def test_manual_labels_only_machine_rows_never_ground_truth(self):
        raw=gzip_csv(
          "study-specific-measurement,behavioural-classification,individual-local-identifier,timestamp\n"
          "machine,flap,b1,2016-07-01T12:00:01Z\n"
          "human,flap,b1,2016-07-01T12:00:01Z\n"
          "human,walk,b2,2016-07-01T12:00:02Z\n"
          "human,mixed,b2,2016-07-01T12:00:03Z\n")
        rows,meta=h.human_events(raw)
        self.assertEqual(meta["human_labels_total"],3)
        self.assertEqual(meta["machine_labels_excluded"],1)
        self.assertEqual(meta["human_scored_binary_labels"],2)
        self.assertEqual(meta["human_label_counts"]["mixed"],1)
        self.assertEqual({r["label"] for r in rows},{0,1})

    def test_same_bird_preceding_gps_only(self):
        human=[{"bird":"b1","time":h.epoch("2016-01-01T12:02:00Z"),"label":1},
               {"bird":"b2","time":h.epoch("2016-01-01T12:02:00Z"),"label":0}]
        raw=gzip_csv(
          "individual-local-identifier,timestamp,ground-speed,import-marked-outlier\n"
          "b1,2016-01-01T12:01:50Z,10,false\n"
          "b1,2016-01-01T12:02:05Z,300,false\n"
          "b2,2016-01-01T12:00:30Z,0,false\n"
          "b3,2016-01-01T12:01:58Z,500,false\n")
        rows,meta=h.attach_prior_gps(human,raw)
        self.assertEqual(len(rows),2)
        self.assertEqual({r["bird"]:r["speed"] for r in rows},{"b1":10,"b2":0})
        self.assertFalse(meta["later_gps_after_human_annotation_ever_used"])
        self.assertEqual(meta["max_observed_match_lag_seconds"],90)

    def test_older_than_tolerance_rejected(self):
        human=[{"bird":"b1","time":h.epoch("2016-01-01T12:05:00Z"),"label":1}]
        raw=gzip_csv(
          "individual-local-identifier,timestamp,ground-speed\n"
          "b1,2016-01-01T12:00:00Z,3\n")
        rows,meta=h.attach_prior_gps(human,raw)
        self.assertEqual(rows,[])
        self.assertEqual(meta["human_labels_without_past_gps_match"],1)

    def test_geometry_code_is_unlabeled_metric_reconstruction(self):
        train=[{"bird":"A","speed":v,"label":int(v>=10)}
               for v in (0,1,2,10,11,12)]
        first=h.fit(train,"metric")
        permuted=[{**x,"label":int(i%2)} for i,x in enumerate(train)]
        second=h.fit(permuted,"metric")
        self.assertEqual(first["threshold"],second["threshold"])

    def test_task_code_scored_on_actual_train_labels_only(self):
        train=[{"bird":"A","speed":v,"label":int(v>=10)}
               for v in (0,1,2,10,11,12)]
        model=h.fit(train,"task")
        pred=[h.predict(model["codebook"],model["threshold"],x["speed"])
              for x in train]
        self.assertEqual(pred,[x["label"] for x in train])
        self.assertEqual(h.balanced_accuracy(pred,[x["label"] for x in train]),1)

    def test_leave_one_bird_out_has_no_row_splitting(self):
        data=[{"bird":f"b{bird}","speed":s,
               "label":int(s>=10)}
              for bird in range(5) for s in (1,2,11,12,14)]
        result=h.held_out_bird_validation(data)
        self.assertEqual(result["status"],
                         "HUMAN_ANNOTATION_LOBO_BENCHMARK_COMPLETE")
        self.assertEqual(result["distinct_matched_birds"],5)
        self.assertEqual(result["folds_complete"],5)
        self.assertEqual(result["evaluated_rows"],25)
        self.assertEqual(result["models"]["task"]["balanced_accuracy"],1)

    def test_insufficient_human_rows_marked_not_scorable(self):
        data=[{"bird":"b1","speed":1,"label":0}]*10
        result=h.held_out_bird_validation(data)
        self.assertIn("NOT_SCORABLE",result["status"])
        self.assertNotIn("models",result)

    def test_temporal_parser_requires_actual_timestamp(self):
        self.assertIsNone(h.epoch(""))
        self.assertIsNone(h.epoch("not-a-time"))
        self.assertEqual(h.epoch("2016-01-01T12:00:00Z"),
                         h.epoch("2016-01-01T12:00:00+00:00"))


if __name__=="__main__":
    unittest.main(verbosity=2)
