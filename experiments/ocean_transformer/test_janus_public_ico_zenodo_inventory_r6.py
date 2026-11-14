#!/usr/bin/env python3
"""Zenodo 2026 archive inventory safety checks — synthetic only."""
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import janus_public_ico_zenodo_inventory_r6 as q


def make_zip(files):
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,"w") as z:
        for path,body in files.items():
            z.writestr(path,body)
    return raw.getvalue()


class ZenodoInventoryTests(unittest.TestCase):
    def test_small_python_and_data_archive_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.zip"
            p.write_bytes(make_zip({
                "study/readme.txt":b"method",
                "study/results.csv":b"outcome,probability\n0,.5\n1,.5\n",
                "study/analysis.py":b"raise RuntimeError('DO NOT EXECUTE')\n"
            }))
            r=q.inspect(p)
            self.assertEqual(r["file_count"],3)
            self.assertEqual(r["code_files_by_extension"],1)
            self.assertGreaterEqual(r["data_candidate_files_by_extension"],2)
            self.assertFalse(r["external_code_executed"])
            self.assertFalse(r["physical_future_to_past_message_demonstrated"])

    def test_unsafe_parent_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"escape.zip"
            p.write_bytes(make_zip({"../unsafe.py":b"print('bad')"}))
            with self.assertRaisesRegex(ValueError,"UNSAFE_ZIP_PATH"):
                q.inspect(p)

    def test_invalid_zip_must_not_be_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"not_zip.zip"
            p.write_bytes(b"arbitrary network denial response")
            with self.assertRaisesRegex(ValueError,"NOT_A_SAFE_ZENODO_ZIP"):
                q.inspect(p)

    def test_data_source_and_claims_are_explicit(self):
        self.assertEqual(q.DOI,"10.5281/zenodo.21916346")
        self.assertIn("zenodo.org",q.SOURCE)


if __name__=="__main__":
    unittest.main(verbosity=2)
