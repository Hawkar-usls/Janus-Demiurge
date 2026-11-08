#!/usr/bin/env python3
"""Gull R12 fail-closed original source extraction tests, synthetic fixtures."""
import copy
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import zipfile

import janus_gull_real_data_audit_v2 as a

DATA=Path(__file__).with_name("real_gull_source_manifest_v2.json")
NS="http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_fixture():
    text='''<?xml version="1.0" encoding="utf-8"?>
<w:document xmlns:w="%s"><w:body>
<w:p><w:r><w:t>Table S1 Kittiwakes</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc><w:p><w:r><w:t>Elevation</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>Bird 1</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>90</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>NR</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:t>Table S2 Herring Gulls</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>120</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><w:r><w:t>Table S3 Lesser Black-backed Gulls</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>160</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>'''%NS
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("word/document.xml",text.encode())
    return b.getvalue()


class OfficialRawGullSourceTests(unittest.TestCase):
    def test_manifest_contains_four_disjoint_real_studies(self):
        m=json.loads(DATA.read_text())
        self.assertTrue(a.analyze_manifest(m))
        self.assertEqual(len(m["sources"]),4)
        self.assertFalse(m["hypothesis_test"][
            "actual_same_individual_vision_plus_behavior_dataset_available"])

    def test_zenodo_md5_values_pinned_not_computed_from_fake_data(self):
        m=json.loads(DATA.read_text())
        z=next(s for s in m["sources"] if s["id"].startswith("hg_texel"))
        self.assertEqual(len(z["files"]),5)
        for f in z["files"]:
            self.assertEqual(len(f["md5"]),32)
            self.assertTrue(all(c in "0123456789abcdef" for c in f["md5"]))
        self.assertEqual(z["tracked_gulls"],31)

    def test_word_tables_preserve_NR_and_raw_anatomical_columns(self):
        r,t=a.extract_docx_tables(docx_fixture())
        self.assertEqual(r["table_count"],3)
        self.assertEqual(r["NR_cells"],1)
        self.assertEqual(t["tables"][0][1],["90","NR"])
        self.assertTrue(r["preserved_all_original_cells"])
        self.assertFalse(r["individual_table_mapping_confirmed"])

    def test_invalid_html_as_docx_is_refused(self):
        with self.assertRaisesRegex(ValueError,"NOT_ORIGINAL_SMALL_DOCX"):
            a.extract_docx_tables(b"<html>Access denied</html>")

    def test_space_delimited_or_tsv_csv_is_incomplete_until_parsed(self):
        raw=b"individual-local-identifier,study-specific-measurement,behavior\nbird1,human,flight\nbird2,model,rest\n"
        x=a.inspect_csv_bytes(raw)
        self.assertEqual(x["rows_scanned"],2)
        self.assertEqual(x["distinct_individuals_in_scanned_rows"],2)
        self.assertFalse(x["individual_identifiers_or_coordinates_exported"])
        self.assertIn("behavior",x["behavior_column_names"])

    def test_gzip_real_format_streams_labels_without_positions(self):
        data=b"individual-local-identifier,study-specific-measurement,behaviour,location-lat\nb1,human,flight,50.1\nb2,GULLIVER,rest,50.2\n"
        x=a.inspect_csv_bytes(gzip.compress(data))
        self.assertEqual(x["rows_scanned"],2)
        self.assertEqual(x["distinct_individuals_in_scanned_rows"],2)
        self.assertIn("study-specific-measurement",x["behavior_column_names"])
        self.assertNotIn("50.1",json.dumps(x))

    def test_mixed_original_source_failure_is_not_null_result(self):
        self.assertEqual(a.status_reason(
            urllib.error.HTTPError("https://example.org",403,
                                   "Forbidden",None,None)),
            "HTTP_403")

    def test_manifest_rejects_joining_different_bird_groups(self):
        m=json.loads(DATA.read_text())
        m["hypothesis_test"][
            "actual_same_individual_vision_plus_behavior_dataset_available"]=True
        with self.assertRaisesRegex(ValueError,"FORBID_JOINING_UNRELATED"):
            a.analyze_manifest(m)

    def test_manifest_rejects_lost_source(self):
        m=json.loads(DATA.read_text())
        m["sources"].pop()
        with self.assertRaisesRegex(ValueError,"SOURCE_SET_CHANGED"):
            a.analyze_manifest(m)

    def test_zip_bomb_style_missing_word_document_refused(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            z.writestr("README.txt","not a word document")
        with self.assertRaisesRegex(ValueError,"DOCX_HAS_NO_WORD_DOCUMENT"):
            a.extract_docx_tables(b.getvalue())


if __name__=="__main__":
    unittest.main(verbosity=2)
