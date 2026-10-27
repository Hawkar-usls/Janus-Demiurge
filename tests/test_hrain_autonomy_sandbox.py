"""Owner All Star HRAiN sandbox autonomy; synthetic-only regression suite."""
import copy
import random
import unittest
from unittest import mock
from hrain_graph_engine import HrainGraphEngine
from restored.hrain_autonomy import HrainAutonomy


class HrainAutonomySandbox(unittest.TestCase):
    def graph(self, max_nodes=40):
        return HrainGraphEngine({
            "max_nodes": max_nodes, "edge_decay": 1.0,
            "energy_decay": 1.0, "energy_flow_rate": 0.0,
            "exploration_prob": 0.0, "similarity_threshold": 2.0,
            "node_energy_threshold": 0.0, "compression_interval": 1
        })

    def test_default_disarmed_and_mutating_methods_blocked(self):
        graph = self.graph()
        a = HrainAutonomy(graph)
        before = copy.deepcopy(graph.get_full_state())
        state, event = a.cycle_once()
        self.assertEqual(event["kind"], "HOLD_NOT_ACTIVATED")
        for call in (
            lambda: a.create_node("ally", "test", "test"),
            a.ensure_foundation,
            a.run_dynamics,
            lambda: a.upsert_device("test", {}),
            lambda: a._maxwell(None),
        ):
            with self.assertRaisesRegex(PermissionError, "RESEARCH_ONLY_HOLD"):
                call()
        with self.assertRaisesRegex(PermissionError, "RESEARCH_ONLY_HOLD"):
            a.enable_synthetic_sandbox()
        self.assertEqual(graph.get_full_state(), before)

    def test_loaded_or_dirty_graph_cannot_be_armed(self):
        graph = self.graph()
        graph.nodes["private_state_sentinel"] = {"data": {}}
        a = HrainAutonomy(graph, synthetic_only=True)
        with self.assertRaisesRegex(PermissionError, "RESEARCH_ONLY_HOLD"):
            a.enable_synthetic_sandbox()
        self.assertIn("private_state_sentinel", graph.nodes)

    def test_synthetic_growth_and_links_without_pruning(self):
        random.seed(13)
        graph = self.graph()
        a = HrainAutonomy(graph, synthetic_only=True)
        a.enable_synthetic_sandbox()
        before = copy.deepcopy(graph.get_full_state())
        public, first = a.cycle_once()
        self.assertEqual(first["kind"], "foundation")
        self.assertEqual(len(graph.nodes), 4)
        self.assertEqual(a.runtime["nodes_pruned"], 0)
        self.assertFalse(any(e["op"].endswith("_remove") for e in graph.pending_diffs))
        with mock.patch("restored.hrain_autonomy.random.random", return_value=0.99):
            state, event = a.cycle_once()
        self.assertEqual(event["kind"], "growth")
        self.assertEqual(len(graph.nodes), 5)
        self.assertGreaterEqual(len(graph.edges), 1)
        self.assertEqual(a.runtime["nodes_pruned"], 0)
        self.assertNotEqual(graph.get_full_state(), before)

    def test_capacity_hold_is_non_mutating(self):
        graph = self.graph(max_nodes=4)
        a = HrainAutonomy(graph, synthetic_only=True)
        a.enable_synthetic_sandbox()
        a.cycle_once()
        before = copy.deepcopy(graph.get_full_state())
        state, event = a.cycle_once()
        self.assertEqual(event["kind"], "CAPACITY_HOLD")
        self.assertEqual(graph.get_full_state(), before)
        self.assertEqual(a.runtime["nodes_pruned"], 0)

    def test_maxwell_never_claims_prune(self):
        graph = self.graph(max_nodes=40)
        a = HrainAutonomy(graph, synthetic_only=True)
        a.enable_synthetic_sandbox()
        for i in range(16):
            graph.nodes[f"n{i}"] = {
                "id": f"n{i}", "type": "ally", "energy": 0.01,
                "data": {"role": "idea", "parentId": None, "label": "synthetic"}, "last_used": 0
            }
        before = copy.deepcopy((graph.nodes, graph.edges))
        result = a._maxwell(None)
        self.assertIn("HOLD", result)
        self.assertEqual(a.runtime["daemon_mode"], "retention_hold")
        self.assertEqual(a.runtime["nodes_pruned"], 0)
        self.assertEqual((graph.nodes, graph.edges), before)

if __name__ == "__main__":
    unittest.main()
