"""Static preservation tests; never import or execute old NAS cores."""
import ast
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]/"archaeology"/"nas_early_cores_20261031"
FILENAMES=(
    "blood_core.py","quantum_core.py","microgpt.py",
    "janus_memory_bridge.py","janus_db_writer.py",
    "mod_hrein_bridge_enhancer.py","mod_model_selector.py",
    "mod_training_feedback_loop.py","brain_ext_bridge.py"
)


class NASLegacyCoreTests(unittest.TestCase):
    def test_nine_archive_sources_parse_without_execution(self):
        self.assertTrue((ROOT/"README.md").exists())
        for name in FILENAMES:
            with self.subTest(name=name):
                raw=(ROOT/name).read_text(encoding="utf-8")
                ast.parse(raw,filename=name)
                self.assertNotRegex(raw,r"-----BEGIN (?:RSA|OPENSSH|EC)? ?PRIVATE KEY-----")
                self.assertNotRegex(raw,r"github_pat_[A-Za-z0-9_]{15}|ghp_[A-Za-z0-9]{15}")
                self.assertNotRegex(raw,r"192[.]168[.][0-9]+[.][0-9]+")
    def test_no_private_model_or_database_assets(self):
        self.assertEqual(sorted(p.name for p in ROOT.iterdir() if p.is_file()
                                and p.suffix in (".db",".sqlite",".pkl",".pt",".env")),[])
        self.assertEqual(len(list(ROOT.glob("*.py"))),9)


if __name__ == "__main__":
    unittest.main()
