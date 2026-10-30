import unittest
from unittest import mock

from janus_model.extensions import wikipedia_trunk as wiki


class WikipediaTrunkTests(unittest.TestCase):
    def test_registry_inspired_hypothesis_routes_reach_next_search(self):
        research = {
            "hypothesis_routes": ["Replay-safe discovery processing", "Independent verifier recovery"],
            "improvement_policy": {"primary_target": "Hawkar-usls/Janus-Fundamentum"},
        }
        topics = wiki.derive_topics(None, research, max_topics=6)
        self.assertIn("Replay safe discovery processing", topics)
        self.assertIn("Independent verifier recovery", topics)

    def test_route_attention_is_not_exhausted_by_first_route_keyword_expansions(self):
        research = {"hypothesis_routes": ["security safety integrity proof verification", "Replay recovery"]}
        self.assertEqual(wiki.derive_topics(None, research, max_topics=2), research["hypothesis_routes"])

    def test_empty_or_nontext_routes_do_not_create_empty_searches(self):
        topics = wiki.derive_topics(None, {"hypothesis_routes": ["https://example.org/", None]})
        self.assertTrue(all(topics))

    def test_topics_derive_from_current_state_and_stay_bounded(self):
        decision = {
            "selected": {
                "score_text": "PROTECT_MODULE_AUTHORITY_CONTRACT",
                "candidate_id": "HRAIN_PROTECT_MODULE_AUTHORITY_CONTRACT",
                "priority_class": "CRITICAL_INTEGRITY",
                "target": {"repository": "Hawkar-usls/Hrain"},
            }
        }
        research = {"improvement_policy": {"primary_target": "Hawkar-usls/Janus-Fundamentum"}, "research_spine": {"arxiv": {"queries": []}}}
        topics = wiki.derive_topics(decision, research, max_topics=6)
        self.assertLessEqual(len(topics), 6)
        self.assertIn("PROTECT MODULE AUTHORITY CONTRACT", topics)
        self.assertIn("access control", topics)

    def test_wikipedia_is_source_bound_context_not_authority(self):
        fake = {
            "topic": "formal verification",
            "status": "PASS",
            "page_count": 1,
            "pages": [{
                "pageid": 1,
                "title": "Formal verification",
                "canonical_url": "https://en.wikipedia.org/wiki/Formal_verification",
                "lastrevid": 123,
                "revision_id": 123,
                "parent_revision_id": 122,
                "revision_timestamp": "2026-01-01T00:00:00Z",
                "extract": "bounded text",
                "extract_sha256": "a" * 64,
            }],
        }
        with mock.patch.object(wiki, "derive_topics", return_value=["formal verification"]), mock.patch.object(wiki, "query_topic", return_value=fake):
            obj = wiki.build_wikipedia_trunk({}, {}, max_topics=1, max_pages_per_topic=1)
        self.assertEqual(obj["status"], "READY")
        self.assertEqual(obj["page_count"], 1)
        self.assertFalse(obj["authority"]["article_presence_is_truth"])
        self.assertFalse(obj["firewalls"]["wikipedia_is_direct_gradient_source"])
        self.assertFalse(obj["authority"]["may_grant_mutation_authority"])
        self.assertEqual(len(obj["context_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
