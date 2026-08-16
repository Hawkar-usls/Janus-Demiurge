#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import copy
import unittest
from pathlib import Path

from habitat.demiurge_face import canonical_sha256
from habitat.lab_supervisor import (
    CHECKPOINT_SCHEMA,
    SUPERVISOR_SCHEMA,
    DemiurgeLabSupervisor,
    LabSupervisorError,
)


class DemiurgeLabSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = DemiurgeLabSupervisor()
        self.base = {"alpha": 0.08, "gamma": 0.86, "epsilon": 0.65}
        self.target = {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}

    def test_no_objective_means_wait_not_self_generated_goal(self):
        result = self.supervisor.wait_without_objective()
        self.assertEqual(result["state"], "WAIT_NO_ADMITTED_OBJECTIVE")
        self.assertFalse(result["objective_present"])
        self.assertFalse(result["self_generated_objective"])
        self.assertFalse(result["work_performed"])
        self.assertFalse(result["authorized"])
        unsigned = dict(result)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_supervisor_replay_is_deterministic(self):
        kwargs = dict(
            objective_id="objective-001",
            base_config=self.base,
            target_config=self.target,
            root_seed=12345,
            generation_window=6,
            max_windows=4,
            candidate_count=8,
            patience_windows=8,
        )
        first = self.supervisor.run_objective(**kwargs)
        second = self.supervisor.run_objective(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], SUPERVISOR_SCHEMA)
        self.assertFalse(first["self_generated_objective"])
        self.assertFalse(first["authorized"])
        self.assertFalse(first["external_effect"])
        self.assertFalse(first["source_writeback"])
        self.assertFalse(first["automatic_merge"])

    def test_window_scores_are_monotonic(self):
        result = self.supervisor.run_objective(
            objective_id="objective-monotonic",
            base_config=self.base,
            target_config=self.target,
            root_seed=77,
            generation_window=4,
            max_windows=8,
            candidate_count=12,
            patience_windows=8,
        )
        previous = result["initial_score"]
        for row in result["windows"]:
            self.assertEqual(row["score_before"], previous)
            self.assertGreaterEqual(row["score_after"], row["score_before"])
            self.assertGreaterEqual(row["improvement"], 0.0)
            unsigned = dict(row)
            receipt = unsigned.pop("receipt_sha256")
            self.assertEqual(receipt, canonical_sha256(unsigned))
            previous = row["score_after"]
        self.assertEqual(previous, result["final_score"])

    def test_exact_target_enters_wait_fixed_point(self):
        result = self.supervisor.run_objective(
            objective_id="objective-fixed",
            base_config=self.target,
            target_config=self.target,
            root_seed=1,
            generation_window=4,
            max_windows=10,
            candidate_count=8,
            patience_windows=2,
        )
        self.assertEqual(result["state"], "WAIT_FIXED_POINT")
        self.assertEqual(result["windows_executed"], 1)
        self.assertEqual(result["final_score"], 0.0)
        self.assertEqual(result["checkpoint"]["state"], "WAIT_FIXED_POINT")
        with self.assertRaises(LabSupervisorError):
            self.supervisor.resume_from_checkpoint(result["checkpoint"])

    def test_plateau_enters_wait_instead_of_busy_loop(self):
        result = self.supervisor.run_objective(
            objective_id="objective-plateau",
            base_config=self.base,
            target_config=self.target,
            root_seed=2,
            generation_window=2,
            max_windows=20,
            candidate_count=2,
            patience_windows=2,
            min_window_improvement=1.0,
        )
        self.assertEqual(result["state"], "WAIT_PLATEAU")
        self.assertEqual(result["windows_executed"], 2)
        self.assertLess(result["windows_executed"], result["max_windows"])
        with self.assertRaises(LabSupervisorError):
            self.supervisor.resume_from_checkpoint(result["checkpoint"])

    def test_budget_checkpoint_resumes_exact_window_sequence(self):
        common = dict(
            objective_id="objective-resume",
            base_config=self.base,
            target_config=self.target,
            root_seed=37037,
            generation_window=3,
            candidate_count=8,
            patience_windows=16,
            min_window_improvement=0.0,
            weights={"alpha": 2.0, "gamma": 1.0, "epsilon": 3.0},
        )
        first = self.supervisor.run_objective(max_windows=2, **common)
        self.assertEqual(first["state"], "BUDGET_EXHAUSTED")
        checkpoint = first["checkpoint"]
        self.assertEqual(checkpoint["schema"], CHECKPOINT_SCHEMA)
        self.assertEqual(checkpoint["weights"], common["weights"])
        self.assertEqual(checkpoint["next_window_index"], 2)

        resumed = self.supervisor.resume_from_checkpoint(
            checkpoint, additional_windows=2
        )
        direct = self.supervisor.run_objective(max_windows=4, **common)
        self.assertEqual(resumed["window_offset"], 2)
        self.assertEqual(resumed["windows"][0]["window_index"], 2)
        self.assertEqual(resumed["windows"], direct["windows"][2:])
        self.assertEqual(resumed["final_config"], direct["final_config"])
        self.assertEqual(resumed["final_score"], direct["final_score"])
        self.assertEqual(
            resumed["checkpoint"]["parent_checkpoint_receipt_sha256"],
            checkpoint["receipt_sha256"],
        )
        self.assertEqual(
            resumed["cumulative_generations"], direct["cumulative_generations"]
        )

    def test_tampered_checkpoint_fails_closed(self):
        first = self.supervisor.run_objective(
            objective_id="objective-tamper",
            base_config=self.base,
            target_config=self.target,
            root_seed=8,
            generation_window=2,
            max_windows=1,
            candidate_count=4,
            patience_windows=8,
        )
        self.assertEqual(first["state"], "BUDGET_EXHAUSTED")
        checkpoint = copy.deepcopy(first["checkpoint"])
        checkpoint["resume_config"]["alpha"] = 0.49
        with self.assertRaises(LabSupervisorError):
            self.supervisor.resume_from_checkpoint(checkpoint)

    def test_rehashed_but_inconsistent_checkpoint_fails_score_replay(self):
        first = self.supervisor.run_objective(
            objective_id="objective-forged",
            base_config=self.base,
            target_config=self.target,
            root_seed=9,
            generation_window=2,
            max_windows=1,
            candidate_count=4,
            patience_windows=8,
        )
        checkpoint = copy.deepcopy(first["checkpoint"])
        checkpoint["resume_score"] = checkpoint["resume_score"] + 0.01
        unsigned = dict(checkpoint)
        unsigned.pop("receipt_sha256")
        checkpoint["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(LabSupervisorError):
            self.supervisor.resume_from_checkpoint(checkpoint)

    def test_hard_budgets_fail_closed(self):
        with self.assertRaises(LabSupervisorError):
            self.supervisor.run_objective(
                objective_id="bad",
                base_config=self.base,
                target_config=self.target,
                root_seed=1,
                generation_window=64,
                max_windows=65,
            )
        with self.assertRaises(LabSupervisorError):
            self.supervisor.run_objective(
                objective_id="bad",
                base_config=self.base,
                target_config=self.target,
                root_seed=1,
                generation_window=64,
                max_windows=64,
                candidate_count=17,
            )

    def test_supervisor_source_has_no_effect_surface(self):
        path = Path(__file__).resolve().parents[1] / "habitat" / "lab_supervisor.py"
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
