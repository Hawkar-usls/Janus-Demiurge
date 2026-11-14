#!/usr/bin/env python3
"""JANUS 010G PPS-only lag detection can NEVER certify a physical clock offset."""
import random
import unittest
import nist_pps_waveform_010g as q


class PPSWaveformGateTests(unittest.TestCase):
    def test_known_shared_jitter_lag_heldout(self):
        rng=random.Random(1734)
        a=[rng.gauss(0,7) for _ in range(416)]
        b=[rng.gauss(0,7) for _ in range(416)]
        lag=7
        for i in range(416-lag):
            b[i+lag]=a[i]+rng.gauss(0,0.1)
        result=q.evaluate(a,b)
        self.assertEqual(result["candidate_B_index_minus_A_index"],lag)
        self.assertGreater(result["validation_pearson_r"],0.99)
        self.assertTrue(result["relative_pps_sequence_candidate_detected"])
        self.assertFalse(result["certified_UTC_second_index_mapping_established"])
        self.assertFalse(result["independent_physical_clock_offset_established"])

    def test_independent_fake_inputs_not_promoted_to_absolute_time(self):
        rng=random.Random(77)
        a=[rng.gauss(0,7) for _ in range(416)]
        b=[rng.gauss(0,7) for _ in range(416)]
        result=q.evaluate(a,b)
        self.assertFalse(result["certified_UTC_second_index_mapping_established"])
        self.assertFalse(result["independent_physical_clock_offset_established"])
        self.assertFalse(result["causal_inference_eligible"])

    def test_pearson_anticorrelation(self):
        self.assertAlmostEqual(q.pearson([2,3,7,4],[-2,-3,-7,-4]),-1)

    def test_insufficient_data_refused(self):
        with self.assertRaisesRegex(ValueError,"EXPECTED_416_PPS_GAPS"):
            q.evaluate([1,2],[3,4])

    def test_lag_index_is_mathematical_not_absolute_gps_second(self):
        x,y=q.paired_lag(list(range(100)),list(range(100)),10,0,20)
        self.assertEqual(x,list(range(20)))
        self.assertEqual(y,list(range(10,30)))


if __name__=="__main__":unittest.main()
