from __future__ import annotations

import json
import unittest

from janus_model.keymaster_candidate_materializer import materialize


def forge(family: str = "TRACTABLE_ISLAND_CONTRACTION") -> dict:
    return {
        "schema": "janus.keymaster.autonomous_forge.v1",
        "state_sha256": "a" * 64,
        "candidate": {
            "candidate_id": "C1",
            "candidate_fingerprint": "b" * 64,
            "operator_family": family,
            "target_from_type": "A",
            "target_to_type": "B",
        },
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


class CandidateMaterializerTests(unittest.TestCase):
    def test_tractable_island_gets_executable_reference_variant(self) -> None:
        report, source = materialize(forge(), "runtime/materialized_candidate.py")
        self.assertEqual(report["status"], "EXECUTABLE_REFERENCE_VARIANT_READY")
        self.assertEqual(
            report["profile_id"],
            "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1",
        )
        self.assertTrue(report["executable_artifact"]["entrypoints_complete"])
        self.assertFalse(report["materialized_variant_is_proved"])
        self.assertFalse(report["keymaster_shadow_admission"])
        self.assertEqual(report["firewall"]["P_VS_NP"], "OPEN")

        ns = {}
        exec(compile(source, "materialized_candidate.py", "exec"), ns)
        execution = ns["run_battery"]()
        self.assertEqual(execution["status"], "EXACT_PROFILE_COUNTEREXAMPLE_FOUND")
        self.assertEqual(
            execution["counterexample"]["relation_cardinality"],
            "2^(k-1)",
        )
        self.assertEqual(
            execution["counterexample"]["witness"]["status"],
            "REJECT_FIXED_INTERFACE_WIDTH",
        )
        self.assertTrue(all(x["formula_verified"] for x in execution["samples"]))

    def test_known_other_family_is_partial_not_fake_executable_solver(self) -> None:
        report, source = materialize(forge("CYCLE_SPACE_PARITY_OVERLAY"), "runtime/c.py")
        self.assertEqual(report["status"], "PARTIAL_EXECUTABLE_ATTACK_PROFILE_READY")
        self.assertFalse(report["executable_artifact"]["entrypoints_complete"])
        ns = {}
        exec(compile(source, "c.py", "exec"), ns)
        execution = ns["run_battery"]()
        self.assertEqual(
            execution["status"],
            "EXECUTED_NO_EXACT_COUNTEREXAMPLE_IN_REFERENCE_BATTERY",
        )

    def test_unknown_family_fails_closed(self) -> None:
        report, _ = materialize(forge("ALIEN_FAMILY"), "runtime/c.py")
        self.assertEqual(report["status"], "UNMATERIALIZABLE_UNKNOWN_OPERATOR_FAMILY")
        self.assertEqual(report["next_action"], "RETURN_TO_FORGE_WITH_UNMATERIALIZABLE_REASON")

    def test_authority_escalation_rejected(self) -> None:
        bad = forge()
        bad["firewall"]["automatic_theorem_promotion"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY_REJECTED"):
            materialize(bad, "runtime/c.py")


if __name__ == "__main__":
    unittest.main()
