#!/usr/bin/env python3
import pathlib
import tempfile
import unittest
import zipfile
import nist_original_code_010i as c


class NISTSourceAudit(unittest.TestCase):
    def test_select_original_clock_related_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"test.zip"
            with zipfile.ZipFile(p,"w") as z:
                z.writestr("original/program.py", "def get_offset():\n    badSyncInfo = 42\n    bitoffset = 3\n")
                z.writestr("original/large_noise.txt","0"*1_000_000)
            result=c.analyze_archive(p)
        self.assertEqual(len(result["matching_original_scripts"]),1)
        self.assertEqual(result["matching_original_scripts"][0]["matching_lines"][0]["high_specificity"],True)
        self.assertTrue(result["code_not_executed"])

    def test_end_to_end_empty_source_zip_abstains(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/"test.zip"
            with zipfile.ZipFile(p,"w") as z:
                z.writestr("readme.md","No matching physics source.")
            result=c.analyze_archive(p)
        self.assertEqual(result["total_matching_lines_retained"],0)
        self.assertTrue(result["author_clock_calibration_still_requires_independent_validation"])

    def test_original_archive_source(self):
        self.assertTrue(c.URL.startswith("https://s3.amazonaws.com/nist-belltestdata/belldata/code/analysis/"))
        self.assertLess(c.MAX_ZIP,900000000)
        self.assertLessEqual(c.MAX_SINGLE_FILE,750000)


if __name__=="__main__":unittest.main()
