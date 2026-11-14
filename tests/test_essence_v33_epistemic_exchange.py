"""ESSENCE v3.3 source-only tests: spiral lessons are not verdicts."""
import copy
from pathlib import Path
import unittest

from tools import essence_v33_epistemic_exchange as e
from tools import essence_v32_keymaster_memory as memory


def synthetic():
    docs = {
        "spiral": {"schema": "janus.demiurge.spiral_evolution.protocol.v1",
                   "status": "CANONICAL",
                   "laws": ["NO_LEARNING_ENTITY_DELETION", "FAILURE_BECOMES_LESSON",
                            "EXACT_REPEAT_WITHOUT_NEW_INFORMATION_IS_NO_ASCENT"],
                   "admission": {"INTEGRATED_LESSON": "retain negative experience"}},
        "scouts": {"schema": "janus.demiurge.scout_swarm.manifest.v2.spiral.strict_science",
                   "agent_count": 17,
                   "agents": [{"id": "SCOUT_%02d" % i,
                               "target_repo": "Hawkar-usls/repo-%02d" % i}
                              for i in range(17)],
                   "invariants": ["PREVIOUS_SCOUT_REPORT_IS_MEMORY_NOT_EVIDENCE",
                                  "FAILED_RUNS_AND_NEGATIVE_RESULTS_MUST_SURVIVE"]},
        "spi": {"schema_id": "janus.aura_spi.habitat_spiral.v1",
                "spi_contract": {"semantic_synthesis_is_evidence": False},
                "scientific_firewall": ["MEMORY != VERDICT_AUTHORITY"],
                "generation_semantics": {"origin_prime_requires": "VERIFIED_RETURN"}},
        "aura": {"schema": "janus.aura_spi.repository_link.v2",
                 "prediction_authority": False,
                 "scientific_evidence_authority": False,
                 "may_resolve_own_forecast": False,
                 "write_back_default": "DENY"},
        "topa": {"schema": "hawkar.topa.repo_assimilation_protocol.v1",
                 "core_rules": ["NEGATIVE_RESULTS_AND_FAILED_RUNS_REMAIN_SEARCHABLE"],
                 "forbidden_automatic_promotions": ["REPO_TEXT_TO_ARTIFACT_LABEL"],
                 "required_receipt_boundaries": {
                     "repository_corpus_is_supervised_artifact_truth": False}},
        "genesis": {"schema": "janus.essence.github_peer_lineage/1.3",
                    "benchmarks_not_independently_blinded": True,
                    "peers": [{"id": str(i)} for i in range(6)],
                    "policy": {"automatic_code_import": False,
                               "automatic_merge": False,
                               "independent_new_gain_proven": False}},
        "dovod": {"status": "DOVOD_TEMPORAL_WITNESS_LIVE_PASS_HOLD_INSUFFICIENT_FUTURE_COHORT",
                  "experiment_lineage": {"negative_control": {
                      "identical_train_test_sequences": 25, "test_sequences": 50}},
                  "provenance_and_admission": {
                      "independent_neural_improvement_proven": False}},
        "neural": {"first_real_prospective_neural_exam": {
            "verdict": "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN",
            "accepted_generations": 0,
            "independent_future_advantage_proven": False,
            "no_auto_production_weight_change": True}},
        "keymaster": {"schema": "janus.keymaster.attribution_r2_summary.v1",
                      "status": "REPLICATED_EVIDENCE_READY",
                      "attribution": [{"class": "UNRESOLVED"} for _ in range(8)],
                      "claim_ceiling": {"authority_delta": 0,
                                       "automatic_weighting_change": False}},
        "outcome": {"schema": "janus.verified_outcome_memory.v1",
                    "status": "VERIFIED_OUTCOME_MEMORY_READY",
                    "policy": {
                        "feedback_grants_mutation_authority": False,
                        "target_local_reverification_still_required": True,
                        "silence_is_negative_evidence": False,
                        "rejected_provenance_is_negative_evidence": False,
                        "historical_verify_pass_is_world_truth": False,
                        "only_target_local_verify_pass_is_positive_feedback": True,
                        "native_model_selected_required_for_training_prior": True,
                        "clean_patch_lineage_required_for_training_prior": True},
                    "record_count": 0, "training_eligible_count": 0,
                    "records": []},
        "memory": memory.empty_state(),
    }
    return {
        role: {
            "repository": spec[0], "path": spec[2],
            "source_commit": "a" * 40,
            "source_blob_sha1": e.git_blob(e.canonical(docs[role])),
            "source_sha256": e.seal(docs[role]),
            "canonical_sha256": e.seal(docs[role]),
            "payload": docs[role],
        } for role, spec in e.SOURCES.items()
    }


def reseal(item):
    item["canonical_sha256"] = e.seal(item["payload"])
    item["source_sha256"] = item["canonical_sha256"]
    item["source_blob_sha1"] = e.git_blob(e.canonical(item["payload"]))


class EpistemicSpiralTests(unittest.TestCase):
    def setUp(self):
        self.records = synthetic()

    def run_cycle(self, previous=None):
        return e.integrate(self.records, previous or e.empty_state())

    def test_all_eleven_source_groups_and_seventeen_scouts_integrated(self):
        state, report = self.run_cycle()
        self.assertEqual(len(report["source_references"]), 11)
        self.assertEqual(report["scout_identity_count"], 17)
        self.assertEqual(report["genesis_peer_count"], 6)
        self.assertEqual(len(report["historical_negative_results"]), 3)
        self.assertEqual(report["status"], "INTEGRATED_LESSON_NO_PROMOTION")
        self.assertEqual(state["history"][0]["decision"],
                         "INTEGRATED_LESSON_NOT_ASCENDED")
        self.assertEqual(state["history"][0]["turn"], 1)
        self.assertEqual(len(state["history"][0]["scout_identities"]), 17)
        self.assertEqual(e.verify_state(state), state["history"][0]["receipt_sha256"])

    def test_replay_same_sources_is_no_ascent(self):
        first, _ = self.run_cycle()
        again, report = self.run_cycle(first)
        self.assertEqual(first, again)
        self.assertEqual(report["memory_turn"], 1)
        self.assertFalse(report["memory_changed"])
        self.assertEqual(report["status"], "NO_ASCENT_NO_NEW_INFORMATION")

    def test_unrelated_git_commit_does_not_create_false_new_generation(self):
        first, _ = self.run_cycle()
        for role in self.records:
            self.records[role]["source_commit"] = "b" * 40
        second, report = self.run_cycle(first)
        self.assertEqual(second, first)
        self.assertEqual(report["status"], "NO_ASCENT_NO_NEW_INFORMATION")

    def test_scout_identity_replacement_cannot_hide_in_new_turn(self):
        first, _ = self.run_cycle()
        self.records["scouts"]["payload"]["agents"][0]["id"] = "SCOUT_NEW"
        reseal(self.records["scouts"])
        with self.assertRaisesRegex(ValueError, "LINEAGE_REPLACED"):
            self.run_cycle(first)

    def test_changed_source_appends_new_turn_without_erasure(self):
        first, _ = self.run_cycle()
        self.records["topa"]["payload"]["extra_note"] = "new methodological constraint"
        reseal(self.records["topa"])
        second, report = self.run_cycle(first)
        self.assertEqual(len(second["history"]), 2)
        self.assertEqual(second["history"][1]["turn"], 2)
        self.assertEqual(second["history"][1]["previous_sha256"],
                         second["history"][0]["receipt_sha256"])
        self.assertEqual(second["history"][0], first["history"][0])
        self.assertEqual(len(second["history"][1]["negative_evidence"]), 3)
        self.assertIs(report["production_authority"], False)

    def test_rerun_older_snapshot_does_not_relearn(self):
        initial = copy.deepcopy(self.records)
        first, _ = self.run_cycle()
        self.records["spi"]["payload"]["new_method"] = True
        reseal(self.records["spi"])
        second, _ = self.run_cycle(first)
        self.records = initial
        third, report = self.run_cycle(second)
        self.assertEqual(third, second)
        self.assertFalse(report["memory_changed"])

    def test_receipt_never_grants_truth_weight_or_training(self):
        _, report = self.run_cycle()
        for field in ("forecast_resolved", "independent_neural_gain_proven",
                      "classifier_labels_created", "foreign_code_executed",
                      "holdout_added_to_training", "model_weights_updated",
                      "automatic_merge", "production_authority",
                      "scientific_world_truth_promoted"):
            self.assertIs(report[field], False)
        self.assertIn("MEMORY != VERDICT_AUTHORITY", report["cross_repo_evidence_policies"])

    def test_unpinned_source_document_rejected(self):
        self.records["spi"]["source_commit"] = "main"
        with self.assertRaisesRegex(ValueError, "PROVENANCE"):
            self.run_cycle()

    def test_blob_digest_mismatch_rejected(self):
        self.records["topa"]["payload"]["unreviewed"] = True
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            self.run_cycle()

    def test_missing_canonical_group_rejected(self):
        del self.records["neural"]
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            self.run_cycle()

    def test_legacy_spiral_entity_deletion_rejected(self):
        self.records["spiral"]["payload"]["laws"].remove("NO_LEARNING_ENTITY_DELETION")
        reseal(self.records["spiral"])
        with self.assertRaisesRegex(ValueError, "SPIRAL"):
            self.run_cycle()

    def test_scout_identity_loss_rejected(self):
        self.records["scouts"]["payload"]["agents"].pop()
        reseal(self.records["scouts"])
        with self.assertRaisesRegex(ValueError, "SCOUT"):
            self.run_cycle()

    def test_scout_duplicate_identity_rejected(self):
        self.records["scouts"]["payload"]["agents"][0]["id"] = "SCOUT_01"
        reseal(self.records["scouts"])
        with self.assertRaisesRegex(ValueError, "SCOUT"):
            self.run_cycle()

    def test_aura_cannot_claim_forecast_truth(self):
        self.records["aura"]["payload"]["may_resolve_own_forecast"] = True
        reseal(self.records["aura"])
        with self.assertRaisesRegex(ValueError, "AURA"):
            self.run_cycle()

    def test_topa_cannot_make_classifier_labels_from_repo_text(self):
        self.records["topa"]["payload"]["required_receipt_boundaries"][
            "repository_corpus_is_supervised_artifact_truth"] = True
        reseal(self.records["topa"])
        with self.assertRaisesRegex(ValueError, "TOPA"):
            self.run_cycle()

    def test_genesis_peer_is_not_independent_gain(self):
        self.records["genesis"]["payload"]["policy"]["independent_new_gain_proven"] = True
        reseal(self.records["genesis"])
        with self.assertRaisesRegex(ValueError, "GENESIS"):
            self.run_cycle()

    def test_dovod_negative_control_cannot_be_hidden(self):
        self.records["dovod"]["payload"]["experiment_lineage"]["negative_control"][
            "identical_train_test_sequences"] = 0
        reseal(self.records["dovod"])
        with self.assertRaisesRegex(ValueError, "DOVOD"):
            self.run_cycle()

    def test_neural_exam_must_stay_hold(self):
        self.records["neural"]["payload"]["first_real_prospective_neural_exam"][
            "verdict"] = "PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN"
        reseal(self.records["neural"])
        with self.assertRaisesRegex(ValueError, "NEURAL"):
            self.run_cycle()

    def test_keymaster_ablation_is_not_causal_proof(self):
        self.records["keymaster"]["payload"]["attribution"][0]["class"] = "PROVED"
        reseal(self.records["keymaster"])
        with self.assertRaisesRegex(ValueError, "KEYMASTER"):
            self.run_cycle()

    def test_outcome_memory_no_authority_escalation(self):
        self.records["outcome"]["payload"]["policy"]["feedback_grants_mutation_authority"] = True
        reseal(self.records["outcome"])
        with self.assertRaisesRegex(ValueError, "OUTCOME"):
            self.run_cycle()

    def test_spiral_history_tamper_rejected_even_if_outer_resealed(self):
        first, _ = self.run_cycle()
        first["history"][0]["decision"] = "ASCENDED"
        first["state_sha256"] = e.seal({k:v for k,v in first.items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "CHAIN"):
            self.run_cycle(first)

    def test_hash_chain_tamper_fails_closed(self):
        first, _ = self.run_cycle()
        first["history"][0]["production_authority"] = True
        first["history"][0]["receipt_sha256"] = e.seal({
            k:v for k,v in first["history"][0].items() if k!="receipt_sha256"})
        first["state_sha256"] = e.seal({k:v for k,v in first.items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "CHAIN"):
            self.run_cycle(first)

    def test_actual_local_spiral_and_scout_contracts(self):
        root = Path(__file__).resolve().parents[1]
        for role in ("spiral", "scouts"):
            path = root / e.SOURCES[role][2]
            obj = __import__("json").loads(path.read_text(encoding="utf-8"))
            self.records[role]["payload"] = obj
            reseal(self.records[role])
        state, report = self.run_cycle()
        self.assertEqual(report["scout_identity_count"], 17)
        self.assertTrue(all("SCOUT_" in sid for sid in state["history"][0]["scout_identities"]))


if __name__ == "__main__":
    unittest.main()
