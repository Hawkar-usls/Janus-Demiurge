#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import copy
import math
import unittest
from pathlib import Path

from habitat.demiurge_face import (
    ARCH_TYPES,
    CORE_RANGES,
    DemiurgeFaceError,
    HabitatDemiurgeFace,
    PROPOSAL_SCHEMA,
    REQUEST_SCHEMA,
    canonical_sha256,
)


class HabitatDemiurgeFaceTests(unittest.TestCase):
    def setUp(self):
        self.face = HabitatDemiurgeFace()
        self.arch_request = {
            "schema": REQUEST_SCHEMA,
            "request_id": "req-arch-001",
            "mode": "ARCHITECTURE_VARIATION",
            "seed": 37037,
            "candidate_count": 8,
            "base_config": {
                "arch_type": "transformer",
                "n_embd": 256,
                "n_head": 8,
                "n_layer": 6,
            },
        }

    def _evaluations(self, proposal_set):
        return [
            {"proposal_id": row["proposal_id"], "score": float(index)}
            for index, row in enumerate(proposal_set["proposals"])
        ]

    def test_face_has_no_effect_or_execution_authority(self):
        desc = self.face.describe()
        self.assertTrue(desc["can_propose"])
        self.assertFalse(desc["can_verify"])
        self.assertFalse(desc["can_execute_proposal"])
        self.assertFalse(desc["can_mutate_source"])
        self.assertFalse(desc["can_trigger_external_effect"])
        self.assertEqual(desc["write_back_default"], "DENY")

    def test_architecture_replay_is_deterministic(self):
        first = self.face.propose(self.arch_request)
        second = self.face.propose(self.arch_request)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], PROPOSAL_SCHEMA)
        unsigned = dict(first)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_architecture_variants_remain_admissible(self):
        result = self.face.propose(self.arch_request)
        for row in result["proposals"]:
            config = row["config"]
            self.assertIn(config["arch_type"], ARCH_TYPES)
            self.assertEqual(config["n_embd"] % config["n_head"], 0)
            self.assertFalse(row["tested"])
            self.assertFalse(row["selected"])
            self.assertFalse(row["authorized"])

    def test_different_seed_changes_proposal_receipt(self):
        first = self.face.propose(self.arch_request)
        changed = dict(self.arch_request)
        changed["seed"] = 37038
        second = self.face.propose(changed)
        self.assertNotEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_core_parameter_variation_respects_bounds(self):
        request = {
            "schema": REQUEST_SCHEMA,
            "request_id": "req-core-001",
            "mode": "CORE_PARAMETER_VARIATION",
            "seed": 12,
            "candidate_count": 16,
            "base_config": {"alpha": 0.2, "gamma": 0.95, "epsilon": 0.1},
        }
        result = self.face.propose(request)
        for row in result["proposals"]:
            for key, value in row["config"].items():
                low, high = CORE_RANGES[key]
                self.assertGreaterEqual(value, low)
                self.assertLessEqual(value, high)

    def test_request_schema_is_closed_against_effect_smuggling(self):
        request = dict(self.arch_request)
        request["effects"] = {"allow_external_compute": True}
        with self.assertRaises(DemiurgeFaceError):
            self.face.propose(request)

    def test_invalid_architecture_is_rejected(self):
        request = dict(self.arch_request)
        request["base_config"] = dict(request["base_config"])
        request["base_config"]["n_head"] = 12
        with self.assertRaises(DemiurgeFaceError):
            self.face.propose(request)

    def test_rank_uses_only_complete_external_measurements(self):
        proposal_set = self.face.propose(self.arch_request)
        evaluations = self._evaluations(proposal_set)
        ranking = self.face.rank_evaluated(proposal_set, evaluations)
        self.assertTrue(ranking["selection_is_recommendation_only"])
        self.assertFalse(ranking["authorized"])
        self.assertFalse(ranking["execution_requested"])
        self.assertEqual(ranking["selected_proposal_id"], evaluations[-1]["proposal_id"])
        unsigned = dict(ranking)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_incomplete_or_unknown_external_evaluation_rejected(self):
        proposal_set = self.face.propose(self.arch_request)
        rows = proposal_set["proposals"]
        incomplete = [
            {"proposal_id": row["proposal_id"], "score": 1.0}
            for row in rows[:-1]
        ]
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(proposal_set, incomplete)
        unknown = self._evaluations(proposal_set)
        unknown[0] = {"proposal_id": "not-a-real-proposal", "score": 1.0}
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(proposal_set, unknown)

    def test_non_finite_measurement_rejected(self):
        proposal_set = self.face.propose(self.arch_request)
        evaluations = self._evaluations(proposal_set)
        evaluations[0]["score"] = math.nan
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(proposal_set, evaluations)

    def test_tampered_proposal_body_is_rejected_before_ranking(self):
        proposal_set = self.face.propose(self.arch_request)
        tampered = copy.deepcopy(proposal_set)
        tampered["proposals"][0]["config"]["n_layer"] = 12
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(tampered, self._evaluations(proposal_set))

    def test_preasserted_authorization_is_rejected_even_with_rehashed_receipt(self):
        proposal_set = self.face.propose(self.arch_request)
        forged = copy.deepcopy(proposal_set)
        forged["proposals"][0]["authorized"] = True
        unsigned = dict(forged)
        unsigned.pop("receipt_sha256")
        forged["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(forged, self._evaluations(proposal_set))

    def test_unsafe_or_reserved_objective_name_rejected(self):
        proposal_set = self.face.propose(self.arch_request)
        evaluations = self._evaluations(proposal_set)
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(proposal_set, evaluations, objective="proposal_id")
        with self.assertRaises(DemiurgeFaceError):
            self.face.rank_evaluated(proposal_set, evaluations, objective="score/../../effect")

    def test_candidate_count_is_bounded(self):
        request = dict(self.arch_request)
        request["candidate_count"] = 17
        with self.assertRaises(DemiurgeFaceError):
            self.face.propose(request)

    def test_adapter_has_no_network_process_or_file_write_surface(self):
        source_path = Path(__file__).resolve().parents[1] / "habitat" / "demiurge_face.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_import_roots = {
            "aiohttp", "httpx", "requests", "socket", "subprocess", "urllib",
            "pathlib", "os", "shutil", "ftplib", "paramiko"
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "compile", "__import__"})
        self.assertTrue(imported.isdisjoint(forbidden_import_roots), imported)


if __name__ == "__main__":
    unittest.main()
