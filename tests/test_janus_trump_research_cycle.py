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
            "scientific_question": "Could a total polynomial exact SAT algorithm exist here?",
            "optimization_goal": "Improve or falsify.",
            "current_scientific_boundary": {
                "TRUMP_finished": False,
                "SAT_in_P_proved": False,
                "P_equals_NP_proved": False,
                "P_not_equals_NP_proved": False,
                "P_VS_NP": "OPEN",
            },
            "active_lineage": {
                "tracking_ref": "research/r30-test",
                "active_stage": "R30",
                "active_stage_status": "FROZEN_PREREG_NOT_EXECUTED",
                "active_contract_commit": "c" * 40,
                "active_contract_path": "research/R30.json",
                "frozen_R29_contract_commit": "a" * 40,
                "frozen_R29_contract_path": "research/R29.json",
                "R29_sealed_result_path": "research/R29_RESULT.json",
                "next_gate": "R30_RESTRICTION_BRANCH_ISOLATION_FORENSICS",
                "R31_design_allowed_before_R30_seal": False,
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

    def test_objective_rejects_premature_r31_design(self):
        obj = self.objective()
        obj["active_lineage"]["R31_design_allowed_before_R30_seal"] = True
        with self.assertRaisesRegex(RuntimeError, "R31_PREMATURE"):
            trc.validate_objective(obj)

    def test_cycle_follows_active_contract_and_keeps_context_non_authoritative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "research").mkdir()
            (root / "research/R30.json").write_text("{}", encoding="utf-8")
            (root / "research/R29.json").write_text("{}", encoding="utf-8")
            (root / "research/R29_RESULT.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(trc, "git_head", return_value="b" * 40):
                out = trc.build_cycle(self.objective(), root, enable_network=False)
        self.assertEqual(out["status"], "READY_NETWORK_DISABLED_TEST")
        self.assertEqual(out["P_VS_NP"], "OPEN")
        self.assertEqual(out["fundamentum"]["active_contract_path"], "research/R30.json")
        self.assertEqual(out["fundamentum"]["active_stage"], "R30")
        self.assertFalse(out["authority"]["research_context_is_truth"])
        self.assertFalse(out["authority"]["may_grant_runtime_promotion"])
        self.assertFalse(out["janus_self_compute_policy"]["candidate_output_may_replace_baseline_without_equivalence_receipt"])
        self.assertEqual(len(out["context_sha256"]), 64)

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
