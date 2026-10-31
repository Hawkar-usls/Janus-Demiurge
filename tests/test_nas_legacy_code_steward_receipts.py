"""JANUS NAS Steward recovery: static-only self-hash and archive safety checks.

NEVER IMPORT OR EXECUTE historic NAS scripts in this test.
"""
import ast
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]/"archaeology"/"nas_steward_v161"
NAMES=(
    "janus_code_steward.py", "janus_archive_stack.py", "db_guard.py",
    "janus_habitat_gate.py", "janus_habitat_terminal.py",
    "decision_governor.py",
)
EXPECTED_SHA={
    "release_000001.json":"a146251b2da7d6e0a64adaabba5c8988e3cc6f93e4d3b2b2a8ad2a82aac9afcc",
    "release_000002.json":"eb30ea6952697d4a0829ab9e77269ed7a2404e58d2a0dfacc5a2813ce828c6ac",
    "activation_000001.json":"ea77e5dd1fd447caeea696425ea8b562cb961e362112e0cc63b0d8188fd54613",
    "activation_000002.json":"d9c98f954fbf6c471eafc2538daf8ee6eaa2b86836b5a8b44d8132840ceda896",
}
def digest(value):
    return hashlib.sha256(json.dumps(
        value,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()

class ArchiveStaticProof(unittest.TestCase):
    def test_original_sources_are_syntactically_valid_without_execution(self):
        self.assertEqual(len(list(ROOT.glob("*.py"))),len(NAMES))
        for n in NAMES:
            with self.subTest(name=n):
                s=(ROOT/n).read_text(encoding="utf-8")
                ast.parse(s, filename=n)
                self.assertNotIn("github_pat_",s)
                self.assertNotIn("-----BEGIN OPENSSH PRIVATE KEY",s)
    def test_self_hash_receipts_and_lineage(self):
        records={}
        for name,expected in EXPECTED_SHA.items():
            with self.subTest(receipt=name):
                v=json.loads((ROOT/"receipts"/name).read_text(encoding="utf-8"))
                k=("manifest_receipt_sha256" if name.startswith("release")
                   else "activation_receipt_sha256")
                self.assertEqual(v[k],expected)
                unsigned={k2:x for k2,x in v.items() if k2!=k}
                self.assertEqual(digest(unsigned),expected)
                records[name]=v
        a=records["activation_000001.json"]
        b=records["activation_000002.json"]
        self.assertEqual([a["sequence"],b["sequence"]],[1,2])
        self.assertIsNone(a["previous_release"])
        self.assertEqual(b["previous_release"],a["target_release"])
        self.assertEqual(b["target_release"],"000002")
        self.assertEqual(records["release_000002.json"]["parent_release"],"000001")
    def test_smoke_candidate_does_not_prove_full_autonomy(self):
        v=json.loads((ROOT/"receipts"/"release_000002.json").read_text())
        self.assertIn("SMOKE_TEST",v["source"])
        self.assertLess(v["components"]["gate"]["bytes"],1024)
        self.assertLess(v["components"]["terminal"]["bytes"],1024)
        original=json.loads((ROOT/"receipts"/"release_000001.json").read_text())
        self.assertFalse(original["gates"]["ci"])
        self.assertFalse(original["gates"]["demihead"])
    def test_dangerous_legacy_restore_is_archive_only(self):
        s=(ROOT/"db_guard.py").read_text(encoding="utf-8")
        self.assertIn("JANUS_DB_GUARD_ALLOW_FULL_RESTORE",s)
        self.assertIn('"1"',s)
        self.assertFalse((ROOT/"__init__.py").exists())
        self.assertFalse((ROOT/"Dockerfile").exists())
        self.assertFalse((ROOT/"requirements.txt").exists())
    def test_no_model_or_private_database_assets(self):
        for suffix in (".db",".sqlite",".pkl",".pt",".env"):
            self.assertFalse(list(ROOT.rglob("*"+suffix)))

if __name__=="__main__":
    unittest.main()
