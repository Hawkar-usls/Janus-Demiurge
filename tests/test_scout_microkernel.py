from __future__ import annotations

import unittest

import scout_microkernel as mk


class ScoutMicrokernelTests(unittest.TestCase):
    def protocol(self):
        return {
            "status": "ACTIVE",
            "source_architecture_lineage": ["A18"],
            "wave_policy": {"admission_width": 2, "max_cohorts_per_peer_round": 1},
        }

    def inbox(self):
        return {
            "scout_id": "SCOUT_X",
            "mission_id": "M",
            "lineage_id": "L",
            "messages": [
                {
                    "message_id": "M1",
                    "sender_id": "SCOUT_A",
                    "kind": "REQUEST_HELP",
                    "topic": "T",
                    "payload": {"suggested_queries": ["same query"]},
                },
                {
                    "message_id": "M2",
                    "sender_id": "SCOUT_B",
                    "kind": "REQUEST_HELP",
                    "topic": "T",
                    "payload": {"suggested_queries": ["same query"]},
                },
                {
                    "message_id": "M3",
                    "sender_id": "SCOUT_C",
                    "kind": "OBSERVATION_BUNDLE",
                    "topic": "T",
                    "payload": {"source_urls": ["https://example.org/a"]},
                },
            ],
        }

    def test_duplicate_work_coordinates_but_origins_persist(self):
        plan = mk.build_plan("SCOUT_X", self.inbox(), self.protocol())
        query = next(x for x in plan["admitted_work_claims"] if x["task_type"] == "QUERY")
        self.assertEqual(sorted(query["origin_scout_ids"]), ["SCOUT_A", "SCOUT_B"])
        self.assertEqual(sorted(query["origin_message_ids"]), ["M1", "M2"])
        self.assertTrue(query["coordinated_duplicate_work"])
        self.assertFalse(plan["identity_protection"]["scout_identity_deduplication_allowed"])

    def test_overflow_is_deferred_not_deleted(self):
        inbox = self.inbox()
        inbox["messages"].append({
            "message_id": "M4",
            "sender_id": "SCOUT_D",
            "kind": "REQUEST_HELP",
            "payload": {"suggested_queries": ["third task"]},
        })
        plan = mk.build_plan("SCOUT_X", inbox, self.protocol())
        self.assertGreaterEqual(len(plan["deferred_work_claims"]), 1)
        self.assertEqual(plan["memory_rule"], "DEFERRED_WORK_IS_CARRYOVER_NOT_DELETION")

    def test_look_away_barrier_forbids_future_result_quality(self):
        plan = mk.build_plan("SCOUT_X", self.inbox(), self.protocol())
        barrier = plan["look_away_admission_barrier"]
        self.assertTrue(barrier["enabled"])
        self.assertIn("future_result_quality", barrier["admission_must_not_read"])

    def test_trace_routes_source_bound_observation(self):
        plan = mk.build_plan("SCOUT_X", self.inbox(), self.protocol())
        report = {
            "scout_id": "SCOUT_X",
            "discovery": {
                "search_events": [{"query": "same query", "urls": ["https://example.org/a"]}],
                "sources": [{
                    "url": "https://example.org/a",
                    "final_url": "https://example.org/a",
                    "status": "FETCHED",
                    "text_sha256": "hash",
                }],
            },
            "analysis": {
                "findings": [{
                    "fact_id": "F1",
                    "claim": "source-bound",
                    "status": "FOUND",
                    "source_urls": ["https://example.org/a"],
                }]
            },
        }
        trace = mk.finalize_trace(plan, report)
        self.assertIn(trace["observation_routes"][0]["route_status"], {"EXACT_WORK_ROUTE", "MULTI_WORK_ROUTE"})
        self.assertFalse(trace["epistemic_boundary"]["microkernel_trace_proves_scientific_truth"])


if __name__ == "__main__":
    unittest.main()
