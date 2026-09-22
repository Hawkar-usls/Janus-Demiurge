from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from janus_model.keymaster_mechanism_composer import (
    CANDIDATE_STATUSES,
    compose,
    load_contract,
    load_registry,
    scan_fundamentum,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "janus_model" / "keymaster" / "MECHANISM_REGISTRY-v0.json"
CONTRACT = ROOT / "janus_model" / "keymaster" / "MECHANISM_COMPOSITION_CONTRACT-v1.json"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


class KeymasterMechanismCompositionTests(unittest.TestCase):
    def test_seed_registry_and_contract_validate(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        self.assertGreaterEqual(len(reg["mechanisms"]), 5)
        self.assertEqual(cfg["search"]["start_type"], "ARBITRARY_SIGNED_3CNF")
        self.assertFalse(cfg["firewalls"]["automatic_d1_promotion"])

    def test_candidate_theorem_is_not_authoritative_edge(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        fake_scan = {
            "snapshot_sha256": "0" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "normalization_queue": [],
        }
        report = compose(reg, fake_scan, cfg)
        candidate_ids = {x["id"] for x in report["candidate_only_mechanisms"]}
        self.assertIn("M_RESIDUALLY_SMALL_CUBE_COMPACT_TO_SHORT_PP", candidate_ids)
        self.assertEqual(report["complete_universal_lifecycle_candidates"], [])
        self.assertEqual(report["firewall"]["D1"], "EMPTY")
        self.assertEqual(report["firewall"]["P_VS_NP"], "OPEN")

    def test_missing_interface_queue_is_nonempty(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        fake_scan = {
            "snapshot_sha256": "1" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "normalization_queue": [],
        }
        report = compose(reg, fake_scan, cfg)
        self.assertTrue(report["missing_interface_queue"])
        pairs = {(x["from_type"], x["to_type"]) for x in report["missing_interface_queue"]}
        self.assertIn(("SIGNED_OR3_CSP", "TRACTABLE_FIXED_TEMPLATE_CSP"), pairs)
        self.assertIn(("ARBITRARY_SIGNED_3CNF", "SAT_DECISION_WITNESS"), pairs)
        self.assertNotEqual(
            (report["missing_interface_queue"][0]["from_type"], report["missing_interface_queue"][0]["to_type"]),
            ("ARBITRARY_SIGNED_3CNF", "SAT_DECISION_WITNESS"),
        )
        contexts = [x["proved_context_edges"] for x in report["missing_interface_queue"]]
        self.assertEqual(contexts, sorted(contexts, reverse=True))

    def test_scan_new_branch_ingests_typed_contract_and_queues_untyped_pass(self) -> None:
        cfg = load_contract(CONTRACT)
        with tempfile.TemporaryDirectory(prefix="keymaster-mechanism-test-") as td:
            repo = Path(td)
            subprocess.check_call(["git", "init", "-b", "main"], cwd=repo)
            git(repo, "config", "user.email", "keymaster-test@example.invalid")
            git(repo, "config", "user.name", "Keymaster Test")
            (repo / "registry").mkdir()
            (repo / "research").mkdir()

            typed = {
                "schema": "janus.keymaster.mechanism.v1",
                "id": "TEST_TYPED_MECHANISM",
                "input_type": "TEST_A",
                "output_type": "TEST_B",
                "status": "PROVED",
                "semantics": "EXACT",
                "construction_poly": True,
                "state_poly": True,
                "reconstruction_poly": True,
                "verification_poly": True,
                "universal_scope": True,
                "roles": ["REPRESENTATION"],
                "authority": {"test": True},
            }
            (repo / "registry" / "typed.json").write_text(json.dumps(typed), encoding="utf-8")
            barrier = {
                "schema": "janus.keymaster.barrier.v1",
                "id": "TEST_DYNAMIC_BARRIER",
                "from_type": "TEST_A",
                "to_type": "TEST_B",
                "status": "PROVED",
                "kind": "ANTI_LOOP",
                "scope": "TEST_ONLY",
                "authority": {"test": True}
            }
            (repo / "registry" / "barrier.json").write_text(json.dumps(barrier), encoding="utf-8")
            (repo / "registry" / "untyped.json").write_text(
                json.dumps({"artifact_id": "UNTYPED_PASS", "status": "PASS"}),
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "main seed")

            git(repo, "checkout", "-b", "research/keymaster-new-branch")
            (repo / "registry" / "branch.json").write_text(
                json.dumps({"artifact_id": "BRANCH_PASS", "status": "PROVED"}),
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "branch evidence")

            scan = scan_fundamentum(repo, cfg)
            self.assertGreaterEqual(len(scan["refs"]), 2)
            dyn = {x["id"] for x in scan["dynamic_mechanisms"]}
            self.assertIn("TEST_TYPED_MECHANISM", dyn)
            dynamic_barriers = {x["id"] for x in scan["dynamic_barriers"]}
            self.assertIn("TEST_DYNAMIC_BARRIER", dynamic_barriers)
            queued = {x["artifact_id"] for x in scan["normalization_queue"]}
            self.assertIn("UNTYPED_PASS", queued)
            self.assertIn("BRANCH_PASS", queued)

    def test_mapping_status_is_fail_closed_or_explicitly_normalized(self) -> None:
        cfg = load_contract(CONTRACT)
        with tempfile.TemporaryDirectory(prefix="keymaster-status-test-") as td:
            repo = Path(td)
            subprocess.check_call(["git", "init", "-b", "main"], cwd=repo)
            git(repo, "config", "user.email", "keymaster-test@example.invalid")
            git(repo, "config", "user.name", "Keymaster Test")
            (repo / "registry").mkdir()
            (repo / "research").mkdir()
            (repo / "registry" / "nested-pass.json").write_text(
                json.dumps({"artifact_id": "NESTED_PASS", "status": {"status": "PASS"}}),
                encoding="utf-8",
            )
            (repo / "registry" / "opaque-status.json").write_text(
                json.dumps({"artifact_id": "OPAQUE", "status": {"phase": "PASS"}}),
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "status fixtures")

            scan = scan_fundamentum(repo, cfg)
            queued = {x["artifact_id"] for x in scan["normalization_queue"]}
            self.assertIn("NESTED_PASS", queued)
            self.assertNotIn("OPAQUE", queued)

    def test_dynamic_barrier_penalty_demotes_known_antiloop(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        scan = {
            "snapshot_sha256": "3" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "dynamic_barriers": [{
                "id": "TEST_EP_REPACKAGING",
                "from_type": "THREE_SHEET_DISJUNCTIVE_CSP",
                "to_type": "EP_COMPACT_REPRESENTATION",
                "status": "PROVED",
                "kind": "REPACKAGING",
                "scope": "TEST_ONLY",
                "authority": {"test": True},
                "penalty": 12,
            }],
            "normalization_queue": [],
        }
        report = compose(reg, scan, cfg)
        top = report["missing_interface_queue"][0]
        self.assertNotEqual(
            (top["from_type"], top["to_type"]),
            ("THREE_SHEET_DISJUNCTIVE_CSP", "EP_COMPACT_REPRESENTATION"),
        )
        hit = next(
            x for x in report["missing_interface_queue"]
            if (x["from_type"], x["to_type"]) ==
               ("THREE_SHEET_DISJUNCTIVE_CSP", "EP_COMPACT_REPRESENTATION")
        )
        self.assertEqual(hit["barrier_penalty"], 12)
        self.assertEqual(hit["barriers"][0]["kind"], "REPACKAGING")

    def test_dynamic_candidate_cannot_self_promote(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        candidate = {
            "id": "TEST_CANDIDATE",
            "input_type": "ARBITRARY_SIGNED_3CNF",
            "output_type": "SAT_DECISION_WITNESS",
            "status": next(iter(CANDIDATE_STATUSES)),
            "semantics": "EXACT",
            "construction_poly": True,
            "state_poly": True,
            "reconstruction_poly": True,
            "verification_poly": True,
            "universal_scope": True,
            "roles": ["COVERAGE", "CONSISTENCY", "VERIFICATION"],
            "authority": {"test": True},
        }
        scan = {
            "snapshot_sha256": "2" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [candidate],
            "normalization_queue": [],
        }
        report = compose(reg, scan, cfg)
        self.assertEqual(report["complete_universal_lifecycle_candidates"], [])
        self.assertTrue(report["shadow_paths_including_unsealed_candidates"])
        self.assertFalse(report["firewall"]["automatic_theorem_promotion"])


if __name__ == "__main__":
    unittest.main()
