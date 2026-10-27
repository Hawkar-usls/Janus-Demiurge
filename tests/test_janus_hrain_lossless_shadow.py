"""JANUS HRAiN private reversible SHADOW; synthetic fixtures only."""
import copy
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import janus_hrain_lossless_shadow as shadow


def sample():
    nodes = {
        "a": {"data": {"role": "same", "text": "synthetic a"}, "energy": 1.2},
        "b": {"data": {"role": "same", "text": "synthetic b"}, "energy": 0.9},
        "c": {"data": {"role": "other", "text": "synthetic c"}, "energy": 0.4},
        "d": {"data": {"role": "other", "text": "synthetic d"}, "energy": 0.4},
        "outside": {"data": {"role": "outside", "text": "synthetic outside"}, "energy": 0.2},
    }
    edges = {
        "a->b": {"weight": 1.1, "direction": "bidir"},
        "b->a": {"weight": 1.2, "direction": "reverse"},
        "outside->a": {"weight": 2.0, "direction": "in"},
        "a->outside": {"weight": 2.2, "direction": "out"},
        "b->c": {"weight": 3.0, "direction": "inter"},
        "c->d": {"weight": 4.0, "direction": "internal"},
        "d->d": {"weight": 4.1, "direction": "self"},
        "outside->outside": {"weight": 4.2, "direction": "self"},
    }
    record = {"nodes": nodes, "edges": edges, "tick": 200, "node_counter": 31, "custom": {"p": [1, None, True]}}
    return (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "  \n").encode("utf-8")


class ShadowContract(unittest.TestCase):
    def test_exact_byte_round_trip_with_two_clusters_crosslinks_selfloops(self):
        raw = sample()
        packet = shadow.make_shadow(raw)
        self.assertEqual(shadow.expanded_bytes(packet), raw)
        self.assertEqual(packet["sourceSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(packet["compactView"]["originalEdgeCount"], 8)
        self.assertEqual(packet["compactView"]["originalNodesRepresented"], 5)
        self.assertEqual(sum(x["originalEdgeMultiplicity"] for x in packet["compactView"]["relations"]), 8)
        self.assertTrue(packet["losslessness"]["rawSourceBytesRetained"])
        self.assertFalse(packet["compactView"]["sourceGraphMutationAllowed"])
        self.assertEqual(packet["status"], "OWNER_PRIVATE_REVERSIBLE_SHADOW_NOT_PRODUCTION")

    def test_tampered_archive_and_projection_rejected(self):
        raw = sample()
        base = shadow.make_shadow(raw)
        a = copy.deepcopy(base)
        a["archive"]["payload"] = a["archive"]["payload"][:-4] + "0000"
        with self.assertRaises(ValueError):
            shadow.expanded_bytes(a)
        b = copy.deepcopy(base)
        b["compactView"]["relations"][0]["originalEdgeMultiplicity"] = 999999
        with self.assertRaisesRegex(ValueError, "SHADOW_PROJECTED_GRAPH_TAMPERED_HOLD"):
            shadow.expanded_bytes(b)
        c = copy.deepcopy(base)
        c["sourceSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHADOW_SHA256_MISMATCH_HOLD"):
            shadow.expanded_bytes(c)

    def test_invalid_ids_and_dangling_edges_fail_closed(self):
        x = json.loads(sample())
        x["edges"]["ghost->a"] = {"weight": 1}
        with self.assertRaisesRegex(ValueError, "DANGLING_SOURCE_EDGES_HOLD"):
            shadow.make_shadow(json.dumps(x).encode())
        del x["edges"]["ghost->a"]
        x["edges"]["a->b->c"] = {"weight": 1}
        with self.assertRaisesRegex(ValueError, "UNSAFE_EDGE_ID_HOLD"):
            shadow.make_shadow(json.dumps(x).encode())

    def test_strict_small_byte_bound(self):
        with mock.patch.object(shadow, "MAX_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_BYTE_BOUND_HOLD"):
                shadow.make_shadow(sample())

    def test_private_output_never_overwrites_source_and_verifies_against_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            source = root / "raw_logs" / "hrain_graph_state.json"
            source.parent.mkdir()
            audit = root / "artifacts" / "audits"
            audit.mkdir(parents=True)
            original = sample()
            source.write_bytes(original)
            out = audit / "synthetic_shadow.json"
            with mock.patch.object(sys, "argv", ["shadow", "--snapshot", str(source), "--shadow", str(out)]):
                with redirect_stdout(io.StringIO()) as report:
                    shadow.main()
            self.assertNotIn("synthetic a", report.getvalue())
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(out.is_file())
            with mock.patch.object(sys, "argv", ["shadow", "--snapshot", str(source), "--shadow", str(out), "--verify-only"]):
                with redirect_stdout(io.StringIO()) as verified:
                    shadow.main()
            self.assertIn("VERIFIED_NO_MUTATIONS", verified.getvalue())
            with mock.patch.object(sys, "argv", ["shadow", "--snapshot", str(source), "--shadow", str(out)]):
                with self.assertRaises(FileExistsError):
                    shadow.main()
            source.write_bytes(original + b" ")
            with mock.patch.object(sys, "argv", ["shadow", "--snapshot", str(source), "--shadow", str(out), "--verify-only"]):
                with self.assertRaisesRegex(ValueError, "SHADOW_SOURCE_MISMATCH_HOLD"):
                    shadow.main()

if __name__ == "__main__":
    unittest.main()
