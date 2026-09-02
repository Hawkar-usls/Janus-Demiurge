import tempfile
import unittest
from pathlib import Path
from unittest import mock

from janus_model.extensions import trump_research_cycle as trc


class TrumpResearchCycleTests(unittest.TestCase):
    def objective(self):
        return {
            "schema": "janus.trump.research_objective.v1",
            "status": "ACTIVE_RESEARCH_OBJECTIVE",
            "objective_id": "T",
            "scientific_question": "Could one fixed total polynomial exact SAT algorithm exist here?",
            "optimization_goal": "Improve or falsify without skipping proof levels.",
            "current_scientific_boundary": {
                "TRUMP_finished": False,
                "SAT_in_P_proved": False,
                "P_equals_NP_proved": False,
                "P_not_equals_NP_proved": False,
                "P_VS_NP": "OPEN",
            },
            "active_lineage": {
                "tracking_ref": "research/r38-test",
                "active_stage": "R38",
                "active_stage_status": "SEALED",
                "active_contract_commit": "c" * 40,
                "active_contract_path": "research/R38_RESULT.json",
                "last_parent_contract_path": "research/R38_PREREG.json",
                "last_sealed_result_path": "research/R38_RESULT.json",
                "next_gate": "R39_EXACT_QHORN_RECOGNITION",
            },
            "algorithmic_proof_ladder": {
                "schema": "janus.trump.algorithmic_proof_ladder.v1",
                "highest_verified_level": "L1_LOCAL_FINITE_INSTANCE_EXACTNESS_ONLY",
                "levels": {
                    "L1_LOCAL_FINITE_INSTANCE_EXACTNESS": {"verified": True},
                    "L2_UNIVERSAL_3CNF_COVERAGE": {"verified": False},
                    "L3_ONE_UNIFORM_TOTAL_TRUMP_RESOLVER": {"verified": False},
                    "L4_WORST_CASE_POLYNOMIAL_UNIFORM_TRUMP_RESOLVER": {"verified": False},
                },
                "release_gate": {
                    "domain_and_encoding_closed": False,
                    "one_fixed_algorithm_identified_before_adversarial_input": False,
                    "all_input_termination_proved": False,
                    "all_input_correctness_proved": False,
                    "build_worst_case_polynomial_bound_proved": False,
                },
                "empirical_success_may_advance_level": False,
                "benchmark_speedup_may_advance_level": False,
                "no_counterexample_found_may_advance_level": False,
            },
            "research_queries": {
                "arxiv": ["SAT exact algorithms"],
                "wikipedia_topics": ["P versus NP problem"],
            },
            "janus_self_compute_policy": {
                "runtime_promotion_requires_exact_output_equivalence": True,
                "runtime_promotion_requires_no_integrity_regression": True,
                "runtime_promotion_requires_repeated_resource_win": True,
                "runtime_promotion_requires_bounded_resource_envelope": True,
                "fallback_to_baseline_required": True,
                "rollback_required": True,
                "candidate_output_may_replace_baseline_without_equivalence_receipt": False,
                "speedup_may_imply_universal_coverage": False,
                "speedup_may_imply_uniform_resolver": False,
                "speedup_may_imply_polynomial_bound": False,
                "speedup_may_imply_P_equals_NP": False,
                "authority_delta": 0,
            },
        }

    def test_objective_requires_open_boundary_and_strict_acceleration_gate(self):
        obj = self.objective()
        trc.validate_objective(obj)
        obj["current_scientific_boundary"]["P_equals_NP_proved"] = True
        with self.assertRaisesRegex(RuntimeError, "BOUNDARY_REJECTED"):
            trc.validate_objective(obj)
        obj = self.objective()
        obj["janus_self_compute_policy"]["speedup_may_imply_universal_coverage"] = True
        with self.assertRaisesRegex(RuntimeError, "SPEEDUP_CLAIM_CEILING"):
            trc.validate_objective(obj)

    def test_ladder_rejects_skipping_universal_coverage(self):
        obj = self.objective()
        obj["algorithmic_proof_ladder"]["levels"]["L1_LOCAL_FINITE_INSTANCE_EXACTNESS"]["verified"] = False
        obj["algorithmic_proof_ladder"]["levels"]["L2_UNIVERSAL_3CNF_COVERAGE"]["verified"] = True
        obj["algorithmic_proof_ladder"]["highest_verified_level"] = "L2_UNIVERSAL_3CNF_COVERAGE"
        with self.assertRaisesRegex(RuntimeError, "NONMONOTONIC"):
            trc.validate_objective(obj)

    def test_ladder_rejects_uniform_resolver_without_coverage(self):
        obj = self.objective()
        obj["algorithmic_proof_ladder"]["levels"]["L3_ONE_UNIFORM_TOTAL_TRUMP_RESOLVER"]["verified"] = True
        obj["algorithmic_proof_ladder"]["highest_verified_level"] = "L3_ONE_UNIFORM_TOTAL_TRUMP_RESOLVER"
        with self.assertRaisesRegex(RuntimeError, "NONMONOTONIC"):
            trc.validate_objective(obj)

    def test_l4_requires_every_release_obligation(self):
        obj = self.objective()
        levels = obj["algorithmic_proof_ladder"]["levels"]
        for level in levels.values():
            level["verified"] = True
        obj["algorithmic_proof_ladder"]["highest_verified_level"] = "L4_WORST_CASE_POLYNOMIAL_UNIFORM_TRUMP_RESOLVER"
        with self.assertRaisesRegex(RuntimeError, "OPEN_RELEASE_OBLIGATIONS"):
            trc.validate_objective(obj)

    def test_cycle_follows_exact_active_head_and_keeps_ladder_non_authoritative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "research").mkdir()
            (root / "research/R38_RESULT.json").write_text("{}", encoding="utf-8")
            (root / "research/R38_PREREG.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(trc, "git_head", return_value="c" * 40):
                out = trc.build_cycle(self.objective(), root, enable_network=False)
        self.assertEqual(out["status"], "READY_NETWORK_DISABLED_TEST")
        self.assertEqual(out["P_VS_NP"], "OPEN")
        self.assertEqual(out["fundamentum"]["active_contract_path"], "research/R38_RESULT.json")
        self.assertTrue(out["fundamentum"]["active_contract_head_match"])
        self.assertEqual(out["algorithmic_proof_ladder"]["highest_verified_level"], "L1_LOCAL_FINITE_INSTANCE_EXACTNESS_ONLY")
        self.assertFalse(out["authority"]["proof_ladder_state_is_theorem"])
        self.assertFalse(out["authority"]["may_grant_runtime_promotion"])
        self.assertIn("POLYNOMIAL_TERMINATION != DECISION_COMPLETENESS", out["firewalls"])
        self.assertEqual(len(out["context_sha256"]), 64)

    def test_active_head_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "research").mkdir()
            (root / "research/R38_RESULT.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(trc, "git_head", return_value="d" * 40):
                with self.assertRaisesRegex(RuntimeError, "ACTIVE_LINEAGE_HEAD_DRIFT"):
                    trc.build_cycle(self.objective(), root, enable_network=False)

    def test_benign_state_drift_is_allowed_but_code_or_objective_drift_is_not(self):
        paths = trc.validate_benign_persistence_drift([
            "janus_model/state/JANUS_TRUMP_SHADOW_COMPUTE.json",
            "janus_model/receipts/X.json",
        ])
        self.assertEqual(len(paths), 2)
        with self.assertRaisesRegex(RuntimeError, "NONBENIGN_MAIN_DRIFT"):
            trc.validate_benign_persistence_drift(["trump/TRUMP_RESEARCH_OBJECTIVE-v1.json"])
        with self.assertRaisesRegex(RuntimeError, "NONBENIGN_MAIN_DRIFT"):
            trc.validate_benign_persistence_drift(["janus_model/extensions/trump_research_cycle.py"])


if __name__ == "__main__":
    unittest.main()
