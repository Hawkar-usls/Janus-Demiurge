"""Offline R1 typed-organ adapter tests, including adverse control mutations."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from janus_model.divergent_mind_r1 import (
    MAX_QUESTIONS, validate, run,
)
from janus_model.divergent_mind_r1_benchmark import PACK, RUBRIC, evaluate
from janus_model.divergent_mind_r1_source_audit import (
    assert_source_excerpt_matches, git_blob_sha1,
)


def case():
    return json.loads(PACK.read_text(encoding="utf-8"))


class OrganR1Tests(unittest.TestCase):
    def test_native_schema_and_origin_pin_checks(self):
        sources = validate(case())
        self.assertEqual(len(sources), 6)
        self.assertEqual(sources["inaihr_state"]["candidate_count"], 128)
        self.assertEqual(sources["eye_independence"]["pair_count"], 10)

    def test_matched_input_budget_and_repeated_determinism(self):
        pack = case()
        a = run(pack, "native_baseline")
        b = run(pack, "divergent_r1")
        self.assertEqual(len(a["questions"]), MAX_QUESTIONS)
        self.assertEqual(len(b["questions"]), MAX_QUESTIONS)
        self.assertEqual(a["source_pack_sha256"], b["source_pack_sha256"])
        self.assertEqual(b, run(deepcopy(pack), "divergent_r1"))

    def test_fresh_candidate_has_different_registry_pin(self):
        r = run(case(), "divergent_r1")
        self.assertTrue(r["attention_flags"]["cross_organ_registry_pin_differs"])
        self.assertEqual(r["questions"][0]["kind"], "CROSS_ORGAN_SOURCE_PIN_DRIFT")
        self.assertEqual({x["repository"] for x in r["questions"][0]["source_refs"]},
                         {"Hawkar-usls/Hrain", "Hawkar-usls/iNaiHR"})

    def test_equal_pin_is_not_described_as_drift(self):
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["registry"]["source_commit"] = (
            p["sources"]["hrain_provenance"]["excerpt"]["source_commit"])
        report = run(p)
        self.assertEqual(report["questions"][0]["kind"], "CROSS_ORGAN_PIN_ALIGNMENT")
        self.assertFalse(report["attention_flags"]["cross_organ_registry_pin_differs"])

    def test_model_independence_is_not_independent_evidence(self):
        r = run(case())
        self.assertTrue(r["attention_flags"]["eye_independence_conflicts_unknown"])
        self.assertEqual(r["questions"][1]["kind"], "MODEL_PAIR_NE_INDEPENDENT_WITNESS")
        self.assertTrue(all(x["independence_verified"] is False for x in r["questions"]))

    def test_no_scientific_or_execution_promotion_in_either_arm(self):
        for arm in ("native_baseline", "divergent_r1"):
            report = run(case(), arm)
            gates = report["guardrails"]
            self.assertEqual(gates["authority_delta"], 0)
            self.assertFalse(gates["runtime_invoked"])
            self.assertFalse(gates["direct_eye_to_inaihr_bypass"])
            self.assertFalse(gates["cross_repo_mutation"])
            self.assertFalse(gates["repository_writeback"])
            self.assertFalse(gates["scientific_claim_promotion"])
            self.assertFalse(gates["complete_origin_file_hashes_reverified_at_run_time"])
            self.assertFalse(gates["independent_evaluator_executed"])
            self.assertTrue(all(x["claim_promotion"] is False and x["effect_authority"] is False
                                for x in report["questions"]))

    def test_unavailable_eye_test_never_becomes_available(self):
        p = case()
        p["sources"]["eye_next_tests"]["excerpt"]["available_ranked"] = []
        r = run(p, "native_baseline")
        self.assertIn("NONE", r["questions"][2]["question"])
        self.assertEqual(r["attention_flags"]["eye_available_test_count"], 0)
        self.assertEqual(r["attention_flags"]["eye_unavailable_test_count"], 1)

    def test_rejects_unsafe_legacy_policy_mutations(self):
        p = case()
        p["sources"]["hrain_manifest"]["excerpt"]["authority"]["chat_event_is_command"] = True
        with self.assertRaises(ValueError):
            run(p)
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["authority"]["truth"] = True
        with self.assertRaises(ValueError):
            run(p)
        p = case()
        p["sources"]["hrain_provenance"]["excerpt"]["cross_repository_write"] = True
        with self.assertRaises(ValueError):
            run(p)

    def test_rejects_malformed_and_cross_repo_pin_mix(self):
        p = case()
        p["sources"]["eye_next_tests"]["origin"]["path"] = "../.env"
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["hrain_head"]["origin"]["commit"] = "main"
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["hrain_head"]["origin"]["repository"] = "Hawkar-usls/iNaiHR"
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["hrain_manifest"]["origin"]["commit"] = "0" * 40
        with self.assertRaises(ValueError):
            validate(p)

    def test_rejects_unexpected_authority_fields_and_fake_live_claim(self):
        p = case()
        p["capture_kind"] = "LIVE_RUNTIME_CONFIRMED"
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["execute"] = "true"
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["eye_next_tests"]["excerpt"]["available_ranked"][0]["claim_promotion"] = True
        with self.assertRaises(ValueError):
            validate(p)

    def test_rejects_invalid_scores_and_timestamp(self):
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["attention_score"] = True
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["eye_next_tests"]["excerpt"]["available_ranked"][0]["gain_per_cost"] = True
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["generated_at"] = "2026-10-18T04:00:00+03:00"
        with self.assertRaises(ValueError):
            validate(p)

    def test_rejects_duplicate_candidate_or_eye_test(self):
        p = case()
        p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][1]["id"] = (
            p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["id"])
        with self.assertRaises(ValueError):
            validate(p)
        p = case()
        p["sources"]["eye_next_tests"]["excerpt"]["unavailable_counterfactual_value_ranked"][0]["test_id"] = "TOPA-RT-H1"
        with self.assertRaises(ValueError):
            validate(p)

    def test_rejects_unsupported_organ_or_arm(self):
        p = case()
        p["sources"]["fourth_hemi"] = {}
        with self.assertRaises(ValueError):
            validate(p)
        with self.assertRaises(ValueError):
            run(case(), "execute_all")

    def test_designer_benchmark_counterfactuals(self):
        r = evaluate(case(), json.loads(RUBRIC.read_text(encoding="utf-8")))
        self.assertEqual(r["diagnostic_status"], "SMOKE_PASS")
        self.assertTrue(all(r["counterfactual_and_safety_controls"].values()))
        self.assertEqual(r["native_baseline"]["questions"], r["divergent_r1"]["questions"])
        self.assertEqual(r["independent_judge_status"], "NOT_EXECUTED__DESIGNER_EVALUATOR_ONLY")

    def test_whole_file_git_blob_hash_algorithm(self):
        # Standard Git SHA-1 of the bytes b"hello\n" as a blob.
        self.assertEqual(git_blob_sha1(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_excerpt_extraction_rejects_tampering(self):
        excerpt = case()["sources"]["hrain_head"]["excerpt"]
        original = {**excerpt, "extra_native_field": "ignored"}
        assert_source_excerpt_matches("hrain_head", original, excerpt)
        original["event_object_count"] = 500
        with self.assertRaises(ValueError):
            assert_source_excerpt_matches("hrain_head", original, excerpt)

    def test_organ_excerpts_are_not_silent_truth_claims(self):
        p = case()
        for key in p["sources"]:
            self.assertEqual(len(p["sources"][key]["origin"]["blob_sha"]), 40)
        self.assertTrue(p["capture_kind"].endswith("NOT_LIVE_RUNTIME"))
        self.assertTrue(all(c["independent_replication_established"] is False
                            for c in p["sources"]["inaihr_state"]["excerpt"]["recent_candidates"]))

    def test_rejects_mismatched_rubric(self):
        rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
        rubric["source_pack_id"] = "DIFFERENT_SOURCE_PACK"
        with self.assertRaises(ValueError):
            evaluate(case(), rubric)


if __name__ == "__main__":
    unittest.main()
