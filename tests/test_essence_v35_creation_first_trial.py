"""Adversarial ESSENCE v3.5 memory-to-candidate and paired prospective research tests.

All generated outcome streams here are DEVELOPMENT FIXTURES, NOT external or
prospective scientific validation. Only the live post-Git-commit cohort counts.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import unittest

from tools import essence_v32_keymaster_memory as km
from tools import essence_v33_epistemic_exchange as spi
from tools import essence_v35_creation_first_trial as m

FREEZE_TIME = "2026-11-14T20:00:00+00:00"
PUBLISHED = "2026-11-14T23:59:00+00:00"
EXAM_TIME = "2026-11-18T00:00:00+00:00"


def memories():
    ep = spi.empty_state()
    negative = [
        {"id": "DOVOD_SHA_25_OF_50_TEST_LEAKAGE",
         "status": "NEGATIVE_CONTROL_CONTAMINATED"},
        {"id": "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114",
         "status": "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"},
        {"id": "KEYMASTER_R2_REPLICATED_ABLATIONS",
         "status": "UNRESOLVED_EIGHT_CONTRIBUTORS"},
    ]
    entry = {
        "turn": 1, "entity": "JANUS_ESSENCE_EPISTEMIC_EXCHANGE",
        "previous_sha256": spi.ROOT, "source_fingerprint_sha256": "a" * 64,
        "scout_identities": ["SCOUT_%02d" % i for i in range(17)],
        "negative_evidence": negative,
        "constraints_inherited": list(spi.LAWS),
        "decision": "INTEGRATED_LESSON_NOT_ASCENDED",
        "production_authority": False,
    }
    entry["receipt_sha256"] = spi.seal(entry)
    ep["history"].append(entry)
    ep["state_sha256"] = spi.seal({
        k:v for k,v in ep.items() if k!="state_sha256"})
    key = km.empty_state()
    record = {
        "sequence": 0, "evidence_sha256": "f" * 64,
        "source_commit": "a" * 40, "previous_sha256": km.ROOT,
        "donor_count": 8, "verified_local_lessons": 1,
        "keymaster_guard": "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION",
        "authority_delta": 0, "training_admission": False,
    }
    record["receipt_sha256"] = km.seal(record)
    key["history"].append(record)
    key["state_sha256"] = km.seal({
        k:v for k,v in key.items() if k!="state_sha256"})
    return ep, key


def run(i, wid, label, *, future=False, event="workflow_dispatch"):
    # Deliberately use timestamps and labels of *synthetic* event streams only.
    start = datetime(2026, 11, 15 if future else 11, tzinfo=timezone.utc)
    created = start + timedelta(minutes=5*i)
    started = created + timedelta(seconds=2)
    updated = started + timedelta(seconds=(15, 75, 170)[label])
    return {
        "id": (10000 if future else 1) + i, "workflow_id": wid,
        "head_branch": "main", "event": event, "status": "completed",
        "conclusion": "success", "run_attempt": 1,
        "created_at": created.isoformat(), "run_started_at": started.isoformat(),
        "updated_at": updated.isoformat(),
    }


def train_events():
    return [run(i, 100+(i % 9), (i % 9) % 3) for i in range(198)]


def future_events():
    return [run(i, 100+(i % 8), (i % 8) % 3, future=True)
            for i in range(64)]


class MemoryProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.ep, self.key = memories()
        self.train = train_events()
        self.future = future_events()
        self.commits = {"epistemic": "a"*40, "keymaster": "b"*40}

    def packet(self):
        return m.freeze(self.ep, self.key, self.train, observed_at=FREEZE_TIME,
                        source_commits=self.commits)

    def test_verified_memory_generates_three_source_bound_microcores(self):
        source = m.source_memory(self.ep, self.key)
        blueprints = m.propose(source)
        self.assertEqual(len(blueprints), 3)
        self.assertEqual({x["source_negative_result"] for x in blueprints},
                         set(m.NEGATIVE))
        self.assertEqual([x["mode"] for x in blueprints].count(
            "EXECUTABLE_STDLIB_PROSPECTIVE"), 1)
        self.assertTrue(all(not x["auto_code_execution"] and
                            not x["production_authority"] for x in blueprints))
        self.assertTrue(all(x["candidate_sha256"] == m.sha({
            k:v for k,v in x.items() if k!="candidate_sha256"}) for x in blueprints))

    def test_proposal_requires_actual_negative_memory(self):
        source = m.source_memory(self.ep, self.key)
        source["negative_result_ids"].pop()
        with self.assertRaisesRegex(ValueError, "LESSON"):
            m.propose(source)

    def test_memory_tampering_rejected(self):
        self.ep["history"][0]["negative_evidence"][0]["status"] = "PROVED"
        with self.assertRaisesRegex(ValueError, "CHAIN|HASH"):
            self.packet()

    def test_resigned_wrong_negative_status_is_not_permitted(self):
        entry = self.ep["history"][0]
        entry["negative_evidence"][0]["status"] = "PROVED"
        entry["receipt_sha256"] = spi.seal({
            k:v for k,v in entry.items() if k!="receipt_sha256"})
        self.ep["state_sha256"] = spi.seal({
            k:v for k,v in self.ep.items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "NEGATIVE_CONTROL"):
            self.packet()

    def test_keymaster_unresolved_guard_must_remain(self):
        entry = self.key["history"][0]
        entry["keymaster_guard"] = "AUTO_PROMOTE_MODEL"
        entry["receipt_sha256"] = km.seal({
            k:v for k,v in entry.items() if k!="receipt_sha256"})
        self.key["state_sha256"] = km.seal({
            k:v for k,v in self.key.items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_KEYMASTER"):
            self.packet()

    def test_freeze_from_realistic_pre_event_features_and_baseline(self):
        packet, receipt = self.packet()
        self.assertEqual(receipt["proposed_microkernel_count"], 3)
        self.assertEqual(receipt["prospective_tested_count"], 0)
        self.assertEqual(packet["models"]["train_count"], 198)
        self.assertEqual(packet["models"]["train_workflow_families"], 9)
        self.assertEqual(packet["selected_candidate_id"],
                         "workflow_family_shrinkage_duration")
        self.assertEqual(packet["models"]["candidate"]["alpha"], 12)
        self.assertTrue(m.validate_freeze(packet))
        self.assertFalse(packet["future_labels_used_in_training"])
        self.assertFalse(packet["production_authority"])
        self.assertEqual(packet["freeze_sha256"], m.sha({
            k:v for k,v in packet.items() if k!="freeze_sha256"}))

    def test_train_history_must_be_sufficient(self):
        with self.assertRaisesRegex(ValueError, "TOO_FEW_PRE_FREEZE"):
            m.freeze(self.ep, self.key, self.train[:50],
                     observed_at=FREEZE_TIME, source_commits=self.commits)

    def test_train_families_must_be_diverse(self):
        narrow = [dict(x, workflow_id=100) for x in self.train]
        with self.assertRaisesRegex(ValueError, "TOO_FEW_TRAIN_FAMILIES"):
            m.freeze(self.ep, self.key, narrow,
                     observed_at=FREEZE_TIME, source_commits=self.commits)

    def test_memory_source_must_have_pinned_git_commit(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_MEMORY_GIT_COMMITS"):
            m.freeze(self.ep, self.key, self.train, observed_at=FREEZE_TIME,
                     source_commits={"epistemic":"main","keymaster":"b"*40})

    def test_prepublication_event_cannot_be_scored_as_future(self):
        packet, _ = self.packet()
        receipt = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                             published_at="2026-11-16T00:00:00+00:00")
        self.assertEqual(receipt["status"], "HOLD_AWAITING_FIRST_64_CREATED_RUNS")
        self.assertLess(receipt["future_records_observed"], 64)

    def test_future_unseen_cohort_expected_groupwise_strong_signal(self):
        packet, _ = self.packet()
        report = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                            published_at=PUBLISHED)
        self.assertEqual(report["future_records_observed"], 64)
        self.assertEqual(report["workflow_families"], 8)
        self.assertLess(report["candidate_nll"], report["baseline_nll"])
        self.assertEqual(report["status"], "RESEARCH_PASS_INTERNAL_PROSPECTIVE_PAIRED")
        self.assertFalse(report["production_authority"])
        self.assertFalse(report["model_weights_updated"])
        self.assertFalse(report["scientific_independence_claimed"])

    def test_prefreeze_created_event_completed_after_publication_is_excluded(self):
        packet, _ = self.packet()
        older = run(999, 999, 0, future=True)
        older["id"] = 999888777
        older["created_at"] = "2026-11-14T23:58:00+00:00"
        older["run_started_at"] = "2026-11-15T00:01:00+00:00"
        older["updated_at"] = "2026-11-15T00:01:15+00:00"
        report = m.evaluate(packet, [older] + self.future,
                            observed_at=EXAM_TIME, published_at=PUBLISHED)
        self.assertEqual(report["future_records_observed"], 64)
        self.assertEqual(report["first_future_run_id"], self.future[0]["id"])
        self.assertEqual(report["last_future_run_id"], self.future[-1]["id"])

    def test_no_future_events_returns_hold_without_fabricated_gain(self):
        packet, _ = self.packet()
        receipt = m.evaluate(packet, [], observed_at=EXAM_TIME,
                             published_at=PUBLISHED)
        self.assertEqual(receipt["remaining"], 64)
        self.assertFalse(receipt["model_weights_updated"])
        self.assertNotIn("candidate_nll", receipt)

    def test_exact_first_64_fixed_no_cherry_picking_later(self):
        packet, _ = self.packet()
        bad = [run(i, 100, 0, future=True) for i in range(64)]
        good = [run(i+64, 100+(i%8), (i%8)%3, future=True)
                for i in range(64)]
        report = m.evaluate(packet, bad+good, observed_at=EXAM_TIME,
                            published_at=PUBLISHED)
        self.assertEqual(report["status"], "HOLD_FIXED_FUTURE_FAMILY_CONCENTRATION")
        self.assertEqual(report["workflow_families"], 1)
        self.assertFalse(report["candidate_gain_proven"])
        self.assertNotIn("candidate_nll", report)

    def test_source_run_duplicate_conflict_rejected(self):
        pair = [self.train[0],dict(self.train[0],conclusion="failure")]
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            m.source_rows(pair, FREEZE_TIME)

    def test_exact_duplicate_api_record_deduped(self):
        out = m.source_rows([self.train[0], self.train[0]], FREEZE_TIME)
        self.assertEqual(len(out), 1)

    def test_run_attempt_rerun_not_training_or_future(self):
        packet, _ = self.packet()
        reruns = [dict(x, run_attempt=2) for x in self.future]
        report = m.evaluate(packet, reruns, observed_at=EXAM_TIME,
                            published_at=PUBLISHED)
        self.assertEqual(report["future_records_observed"], 0)

    def test_changed_engine_is_not_same_frozen_candidate(self):
        packet, _ = self.packet()
        packet["engine_sha256"] = "b"*64
        packet["freeze_sha256"] = m.sha({
            k:v for k,v in packet.items() if k!="freeze_sha256"})
        with self.assertRaisesRegex(ValueError, "ENGINE_CHANGED"):
            m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                       published_at=PUBLISHED)

    def test_future_freeze_before_training_forbidden(self):
        packet, _ = self.packet()
        with self.assertRaisesRegex(ValueError, "INVALID_FUTURE"):
            m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                       published_at="2026-11-12T00:00:00+00:00")

    def test_no_frozen_model_hyperparameter_tuning_after_commit(self):
        packet, _ = self.packet()
        packet["models"]["candidate"]["alpha"] = 3
        packet["freeze_sha256"] = m.sha({
            k:v for k,v in packet.items() if k!="freeze_sha256"})
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_DRIFT"):
            m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                       published_at=PUBLISHED)

    def test_family_model_falls_back_on_unseen_workflow(self):
        packet, _ = self.packet()
        base=packet["models"]["baseline"]["prior"]
        cand=packet["models"]["candidate"]
        self.assertEqual(m.probabilities(cand,999999),base)

    def test_negative_memory_not_turned_into_ground_truth(self):
        packet, _ = self.packet()
        self.assertEqual(packet["models"]["baseline"]["operator"],
                         "global_laplace_frequency")
        self.assertEqual(len(packet["candidate_blueprints"]), 3)
        self.assertFalse(packet["automatic_module_activation"])
        self.assertFalse(packet["neural_weights_changed"])
        self.assertFalse(packet["scientific_independence_claimed"])


    def test_early_long_running_job_cannot_be_replaced_by_later_success(self):
        packet, _ = self.packet()
        early = dict(self.future[0], status="in_progress", conclusion=None)
        late = run(64, 101, 1, future=True)
        report = m.evaluate(packet, [early] + self.future[1:] + [late],
                            observed_at=EXAM_TIME, published_at=PUBLISHED)
        self.assertEqual(report["status"], "HOLD_AWAITING_64_FIXED_COHORT_OUTCOMES")
        self.assertEqual(report["future_records_observed"], 64)
        self.assertEqual(report["pending_future_outcomes"], 1)
        self.assertEqual(report["cohort_manifest"]["run_keys"][0]["run_id"], early["id"])
        self.assertEqual(report["cohort_manifest"]["run_keys"][-1]["run_id"],
                         self.future[-1]["id"])
        self.assertNotIn("candidate_nll", report)

    def test_cancelled_early_job_cannot_be_replaced_by_later_success(self):
        packet, _ = self.packet()
        cancelled = dict(self.future[0], status="completed", conclusion="cancelled")
        late = run(64, 101, 1, future=True)
        receipt = m.evaluate(packet, [cancelled] + self.future[1:] + [late],
                             observed_at=EXAM_TIME, published_at=PUBLISHED)
        self.assertEqual(receipt["status"], "HOLD_FIXED_COHORT_UNSCORABLE_TERMINAL")
        self.assertEqual(receipt["invalid_terminal_future_outcomes"], 1)
        self.assertFalse(receipt["candidate_gain_proven"])

    def test_replayed_unchanged_cohort_keys_remain_frozen(self):
        packet, _ = self.packet()
        initial = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                             published_at=PUBLISHED)
        cohort = initial["cohort_manifest"]
        self.assertTrue(m.check_cohort(cohort, packet))
        repeat = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                            published_at=PUBLISHED, cohort=cohort)
        self.assertEqual(repeat["frozen_cohort_sha256"], cohort["cohort_sha256"])

    def test_forged_cohort_hash_rejected(self):
        packet, _ = self.packet()
        receipt = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                             published_at=PUBLISHED)
        cohort = receipt["cohort_manifest"]
        cohort["run_keys"][0]["run_id"] = 101010101
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                       published_at=PUBLISHED, cohort=cohort)

    def test_resigned_wrong_cohort_identity_holds_not_reselect(self):
        packet, _ = self.packet()
        receipt = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                             published_at=PUBLISHED)
        cohort = receipt["cohort_manifest"]
        cohort["run_keys"][0]["run_id"] = 101010101
        cohort["cohort_sha256"] = m.sha({
            k:v for k,v in cohort.items() if k!="cohort_sha256"})
        reply = m.evaluate(packet, self.future, observed_at=EXAM_TIME,
                           published_at=PUBLISHED, cohort=cohort)
        self.assertEqual(reply["status"], "HOLD_GITHUB_FROZEN_COHORT_IDENTITY_DRIFT")
        self.assertNotIn("candidate_nll", reply)

    def test_recent_eight_pages_missing_cutoff_cannot_score(self):
        packet, _ = self.packet()
        rows = [run(i, 100+(i%8), (i%8)%3, future=True)
                for i in range(800)]
        receipt = m.evaluate(packet, rows, observed_at=EXAM_TIME,
                             published_at=PUBLISHED)
        self.assertEqual(receipt["status"],
                         "HOLD_FUTURE_API_LOOKBACK_CANNOT_PROVE_FIRST_RUNS")
        self.assertNotIn("candidate_nll", receipt)


if __name__ == "__main__":
    unittest.main()
