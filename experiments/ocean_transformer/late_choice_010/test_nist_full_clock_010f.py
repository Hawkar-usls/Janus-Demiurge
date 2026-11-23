#!/usr/bin/env python3
"""Offline contracts for NIST full-run streaming, GPS-only alignment abstention."""
import io
import pathlib
import tempfile
import unittest
import zipfile
import nist_full_clock_010f as n


class NISTFullClockContracts(unittest.TestCase):
    def make_zip(self,path,record_bytes):
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("demo.dat",record_bytes)

    def test_real_raw_record_shape_and_gps_rate(self):
        # Three one-second PPS marks, with photon/RNG and sync data intermixed.
        data=b"".join(n.REC.pack(*r) for r in [
            (6,10,0),(0,13,0),(5,100,0),(2,105,0),(64,107,0),
            (5,100+n.SECOND_TICKS,1),(4,100+n.SECOND_TICKS+3,1),
            (5,100+2*n.SECOND_TICKS,2)])
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"test.zip"
            self.make_zip(p,data)
            s=n.summarize_raw(p,5000)
        self.assertEqual(s["n_original_raw_events"],8)
        self.assertEqual(s["counts_by_channel"]["64"],1)
        self.assertEqual(s["mapped_physical_channels"]["0"],1)
        self.assertEqual(s["gps_phase_rate_diagnostics"]["n_pps"],3)
        self.assertEqual(s["gps_phase_rate_diagnostics"]["median_period_minus_1s_ns"],0)
        self.assertTrue(s["gps_phase_rate_diagnostics"]["rate_estimate_valid"])

    def test_no_false_absolute_clock_alignment(self):
        p={"rate_estimate_valid":True,"median_period_ns":1e9,
           "median_period_ticks":n.SECOND_TICKS}
        a={"gps_phase_rate_diagnostics":p}
        b={"gps_phase_rate_diagnostics":dict(p)}
        out=n.clock_audit(a,b)
        self.assertFalse(out["identifiable_absolute_A_minus_B_clock_offset_ticks"])
        self.assertFalse(out["clock_offset_fitted_using_detector_correlations"] if "clock_offset_fitted_using_detector_correlations" in out else False)
        self.assertEqual(out["fractional_frequency_difference_ppm"],0)
        self.assertTrue(out["relative_clock_rate_eligible_for_diagnostic"])

    def test_gps_rate_difference_not_offset(self):
        a={"gps_phase_rate_diagnostics":{"rate_estimate_valid":True,
            "median_period_ticks":n.SECOND_TICKS+128,"median_period_ns":1e9+10}}
        b={"gps_phase_rate_diagnostics":{"rate_estimate_valid":True,
            "median_period_ticks":n.SECOND_TICKS,"median_period_ns":1e9}}
        res=n.clock_audit(a,b)
        self.assertAlmostEqual(res["fractional_frequency_difference_ppm"],.01)
        self.assertFalse(res["identifiable_absolute_A_minus_B_clock_offset_ticks"])

    def test_unaligned_archive_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"bad.zip"
            self.make_zip(p,b"HELLO")
            with self.assertRaisesRegex(ValueError,"RAW_ARCHIVE_SIZE_NOT_24_BYTE_ALIGNED"):
                n.summarize_raw(p,5000)

    def test_unknown_hardware_channel_preserved_but_not_classified(self):
        data=b"".join(n.REC.pack(*r) for r in [(64,1,0),(5,3,0),(64,4,0)])
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"unclassified.zip"
            self.make_zip(p,data)
            r=n.summarize_raw(p,5000)
        self.assertEqual(r["unclassified_codes"],{"64":2})
        self.assertEqual(r["mapped_physical_channels"]["0"],0)

    def test_implausible_channel_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"invalid.zip"
            self.make_zip(p,n.REC.pack(888,1,0))
            with self.assertRaisesRegex(ValueError,"IMPLAUSIBLE_CHANNEL_CODE"):
                n.summarize_raw(p,5000)

    def test_raw_size_cap(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"too_big.zip"
            self.make_zip(p,n.REC.pack(5,1,0)*10)
            with self.assertRaisesRegex(ValueError,"RAW_DECOMPRESSED_FILE_SIZE_OVER_CAP"):
                n.summarize_raw(p,100)


if __name__=="__main__": unittest.main()
