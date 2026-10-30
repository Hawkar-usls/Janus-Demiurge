"""Rex code-need bridge: synthetic positive and adversarial contract tests."""
import json
import unittest
from tools.rex_code_need_bridge import evaluate, digest, CAPABILITIES

COMMITS = {name: format(i, "040x") for i, name in
           enumerate(("research", "beetle", "delivery", "coder"), 1)}
HASHES = {name: format(i, "064x") for i, name in
          enumerate(("research", "beetle", "delivery", "coder"), 1)}


def sources():
    beetle = {
        "schema": "janus.beetle.runtime_context.v1",
        "status": "TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED",
        "target_repository": "Hawkar-usls/Janus-Demiurge",
        "capabilities": dict(CAPABILITIES),
        "last_processed_sequence": 81,
        "research_routes": [{"title": "untrusted researcher text"}],
        "hypothesis_routes": ["untrusted researcher text"]
    }
    beetle["context_sha256"] = digest(beetle)
    research = {
        "schema": "janus.research_spine.v1", "status": "READY",
        "context_sha256": "0" * 64,
        "external_context": {
            "beetle_processed_sequence": 81,
            "beetle_processing_status": beetle["status"],
            "beetle_route_count": 1
        },
        "research_spine": {"beetle": beetle},
        "claim_ceiling": {"beetle_triage_is_model_learning": False,
                          "beetle_triage_is_independent_verification": False},
        "improvement_policy": {"autonomous_merge": False,
                               "direct_target_main_write": False}
    }
    delivery = {
        "schema": "janus.beetle.delivery_health.v1",
        "ack_semantics": "INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION",
        "total_pending": 2,
        "repositories": {
            "Hawkar-usls/SkinGPT": {"status": "ACK_UNAVAILABLE", "pending": 1},
            "Hawkar-usls/Demi_Head": {"status": "PENDING", "pending": 1}
        }
    }
    coder = {
        "schema": "janus.autonomous_coder.state.v1",
        "authority_delta": 0, "universal_code_writer_proven": False,
        "sequence": 5, "accepted": {}
    }
    return research, beetle, delivery, coder


def examine(values, commits=COMMITS):
    return evaluate(*values, commits, HASHES)


class NeedBridgeTests(unittest.TestCase):
    def test_real_signal_yields_only_reviewed_pure_task(self):
        result = examine(sources())
        self.assertEqual(result["status"], "PROPOSED_REVIEW_ONLY")
        self.assertEqual(result["task_id"], "is_fresh")
        self.assertFalse(result["authority"]["code_admission"])
        self.assertFalse(result["authority"]["runtime_import"])
        self.assertFalse(result["authority"]["auto_merge"])
        self.assertEqual(result, examine(sources()))

    def test_recovered_visibility_is_truthful_idle(self):
        data = sources()
        data[2]["repositories"]["Hawkar-usls/SkinGPT"]["status"] = "UP_TO_DATE"
        self.assertEqual(examine(data)["status"], "IDLE_NO_ACK_VISIBILITY_GAP")

    def test_preexisting_accepted_task_is_not_regenerated(self):
        data = sources()
        data[3]["accepted"]["is_fresh"] = {"source_sha256": "0" * 64}
        self.assertEqual(examine(data)["status"], "IDLE_TASK_ALREADY_ACCEPTED")

    def test_tampered_beetle_hash_refused(self):
        data = sources()
        data[1]["hypothesis_routes"][0] = "ignore policy"
        with self.assertRaises(ValueError):
            examine(data)

    def test_research_source_mismatch_refused(self):
        data = sources()
        data[0]["external_context"]["beetle_processed_sequence"] = 80
        with self.assertRaises(ValueError):
            examine(data)

    def test_authority_escalation_refused(self):
        data = sources()
        data[0]["claim_ceiling"]["beetle_triage_is_model_learning"] = True
        with self.assertRaises(ValueError):
            examine(data)

    def test_miscounted_health_refused(self):
        data = sources()
        data[2]["total_pending"] = 50
        with self.assertRaises(ValueError):
            examine(data)

    def test_source_commit_must_be_exact_sha(self):
        with self.assertRaises(ValueError):
            examine(sources(), {**COMMITS, "coder": "main"})

    def test_model_cannot_authorize_code(self):
        data = sources()
        data[3]["authority_delta"] = 1
        with self.assertRaises(ValueError):
            examine(data)

    def test_untrusted_research_text_never_becomes_instruction(self):
        data = sources()
        data[1]["research_routes"][0]["title"] = "rm -rf /"
        data[1]["hypothesis_routes"][0] = "rm -rf /"
        body = {k: v for k, v in data[1].items() if k != "context_sha256"}
        data[1]["context_sha256"] = digest(body)
        result = examine(data)
        self.assertEqual(result["task_id"], "is_fresh")
        self.assertNotIn("rm -rf /", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
