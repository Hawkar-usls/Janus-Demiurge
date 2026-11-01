"""End-to-end reconstruction: old organ graph -> safe modern memory query -> Nexus ABI."""
import copy
import hashlib
import json
import unittest
from restored.legacy_nexus_conductor import build_plan, probation_run
from restored.legacy_core_graph_query_port import (
    GraphProjectionHold, LegacyGraphQueryPort, project_readonly_legacy_graph,
    run_legacy_graph_query
)


def source_fixture():
    return {
        "schema": "janus.legacy_core.module_relationships_non_authoritative.v1",
        "status": "ARCHIVAL_RELATIONSHIP_PROJECTION_ONLY",
        "projection": {
            "node_count": 3, "relation_count": 3,
            "relations_with_both_endpoints_declared": 2,
            "relations_with_unresolved_endpoint": 1,
            "nodes": [{"id": "cortex", "kind": "cognition"},
                      {"id": "memory", "kind": "memory"},
                      {"id": "hero", "kind": "system"}],
            "historical_relations": [
                {"from": "cortex", "to": "memory", "historical_relation": "reads",
                 "endpoints_declared_in_legacy_nodes": True},
                {"from": "memory", "to": "hero", "historical_relation": "context",
                 "endpoints_declared_in_legacy_nodes": True},
                {"from": "hero", "to": "external_service", "historical_relation": "calls",
                 "endpoints_declared_in_legacy_nodes": False},
            ],
        }
    }


class GraphOrganIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_graph_normalized_for_real_modern_query(self):
        source = source_fixture()
        before = copy.deepcopy(source)
        g = project_readonly_legacy_graph(source)
        self.assertEqual(len(g["nodes"]), 3)
        self.assertEqual(len(g["edges"]), 2)
        self.assertEqual(g["excluded_unresolved_relations"], 1)
        self.assertEqual(source, before)

    async def test_actual_modern_readonly_organ_runs_through_nexus(self):
        src = source_fixture()
        port = LegacyGraphQueryPort(src, "cortex", "hero")
        plan = build_plan([{
            "id": "legacy_graph_query", "mode": "PLUGIN",
            "source_sha256": hashlib.sha256(b"audited modern organ").hexdigest(),
            "priority": 2, "dependencies": [],
            "capabilities": ["READ_GRAPH"], "reviewed": True, "synthetic_only": True
        }], intent="graph query")
        result = await probation_run(
            plan, target="legacy_graph_query",
            handlers={"legacy_graph_query": run_legacy_graph_query},
            core_port=port, operator_approved=True
        )
        self.assertEqual(result["outcomes"]["legacy_graph_query"],
                         "PROBATION_CALLBACK_COMPLETED")
        self.assertEqual(port.receipt["path"], ["cortex", "memory", "hero"])
        self.assertEqual(port.receipt["excluded_unresolved_relations"], 1)
        self.assertFalse(port.receipt["mutation_authority"])
        self.assertFalse(result["authority"]["production_service_started"])

    async def test_unresolved_not_fabricated_as_live_module(self):
        port = LegacyGraphQueryPort(source_fixture(), "cortex", "hero")
        with self.assertRaisesRegex(GraphProjectionHold, "QUERY_END_NOT_A_DECLARED_NODE"):
            LegacyGraphQueryPort(source_fixture(), "cortex", "external_service")
        await run_legacy_graph_query(port)
        self.assertNotIn("external_service", port.receipt["path"])

    async def test_forged_flag_and_counts_fail_closed(self):
        src = source_fixture()
        src["projection"]["historical_relations"][2]["endpoints_declared_in_legacy_nodes"] = True
        with self.assertRaisesRegex(GraphProjectionHold, "FLAG_MISMATCH"):
            project_readonly_legacy_graph(src)
        src = source_fixture()
        src["projection"]["relation_count"] = 99
        with self.assertRaisesRegex(GraphProjectionHold, "SOURCE_COUNT_CONTRACT"):
            project_readonly_legacy_graph(src)

    async def test_duplicate_id_and_malicious_name_hold(self):
        src = source_fixture()
        src["projection"]["nodes"][2]["id"] = "cortex"
        with self.assertRaisesRegex(GraphProjectionHold, "DUPLICATE"):
            project_readonly_legacy_graph(src)
        src = source_fixture()
        src["projection"]["historical_relations"][0]["to"] = "../../etc"
        with self.assertRaisesRegex(GraphProjectionHold, "RELATION_ID"):
            project_readonly_legacy_graph(src)

    async def test_no_implicit_handler_when_no_approval(self):
        src = source_fixture()
        port = LegacyGraphQueryPort(src, "cortex", "hero")
        plan = build_plan([{
            "id": "legacy_graph_query", "mode": "PLUGIN",
            "source_sha256": "a" * 64, "priority": 10,
            "dependencies": [], "capabilities": ["READ_GRAPH"],
            "reviewed": True, "synthetic_only": True
        }])
        with self.assertRaises(PermissionError):
            await probation_run(plan, target="legacy_graph_query",
                               handlers={"legacy_graph_query": run_legacy_graph_query},
                               core_port=port)
        self.assertIsNone(port.receipt)


if __name__ == "__main__":
    unittest.main()
