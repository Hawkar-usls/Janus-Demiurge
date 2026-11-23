#!/usr/bin/env python3
"""R6 aggregate photonic public data: independent defensive parser tests."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import janus_public_ico_dryad_audit_r6 as a


def build(files_missing=(), corrupted=None):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name in a.EXPECTED:
            if name in files_missing:continue
            rows=["outcome,probability,errorbar"]
            rows += [f"{i:04b},{1/16},0.003" for i in range(16)]
            if corrupted==name:
                rows[1]="0000,0.5,0.003"
            z.writestr(name,"\n".join(rows)+"\n")
    return stream.getvalue()


class DryadAuditTests(unittest.TestCase):
    def test_complete_synthetic_16_setting_aggregates(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"dataset.zip"
            p.write_bytes(build())
            r=a.inspect_zip(p)
            self.assertEqual(r["settings_verified"],16)
            self.assertEqual(r["sum_probability_min"],1)
            self.assertFalse(r["physical_retrocausality_proven"])
            self.assertFalse(r["original_trial_level_detector_time_tags_in_these_16_csv"])
            self.assertFalse(r["published_inequality_reference"]
                             ["raw_csv_to_inequality_term_mapping_reproduced"])

    def test_missing_setting_refused_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.zip"
            p.write_bytes(build(files_missing={"Fig4_input_setting0011_vs_probability.csv"}))
            with self.assertRaisesRegex(ValueError,"MISSING_ONE_OR_MORE"):
                a.inspect_zip(p)

    def test_corrupted_normalization_not_automatically_fixed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.zip"
            p.write_bytes(build(corrupted="Fig4_input_setting0000_vs_probability.csv"))
            with self.assertRaisesRegex(ValueError,"PROBABILITY_NORMALIZATION"):
                a.inspect_zip(p)

    def test_bad_probability_columns_rejected(self):
        rows="outcome,probability,errorbar\n"+"".join(
          f"{i:04b},0.0625,0.01,unexpected\n" for i in range(16))
        with self.assertRaisesRegex(ValueError,"UNEXPECTED_DATA_COLUMNS"):
            a.read_aggregate_csv(rows.encode())

    def test_negative_errorbar_rejected(self):
        rows="outcome,probability,errorbar\n"+"".join(
          f"{i:04b},0.0625,-0.001\n" for i in range(16))
        with self.assertRaisesRegex(ValueError,"INVALID_PROBABILITY_OR_ERRORBAR"):
            a.read_aggregate_csv(rows.encode())

    def test_repeated_outcome_rejected(self):
        rows="outcome,probability,errorbar\n"+"".join(
          "0000,0.0625,0.001\n" for i in range(16))
        with self.assertRaisesRegex(ValueError,"EMPTY_OR_DUPLICATE_OUTCOME"):
            a.read_aggregate_csv(rows.encode())

    def test_expected_16_binary_settings_are_fixed(self):
        self.assertEqual(set(a.EXPECTED.values()),
                         {f"{i:04b}" for i in range(16)})
        self.assertEqual(a.DATASET_DOI,"10.5061/dryad.8kprr4z24")


if __name__=="__main__":
    unittest.main(verbosity=2)
