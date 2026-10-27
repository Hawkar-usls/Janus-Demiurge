"""HRAiN transaction firewall: isolated fixtures, never owner graph."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from tools.janus_hrain_incremental_transaction import Hold, apply_transaction


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class IncrementalTransactionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "All Star"
        (self.root / "raw_logs").mkdir(parents=True)
        (self.root / "artifacts" / "audits" / "private_graph_backups").mkdir(parents=True)
        self.graph_file = self.root / "raw_logs" / "hrain_graph_state.json"
        self.sample = {
            "nodes": {
                "a": {"id": "a", "type": "intel", "data": {"label": "a", "provenance": {"evidence": 7}}, "energy": 0.1},
                "b": {"id": "b", "type": "intel", "data": {"label": "b"}, "energy": 0.2},
            },
            "edges": {
                "a->b": {"weight": 0.01, "direction": "directed", "meta": {"private": "never print"}},
                "b->a": {"weight": 0.03, "direction": "directed"},
                "a->a": {"weight": 0.07, "direction": "directed"},
            },
            "tick": 42, "node_counter": 7, "unknown": {"all_star_owner_field": True},
        }
        self.raw = (json.dumps(self.sample, indent=4) + "\n").encode()
        self.graph_file.write_bytes(self.raw)

    def req(self, operation, *, expected=None, request_id=None):
        return {
            "requestId": request_id or str(uuid.uuid4()),
            "expectedSha256": expected or sha(self.graph_file.read_bytes()),
            "operation": operation,
        }

    def test_new_node_preserves_every_historical_byte_in_backup_and_semantics(self):
        r = apply_transaction(self.root, self.req({"op": "add_node", "nodeType": "intel", "label": "safe"}))
        self.assertEqual(r["status"], "COMMITTED_INCREMENTAL_ONLY")
        data = json.loads(self.graph_file.read_bytes())
        self.assertEqual(data["edges"], self.sample["edges"])
        self.assertEqual(data["nodes"]["a"], self.sample["nodes"]["a"])
        self.assertEqual(data["unknown"], self.sample["unknown"])
        self.assertEqual(len(data["nodes"]), 3)
        self.assertEqual(data["node_counter"], 8)
        self.assertEqual(data["tick"], 43)
        archive = self.root / "artifacts" / "audits" / "private_graph_backups" / "incremental" / ("hrain-before-" + sha(self.raw) + ".json")
        self.assertEqual(archive.read_bytes(), self.raw)
        self.assertTrue((archive.parent / ("receipt-" + r["requestId"] + ".json")).exists())

    def test_update_label_preserves_other_fields_and_edges(self):
        r = apply_transaction(self.root, self.req({"op": "set_label", "nodeId": "a", "label": "revised"}))
        data = json.loads(self.graph_file.read_bytes())
        self.assertEqual(data["nodes"]["a"]["data"]["label"], "revised")
        self.assertEqual(data["nodes"]["a"]["data"]["provenance"], {"evidence": 7})
        self.assertEqual(data["edges"], self.sample["edges"])
        self.assertEqual(r["resultId"], "a")

    def test_add_directed_edge_keeps_both_directions_and_loops(self):
        self.graph_file.write_bytes((json.dumps({**self.sample, "edges": {"b->a": self.sample["edges"]["b->a"]}})+"\n").encode())
        apply_transaction(self.root, self.req({"op": "add_edge", "source": "a", "target": "b"}))
        data = json.loads(self.graph_file.read_bytes())
        self.assertIn("a->b", data["edges"])
        self.assertIn("b->a", data["edges"])
        self.assertEqual(data["edges"]["b->a"], self.sample["edges"]["b->a"])

    def test_conflict_and_replay_do_not_change_state(self):
        request = self.req({"op": "add_node", "nodeType": "intel", "label": "one"})
        apply_transaction(self.root, request)
        before = self.graph_file.read_bytes()
        with self.assertRaisesRegex(Hold, "STALE_REVISION_HOLD"):
            apply_transaction(self.root, request)
        self.assertEqual(self.graph_file.read_bytes(), before)

    def test_rejects_delete_replace_and_unsupported_payloads(self):
        for op in (
            {"op": "delete_node", "nodeId": "a"},
            {"op": "replace_graph", "nodes": {}, "edges": {}},
            {"op": "add_edge", "source": "absent", "target": "b"},
            {"op": "set_label", "nodeId": "a", "label": ""},
            {"op": "add_node", "nodeType": "intel", "label": "x", "id": "a"},
            {"op": "add_node", "nodeType": "intel", "label": "x", "energy": 7},
            {"op": "add_edge", "source": "a", "target": "b"},
        ):
            with self.subTest(op=op):
                with self.assertRaises(Hold):
                    apply_transaction(self.root, self.req(op))
                self.assertEqual(self.graph_file.read_bytes(), self.raw)

    def test_capacity_fail_is_atomic(self):
        with self.assertRaisesRegex(Hold, "GRAPH_CAPACITY_HOLD"):
            apply_transaction(self.root, self.req({"op": "add_node", "nodeType": "intel", "label": "x"}), max_nodes=2)
        self.assertEqual(self.graph_file.read_bytes(), self.raw)
        self.assertFalse((self.root / "artifacts" / "audits" / "private_graph_backups" / "incremental").exists())

    def test_corrupt_graph_refuses_any_transaction(self):
        for raw in (b"{", b"", b'{"nodes":{},"edges":{},"tick":0,"node_counter":true}', b'{"nodes":{},"edges":{},"tick":NaN,"node_counter":1}'):
            self.graph_file.write_bytes(raw)
            with self.subTest(raw=raw[:15]):
                with self.assertRaises(Hold):
                    apply_transaction(self.root, self.req({"op": "add_node", "nodeType": "intel", "label": "x"}))
                self.assertEqual(self.graph_file.read_bytes(), raw)

    def test_stale_lock_and_duplicate_request_hold(self):
        store = self.root / "artifacts" / "audits" / "private_graph_backups" / "incremental"
        store.mkdir()
        (store / "transaction.lock").write_text("external writer", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            apply_transaction(self.root, self.req({"op": "add_node", "nodeType": "intel", "label": "x"}))
        self.assertEqual(self.graph_file.read_bytes(), self.raw)

    def test_old_private_archive_tamper_is_detected(self):
        req = self.req({"op": "set_label", "nodeId": "a", "label": "changed"})
        r = apply_transaction(self.root, req)
        archive = self.root / "artifacts" / "audits" / "private_graph_backups" / "incremental" / ("hrain-before-" + sha(self.raw) + ".json")
        archive.write_bytes(b"tampered")
        self.graph_file.write_bytes(self.raw)
        with self.assertRaisesRegex(Hold, "ARCHIVE_HASH_HOLD"):
            apply_transaction(self.root, self.req({"op": "set_label", "nodeId": "a", "label": "again"}))
        self.assertEqual(self.graph_file.read_bytes(), self.raw)

if __name__ == "__main__":
    unittest.main()
