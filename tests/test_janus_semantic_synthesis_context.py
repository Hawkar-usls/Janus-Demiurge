import unittest

from janus_model.extensions import semantic_synthesis_context as sctx


class SemanticSynthesisContextTests(unittest.TestCase):
    def source(self):
        return {
            "schema": "janus.inaihr.semantic_evolution.v2",
            "state_sha256": "a" * 64,
            "generated_at": "2026-09-02T00:00:00Z",
            "registry": {"source_commit": "b" * 40},
            "candidate_count": 2,
            "attention": {
                "policy": "MIGRATING_FOCUS_WITH_REPLAY_FATIGUE_AND_LINEAGE_DIVERSITY",
                "focus_key": "lineage:proof",
                "focus_age": 1,
                "attention_weight_is_evidence_weight": False,
            },
            "candidates": [
                {
                    "id": "syn:1",
                    "kind": "SEMANTIC_CANDIDATE",
                    "status": "CANDIDATE_AWAITING_CORROBORATION",
                    "depth": 1,
                    "focus_key": "lineage:proof",
                    "label": "S1 · Proof Carrier ↔ Independent Verifier",
                    "authority": {"truth": False, "proof": False, "causal": False, "mutation": False, "automatic_promotion": False},
                    "meaning": {
                        "purpose": "Explore a joint meaning.",
                        "mechanism": "SOURCE_A -> proof -> SOURCE_B",
                        "next_steps": ["Search for a counterexample.", "Seek independent corroboration."],
                        "evidence": {
                            "registry_source_commit": "b" * 40,
                            "source_records": [
                                {"id": "obj:a", "path": "data/a.json", "status": "PASS", "sha256": "1" * 64, "lineage_key": "proof"},
                                {"id": "obj:b", "path": "data/b.json", "status": "CANDIDATE", "sha256": "2" * 64, "lineage_key": "proof"},
                            ],
                        },
                    },
                },
                {
                    "id": "syn:2",
                    "kind": "SEMANTIC_CANDIDATE",
                    "status": "CANDIDATE_AWAITING_CORROBORATION",
                    "depth": 2,
                    "focus_key": "lineage:resource",
                    "label": "S2 · Resource Gate ↔ Message Complexity",
                    "authority": {"truth": False, "proof": False, "causal": False, "mutation": False, "automatic_promotion": False},
                    "meaning": {
                        "purpose": "Explore resource interaction.",
                        "mechanism": "SOURCE_A -> resource -> SOURCE_B",
                        "next_steps": ["Measure the suspected interaction."],
                        "evidence": {
                            "registry_source_commit": "b" * 40,
                            "source_records": [
                                {"id": "obj:c", "path": "data/c.json", "status": "OPEN", "sha256": "3" * 64},
                                {"id": "obj:d", "path": "data/d.json", "status": "PASS", "sha256": "4" * 64},
                            ],
                        },
                    },
                },
            ],
        }

    def test_context_is_bounded_candidate_only(self):
        obj = sctx.build_context(self.source())
        self.assertEqual(obj["status"], "READY_CANDIDATE_HYPOTHESIS_CONTEXT")
        self.assertEqual(len(obj["candidate_context"]), 2)
        self.assertTrue(obj["capabilities"]["may_generate_research_questions"])
        self.assertFalse(obj["capabilities"]["may_be_used_as_world_truth"])
        self.assertFalse(obj["capabilities"]["may_be_direct_gradient_signal"])
        self.assertFalse(obj["capabilities"]["may_auto_promote_semantic_candidate"])
        self.assertGreater(len(obj["research_route_seeds"]), 0)
        self.assertEqual(len(obj["context_sha256"]), 64)

    def test_authority_inflation_is_rejected(self):
        src = self.source()
        src["candidates"][0]["authority"]["truth"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY"):
            sctx.build_context(src)

    def test_bad_provenance_is_rejected(self):
        src = self.source()
        src["candidates"][0]["meaning"]["evidence"]["source_records"] = []
        with self.assertRaisesRegex(RuntimeError, "SOURCE_COUNT"):
            sctx.build_context(src)

    def test_attention_cannot_be_evidence(self):
        src = self.source()
        src["attention"]["attention_weight_is_evidence_weight"] = True
        with self.assertRaisesRegex(RuntimeError, "ATTENTION_AUTHORITY"):
            sctx.build_context(src)


if __name__ == "__main__":
    unittest.main()
