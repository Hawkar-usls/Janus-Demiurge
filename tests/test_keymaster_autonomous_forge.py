from __future__ import annotations

import unittest

from janus_model.keymaster_autonomous_forge import (
    CANDIDATE_SCHEMA,
    build_search_queries,
    build_state,
    literature_phrase,
    normalize_candidate,
    select_target,
)


def keymaster_report() -> dict:
    return {
        "schema": "janus.keymaster.mechanism_composition_report.v1",
        "report_sha256": "a" * 64,
        "missing_interface_queue": [
            {
                "from_type": "A",
                "to_type": "B",
                "lockpick_score": 90,
                "proved_context_edges": 9,
                "complete_path_edges_if_closed": 10,
                "barrier_penalty": 0,
                "barriers": [],
                "required_contract": {
                    "semantics": "EXACT",
                    "construction_poly": True,
                    "state_poly": True,
                    "reconstruction_poly": True,
                    "verification_poly": True,
                    "universal_scope": True,
                },
            }
        ],
        "firewall": {
            "automatic_theorem_promotion": False,
            "D1": "EMPTY",
            "P_VS_NP": "OPEN",
        },
    }


def candidate() -> dict:
    return {
        "schema": CANDIDATE_SCHEMA,
        "candidate_id": "candidate-1",
        "title": "candidate",
        "target_from_type": "A",
        "target_to_type": "B",
        "strategy": "bounded decomposition",
        "algorithm_steps": ["normalize", "decompose", "reconstruct"],
        "complexity_plan": {
            "construction": "O(n^2)",
            "state": "O(n^2)",
            "reconstruction": "O(n)",
            "verification": "O(n^2)",
        },
        "proof_obligations": [
            {"id": "EXACT_SEMANTICS", "status": "OPEN"},
            {"id": "POLYNOMIAL_CONSTRUCTION", "status": "OPEN"},
            {"id": "POLYNOMIAL_STATE", "status": "OPEN"},
            {"id": "POLYNOMIAL_RECONSTRUCTION", "status": "OPEN"},
            {"id": "POLYNOMIAL_VERIFICATION", "status": "OPEN"},
            {"id": "UNIVERSAL_SCOPE", "status": "OPEN"},
        ],
        "falsification_tests": [{"id": "F1"}, {"id": "F2"}, {"id": "F3"}],
        "donor_ids": [],
        "anti_loop_rationale": "new typed route",
        "resource_firewall": {"hidden_oracle": False, "hidden_exponential_state": False},
        "authority": {
            "truth": False,
            "proof": False,
            "scientific_claim_promotion": False,
            "fundamentum_mutation": False,
            "automatic_merge": False,
        },
    }


class AutonomousForgeTests(unittest.TestCase):
    def test_targets_current_number_one_gap(self) -> None:
        target = select_target(keymaster_report())
        self.assertEqual(target["from_type"], "A")
        self.assertEqual(target["to_type"], "B")
        self.assertEqual(target["proved_context_edges"], 9)

    def test_candidate_is_never_shadow_admitted_by_generation_alone(self) -> None:
        row = normalize_candidate(candidate(), select_target(keymaster_report()))
        self.assertEqual(row["status"], "CANDIDATE_ALGORITHM_PROPOSED_UNVERIFIED")
        self.assertFalse(row["keymaster_shadow_admission"])
        self.assertEqual(row["keymaster_shadow_admission_reason"], "PROOF_OBLIGATIONS_UNDISCHARGED")

    def test_new_candidate_updates_activity_not_proof_authority(self) -> None:
        state = build_state(keymaster_report(), [], model_candidate=candidate())
        self.assertEqual(state["status"], "NEW_CANDIDATE_ALGORITHM_PROPOSED")
        self.assertEqual(state["distinct_candidate_count"], 1)
        self.assertFalse(state["keymaster_shadow_admission"])
        self.assertFalse(state["firewall"]["automatic_theorem_promotion"])
        self.assertFalse(state["firewall"]["automatic_p_equals_np_claim"])
        self.assertEqual(state["firewall"]["P_VS_NP"], "OPEN")

    def test_internal_type_names_are_translated_for_literature_search(self) -> None:
        report = keymaster_report()
        report["missing_interface_queue"][0]["from_type"] = "TSEITIN_CNF_EQSAT"
        report["missing_interface_queue"][0]["to_type"] = "BOOLEAN_CIRCUIT_TREEWIDTH_LE_FIXED_K"
        target = select_target(report)
        queries = build_search_queries(target)
        self.assertEqual(len(queries), 6)
        self.assertTrue(any("Tseitin CNF" in q for q in queries))
        self.assertTrue(any("bounded treewidth" in q for q in queries))
        self.assertFalse(any("TSEITIN_CNF_EQSAT" in q for q in queries))
        self.assertEqual(
            literature_phrase("BOOLEAN_XOR_AND_CHECK_CIRCUIT"),
            "Boolean XOR AND circuit parity constraints",
        )

    def test_quota_free_fallback_generates_candidate_without_external_model(self) -> None:
        records = [
            {
                "provider": "OPENALEX",
                "archive_id": "D1",
                "title": "Tseitin formulas and circuit decomposition",
                "text": "tseitin circuit treewidth decomposition exact",
                "source_url": "https://example.invalid/d1",
                "review_state": "UNEXAMINED",
                "scientific_authority": "DISCOVERY_METADATA_ONLY",
            }
        ]
        state = build_state(keymaster_report(), records)
        self.assertEqual(state["status"], "NEW_CANDIDATE_ALGORITHM_PROPOSED")
        self.assertEqual(state["candidate_proposer"], "DETERMINISTIC_COMBINATORIAL_FALLBACK")
        self.assertEqual(state["candidate"]["synthesis_origin"], "DETERMINISTIC_COMBINATORIAL_FALLBACK")
        self.assertFalse(state["candidate"]["keymaster_shadow_admission"])
        self.assertFalse(state["keymaster_shadow_admission"])

    def test_pending_candidate_blocks_candidate_churn_until_attacked(self) -> None:
        first = build_state(keymaster_report(), [], model_candidate=candidate())
        second = build_state(keymaster_report(), [], previous=first, model_candidate=candidate())
        self.assertEqual(second["status"], "WAITING_FOR_CANDIDATE_ATTACK")
        self.assertEqual(second["candidate_proposer"], "CARRY_FORWARD_PENDING_CANDIDATE")
        self.assertEqual(second["candidate"]["candidate_id"], first["candidate"]["candidate_id"])
        self.assertEqual(second["candidate_proposal_count"], first["candidate_proposal_count"])
        self.assertEqual(second["distinct_candidate_count"], first["distinct_candidate_count"])
        self.assertEqual(second["duplicate_candidate_count"], first["duplicate_candidate_count"])
        self.assertEqual(second["next_action"], "RUN_PROOF_OBLIGATION_AND_FALSIFICATION_GATES")

    def test_attacker_release_advances_to_next_candidate(self) -> None:
        first = build_state(keymaster_report(), [], model_candidate=candidate())
        attack = {
            "schema": "janus.keymaster.autonomous_candidate_attack.v1",
            "status": "DEFERRED_NONEXECUTABLE_PROPOSAL",
            "candidate": {
                "candidate_id": first["candidate"]["candidate_id"],
                "candidate_fingerprint": first["candidate"]["candidate_fingerprint"],
            },
            "advance_forge": True,
            "mathematical_falsification": False,
            "candidate_is_proved": False,
            "keymaster_shadow_admission": False,
            "attack_sha256": "f" * 64,
            "firewall": {
                "automatic_theorem_promotion": False,
                "automatic_p_equals_np_claim": False,
                "automatic_merge": False,
                "writes_fundamentum_main": False,
                "P_VS_NP": "OPEN",
                "D1": "EMPTY",
            },
        }
        second = build_state(keymaster_report(), [], previous=first, attack_result=attack)
        self.assertEqual(second["status"], "NEW_CANDIDATE_ALGORITHM_PROPOSED")
        self.assertNotEqual(second["candidate"]["candidate_fingerprint"], first["candidate"]["candidate_fingerprint"])
        self.assertEqual(second["deferred_candidate_count"], 1)
        self.assertEqual(second["mathematically_falsified_candidate_count"], 0)
        self.assertEqual(second["last_candidate_attack"]["status"], "DEFERRED_NONEXECUTABLE_PROPOSAL")
        self.assertTrue(second["last_candidate_attack"]["advance_forge"])

    def test_target_change_allows_new_candidate_generation(self) -> None:
        first = build_state(keymaster_report(), [], model_candidate=candidate())
        changed = keymaster_report()
        changed["missing_interface_queue"][0]["from_type"] = "C"
        changed["missing_interface_queue"][0]["to_type"] = "D"
        new_candidate = candidate()
        new_candidate["candidate_id"] = "candidate-2"
        new_candidate["target_from_type"] = "C"
        new_candidate["target_to_type"] = "D"
        second = build_state(changed, [], previous=first, model_candidate=new_candidate)
        self.assertEqual(second["status"], "NEW_CANDIDATE_ALGORITHM_PROPOSED")
        self.assertEqual(second["candidate_proposal_count"], first["candidate_proposal_count"] + 1)
        self.assertEqual(second["distinct_candidate_count"], first["distinct_candidate_count"] + 1)


if __name__ == "__main__":
    unittest.main()
