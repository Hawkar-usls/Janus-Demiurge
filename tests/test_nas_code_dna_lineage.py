"""Safety and dedup tests for the non-executing code_dna forensic reader."""
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools" / "nas_code_dna_lineage.py"
spec = importlib.util.spec_from_file_location("nas_code_dna_lineage", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NASCodeDNAForensicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "copy.db"
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE code_dna (id INTEGER PRIMARY KEY, timestamp TEXT, version_tag TEXT, file_name TEXT, source_code TEXT)")
        con.execute("CREATE TABLE vault (id INTEGER PRIMARY KEY, value TEXT)")
        con.execute("INSERT INTO vault VALUES (1, 'SECRET_NEVER_EMIT_12345')")
        self.source = "# innocuous historical code\nx = 1\n"
        for i, code in enumerate([self.source, self.source, "x = 2\n"], start=1):
            con.execute("INSERT INTO code_dna VALUES (?,?,?,?,?)",
                        (i, f"2025-12-27T01:40:0{i}", "v.1234abcd", "/app/services/ai_engine.py", code))
        con.commit()
        con.close()

    def test_metadata_only_deduplicates_and_no_secret_leak(self):
        report = mod.build(self.db)
        self.assertEqual(report["snapshot_rows"], 3)
        self.assertEqual(report["distinct_code_sha256"], 2)
        self.assertEqual(report["duplicate_snapshots"], 1)
        self.assertEqual(report["records"][0]["source_basename"], "ai_engine.py")
        self.assertEqual(report["records"][0]["source_text_sha256"],
                         hashlib.sha256(self.source.encode()).hexdigest())
        text = json.dumps(report)
        self.assertNotIn("SECRET_NEVER_EMIT", text)
        self.assertNotIn("innocuous historical code", text)
        self.assertNotIn("/app/services", text)
        self.assertFalse(report["authority"]["source_execution"])
        self.assertFalse(report["authority"]["automatic_model_promotion"])

    def test_source_database_is_not_modified(self):
        before = self.db.read_bytes()
        mod.build(self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_refuses_nonstandard_names_and_tags(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE code_dna SET file_name='../../secret.json' WHERE id=1")
        con.commit()
        con.close()
        with self.assertRaisesRegex(mod.LineageHold, "BAD_SOURCE_NAME"):
            mod.build(self.db)

    def test_rejects_missing_table_and_non_sqlite(self):
        other = Path(self.temp.name) / "other.db"
        con = sqlite3.connect(other)
        con.execute("CREATE TABLE unrelated (value TEXT)")
        con.commit()
        con.close()
        with self.assertRaisesRegex(mod.LineageHold, "INVALID_OR_INACCESSIBLE"):
            mod.build(other)
        bogus = Path(self.temp.name) / "bogus.db"
        bogus.write_bytes(b"x" * 2048)
        with self.assertRaises(mod.LineageHold):
            mod.build(bogus)

    def test_exclusive_output_no_overwrite(self):
        report = mod.build(self.db)
        output = Path(self.temp.name) / "result.json"
        mod.save_exclusive(output, report)
        self.assertEqual(json.loads(output.read_text())["snapshot_rows"], 3)
        with self.assertRaises(FileExistsError):
            mod.save_exclusive(output, report)
        self.assertFalse((Path(self.temp.name) / "result.json.tmp").exists())

    def test_rejects_unbounded_code(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE code_dna SET source_code=? WHERE id=1", ("x" * (mod.MAX_SOURCE_BYTES + 1),))
        con.commit()
        con.close()
        with self.assertRaisesRegex(mod.LineageHold, "SOURCE_CODE_SIZE"):
            mod.build(self.db)


if __name__ == "__main__":
    unittest.main()
