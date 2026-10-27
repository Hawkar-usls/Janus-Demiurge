"""Synthetic fail-closed regression for HRAiN runtime compressor.

Never import private owner graph snapshots or execute autonomous loops.
"""
import ast
import copy
import pathlib
import unittest

from hrain_graph_engine import HrainGraphEngine


class HrainRuntimeCompressionHold(unittest.TestCase):
    def make_graph(self):
        g = HrainGraphEngine({
            "compression_interval": 1,
            "energy_decay": 1.0,
            "edge_decay": 1.0,
            "energy_flow_rate": 0.0,
            "exploration_prob": 0.0,
            "similarity_threshold": 2.0,
            "node_energy_threshold": 0.0,
            "max_nodes": 200,
        })
        g.nodes = {
            "a": {"id": "a", "type": "t", "data": {"agent_id": "same"}, "energy": 0.2, "last_used": 0, "cluster": None},
            "b": {"id": "b", "type": "t", "data": {"agent_id": "same"}, "energy": 0.2, "last_used": 0, "cluster": None},
            "c": {"id": "c", "type": "t", "data": {"agent_id": "other"}, "energy": 0.2, "last_used": 0, "cluster": None},
            "d": {"id": "d", "type": "t", "data": {"agent_id": "other"}, "energy": 0.2, "last_used": 0, "cluster": None},
            "outside": {"id": "outside", "type": "t", "data": {}, "energy": 0.2, "last_used": 0, "cluster": None},
        }
        def e(src, dst, weight):
            g.edges[f"{src}->{dst}"] = {"weight": weight, "direction": "directed", "last_traversal": 0}
        e("a", "b", 2.0)              # internal edge
        e("b", "a", 2.5)              # reverse direction is distinct
        e("outside", "a", 3.0)        # incoming to cluster
        e("b", "outside", 4.0)        # outgoing from cluster
        e("a", "c", 5.0)              # cross-cluster edge
        e("c", "d", 6.0)              # second cluster
        e("d", "c", 6.5)
        e("d", "d", 7.0)              # self-loop
        return g

    def test_direct_call_preserves_every_original_byte_representable_field(self):
        g = self.make_graph()
        g.pending_diffs = [{"op": "before", "payload": {"a": 1}, "tick": 0}]
        before = copy.deepcopy(vars(g))
        result = g.compress_clusters()
        self.assertEqual(vars(g), before)
        self.assertEqual(result["status"], "HOLD_LEGACY_DESTRUCTIVE_COMPRESSION")
        self.assertFalse(result["production_use_authorized"])
        self.assertEqual(result["source_edges"], 8)
        self.assertEqual(result["source_nodes"], 5)

    def test_periodic_update_does_not_delete_existing_nodes_or_edges(self):
        g = self.make_graph()
        original_nodes = copy.deepcopy(g.nodes)
        original_edges = copy.deepcopy(g.edges)
        diff = g.update([])
        self.assertEqual(g.tick, 1)
        self.assertEqual(diff, [])
        self.assertEqual(g.nodes, original_nodes)
        self.assertEqual(g.edges, original_edges)

    def test_repeated_compression_no_data_loss(self):
        g = self.make_graph()
        original = copy.deepcopy(g.get_full_state())
        for _ in range(10):
            g.compress_clusters()
        self.assertEqual(g.get_full_state(), original)

    def test_ambiguous_and_dangling_graph_ids_remain_untouched_on_hold(self):
        g = self.make_graph()
        g.nodes["ambiguous->id"] = {"data": {"role": "synthetic"}}
        g.edges["ghost->ambiguous->id"] = {"weight": 1.2, "direction": "directed"}
        before = copy.deepcopy(vars(g))
        result = g.compress_clusters()
        self.assertFalse(result["production_use_authorized"])
        self.assertEqual(vars(g), before)

    def test_no_mutating_calls_inside_runtime_entrypoint(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "hrain_graph_engine.py"
        module = ast.parse(path.read_text(encoding="utf8"))
        cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "HrainGraphEngine")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "compress_clusters")
        calls = {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(calls.intersection({"remove_node", "add_node", "add_edge", "clear", "pop", "update"}))


if __name__ == "__main__":
    unittest.main()
