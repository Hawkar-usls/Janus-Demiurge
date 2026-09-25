from __future__ import annotations

import copy
import unittest

from janus_model.keymaster_candidate_attacker import build_attack


def report(barriers=None, penalty=0) -> dict:
    return {
        "schema": "janus.keymaster.mechanism_composition_report.v1",
        "report_sha256": "a" * 64,
        "missing_interface_queue": [{
            "from_type": "A",
            "to_type": "B",
            "lockpick_score": 80,
            "proved_context_edges": 8,
            "complete_path_edges_if_closed": 9,
            "barrier_penalty": penalty,
            "barriers": list(barriers or []),
        }],
        "firewall": {
            "automatic_theorem_promotion": False,
            "D1": "EMPTY",
            "P_VS_NP": "OPEN",
        },
    }


def forge() -> dict:
    obligations = [
        {"id": oid, "status": "OPEN", "attack": f"attack {oid}"}
        for oid in (
            "EXACT_SEMANTICS",
            "POLYNOMIAL_CONSTRUCTION",
            "POLYNOMIAL_STATE",
            "POLYNOMIAL_RECONSTRUCTION",
            "POLYNOMIAL_VERIFICATION",
            "UNIVERSAL_SCOPE",
        )
    ]
    return {
        "schema": "janus.keymaster.autonomous_forge.v1",
        "state_sha256": "b" * 64,
        "status": "NEW_CANDIDATE_ALGORITHM_PROPOSED",
        "target": {"from_type": "A", "to_type": "B"},
        "candidate": {
            "candidate_id": "C1",
            "title": "candidate",
            "target_from_type": "A",
            "target_to_type": "B",
            "operator_family": "EXACT_INTERFACE_QUOTIENT",
            "candidate_fingerprint": "c" * 64,
            "status": "CANDIDATE_ALGORITHM_PROPOSED_UNVERIFIED",
            "proof_obligations": obligations,
            "falsification_tests": [{"id": "F1", "test": "x"}],
        },
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


def controls(pass_all=True) -> dict:
    return {
        "controls": [
            {
                "id": "CTRL1",
                "path": "checker.py",
                "ref": "origin/research/x",
                "status": "PASS" if pass_all else "FAIL",
                "returncode": 0 if pass_all else 1,
                "output_sha256": "d" * 64,
                "boundary_open_seen": True,
                "d1_empty_seen": True,
            }
        ]
    }


class CandidateAttackerTests(unittest.TestCase):
    def test_nonexecutable_proposal_is_deferred_and_releases_forge(self) -> None:
        x = build_attack(report(), forge(), controls())
        self.assertEqual(x["status"], "DEFERRED_NONEXECUTABLE_PROPOSAL")
        self.assertFalse(x["candidate_survives_known_screen"])
        self.assertFalse(x["candidate_is_proved"])
        self.assertFalse(x["candidate_is_keymaster_edge"])
        self.assertTrue(x["advance_forge"])
        self.assertFalse(x["mathematical_falsification"])
        self.assertFalse(x["keymaster_shadow_admission"])
        self.assertFalse(x["firewall"]["deferred_nonexecutability_is_mathematical_falsification"])
        self.assertEqual(len(x["proof_work_packet"]["proof_obligations"]), 6)

    def test_executable_candidate_can_reach_known_control_screen(self) -> None:
        f = forge()
        f["candidate"]["executable_artifact"] = {"path": "candidate.py", "sha256": "e" * 64}
        x = build_attack(report(), f, controls())
        self.assertEqual(x["status"], "SURVIVES_KNOWN_CONTROL_SCREEN__PROOF_OBLIGATIONS_OPEN")
        self.assertTrue(x["candidate_survives_known_screen"])
        self.assertFalse(x["advance_forge"])
        self.assertFalse(x["candidate_is_proved"])

    def test_known_typed_barrier_rejects_candidate(self) -> None:
        barrier = {
            "id": "B1",
            "kind": "REPRESENTATION_LOWER_BOUND",
            "penalty": 6,
            "scope": "blocked",
        }
        x = build_attack(report([barrier], 6), forge(), controls())
        self.assertEqual(x["status"], "REJECTED_KNOWN_TYPED_BARRIER")
        self.assertFalse(x["candidate_survives_known_screen"])
        self.assertTrue(x["advance_forge"])
        self.assertTrue(x["mathematical_falsification"])
        self.assertEqual(x["next_action"], "RETURN_TO_FORGE_FOR_DIFFERENT_CANDIDATE")

    def test_changed_top_gap_rejects_stale_candidate(self) -> None:
        r = report()
        r["missing_interface_queue"][0]["to_type"] = "C"
        x = build_attack(r, forge(), controls())
        self.assertEqual(x["status"], "REJECTED_STALE_TARGET")
        self.assertFalse(x["candidate_survives_known_screen"])

    def test_control_failure_is_unresolved_not_candidate_falsification(self) -> None:
        x = build_attack(report(), forge(), controls(False))
        self.assertEqual(x["status"], "ATTACK_INFRA_OR_CONTROL_UNRESOLVED")
        self.assertEqual(x["rejection_reason"], "NEGATIVE_CONTROL_REPLAY_NOT_CLEAN")
        self.assertFalse(x["candidate_survives_known_screen"])
        self.assertEqual(x["control_replay"]["status"], "UNRESOLVED")

    def test_authority_escalation_is_rejected(self) -> None:
        f = forge()
        f["firewall"]["automatic_theorem_promotion"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY_REJECTED"):
            build_attack(report(), f, controls())


if __name__ == "__main__":
    unittest.main()
