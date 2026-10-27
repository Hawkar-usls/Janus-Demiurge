"""Synthetic-only private checkpoint journal and ledger regression."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import janus_hrain_private_checkpoint_ledger as ledger


def state(n=2):
    nodes = {f"n{i}": {"data": {"role": "same"}, "energy": 0.5} for i in range(n)}
    edges = {"n0->n1": {"weight": 1.0, "direction": "directed"}}
    return (json.dumps({"nodes": nodes, "edges": edges, "tick": n}, indent=2) + "\n").encode()


class CheckpointJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "All Star"
        (self.root / "raw_logs").mkdir(parents=True)
        self.backups = self.root / "artifacts" / "audits" / "private_graph_backups"
        self.backups.mkdir(parents=True)
        self.source = self.root / "raw_logs" / "hrain_graph_state.json"
        self.original = state()
        self.source.write_bytes(self.original)

    def test_check_only_is_nonmutating(self):
        first = ledger.checkpoint(self.root)
        self.assertEqual(first["status"], "CHECK_ONLY_NO_CHECKPOINT")
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_exact_verified_checkpoint_and_idempotence(self):
        created = ledger.checkpoint(self.root, create=True)
        self.assertEqual(created["status"], "OWNER_PRIVATE_CHECKPOINT_VERIFIED")
        self.assertEqual(created["originalNodes"], 2)
        self.assertEqual(created["originalEdges"], 1)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(ledger.checkpoint(self.root)["entries"], 1)
        again = ledger.checkpoint(self.root, create=True)
        self.assertEqual(again["status"], "UNCHANGED_ALREADY_CHECKPOINTED")
        self.assertEqual(again["entries"], 1)
        self.assertFalse(created["productionUseAuthorized"])

    def test_new_state_appends_chain_and_preserves_prior_archive(self):
        first = ledger.checkpoint(self.root, create=True)
        old_archive = self.backups / ("hrain-checkpoint-" + first["sourceSha256"] + ".json")
        old = old_archive.read_bytes()
        self.source.write_bytes(state(3))
        second = ledger.checkpoint(self.root, create=True)
        self.assertEqual(second["entries"], 2)
        self.assertEqual(old_archive.read_bytes(), old)
        records = ledger.read_ledger(self.backups / "hrain-checkpoint-ledger.jsonl", self.backups)
        self.assertEqual(records[1]["prevEntrySha256"], records[0]["entrySha256"])

    def test_tampering_and_torn_write_fail_closed(self):
        ledger.checkpoint(self.root, create=True)
        log = self.backups / "hrain-checkpoint-ledger.jsonl"
        old = log.read_bytes()
        log.write_bytes(old[:-1])
        with self.assertRaisesRegex(ValueError, "TORN_WRITE_HOLD"):
            ledger.checkpoint(self.root)
        log.write_bytes(old)
        archive = next(self.backups.glob("hrain-checkpoint-*.json"))
        archive.write_bytes(archive.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "ARCHIVE_TAMPERED_HOLD"):
            ledger.checkpoint(self.root)

    def test_bad_root_and_stale_lock_block_creation(self):
        with self.assertRaisesRegex(ValueError, "ROOT_ONLY"):
            ledger.checkpoint(pathlib.Path(self.tmp.name))
        lock = self.backups / "hrain-checkpoint-ledger.lock"
        lock.write_text("other writer")
        with self.assertRaises(FileExistsError):
            ledger.checkpoint(self.root, create=True)
        self.assertEqual(lock.read_text(), "other writer")
        self.assertEqual(self.source.read_bytes(), self.original)

if __name__ == "__main__":
    unittest.main()
