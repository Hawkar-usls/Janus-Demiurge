from __future__ import annotations

import unittest

from swarm_genome_nervous_system import build_nervous_system


class SwarmGenomeNervousSystemTests(unittest.TestCase):
    def _result(self):
        return {
            "mission_id": "TEST",
            "run_id": "42",
            "controller_sha": "abc",
            "orchestrator": "JANUS_SWARM_ORCHESTRATOR_01",
            "identity_count": 2,
            "identity_collapses": 0,
            "identity_rounds": {
                "SCOUT_A": {
                    "lineage_id": "JANUS_SCOUT_LINEAGE::SCOUT_A",
                    "round1_present": True,
                    "round2_present": True,
                    "round1_report_sha256": "a1",
                    "round2_report_sha256": "a2",
                    "inbound_message_ids": [],
                    "new_fact_ids_after_peer_round": [],
                    "identity_preserved": True,
                },
                "SCOUT_B": {
                    "lineage_id": "JANUS_SCOUT_LINEAGE::SCOUT_B",
                    "round1_present": True,
                    "round2_present": True,
                    "round1_report_sha256": "b1",
                    "round2_report_sha256": "b2",
                    "inbound_message_ids": ["MSG::A_TO_B"],
                    "new_fact_ids_after_peer_round": ["FACT_Y"],
                    "identity_preserved": True,
                },
            },
            "observations": [
                {
                    "observation_id": "OBS_A_X",
                    "scout_id": "SCOUT_A",
                    "round": 1,
                    "fact_id": "FACT_X",
                    "status": "FOUND",
                    "claim": "x",
                    "source_urls": ["https://example.test/shared"],
                    "confidence": "HIGH",
                },
                {
                    "observation_id": "OBS_B_X",
                    "scout_id": "SCOUT_B",
                    "round": 1,
                    "fact_id": "FACT_X",
                    "status": "FOUND",
                    "claim": "x",
                    "source_urls": ["https://example.test/shared"],
                    "confidence": "HIGH",
                },
                {
                    "observation_id": "OBS_B_Y",
                    "scout_id": "SCOUT_B",
                    "round": 2,
                    "fact_id": "FACT_Y",
                    "status": "FOUND",
                    "claim": "y",
                    "source_urls": ["https://example.test/new"],
                    "confidence": "HIGH",
                },
            ],
            "message_log": [
                {
                    "message_id": "MSG::A_TO_B",
                    "sender_id": "SCOUT_A",
                    "recipient_ids": ["SCOUT_B"],
                    "kind": "OBSERVATION_BUNDLE",
                    "topic": "TEST",
                    "payload": {"facts": [{"fact_id": "FACT_X"}]},
                    "sequence": 1,
                    "append_only": True,
                    "deletable": False,
                },
                {
                    "message_id": "MSG::B_RESPONSE",
                    "sender_id": "SCOUT_B",
                    "recipient_ids": ["JANUS_ORCHESTRATOR"],
                    "kind": "PEER_ROUND_RESPONSE",
                    "topic": "TEST",
                    "payload": {
                        "in_reply_to": ["MSG::A_TO_B"],
                        "new_fact_ids": ["FACT_Y"],
                    },
                    "sequence": 2,
                    "append_only": True,
                    "deletable": False,
                },
            ],
            "fact_clusters": {
                "FACT_X": {
                    "claim_variants": ["x"],
                    "source_urls": ["https://example.test/shared"],
                    "observations": ["OBS_A_X", "OBS_B_X"],
                    "independent_replication_claimed": False,
                },
                "FACT_Y": {
                    "claim_variants": ["y"],
                    "source_urls": ["https://example.test/new"],
                    "observations": ["OBS_B_Y"],
                    "independent_replication_claimed": False,
                },
            },
        }

    def test_same_fact_keeps_two_observation_genome_nodes(self):
        out = build_nervous_system(self._result())
        fact_node = out["indexes"]["fact_nodes"]["FACT_X"]
        parents = out["swarm_genome_ledger"]["nodes"][fact_node]["parent_ids"]
        self.assertEqual(len(parents), 2)
        self.assertEqual(out["stats"]["observation_node_count"], 3)

    def test_peer_message_becomes_parent_context_for_round2(self):
        out = build_nervous_system(self._result())
        msg_node = out["indexes"]["message_nodes"]["MSG::A_TO_B"]
        round2_node = out["indexes"]["scout_round_nodes"]["SCOUT_B::R2"]
        edges = {
            (e["parent_genome_id"], e["child_genome_id"], e["relation"])
            for e in out["typed_interaction_edges"]
        }
        self.assertIn((msg_node, round2_node, "PEER_CONTEXT_FOR"), edges)

    def test_response_links_inbound_message_and_new_observation(self):
        out = build_nervous_system(self._result())
        response_node = out["indexes"]["message_nodes"]["MSG::B_RESPONSE"]
        inbound_node = out["indexes"]["message_nodes"]["MSG::A_TO_B"]
        obs_node = out["indexes"]["observation_nodes"]["OBS_B_Y"]
        edges = {
            (e["parent_genome_id"], e["child_genome_id"], e["relation"])
            for e in out["typed_interaction_edges"]
        }
        self.assertIn((inbound_node, response_node, "REPLIES_TO"), edges)
        self.assertIn((obs_node, response_node, "REPORTS_NEW_OBSERVATION"), edges)

    def test_round2_birth_record_does_not_overclaim_exact_causation(self):
        out = build_nervous_system(self._result())
        self.assertEqual(len(out["interaction_birth_records"]), 1)
        birth = out["interaction_birth_records"][0]
        self.assertEqual(birth["fact_id"], "FACT_Y")
        self.assertEqual(
            birth["causal_claim"],
            "CONTEXTUAL_ASSOCIATION_ONLY__EXACT_TRIGGER_NOT_PROVEN",
        )
        self.assertFalse(
            out["evidence_boundary"]["round2_new_fact_means_exact_message_caused_fact"]
        )

    def test_identity_collapse_is_rejected(self):
        result = self._result()
        result["identity_collapses"] = 1
        with self.assertRaises(ValueError):
            build_nervous_system(result)


if __name__ == "__main__":
    unittest.main()
