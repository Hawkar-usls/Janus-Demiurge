"""Read-only and negative-control tests for the bounded divergent pilot."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from janus_model.divergent_mind import LIMITS, run, validate_pack
from janus_model.divergent_mind_benchmark import PACK_PATH, RUBRIC_PATH, evaluate


def source_pack():
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


class DivergentMindTests(unittest.TestCase):
    def test_frozen_fixture_is_source_bound(self):
        pack = source_pack()
        facts = validate_pack(pack)
        self.assertGreaterEqual(len({x["repository"] for x in facts}), 5)
        self.assertTrue(all(len(x["commit"]) == 40 for x in facts))
        self.assertTrue(all(x["lineage"] for x in facts))

    def test_deterministic_and_bounded(self):
        pack = source_pack()
        first, second = run(pack), run(deepcopy(pack))
        self.assertEqual(first, second)
        self.assertEqual(len(first["source_pack_sha256"]), 64)
        self.assertLessEqual(len(first["A_attention"]), LIMITS["attention"])
        self.assertLessEqual(len(first["B_cross_domain_candidates"]), LIMITS["bridges"])
        self.assertLessEqual(len(first["V_fundamental_falsification_questions"]), LIMITS["questions"])

    def test_order_agnostic_candidate_identity(self):
        pack = source_pack()
        original = run(pack)
        pack["observations"].reverse()
        other = run(pack)
        self.assertEqual(original["B_cross_domain_candidates"], other["B_cross_domain_candidates"])
        # The exact pack digest changes with source-file observation order.
        self.assertNotEqual(original["source_pack_sha256"], other["source_pack_sha256"])

    def test_structural_baseline_only_attention(self):
        report = run(source_pack(), "structural_baseline")
        self.assertEqual(report["B_cross_domain_candidates"], [])
        self.assertEqual(report["V_fundamental_falsification_questions"], [])
        self.assertTrue(report["A_attention"])

    def test_stale_health_then_ack_is_temporal_not_live_conflict(self):
        attention = run(source_pack())["A_attention"]
        cosmos = [x for x in attention if x["subject"] == "COSMOS_ACK_STATE"]
        self.assertEqual(len(cosmos), 1)
        self.assertEqual(cosmos[0]["kind"], "TEMPORAL_CHANGE__RECHECK_LATEST")
        self.assertEqual(cosmos[0]["newer_value"], "ACK_SEQUENCE_1")

    def test_same_time_disagreement_is_unresolved(self):
        pack = source_pack()
        pack["observations"][1]["observed_at"] = pack["observations"][0]["observed_at"]
        cosmos = [x for x in run(pack)["A_attention"] if x["subject"] == "COSMOS_ACK_STATE"]
        self.assertEqual(cosmos[0]["kind"], "CONCURRENT_CONFLICT__UNRESOLVED")

    def test_same_lineage_does_not_count_as_cross_domain_independence(self):
        bridges = run(source_pack())["B_cross_domain_candidates"]
        forbidden = {"cosmos_jwst_unknown", "topa_jwst_same_lineage"}
        self.assertFalse(any(forbidden.issubset(set(b["source_ids"])) for b in bridges))
        self.assertTrue(all(not b["independence_verified"] for b in bridges))
        self.assertTrue(all(b["lineage_labels_distinct"] for b in bridges))

    def test_never_upgrades_hypotheses_or_permissions(self):
        for mode in ("structural_baseline", "divergent"):
            report = run(source_pack(), mode)
            self.assertEqual(report["verifier"]["positive_claim_count"], 0)
            self.assertTrue(report["verifier"]["frozen_scientific_gates_unchanged"])
            self.assertEqual(report["permissions"]["authority_delta"], 0)
            self.assertFalse(any(v for k, v in report["permissions"].items() if k != "authority_delta"))
            self.assertTrue(all(x["claim_promotion"] is False and x["effect_authority"] is False
                                for x in report["B_cross_domain_candidates"]))

    def test_rejects_hidden_answer_or_authority_labels(self):
        for extra in (("verdict", "PROVED"), ("command", "merge"), ("authority_delta", 1)):
            pack = source_pack()
            pack["observations"][0][extra[0]] = extra[1]
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_pack(pack)
        pack = source_pack()
        pack["judge_labels"] = {"true": True}
        with self.assertRaises(ValueError):
            validate_pack(pack)

    def test_rejects_paths_commit_and_operator_injection(self):
        for path in ("/etc/passwd", "../secrets", "data//ACK.json", "./README.md"):
            pack = source_pack()
            pack["observations"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_pack(pack)
        pack = source_pack()
        pack["observations"][0]["commit"] = "main"
        with self.assertRaises(ValueError):
            validate_pack(pack)
        pack = source_pack()
        pack["observations"][0]["operators"] = [{"__exec__": "anything"}]
        with self.assertRaises(ValueError):
            validate_pack(pack)
        pack = source_pack()
        pack["observations"][0]["operators"] = ["UNSCOPED_COMMAND"]
        with self.assertRaises(ValueError):
            validate_pack(pack)

    def test_rejects_ambiguous_or_non_utc_timestamps(self):
        for time in ("2026-10-17T20:45:31+00:00", "yesterday", "2026-10-17T20:45:31+02:00Z"):
            pack = source_pack()
            pack["observations"][0]["observed_at"] = time
            with self.subTest(time=time), self.assertRaises(ValueError):
                validate_pack(pack)

    def test_rejects_unbounded_and_duplicate_inputs(self):
        pack = source_pack()
        pack["observations"].append(deepcopy(pack["observations"][0]))
        with self.assertRaises(ValueError):
            validate_pack(pack)
        pack = source_pack()
        pack["observations"] *= 8
        with self.assertRaises(ValueError):
            validate_pack(pack)
        with self.assertRaises(ValueError):
            run(source_pack(), "unbounded_agent")

    def test_algorithm_blind_smoke_and_controls(self):
        rubric = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
        report = evaluate(source_pack(), rubric)
        self.assertEqual(report["diagnostic_status"], "SMOKE_PASS")
        self.assertTrue(all(report["negative_controls"].values()))
        self.assertEqual(report["baseline"]["cross_domain_candidates"], 0)
        self.assertEqual(report["divergent"]["relevance_targets_total"], 4)
        self.assertLessEqual(report["divergent"]["relevance_targets_hit"], 4)
        self.assertEqual(report["scientific_status"], "OPEN__NO_INDEPENDENT_VERIFICATION_OR_WORLD_CLAIM")

    def test_rejects_mismatched_rubric(self):
        rubric = json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
        rubric["source_pack_id"] = "OTHER_PILOT"
        with self.assertRaises(ValueError):
            evaluate(source_pack(), rubric)


if __name__ == "__main__":
    unittest.main()
