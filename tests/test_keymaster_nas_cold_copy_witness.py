"""Synthetic, no-network Keymaster NAS cold-copy integrity tests."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "daddy_keymaster" / "nas_cold_copy_witness.py"
spec = importlib.util.spec_from_file_location("nas_cold_copy_witness", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ColdCopyWitnessTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        (self.root / "snapshots").mkdir()
        self.commit = "a" * 40
        self.mirror = b'{"private_token":"NEVER_EXPOSE_THIS_VALUE","epoch":8}\n'
        self.hash = hashlib.sha256(self.mirror).hexdigest()
        self.pointer = {
            "schema": mod.POINTER_SCHEMA, "mode": "PASSIVE_COLD_COPY_NO_MODEL_EXECUTION",
            "active_epoch": 8, "archive_count": 3, "source_commit_sha": self.commit,
            "mirror_file_sha256": self.hash, "snapshot_sha256": "b" * 64
        }
        self.write_pointer()
        (self.root / "MIRROR.json").write_bytes(self.mirror)
        (self.root / "MIRROR.sha256").write_text(self.hash + "  MIRROR.json\n")
        (self.root / "snapshots" / (self.commit + ".json")).write_bytes(self.mirror)

    def write_pointer(self):
        (self.root / "LATEST.json").write_text(json.dumps(self.pointer))

    def test_valid_read_only_and_no_private_content(self):
        report = mod.verify(self.root)
        self.assertEqual(report["status"], "PASS_LOCAL_COLD_COPY_FILE_INTEGRITY_ONLY")
        self.assertEqual(report["observed"]["active_epoch"], 8)
        self.assertFalse(report["authority"]["offsite_backup_independence_verified"])
        self.assertNotIn("NEVER_EXPOSE", json.dumps(report))
        self.assertEqual((self.root / "MIRROR.json").read_bytes(), self.mirror)

    def test_detects_corrupt_mirror(self):
        (self.root / "MIRROR.json").write_bytes(b"changed")
        with self.assertRaisesRegex(mod.WitnessHold, "LATEST_MIRROR_SHA256_MISMATCH"):
            mod.verify(self.root)

    def test_detects_bad_sidecar(self):
        (self.root / "MIRROR.sha256").write_text("0" * 64 + "  MIRROR.json\n")
        with self.assertRaisesRegex(mod.WitnessHold, "SIDECAR_SHA256_MISMATCH"):
            mod.verify(self.root)

    def test_detects_divergent_archived_snapshot(self):
        (self.root / "snapshots" / (self.commit + ".json")).write_bytes(b"divergent")
        with self.assertRaisesRegex(mod.WitnessHold, "ARCHIVED_SNAPSHOT_NOT_BYTE_IDENTICAL"):
            mod.verify(self.root)

    def test_rejects_path_traversal_commit(self):
        self.pointer["source_commit_sha"] = "../../sensitive"
        self.write_pointer()
        with self.assertRaisesRegex(mod.WitnessHold, "SOURCE_COMMIT_SHA_HOLD"):
            mod.verify(self.root)

    def test_rejects_promotion_mode(self):
        self.pointer["mode"] = "AUTO_RESTORE"
        self.write_pointer()
        with self.assertRaisesRegex(mod.WitnessHold, "COLD_COPY_MODE_HOLD"):
            mod.verify(self.root)

    def test_rejects_missing_snapshot(self):
        (self.root / "snapshots" / (self.commit + ".json")).unlink()
        with self.assertRaisesRegex(mod.WitnessHold, "MISSING_OR_SYMLINK_COLD_FILE_HOLD"):
            mod.verify(self.root)


if __name__ == "__main__":
    unittest.main()
