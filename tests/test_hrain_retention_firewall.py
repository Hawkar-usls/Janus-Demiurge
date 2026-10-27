"""Synthetic HRAiN retention firewall: no owner-private input."""
import copy
import unittest
from hrain_graph_engine import HrainGraphEngine


def graph(limit=5):
    g = HrainGraphEngine({
        "max_nodes": limit, "energy_decay": 0.5, "edge_decay": 0.1,
        "node_energy_threshold": 0.1, "energy_flow_rate": 0.0,
        "exploration_prob": 0.0, "similarity_threshold": 2.0,
        "compression_interval": 1,
    })
    for nid in ("a", "b", "c"):
        g.nodes[nid] = {
            "id": nid, "type": "synthetic", "data": {"role": nid},
            "energy": 0.02, "last_used": 0, "cluster": None
        }
    for src, dst, weight in (
        ("a", "b", 0.01), ("b", "a", 0.02), ("c", "a", 0.03),
        ("a", "c", 0.01), ("c", "c", 0.004),
    ):
        g.edges[f"{src}->{dst}"] = {
            "weight": weight, "direction": "directed", "last_traversal": 0,
            "custom": {"evidence": f"{src}:{dst}"}
        }
    return g


class RetentionFirewall(unittest.TestCase):
    def test_manual_remove_node_fails_closed_without_diff(self):
        g = graph()
        before = copy.deepcopy((g.nodes, g.edges, g.pending_diffs))
        self.assertIs(g.remove_node("a"), False)
        self.assertIs(g.remove_node("missing"), False)
        self.assertEqual((g.nodes, g.edges, g.pending_diffs), before)
        self.assertEqual(g.retention_holds["remove_node"], 1)

    def test_decay_never_erases_node_or_relation(self):
        g = graph()
        original_keys = set(g.edges)
        original_nodes = copy.deepcopy(g.nodes)
        directions = {k: (v["direction"], copy.deepcopy(v["custom"])) for k, v in g.edges.items()}
        for _ in range(12):
            g.decay_edges()
            g.decay_nodes()
            g.temporal_decay()
        self.assertEqual(set(g.edges), original_keys)
        self.assertEqual(set(g.nodes), set(original_nodes))
        self.assertEqual(
            {k: (v["direction"], v["custom"]) for k, v in g.edges.items()},
            directions
        )
        self.assertGreater(g.retention_holds["decay_nodes"], 0)
        self.assertGreater(g.retention_holds["decay_edges"], 0)
        self.assertFalse(any(d["op"] in ("node_remove", "edge_remove") for d in g.pending_diffs))

    def test_max_nodes_rejects_before_any_graph_or_tick_mutation(self):
        g = graph(limit=3)
        before = copy.deepcopy(g.get_full_state())
        diffs = copy.deepcopy(g.pending_diffs)
        with self.assertRaisesRegex(MemoryError, "HRAIN_EVENT_BATCH_CAPACITY_HOLD"):
            g.update([{"type": "synthetic", "data": {"x": 1}}])
        self.assertEqual(g.get_full_state(), before)
        self.assertEqual(g.pending_diffs, diffs)
        with self.assertRaisesRegex(MemoryError, "HRAIN_CAPACITY_REACHED_NO_EVICTION"):
            g.add_node("synthetic", {"x": 1})
        self.assertEqual(g.get_full_state(), before)

    def test_batch_limit_preflight_is_atomic_for_all_events(self):
        g = graph(limit=4)
        before = copy.deepcopy(g.get_full_state())
        with self.assertRaisesRegex(MemoryError, "HRAIN_EVENT_BATCH_CAPACITY_HOLD"):
            g.update([{"type": "x"}, {"type": "y"}])
        self.assertEqual(g.get_full_state(), before)

    def test_scheduled_tick_retains_links_when_compression_and_decay_fire(self):
        g = graph()
        original_nodes = set(g.nodes)
        original_edges = set(g.edges)
        g.update([])
        self.assertEqual(set(g.nodes), original_nodes)
        self.assertEqual(set(g.edges), original_edges)
        self.assertEqual(g.tick, 1)

    def test_growth_still_operates_within_capacity(self):
        g = graph(limit=4)
        old_nodes = set(g.nodes)
        g.update([{"type": "added", "data": {"key": "synthetic"}}])
        self.assertEqual(len(g.nodes), 4)
        self.assertTrue(old_nodes.issubset(g.nodes))
        self.assertGreater(len(g.edges), 5)

    def test_invalid_edge_id_remains_untouched_in_retention_methods(self):
        g = graph()
        g.edges["unparseable"] = {"weight": 0.001, "direction": "invalid"}
        before = copy.deepcopy(g.edges)
        g.remove_node("a")
        g.decay_edges()
        self.assertEqual(set(g.edges), set(before))
        self.assertEqual(g.edges["unparseable"]["direction"], "invalid")

if __name__ == "__main__":
    unittest.main()
