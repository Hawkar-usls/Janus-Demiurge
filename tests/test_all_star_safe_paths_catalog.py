"""Portable, read-only All Star intake contracts; only synthetic fixtures."""
import json
import pathlib
import tempfile
import unittest
from restored.project_paths import resolve_paths
from tools.janus_all_star_intake_catalog import inventory, ALLOWED_ROOT_MODULES


class IntakeSafety(unittest.TestCase):
    def test_resolve_has_no_implicit_file_or_directory_creation(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "unused" / "All Star"
            cfg = resolve_paths(root, env={})
            self.assertEqual(cfg.base_dir, root.resolve())
            self.assertEqual(cfg.raw_logs, root.resolve() / "raw_logs")
            self.assertTrue(cfg.safe_inside(root))
            self.assertFalse(root.exists())

    def test_env_override_must_be_explicitly_verified_as_contained(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "All Star"
            cfg = resolve_paths(root, env={"JANUS_RAW_LOGS_DIR": str(pathlib.Path(d).parent)})
            self.assertFalse(cfg.safe_inside(root))
            self.assertFalse(root.exists())

    def test_catalog_only_known_root_files_and_never_reveals_text(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "All Star"
            root.mkdir()
            (root / "experimental_sat_profile.py").write_text("VALUE = 5\n", encoding="utf-8")
            (root / "server.py").write_text(
                '# api_key placeholder only\nimport subprocess\n', encoding="utf-8"
            )
            private = root / "raw_logs"
            private.mkdir()
            (private / "hrain_graph_state.json").write_text(
                '{"private":"SENSITIVE_CONTENT_NOT_FOR_REPORT"}', encoding="utf-8"
            )
            report = inventory(root)
            output = json.dumps(report)
            self.assertEqual(len(report["files"]), len(ALLOWED_ROOT_MODULES))
            self.assertTrue(report["privateDirectoriesTraversed"] is False)
            self.assertFalse(report["automaticGitPushAllowed"])
            self.assertNotIn("import subprocess", output)
            self.assertNotIn("SENSITIVE_CONTENT_NOT_FOR_REPORT", output)
            files = {item["name"]: item for item in report["files"]}
            self.assertEqual(files["experimental_sat_profile.py"]["status"], "STATIC_REVIEW_ONLY")
            self.assertIn("CREDENTIAL_REVIEW", files["server.py"]["signals"])
            self.assertIn("EXTERNAL_IO_IMPORT_REVIEW", files["server.py"]["signals"])
            self.assertFalse(files["server.py"]["autonomousImportAllowed"])

    def test_wrong_root_and_oversize_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "ONLY_EXPLICIT_ALL_STAR_ROOT_ALLOWED"):
                inventory(pathlib.Path(d))
            root = pathlib.Path(d) / "All Star"
            root.mkdir()
            (root / "memory.py").write_bytes(b"a" * 256001)
            files = {x["name"]: x for x in inventory(root)["files"]}
            self.assertEqual(files["memory.py"]["status"], "OVERSIZE_REVIEW")
            self.assertNotIn("sha256", files["memory.py"])

    def test_source_with_invalid_syntax_does_not_abort_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "All Star"
            root.mkdir()
            (root / "server.py").write_text("if = broken", encoding="utf-8")
            output = {x["name"]: x for x in inventory(root)["files"]}
            self.assertEqual(output["server.py"]["status"], "INVALID_SOURCE_REVIEW")

if __name__ == "__main__":
    unittest.main()
