#!/usr/bin/env python3
import unittest
import nist_cycle_order_010e as s
import nist_sync_010d as n


class NISTCausalOrderContract(unittest.TestCase):
    def encode(self,triples):
        return b"".join(n.REC.pack(*x) for x in triples)

    def test_complete_cycle_counts_all_no_postselection(self):
        raw=self.encode([
            (6,100,0),(2,120,0),(0,140,0),
            (6,200,0),(0,220,0),(4,260,0),
            (6,300,0),(4,310,0),(6,400,0)])
        out=s.sync_cycle_audit(raw)
        self.assertEqual(out["counts"]["completed_cycles"],3)
        classes=out["all_completed_cycle_classes"]
        self.assertEqual(classes["earliest_rng_before_earliest_detector"],1)
        self.assertEqual(classes["earliest_detector_before_earliest_rng"],1)
        self.assertEqual(classes["one_rng_no_detector"],1)
        self.assertEqual(out["rng_minus_detector_first_event_ns"]["n"],2)

    def test_ambiguous_rng_marked_not_silent_choice(self):
        raw=self.encode([(6,100,0),(2,110,0),(4,115,0),(0,120,0),(6,200,0)])
        out=s.sync_cycle_audit(raw)
        self.assertEqual(out["all_completed_cycle_classes"]["multiple_rng_pulses"],1)
        self.assertEqual(out["all_completed_cycle_classes"]["multi_rng_with_detector"],1)

    def test_raw_channel64_unclassified(self):
        raw=self.encode([(6,100,0),(64,110,0),(0,115,0),(6,200,0)])
        out=s.sync_cycle_audit(raw)
        self.assertEqual(out["unclassified_raw_channel_codes"],{"64":1})
        self.assertEqual(out["counts"]["completed_cycles"],1)

    def test_gps_not_mistaken_for_photon(self):
        raw=self.encode([(6,100,0),(5,105,0),(6,200,0)])
        out=s.sync_cycle_audit(raw)
        self.assertEqual(out["counts"]["GPS_PPS_within_cycles"],1)
        self.assertEqual(out["all_completed_cycle_classes"]["zero_detectors"],1)
        self.assertEqual(out["all_completed_cycle_classes"]["zero_rng_pulses"],1)

    def test_nonmonotonic_known_timing_rejected(self):
        raw=self.encode([(6,100,0),(0,99,0)])
        with self.assertRaisesRegex(ValueError,"NONMONOTONIC"):
            s.sync_cycle_audit(raw)

    def test_before_sync_not_falsely_counted(self):
        raw=self.encode([(0,90,0),(6,100,0),(6,200,0)])
        out=s.sync_cycle_audit(raw)
        self.assertEqual(out["counts"]["physical_event_records_before_first_sync"],1)
        self.assertEqual(out["all_completed_cycle_classes"]["zero_detectors"],1)


if __name__=="__main__":
    unittest.main()
