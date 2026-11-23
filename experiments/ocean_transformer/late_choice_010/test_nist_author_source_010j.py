import tempfile
import pathlib
import zipfile
import unittest
import nist_author_source_010j as n


class OfficialSourceCustody(unittest.TestCase):
    def test_source_sha_is_prelocked_to_010i(self):
        self.assertEqual(n.EXPECTED_SHA,"80b452b55ce44bb46e37ffbcd1f1684ba3293aaf0b6445c36743da4a5d37c52d")
        self.assertTrue(n.URL.startswith("https://s3.amazonaws.com/nist-belltestdata/"))

    def test_missing_source_script_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/"empty.zip"
            with zipfile.ZipFile(p,"w") as z:z.writestr("wrong_file.py","")
            with self.assertRaisesRegex(ValueError,"MISSING_NIST_ORIGINAL_SCRIPT"):
                n.source_extract(p)

    def test_source_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/"source.zip"
            with zipfile.ZipFile(p,"w") as z:
                for name in n.PATHS:z.writestr(name,"raise RuntimeError('MUST NOT EXECUTE')\n")
            src=n.source_extract(p)
        self.assertEqual(len(src),len(n.PATHS))
        self.assertTrue(all(x["read_only_not_executed"] for x in src.values()))


if __name__=="__main__":unittest.main()
