from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from janus_model.keymaster_mechanism_composer import (
    CANDIDATE_STATUSES,
    _barriers_for_gap,
    compose,
    load_autonomous_forge,
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

    def test_progress_readout_is_route_completeness_not_pnp_probability(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        scan = {
            "snapshot_sha256": "9" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "dynamic_barriers": [],
            "normalization_queue": [],
        }
        report = compose(reg, scan, cfg)
        progress = report["progress_readout"]
        self.assertEqual(progress["metric_kind"], "PROOF_OBLIGATION_COMPLETENESS_NOT_PROBABILITY")
        self.assertIsNone(progress["p_equals_np_probability"])
        self.assertEqual(progress["p_vs_np"], "OPEN")
        self.assertFalse(progress["proof_authorized"])
        self.assertGreaterEqual(progress["stage"], 0)
        self.assertLessEqual(progress["stage"], progress["stage_max"])
        self.assertGreaterEqual(progress["best_route_coverage_percent"], 0.0)
        self.assertLessEqual(progress["best_route_coverage_percent"], 100.0)
        self.assertIn("ROUTE_COVERAGE_PERCENT_IS_NOT_P_EQUALS_NP_PROBABILITY", progress["laws"])
        adoption = report["runtime_adoption_policy"]
        self.assertTrue(adoption["candidate_use_allowed"])
        self.assertTrue(adoption["self_application_allowed"])
        self.assertFalse(adoption["proof_authority_granted"])
        self.assertFalse(adoption["scientific_claim_promotion_granted"])
        self.assertFalse(adoption["direct_main_writeback"])
        self.assertFalse(adoption["automatic_merge"])

    def test_proven_delta_reports_zero_when_only_report_activity_changes(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        scan = {
            "snapshot_sha256": "7" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "dynamic_barriers": [],
            "normalization_queue": [],
        }
        baseline = compose(reg, scan, cfg)
        current = compose(reg, scan, cfg, previous_report=baseline)
        delta = current["proven_delta"]
        self.assertEqual(delta["mathematical_progress"], "ZERO")
        self.assertEqual(delta["proven_advance_event_count"], 0)
        self.assertEqual(delta["authoritative_edge_delta"], 0)
        self.assertEqual(delta["proved_barrier_delta"], 0)
        self.assertEqual(delta["complete_route_delta"], 0)
        self.assertEqual(delta["stage_delta"], 0)
        self.assertEqual(delta["law"], "ROUTE_COVERAGE_DELTA_IS_NOT_PROVEN_PROGRESS")

    def test_proven_delta_counts_new_authoritative_edge_as_positive(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        base_scan = {
            "snapshot_sha256": "6" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "dynamic_barriers": [],
            "normalization_queue": [],
        }
        baseline = compose(reg, base_scan, cfg)
        new_edge = {
            "id": "TEST_NEW_PROVED_EDGE",
            "input_type": "TEST_DELTA_A",
            "output_type": "TEST_DELTA_B",
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
        scan = {**base_scan, "dynamic_mechanisms": [new_edge]}
        current = compose(reg, scan, cfg, previous_report=baseline)
        delta = current["proven_delta"]
        self.assertEqual(delta["mathematical_progress"], "POSITIVE")
        self.assertEqual(delta["authoritative_edge_delta"], 1)
        self.assertGreaterEqual(delta["proven_advance_event_count"], 1)

    def test_autonomous_forge_is_activity_only_and_cannot_enter_shadow_graph(self) -> None:
        reg = load_registry(REGISTRY)
        cfg = load_contract(CONTRACT)
        scan = {
            "snapshot_sha256": "8" * 64,
            "refs": [],
            "artifacts": [],
            "dynamic_mechanisms": [],
            "dynamic_barriers": [],
            "normalization_queue": [],
        }
        forge = {
            "schema": "janus.keymaster.autonomous_forge.v1",
            "status": "NEW_CANDIDATE_ALGORITHM_PROPOSED",
            "state_sha256": "f" * 64,
            "cycle_count": 7,
            "candidate_proposal_count": 5,
            "distinct_candidate_count": 4,
            "duplicate_candidate_count": 1,
            "target": {"from_type": "A", "to_type": "B"},
            "search_queries": ["A B exact polynomial algorithm"],
            "selected_donors": [{"title": "donor"}],
            "candidate": {
                "candidate_id": "AUTO-1",
                "title": "candidate",
                "status": "CANDIDATE_ALGORITHM_PROPOSED_UNVERIFIED",
                "candidate_fingerprint": "e" * 64,
                "keymaster_shadow_admission": False,
                "authority": {"proof": False, "automatic_merge": False},
            },
            "next_action": "RUN_PROOF_OBLIGATION_AND_FALSIFICATION_GATES",
            "keymaster_shadow_admission": False,
            "firewall": {
                "branch_only_research": True,
                "writes_fundamentum_main": False,
                "writes_user_research_branch": False,
                "automatic_merge": False,
                "automatic_theorem_promotion": False,
                "automatic_p_equals_np_claim": False,
                "model_output_is_proof": False,
                "candidate_algorithm_is_proof": False,
                "P_VS_NP": "OPEN",
                "D1": "EMPTY",
            },
        }
        with tempfile.TemporaryDirectory(prefix="keymaster-forge-test-") as td:
            p = Path(td) / "forge.json"
            p.write_text(json.dumps(forge), encoding="utf-8")
            summary = load_autonomous_forge(p)
        baseline = compose(reg, scan, cfg)
        report = compose(reg, scan, cfg, summary)
        self.assertEqual(report["autonomous_forge"]["cycle_count"], 7)
        self.assertEqual(report["autonomous_forge"]["distinct_candidate_count"], 4)
        self.assertFalse(report["autonomous_forge"]["keymaster_shadow_admission"])
        self.assertEqual(report["complete_universal_lifecycle_candidates"], [])
        self.assertEqual(
            report["progress_readout"]["best_route_coverage_percent"],
            baseline["progress_readout"]["best_route_coverage_percent"],
        )

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
            self.assertNotIn("TEST_DYNAMIC_BARRIER", queued)

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

    def test_compositional_barrier_propagates_through_proved_downstream_edge(self) -> None:
        authoritative = [
            {
                "id": "M_B_TO_C",
                "input_type": "B",
                "output_type": "C",
                "status": "PROVED",
            }
        ]
        barriers = [
            {
                "id": "B_A_TO_C",
                "from_type": "A",
                "to_type": "C",
                "status": "PROVED",
                "kind": "REPRESENTATION_LOWER_BOUND",
                "scope": "A_TO_C_BLOCKED",
                "authority": {"test": True},
                "penalty": 6,
            }
        ]
        hits = _barriers_for_gap(barriers, "A", "B", authoritative, 8)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "B_A_TO_C")
        self.assertEqual(hits[0]["inheritance"], "COMPOSITIONAL_IMPLICATION")
        self.assertEqual(hits[0]["implied_blocked_route"], {"from_type": "A", "to_type": "C"})
        self.assertEqual(hits[0]["penalty"], 6)

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
        self.assertGreaterEqual(hit["barrier_penalty"], 12)
        repack = next(x for x in hit["barriers"] if x["id"] == "TEST_EP_REPACKAGING")
        self.assertEqual(repack["kind"], "REPACKAGING")
        self.assertEqual(repack["penalty"], 12)
        self.assertEqual(repack["inheritance"], "DIRECT")

    def test_evidence_only_receipt_skips_normalization_queue(self) -> None:
        cfg = load_contract(CONTRACT)
        with tempfile.TemporaryDirectory(prefix="keymaster-evidence-test-") as td:
            repo = Path(td)
            subprocess.check_call(["git", "init", "-b", "main"], cwd=repo)
            git(repo, "config", "user.email", "keymaster-test@example.invalid")
            git(repo, "config", "user.name", "Keymaster Test")
            (repo / "registry").mkdir()
            (repo / "research").mkdir()
            (repo / "research" / "receipt.json").write_text(
                json.dumps({
                    "artifact_id": "EVIDENCE_ONLY_PASS",
                    "status": "PASS",
                    "keymaster_evidence_only": True,
                }),
                encoding="utf-8",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "evidence fixture")

            scan = scan_fundamentum(repo, cfg)
            queued = {x["artifact_id"] for x in scan["normalization_queue"]}
            self.assertNotIn("EVIDENCE_ONLY_PASS", queued)

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
