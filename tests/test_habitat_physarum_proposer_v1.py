#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import math
import unittest
from pathlib import Path

from habitat.physarum_proposer import (
    PhysarumGridProposer,
    PhysarumProposalError,
    canonical_sha256,
    cell_to_coordinate,
    coordinate_to_cell,
)


class PhysarumGridProposerTests(unittest.TestCase):
    def setUp(self):
        self.proposer = PhysarumGridProposer()

    @staticmethod
    def basin(width=9, height=9, target_x=8, target_y=8):
        return [
            [float((x - target_x) ** 2 + (y - target_y) ** 2) for x in range(width)]
            for y in range(height)
        ]

    def test_upper_bound_maps_to_last_valid_cell_not_size(self):
        self.assertEqual(coordinate_to_cell(0.0, [0.0, 1.0], 50), 0)
        self.assertEqual(coordinate_to_cell(1.0, [0.0, 1.0], 50), 49)
        self.assertEqual(coordinate_to_cell(2.0, [0.0, 1.0], 50), 49)
        self.assertEqual(cell_to_coordinate(49, [0.0, 1.0], 50), 1.0)

    def test_endpoint_round_trip_is_exact(self):
        for size in (2, 3, 17, 64):
            self.assertEqual(
                coordinate_to_cell(cell_to_coordinate(0, [-3.0, 7.0], size), [-3.0, 7.0], size),
                0,
            )
            self.assertEqual(
                coordinate_to_cell(cell_to_coordinate(size - 1, [-3.0, 7.0], size), [-3.0, 7.0], size),
                size - 1,
            )

    def test_replay_is_deterministic(self):
        kwargs = dict(
            landscape=self.basin(),
            x_name="learning_rate",
            x_range=[1e-5, 1e-3],
            y_name="gain",
            y_range=[0.0, 1.0],
            seed=37037,
            agents=192,
            iterations=50,
            candidate_count=8,
        )
        first = self.proposer.propose(**kwargs)
        second = self.proposer.propose(**kwargs)
        self.assertEqual(first, second)
        unsigned = dict(first)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_simple_basin_prioritizes_global_minimum(self):
        result = self.proposer.propose(
            landscape=self.basin(),
            x_name="alpha",
            x_range=[0.01, 0.5],
            y_name="epsilon",
            y_range=[0.01, 0.9],
            seed=11,
            agents=512,
            iterations=80,
            candidate_count=5,
            landscape_bias=0.35,
        )
        top = result["proposals"][0]
        self.assertEqual(top["cell"], {"x": 8, "y": 8})
        self.assertEqual(top["observed_landscape_value"], 0.0)
        self.assertEqual(top["parameters"]["alpha"], 0.5)
        self.assertEqual(top["parameters"]["epsilon"], 0.9)

    def test_proposals_never_claim_selection_or_authorization(self):
        result = self.proposer.propose(
            landscape=self.basin(5, 5, 2, 2),
            x_name="alpha",
            x_range=[0.01, 0.5],
            y_name="epsilon",
            y_range=[0.01, 0.9],
            seed=1,
            agents=64,
            iterations=20,
            candidate_count=6,
        )
        self.assertTrue(result["landscape_was_precomputed"])
        self.assertFalse(result["fitness_callable_executed"])
        self.assertFalse(result["selection_authority_claimed"])
        self.assertFalse(result["execution_requested"])
        self.assertFalse(result["source_writeback_requested"])
        self.assertFalse(result["future_prediction_claimed"])
        self.assertEqual(len({row["proposal_id"] for row in result["proposals"]}), 6)
        for row in result["proposals"]:
            self.assertFalse(row["tested"])
            self.assertFalse(row["selected"])
            self.assertFalse(row["authorized"])

    def test_callable_landscape_is_rejected(self):
        with self.assertRaises(PhysarumProposalError):
            self.proposer.propose(
                landscape=lambda x, y: x + y,
                x_name="x",
                x_range=[0.0, 1.0],
                y_name="y",
                y_range=[0.0, 1.0],
                seed=1,
            )

    def test_nan_ragged_and_oversized_inputs_fail_closed(self):
        with self.assertRaises(PhysarumProposalError):
            self.proposer.propose(
                landscape=[[0.0, 1.0], [2.0, math.nan]],
                x_name="x", x_range=[0, 1], y_name="y", y_range=[0, 1], seed=1,
            )
        with self.assertRaises(PhysarumProposalError):
            self.proposer.propose(
                landscape=[[0.0, 1.0], [2.0]],
                x_name="x", x_range=[0, 1], y_name="y", y_range=[0, 1], seed=1,
            )
        with self.assertRaises(PhysarumProposalError):
            self.proposer.propose(
                landscape=[[0.0, 1.0], [2.0, 3.0]],
                x_name="x", x_range=[0, 1], y_name="y", y_range=[0, 1], seed=1,
                agents=4097,
            )

    def test_flat_landscape_remains_bounded_and_deterministic(self):
        landscape = [[7.0 for _ in range(4)] for _ in range(4)]
        result = self.proposer.propose(
            landscape=landscape,
            x_name="x", x_range=[-1.0, 1.0],
            y_name="y", y_range=[10.0, 20.0],
            seed=8,
            agents=64,
            iterations=10,
            candidate_count=16,
        )
        self.assertEqual(len(result["proposals"]), 16)
        for row in result["proposals"]:
            self.assertGreaterEqual(row["parameters"]["x"], -1.0)
            self.assertLessEqual(row["parameters"]["x"], 1.0)
            self.assertGreaterEqual(row["parameters"]["y"], 10.0)
            self.assertLessEqual(row["parameters"]["y"], 20.0)

    def test_source_has_no_network_process_file_or_numpy_surface(self):
        path = Path(__file__).resolve().parents[1] / "habitat" / "physarum_proposer.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_roots = {
            "aiohttp", "httpx", "requests", "socket", "subprocess", "urllib",
            "os", "pathlib", "shutil", "ftplib", "paramiko", "numpy", "scipy"
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "compile", "__import__"})
        self.assertTrue(imported.isdisjoint(forbidden_roots), imported)


if __name__ == "__main__":
    unittest.main()
