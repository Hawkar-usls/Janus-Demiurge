#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import copy
import unittest
from pathlib import Path

from habitat.counterfactual_loop import (
    LOOP_SCHEMA,
    CounterfactualLoopError,
    DemiurgeCounterfactualLoop,
    canonical_sha256,
    score_core_config,
)


class DemiurgeCounterfactualLoopTests(unittest.TestCase):
    def setUp(self):
        self.loop = DemiurgeCounterfactualLoop()
        self.base = {"alpha": 0.08, "gamma": 0.86, "epsilon": 0.65}
        self.target = {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}

    def test_loop_replay_is_deterministic(self):
        first = self.loop.run(
            base_config=self.base,
            target_config=self.target,
            generations=12,
            candidate_count=8,
            seed=42,
        )
        second = self.loop.run(
            base_config=self.base,
            target_config=self.target,
            generations=12,
            candidate_count=8,
            seed=42,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], LOOP_SCHEMA)
        unsigned = dict(first)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_incumbent_score_never_decreases(self):
        result = self.loop.run(
            base_config=self.base,
            target_config=self.target,
            generations=32,
            candidate_count=16,
            seed=37037,
        )
        previous = result["initial_score"]
        for row in result["lineage"]:
            self.assertEqual(row["incumbent_score_before"], previous)
            self.assertGreaterEqual(row["incumbent_score_after"], row["incumbent_score_before"])
            if row["adopted"]:
                self.assertGreater(row["selected_score"], row["incumbent_score_before"])
                self.assertEqual(row["incumbent_score_after"], row["selected_score"])
            else:
                self.assertLessEqual(row["selected_score"], row["incumbent_score_before"])
                self.assertEqual(row["incumbent_score_after"], row["incumbent_score_before"])
            previous = row["incumbent_score_after"]
        self.assertEqual(previous, result["final_score"])
        self.assertGreaterEqual(result["final_score"], result["initial_score"])

    def test_exact_target_is_fixed_point(self):
        result = self.loop.run(
            base_config=self.target,
            target_config=self.target,
            generations=16,
            candidate_count=16,
            seed=7,
        )
        self.assertEqual(result["initial_score"], 0.0)
        self.assertEqual(result["final_score"], 0.0)
        self.assertEqual(result["final_config"], {k: float(v) for k, v in self.target.items()})
        self.assertEqual(result["adopted_generations"], 0)

    def test_every_generation_has_independent_receipt(self):
        result = self.loop.run(
            base_config=self.base,
            target_config=self.target,
            generations=10,
            candidate_count=5,
            seed=11,
        )
        self.assertEqual(len(result["lineage"]), 10)
        seen = set()
        for row in result["lineage"]:
            receipt = row["receipt_sha256"]
            self.assertNotIn(receipt, seen)
            unsigned = dict(row)
            unsigned.pop("receipt_sha256")
            self.assertEqual(receipt, canonical_sha256(unsigned))
            seen.add(receipt)

    def test_loop_claim_ceiling_is_explicit(self):
        result = self.loop.run(
            base_config=self.base,
            target_config=self.target,
            generations=2,
            candidate_count=2,
            seed=1,
        )
        self.assertTrue(result["simulation_only"])
        self.assertFalse(result["future_prediction_claimed"])
        self.assertFalse(result["scientific_validation_claimed"])
        self.assertFalse(result["source_writeback"])
        self.assertFalse(result["external_effect"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["automatic_merge"])

    def test_bounds_fail_closed(self):
        with self.assertRaises(CounterfactualLoopError):
            self.loop.run(base_config=self.base, target_config=self.target, generations=0)
        with self.assertRaises(CounterfactualLoopError):
            self.loop.run(base_config=self.base, target_config=self.target, generations=65)
        with self.assertRaises(CounterfactualLoopError):
            self.loop.run(base_config=self.base, target_config=self.target, candidate_count=17)
        bad = copy.deepcopy(self.base)
        bad["alpha"] = 999
        with self.assertRaises(CounterfactualLoopError):
            self.loop.run(base_config=bad, target_config=self.target)

    def test_counterfactual_score_is_not_magic_and_is_range_normalized(self):
        self.assertEqual(score_core_config(self.target, self.target), 0.0)
        score = score_core_config(self.base, self.target)
        self.assertLess(score, 0.0)
        weighted = score_core_config(
            self.base,
            self.target,
            {"alpha": 10.0, "gamma": 1.0, "epsilon": 1.0},
        )
        self.assertNotEqual(score, weighted)

    def test_loop_source_has_no_network_process_or_file_write_surface(self):
        path = Path(__file__).resolve().parents[1] / "habitat" / "counterfactual_loop.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_roots = {
            "aiohttp", "httpx", "requests", "socket", "subprocess", "urllib",
            "os", "pathlib", "shutil", "ftplib", "paramiko", "sqlite3"
        }
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "compile", "__import__"})
        self.assertTrue(imports.isdisjoint(forbidden_roots), imports)


if __name__ == "__main__":
    unittest.main()
