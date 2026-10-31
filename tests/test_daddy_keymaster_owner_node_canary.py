"""Owner-node archive replay and sealed canary tests, standard library only."""
from __future__ import annotations
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from daddy_keymaster.broker import canonical, sha
from daddy_keymaster.git_cas_queue import empty, enqueue, claim, checkpoint, complete, ZERO
from daddy_keymaster.queue_rotation import _sign, HEAD_SCHEMA, ARCHIVE_SCHEMA, MARKER_SCHEMA
from daddy_keymaster.owner_node import verify_snapshot, owner_canary

SOURCE = hashlib.sha256(b"owner-synthetic-source").hexdigest()
HEAD = "b" * 40
NOW = "2026-10-31T10:00:00Z"


class OwnerNodeCanaryTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        snapshots = self.root / "snapshots"
        snapshots.mkdir()
        active = empty()
        archived = enqueue(empty(), "ci-contract-test-1", "contract_test", SOURCE)
        archived, token = claim(archived, "owner-test-worker", ["contract_test"], 1, now=NOW)
        archived = checkpoint(archived, token, SOURCE, now=NOW)
        archived = complete(archived, token, SOURCE, now=NOW)
        segment = _sign(ARCHIVE_SCHEMA, {
            "serial":1, "source_ref": "a"*40,
            "previous_segment_digest_sha256":ZERO, "queue":archived,
            "queue_tip_sha256":archived["tip_sha256"],
        })
        head = _sign(HEAD_SCHEMA, {
            "serial":1, "segment_path":"state/archive_segments/00000001.json",
            "segment_digest_sha256":segment["receipt_sha256"],
            "previous_head_digest_sha256":ZERO,
        })
        marker = _sign(MARKER_SCHEMA, {
            "source_sha256":SOURCE, "segment":1,
            "segment_digest_sha256":segment["receipt_sha256"],
            "task_ids":["ci-contract-test-1"], "terminal_states":["COMPLETE"],
        })
        self.files = {
            "state/relay_queue.json": active,
            "state/relay_archive_head.json": head,
            "state/archive_segments/00000001.json": segment,
            f"state/processed_sources/{SOURCE}.json": marker,
        }
        self.zip_path=snapshots/(HEAD+".zip")
        self.receipt_path=snapshots/(HEAD+".receipt.json")
        self.write_zip(self.files)

    def write_zip(self, files):
        with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, obj in files.items():
                z.writestr(name, canonical(obj))
        receipt = {
            "schema":"janus.daddy_keymaster.physical_backup_receipt.v1",
            "head_sha":HEAD,
            "zip_sha256":hashlib.sha256(self.zip_path.read_bytes()).hexdigest(),
            "queue_epoch":0, "queue_tip_sha256":ZERO,
        }
        self.receipt_path.write_bytes(canonical(receipt)+b"\n")

    def test_independent_snapshot_replay_pass(self):
        proof=verify_snapshot.validate(self.zip_path, self.receipt_path)
        self.assertEqual(proof["status"],"JANUS_INDEPENDENT_LOCAL_REPLAY_PASS")
        self.assertEqual(proof["archive_segments"],1)
        self.assertEqual(proof["queue_epoch"],0)

    def test_corrupt_copy_is_rejected_without_touching_original(self):
        original=self.zip_path.read_bytes()
        self.zip_path.write_bytes(original[:18]+bytes([original[18]^1])+original[19:])
        with self.assertRaisesRegex(ValueError,"ZIP_SHA_MISMATCH"):
            verify_snapshot.validate(self.zip_path, self.receipt_path)

    def test_tampered_archive_with_updated_zip_digest_still_rejects(self):
        files=json.loads(json.dumps(self.files))
        files["state/archive_segments/00000001.json"]["queue"]["tasks"]["ci-contract-test-1"]["state"]="HOLD"
        self.write_zip(files)
        with self.assertRaisesRegex(ValueError,"RECEIPT_TAMPER|ARCHIVE_|TASK_PROJECTION"):
            verify_snapshot.validate(self.zip_path, self.receipt_path)

    def test_no_unknown_zip_paths(self):
        with zipfile.ZipFile(self.zip_path,"a") as z:
            z.writestr("../evil.txt","bad")
        receipt=json.loads(self.receipt_path.read_text())
        receipt["zip_sha256"]=hashlib.sha256(self.zip_path.read_bytes()).hexdigest()
        self.receipt_path.write_bytes(canonical(receipt)+b"\n")
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_ZIP_PATH"):
            verify_snapshot.validate(self.zip_path,self.receipt_path)

    def test_local_canary_runs_once_without_side_effects(self):
        shutil.copyfile(Path(verify_snapshot.__file__), self.root/"verify_snapshot.py")
        with patch.object(owner_canary,"ROOT",self.root), redirect_stdout(StringIO()) as captured:
            owner_canary.main()
        proof_path=self.root/"node_receipts"/(HEAD+".json")
        self.assertTrue(proof_path.exists())
        proof=json.loads(proof_path.read_text())
        self.assertEqual(proof["status"],"OWNER_NODE_BOUNDED_CANARY_PASS")
        self.assertEqual(proof["remote_dispatches"],0)
        self.assertEqual(proof["champion_promotions"],0)
        self.assertEqual(proof["owner_node_availability"],"OBSERVED_ONCE_NOT_24_7")
        with patch.object(owner_canary,"ROOT",self.root),redirect_stdout(StringIO()) as repeated:
            owner_canary.main()
        self.assertIn("ALREADY_VERIFIED",repeated.getvalue())
        self.assertEqual(json.loads(proof_path.read_text()),proof)

    def test_canary_detects_local_receipt_tamper(self):
        shutil.copyfile(Path(verify_snapshot.__file__), self.root/"verify_snapshot.py")
        with patch.object(owner_canary,"ROOT",self.root),redirect_stdout(StringIO()):
            owner_canary.main()
        p=self.root/"node_receipts"/(HEAD+".json")
        d=json.loads(p.read_text())
        d["model_promotions"]=8
        p.write_bytes(canonical(d)+b"\n")
        with patch.object(owner_canary,"ROOT",self.root):
            with self.assertRaisesRegex(ValueError,"EXISTING_PROOF_TAMPERED"):
                owner_canary.main()


if __name__=="__main__":
    unittest.main()
