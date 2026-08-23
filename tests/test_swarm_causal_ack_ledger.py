from __future__ import annotations

import copy
import unittest

from swarm_causal_ack_ledger import build_bundle_from_objects


class CausalAckLedgerTests(unittest.TestCase):
    def fixture(self):
        url = "https://example.org/data"
        result = {
            "mission_id": "TEST",
            "run_id": "42",
            "result_sha256": "parent",
            "identity_rounds": {
                "SCOUT_B": {"new_fact_ids_after_peer_round": ["F1"]}
            },
            "observations": [{
                "observation_id": "O1",
                "scout_id": "SCOUT_B",
                "round": 2,
                "fact_id": "F1",
                "source_urls": [url],
            }],
        }
        peer = {
            "scout_id": "SCOUT_B",
            "peer_context": {
                "peer_queries_admitted": ["exact query"],
                "peer_seed_urls_admitted": [],
            },
            "discovery": {
                "search_events": [{
                    "query": "exact query",
                    "urls": [url],
                    "result_count": 1,
                }],
                "sources": [{
                    "url": url,
                    "final_url": url,
                    "status": "FETCHED",
                    "text_sha256": "sha",
                }],
            },
        }
        inbox = {
            "scout_id": "SCOUT_B",
            "messages": [{
                "message_id": "M1",
                "sender_id": "SCOUT_A",
                "kind": "REQUEST_HELP",
                "payload": {"suggested_queries": ["exact query"]},
            }],
        }
        return result, {"SCOUT_B": peer}, {"SCOUT_B": inbox}

    def test_exact_chain_closes_into_state_change(self):
        result, peers, inboxes = self.fixture()
        bundle = build_bundle_from_objects(result, peers, inboxes)
        self.assertEqual(bundle["stats"]["status_counts"]["COMPLETE_TRACE"], 1)
        self.assertEqual(bundle["stats"]["state_change_count"], 1)
        self.assertEqual(bundle["stats"]["complete_trace_interaction_birth_count"], 1)
        ack = bundle["causal_acks"][0]
        self.assertTrue(ack["work_route_proven"])
        self.assertTrue(ack["single_origin_message_proven"])
        self.assertFalse(ack["scientific_causation_claimed"])
        self.assertEqual(ack["candidate_routes"][0]["origin_message_ids"], ["M1"])
        self.assertEqual(
            bundle["state_changes"][0]["change_kind"],
            "FACT_FIRST_OBSERVED_BY_SCOUT_AFTER_PEER_ROUND",
        )

    def test_duplicate_work_coordinates_but_origins_survive(self):
        result, peers, inboxes = self.fixture()
        inboxes = copy.deepcopy(inboxes)
        inboxes["SCOUT_B"]["messages"].append({
            "message_id": "M2",
            "sender_id": "SCOUT_C",
            "kind": "REQUEST_HELP",
            "payload": {"suggested_queries": ["exact query"]},
        })
        bundle = build_bundle_from_objects(result, peers, inboxes)
        self.assertEqual(bundle["stats"]["work_claim_count"], 1)
        self.assertEqual(bundle["stats"]["status_counts"]["COMPLETE_TRACE"], 1)
        ack = bundle["causal_acks"][0]
        self.assertTrue(ack["work_route_proven"])
        self.assertFalse(ack["single_origin_message_proven"])
        self.assertFalse(ack["exact_workflow_trigger_claimed"])
        self.assertEqual(set(ack["candidate_routes"][0]["origin_message_ids"]), {"M1", "M2"})
        self.assertEqual(set(bundle["work_claims"][0]["origin_sender_ids"]), {"SCOUT_A", "SCOUT_C"})

    def test_failed_fetch_cannot_form_complete_trace(self):
        result, peers, inboxes = self.fixture()
        peers = copy.deepcopy(peers)
        peers["SCOUT_B"]["discovery"]["sources"][0]["status"] = "FETCH_FAILED"
        bundle = build_bundle_from_objects(result, peers, inboxes)
        self.assertEqual(bundle["stats"]["status_counts"]["UNATTRIBUTED_OBSERVATION"], 1)
        self.assertFalse(bundle["causal_acks"][0]["work_route_proven"])

    def test_direct_source_pointer_can_form_complete_trace(self):
        result, peers, inboxes = self.fixture()
        url = result["observations"][0]["source_urls"][0]
        peers = copy.deepcopy(peers)
        inboxes = copy.deepcopy(inboxes)
        peers["SCOUT_B"]["peer_context"] = {
            "peer_queries_admitted": [],
            "peer_seed_urls_admitted": [url],
        }
        peers["SCOUT_B"]["discovery"]["search_events"] = []
        inboxes["SCOUT_B"]["messages"] = [{
            "message_id": "M-SOURCE",
            "sender_id": "SCOUT_A",
            "kind": "OBSERVATION_BUNDLE",
            "payload": {"source_urls": [url], "facts": []},
        }]
        bundle = build_bundle_from_objects(result, peers, inboxes)
        self.assertEqual(bundle["stats"]["status_counts"]["COMPLETE_TRACE"], 1)
        self.assertEqual(bundle["work_claims"][0]["kind"], "SOURCE_POINTER")

    def test_two_distinct_work_routes_remain_ambiguous(self):
        result, peers, inboxes = self.fixture()
        url = result["observations"][0]["source_urls"][0]
        peers = copy.deepcopy(peers)
        inboxes = copy.deepcopy(inboxes)
        peers["SCOUT_B"]["peer_context"]["peer_queries_admitted"] = ["exact query", "second query"]
        peers["SCOUT_B"]["discovery"]["search_events"].append({
            "query": "second query", "urls": [url], "result_count": 1
        })
        inboxes["SCOUT_B"]["messages"].append({
            "message_id": "M2",
            "sender_id": "SCOUT_C",
            "kind": "REQUEST_HELP",
            "payload": {"suggested_queries": ["second query"]},
        })
        bundle = build_bundle_from_objects(result, peers, inboxes)
        self.assertEqual(bundle["stats"]["work_claim_count"], 2)
        self.assertEqual(bundle["stats"]["status_counts"]["AMBIGUOUS_MULTI_WORK_TRACE"], 1)
        self.assertFalse(bundle["causal_acks"][0]["work_route_proven"])


if __name__ == "__main__":
    unittest.main()
