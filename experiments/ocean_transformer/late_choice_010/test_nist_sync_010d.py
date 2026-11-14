#!/usr/bin/env python3
"""Independent offline tests of NIST 24-byte timetag interpretation."""
import struct
import unittest
import nist_sync_010d as n


class NISTTimestamperContract(unittest.TestCase):
    def test_24byte_little_endian(self):
        data=n.REC.pack(0,123456789,3)+n.REC.pack(2,123456790,3)+n.REC.pack(4,123456791,3)
        self.assertEqual(len(data),72)
        r=n.parse_events(data)
        self.assertEqual(r["n_raw_events"],3)
        self.assertEqual(r["per_channel"]["0"]["count"],1)
        self.assertEqual(r["per_channel"]["2"]["count"],1)
        self.assertEqual(r["per_channel"]["4"]["count"],1)
        self.assertEqual(r["transfer_counter_min"],3)

    def test_gps_nominal_one_second(self):
        # Based only on the 12.8 GHz clock period documented by NIST.
        records=[(5,1_000_000_000,0),(5,13_800_000_000,1),
                 (5,26_600_000_000,2)]
        r=n.parse_events(b"".join(n.REC.pack(*row) for row in records))
        self.assertEqual(r["GPS_PPS_interval_count"],2)
        self.assertAlmostEqual(r["GPS_PPS_interval_median_ns"],1e9,places=4)

    def test_short_gps_absence_not_fake_measurement(self):
        r=n.parse_events(n.REC.pack(6,12345,0))
        self.assertIsNone(r["GPS_PPS_interval_median_ns"])
        self.assertEqual(r["GPS_PPS_count"],0)

    def test_unaligned_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNALIGNED_24_BYTE"):
            n.parse_events(b"123")

    def test_unclassified_channel_not_mislabeled_as_physical_event(self):
        stat=n.parse_events(n.REC.pack(64,1234567,0))
        self.assertEqual(stat["unclassified_channel_codes"],{"64":1})
        self.assertEqual(stat["per_channel"]["0"]["count"],0)
        self.assertEqual(stat["GPS_PPS_count"],0)

    def test_implausible_channel_refused(self):
        with self.assertRaisesRegex(ValueError,"IMPLAUSIBLE_CHANNEL"):
            n.parse_events(n.REC.pack(999999,1,0))

    def test_nonincreasing_gps_rejected(self):
        with self.assertRaisesRegex(ValueError,"NONINCREASING_GPS"):
            n.parse_events(n.REC.pack(5,100,0)+n.REC.pack(5,90,0))

    def test_channel_mapping_fixed(self):
        self.assertEqual(n.CHANNELS[0],"detector_click")
        self.assertEqual(n.CHANNELS[2],"QRNG_zero_setting_output")
        self.assertEqual(n.CHANNELS[4],"QRNG_one_setting_output")
        self.assertEqual(n.CHANNELS[5],"GPS_PPS")
        self.assertEqual(n.CHANNELS[6],"pockels_sync")


if __name__=="__main__":
    unittest.main()
