"""Long-run JANUS synthetic-only autonomy stress and fault-injection checks."""
import pathlib
import tempfile
import unittest
from unittest import mock

from hrain_graph_engine import HrainGraphEngine
from tools.janus_hrain_synthetic_endurance import simulate, main


class EnduranceTests(unittest.TestCase):
    def test_deterministic_endurance_reaches_capacity_without_loss(self):
        result = simulate(cycles=300, seed=1408, capacity=80)
        self.assertEqual(result["status"], "PASS_SYNTHETIC_LONG_RUN")
        self.assertEqual(result["nodeLosses"], 0)
        self.assertEqual(result["edgeLosses"], 0)
        self.assertGreater(result["roundtripChecks"], 0)
        self.assertGreater(result["outcomes"]["CAPACITY_HOLD"], 0)
        self.assertFalse(result["realProcessRestartTested"])
        self.assertFalse(result["productionAutonomyAuthorized"])

    def test_repeated_seed_yields_same_aggregate_metrics(self):
        x = simulate(cycles=80, seed=7, capacity=28)
        y = simulate(cycles=80, seed=7, capacity=28)
        self.assertEqual(x, y)

    def test_rejects_unbounded_simulation_parameters(self):
        for args in ((59, 7, 80), (1501, 7, 80), (80, 7, 15),
                     (80, 7, 501), (80, -1, 80)):
            with self.subTest(args=args):
                with self.assertRaisesRegex(ValueError, "INPUT_BOUNDS_HOLD"):
                    simulate(*args)

    def test_deliberate_erase_on_late_tick_triggers_hold(self):
        old = HrainGraphEngine.decay_nodes
        def bad(self):
            old(self)
            if self.tick >= 10 and self.nodes:
                self.nodes.pop(next(iter(self.nodes)))
        with mock.patch.object(HrainGraphEngine, "decay_nodes", bad):
            with self.assertRaisesRegex(AssertionError, "AUTONOMOUS_NODE_ERASURE_HOLD"):
                simulate(cycles=80, seed=1408, capacity=40)

    def test_report_is_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "synthetic-report.json"
            with mock.patch("sys.argv", ["endurance", "--cycles", "70", "--report", str(path)]):
                self.assertEqual(main(), 0)
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
            before = path.read_bytes()
            with mock.patch("sys.argv", ["endurance", "--cycles", "70", "--report", str(path)]):
                with self.assertRaisesRegex(FileExistsError, "REFUSES_OVERWRITE"):
                    main()
            self.assertEqual(path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
