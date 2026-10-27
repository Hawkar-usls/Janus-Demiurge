"""Synthetic adversarial regressions for cloud-only HRAiN safety gate."""
import pathlib
import shutil
import tempfile
import unittest

from tools.janus_hrain_unattended_integrity_gate import SOURCES, assess

ROOT = pathlib.Path(__file__).resolve().parents[1]


class UnattendedGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.copy = pathlib.Path(self.tmp.name)
        for relative in SOURCES.values():
            to = self.copy / relative
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, to)

    def change(self, name, original, replacement):
        file = self.copy / SOURCES[name]
        source = file.read_text(encoding="utf-8")
        self.assertIn(original, source)
        file.write_text(source.replace(original, replacement, 1), encoding="utf-8")

    def test_current_public_sources_pass_while_real_memory_unread(self):
        result = assess(self.copy)
        self.assertEqual(result["status"], "PASS_PUBLIC_SOURCE_GATES")
        self.assertEqual(result["failed"], [])
        self.assertFalse(result["privateGraphInspected"])
        self.assertFalse(result["workingMemoryModified"])
        self.assertFalse(result["productionAutonomyAuthorized"])

    def test_detect_destructive_compression_regression(self):
        self.change(
            "graph",
            "    def compress_clusters(self):",
            '    def compress_clusters(self):\n        self.remove_node("a")',
        )
        result = assess(self.copy)
        self.assertIn("compression_hold", result["failed"])

    def test_detect_live_remove_node_regression(self):
        self.change("graph", "        return False", '        self.nodes.pop(node_id, None)\n        return True')
        result = assess(self.copy)
        self.assertIn("remove_node_hold", result["failed"])

    def test_detect_retention_deletion(self):
        self.change(
            "graph",
            '    def decay_edges(self):',
            '    def decay_edges(self):\n        self.edges.clear()',
        )
        self.assertIn("decay_edges_preserves_topology", assess(self.copy)["failed"])

    def test_detect_missing_capacity_hold(self):
        self.change("graph", "HRAIN_EVENT_BATCH_CAPACITY_HOLD", "CAPACITY_DISABLED")
        self.assertIn("capacity_atomic_hold", assess(self.copy)["failed"])

    def test_detect_synthetic_only_authority_regression(self):
        self.change(
            "autonomy",
            'if not self._synthetic_only or self.graph.nodes or self.graph.edges:',
            'if self.graph.nodes or self.graph.edges:',
        )
        self.assertIn("clean_synthetic_only_arm", assess(self.copy)["failed"])

    def test_checkpoint_must_remain_opt_in(self):
        self.change("checkpoint", '"--create"', '"--unattended-create"')
        self.assertIn("checkpoint_opt_in_only", assess(self.copy)["failed"])

    def test_server_full_overwrite_unblocked_is_fatal(self):
        self.change(
            "server",
            '    return web.json_response(\n        {',
            '    graph_engine.nodes = {}\n    return web.json_response(\n        {',
        )
        self.assertIn("server_wholesale_save_hold", assess(self.copy)["failed"])

    def test_server_status_change_is_detected(self):
        self.change("server", '        status=409,', '        status=200,')
        self.assertIn("server_wholesale_save_hold", assess(self.copy)["failed"])

    def test_server_ui_read_route_removal_fails_closed(self):
        self.change("server", "'/api/hrain/state'", "'/api/hrain/not-found'")
        self.assertIn("server_ui_read_route_retained", assess(self.copy)["failed"])

    def test_duplicate_handler_must_not_shadow_hold(self):
        path = self.copy / SOURCES["server"]
        with path.open("a", encoding="utf-8") as out:
            out.write("\\nasync def handle_save_state(request):\\n    return None\\n")
        self.assertIn("server_wholesale_save_hold", assess(self.copy)["failed"])

    def test_route_to_different_handler_is_rejected(self):
        self.change(
            "server",
            "web.post('/api/hrain/save', handle_save_state)",
            "web.post('/api/hrain/save', handle_janus_action)",
        )
        self.assertIn("server_ui_read_route_retained", assess(self.copy)["failed"])

    def test_missing_required_file_fails_closed(self):
        (self.copy / SOURCES["checkpoint"]).unlink()
        with self.assertRaisesRegex(ValueError, "SOURCE_MISSING_OR_UNSAFE"):
            assess(self.copy)

if __name__ == "__main__":
    unittest.main()
