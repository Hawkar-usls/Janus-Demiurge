from __future__ import annotations

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


def forge(family="TRACTABLE_ISLAND_CONTRACTION") -> dict:
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
            "operator_family": family,
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


def materialization(entrypoints_complete=True) -> dict:
    return {
        "schema": "janus.keymaster.candidate_materialization.v1",
        "status": "EXECUTABLE_REFERENCE_VARIANT_READY",
        "candidate_id": "C1",
        "candidate_fingerprint": "c" * 64,
        "operator_family": "TRACTABLE_ISLAND_CONTRACTION",
        "profile_id": "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1",
        "executable_artifact": {
            "path": "candidate.py",
            "sha256": "e" * 64,
            "entrypoints_complete": entrypoints_complete,
        },
        "keymaster_shadow_admission": False,
        "materialization_sha256": "f" * 64,
        "firewall": {
            "automatic_theorem_promotion": False,
            "automatic_p_equals_np_claim": False,
            "automatic_merge": False,
            "writes_fundamentum_main": False,
            "writes_user_research_branch": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }


def execution(counterexample=True) -> dict:
    samples = [
        {
            "k": k,
            "exact_even_parity_rows": 1 << (k - 1),
            "formula_rows": 1 << (k - 1),
            "formula_verified": True,
        }
        for k in range(2, 13)
    ]
    return {
        "schema": "janus.keymaster.materialized_execution.v1",
        "candidate_id": "C1",
        "candidate_fingerprint": "c" * 64,
        "profile_id": "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1",
        "status": (
            "EXACT_PROFILE_COUNTEREXAMPLE_FOUND"
            if counterexample
            else "EXECUTED_NO_EXACT_COUNTEREXAMPLE_IN_REFERENCE_BATTERY"
        ),
        "samples": samples if counterexample else [],
        "counterexample": {
            "kind": "UNBOUNDED_PARITY_ISLAND_BOUNDARY",
            "relation_cardinality": "2^(k-1)",
            "scope": "THIS_MATERIALIZED_EXPLICIT_INTERFACE_VARIANT_ONLY",
            "witness": {
                "status": "REJECT_FIXED_INTERFACE_WIDTH",
                "boundary_variables": 11,
                "max_boundary": 10,
            },
            "failed_obligations": ["POLYNOMIAL_STATE", "UNIVERSAL_SCOPE"],
        } if counterexample else None,
    }


class CandidateAttackerTests(unittest.TestCase):
    def test_nonmaterialized_proposal_waits_for_materializer(self) -> None:
        x = build_attack(report(), forge(), controls())
        self.assertEqual(x["status"], "ATTACK_WAITING_FOR_MATERIALIZATION")
        self.assertFalse(x["candidate_survives_known_screen"])
        self.assertFalse(x["candidate_is_proved"])
        self.assertFalse(x["candidate_is_keymaster_edge"])
        self.assertFalse(x["advance_forge"])
        self.assertFalse(x["mathematical_falsification"])
        self.assertFalse(x["candidate_scope_falsified"])
        self.assertFalse(x["materialized_variant_falsified"])
        self.assertFalse(x["keymaster_shadow_admission"])
        self.assertEqual(x["next_action"], "MATERIALIZE_CURRENT_CANDIDATE")

    def test_exact_materialized_profile_counterexample_advances_only_variant(self) -> None:
        x = build_attack(report(), forge(), controls(), materialization(), execution())
        self.assertEqual(x["status"], "REJECTED_MATERIALIZED_VARIANT_EXACT_COUNTEREXAMPLE")
        self.assertTrue(x["advance_forge"])
        self.assertTrue(x["mathematical_falsification"])
        self.assertFalse(x["candidate_scope_falsified"])
        self.assertTrue(x["materialized_variant_falsified"])
        self.assertEqual(x["falsification_scope"], "MATERIALIZED_VARIANT_ONLY")
        self.assertEqual(x["independent_replay"]["status"], "PASS_EXACT_PROFILE_COUNTEREXAMPLE")
        self.assertFalse(x["candidate_is_proved"])
        self.assertFalse(x["candidate_is_keymaster_edge"])
        ledger = {r["id"]: r["attacker_status"] for r in x["proof_work_packet"]["proof_obligations"]}
        self.assertEqual(ledger["POLYNOMIAL_STATE"], "FALSIFIED_FOR_MATERIALIZED_VARIANT")
        self.assertEqual(ledger["UNIVERSAL_SCOPE"], "FALSIFIED_FOR_MATERIALIZED_VARIANT")
        self.assertFalse(x["firewall"]["materialized_variant_falsification_is_candidate_family_falsification"])

    def test_legacy_executable_candidate_can_reach_screen(self) -> None:
        f = forge("CYCLE_SPACE_PARITY_OVERLAY")
        f["candidate"]["executable_artifact"] = {"path": "candidate.py", "sha256": "e" * 64}
        x = build_attack(report(), f, controls())
        self.assertEqual(x["status"], "SURVIVES_EXECUTABLE_REFERENCE_BATTERY__PROOF_OBLIGATIONS_OPEN")
        self.assertTrue(x["candidate_survives_known_screen"])
        self.assertFalse(x["advance_forge"])
        self.assertFalse(x["candidate_is_proved"])

    def test_known_typed_barrier_rejects_candidate_scope(self) -> None:
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
        self.assertTrue(x["candidate_scope_falsified"])
        self.assertFalse(x["materialized_variant_falsified"])
        self.assertEqual(x["falsification_scope"], "CANDIDATE_SCOPE")

    def test_changed_top_gap_rejects_stale_candidate(self) -> None:
        r = report()
        r["missing_interface_queue"][0]["to_type"] = "C"
        x = build_attack(r, forge(), controls())
        self.assertEqual(x["status"], "REJECTED_STALE_TARGET")
        self.assertFalse(x["candidate_survives_known_screen"])

    def test_control_failure_is_unresolved_not_candidate_falsification(self) -> None:
        f = forge("CYCLE_SPACE_PARITY_OVERLAY")
        f["candidate"]["executable_artifact"] = {"path": "candidate.py", "sha256": "e" * 64}
        x = build_attack(report(), f, controls(False))
        self.assertEqual(x["status"], "ATTACK_INFRA_OR_CONTROL_UNRESOLVED")
        self.assertEqual(x["rejection_reason"], "NEGATIVE_CONTROL_REPLAY_NOT_CLEAN")
        self.assertFalse(x["candidate_survives_known_screen"])
        self.assertEqual(x["control_replay"]["status"], "UNRESOLVED")

    def test_materialization_identity_mismatch_is_rejected(self) -> None:
        m = materialization()
        m["candidate_fingerprint"] = "z" * 64
        with self.assertRaisesRegex(RuntimeError, "FINGERPRINT_MISMATCH"):
            build_attack(report(), forge(), controls(), m, execution())

    def test_authority_escalation_is_rejected(self) -> None:
        f = forge()
        f["firewall"]["automatic_theorem_promotion"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY_REJECTED"):
            build_attack(report(), f, controls())


if __name__ == "__main__":
    unittest.main()
