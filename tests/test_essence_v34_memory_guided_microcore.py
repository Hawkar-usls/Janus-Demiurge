"""ESSENCE 3.4 research-only memory-guided prospective microkernel tests."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from tools import essence_v34_memory_guided_microcore as m
from tools import essence_v32_keymaster_memory as km
from tools import essence_v33_epistemic_exchange as ep

NOW = datetime(2026, 11, 14, 22, 0, tzinfo=timezone.utc)
SRC = "a" * 40


def done_run(i, wf, label, *, base=NOW, event="workflow_dispatch"):
    created = base + timedelta(seconds=i * 4)
    secs = [16, 62, 180][label]
    started = created + timedelta(seconds=2)
    updated = started + timedelta(seconds=secs)
    return {
        "id": i + 1,
        "workflow_id": wf,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "event": event,
        "created_at": created.isoformat(),
        "run_started_at": started.isoformat(),
        "updated_at": updated.isoformat(),
    }


def samples(n=240, *, base=NOW-timedelta(days=20), offset=0):
    return [done_run(i+offset, 20000 + i%12, (i%12)%3,
                     base=base, event="push" if i % 2 else "workflow_dispatch")
            for i in range(n)]


def memory_documents():
    real = json.loads((Path(__file__).resolve().parents[1] /
                       "janus_model/state/JANUS_VERIFIED_OUTCOME_MEMORY.json").read_text())
    lessons = km.check_outcomes(real)
    v32 = km.empty_state()
    row = {
        "sequence": 0, "previous_sha256": km.ROOT,
        "evidence_sha256": "a" * 64,
        "source_commit": SRC,
        "donor_count": 8, "verified_local_lessons": len(lessons),
        "keymaster_guard": "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION",
        "training_admission": False, "authority_delta": 0,
    }
    row["receipt_sha256"] = km.seal(row)
    v32["history"] = [row]
    v32["state_sha256"] = km.seal({k:v for k,v in v32.items() if k!="state_sha256"})

    v33 = ep.empty_state()
    entry = {
        "turn": 1, "entity": "JANUS_ESSENCE_EPISTEMIC_EXCHANGE",
        "previous_sha256": ep.ROOT, "source_fingerprint_sha256": "b" * 64,
        "scout_identities": ["SCOUT_%02d" % i for i in range(17)],
        "negative_evidence": [
            {"id": "DOVOD_SHA_25_OF_50_TEST_LEAKAGE",
             "status": "NEGATIVE_CONTROL_CONTAMINATED"},
            {"id": "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114",
             "status": "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"},
            {"id": "KEYMASTER_R2_REPLICATED_ABLATIONS",
             "status": "UNRESOLVED_EIGHT_CONTRIBUTORS"},
        ],
        "constraints_inherited": list(ep.LAWS),
        "decision": "INTEGRATED_LESSON_NOT_ASCENDED",
        "production_authority": False,
    }
    entry["receipt_sha256"] = ep.seal(entry)
    v33["history"] = [entry]
    v33["state_sha256"] = ep.seal({k:v for k,v in v33.items() if k!="state_sha256"})
    return v32, v33, real


def history():
    return m.rows_from_api(samples(), NOW)


def future(base=NOW+timedelta(minutes=5), n=60):
    # use different run ids and new clock; only these can enter the prospective pair
    return m.rows_from_api(
        [done_run(1000+i, 20000+i%12, (i%12)%3,
                  base=base-timedelta(seconds=4*1000),
                  event="push" if i % 2 else "workflow_dispatch") for i in range(n)],
        base + timedelta(minutes=20))


def freeze():
    mems = memory_documents()
    h = history()
    return m.step(m.empty_state(), mems, h, NOW,
                  source_commit=SRC, v32_commit="b"*40, v33_commit="c"*40)


class MemoryGuidedMicrocoreTests(unittest.TestCase):
    def test_actual_verified_outcome_source_and_memory_contract(self):
        mems = memory_documents()
        binding = m.verified_memories(*mems)
        self.assertEqual(len(binding["scout_identities"]), 17)
        self.assertEqual(len(binding["negative_controls"]), 3)
        self.assertEqual(len(binding["source_lesson_record_sha256"]), 64)

    def test_three_real_memory_derived_blueprints(self):
        state, receipt = freeze()
        self.assertEqual(state["status"], "FROZEN_AWAITING_FUTURE")
        self.assertEqual(len(state["pending"]["new_microcore_blueprints"]), 3)
        self.assertEqual(state["pending"]["new_microcore_blueprints"][0]["kind"],
                         "EXECUTABLE_RESEARCH_MICROKERNEL")
        self.assertEqual(state["pending"]["new_microcore_blueprints"][2]["source_control"],
                         m.verified_memories(*memory_documents())["source_lesson_record_sha256"])
        self.assertEqual(state["pending"]["train_count"], 240)
        self.assertFalse(receipt["future_task_labels_seen"])
        self.assertFalse(receipt["production_authority"])
        m.check_state(state)

    def test_memory_missing_dovod_leakage_fails_closed(self):
        mems=list(memory_documents())
        for x in mems[1]["history"][0]["negative_evidence"]:
            if x["id"] == "DOVOD_SHA_25_OF_50_TEST_LEAKAGE":
                x["status"] = "NEGATIVE_CONTROL_CLEAN"
        entry=mems[1]["history"][0]
        entry["receipt_sha256"] = ep.seal({k:v for k,v in entry.items()
                                           if k!="receipt_sha256"})
        mems[1]["state_sha256"] = ep.seal({
            k:v for k,v in mems[1].items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "NEGATIVE_CONTROLS"):
            m.verified_memories(*mems)

    def test_tampered_v32_memory_fails_closed(self):
        mems=list(memory_documents())
        mems[0]["history"][0]["verified_local_lessons"] = 500
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            m.verified_memories(*mems)

    def test_tampered_verified_outcome_cannot_be_training_material(self):
        mems = list(memory_documents())
        mems[2]["records"][0]["positive_feedback"] = False
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            m.verified_memories(*mems)

    def test_freeze_is_deterministic_for_same_data_and_memory(self):
        a, _ = freeze()
        b, _ = freeze()
        self.assertEqual(a, b)
        self.assertEqual(a["pending"]["candidate_sha256"],
                         m.seal({k:v for k,v in a["pending"].items() if k!="candidate_sha256"}))

    def test_historical_frozen_training_has_multiple_workflows_and_labels(self):
        x=history()
        prior=m.count_priors(x)
        self.assertEqual(len(prior["workflow"]), 12)
        self.assertEqual(sum(prior["global"]), 240)
        self.assertGreater(len(prior["event"]), 1)

    def test_histories_are_not_independent_future_tasks(self):
        state, _ = freeze()
        _, report = m.step(state, memory_documents(), history(), NOW + timedelta(minutes=1),
                           published_at=(NOW+timedelta(seconds=5)).isoformat())
        self.assertEqual(report["status"], "HOLD_AWAITING_INDEPENDENT_FUTURE_WORKFLOW_COHORT")
        self.assertEqual(report["created_after_git_publication"], 0)
        self.assertFalse(report["independent_gain_proven"])

    def test_future_replay_after_freeze_and_commit_pairs_same_rows(self):
        state, _ = freeze()
        next_rows=history()+future()
        next_state, report=m.step(
            state, memory_documents(), next_rows,
            NOW+timedelta(minutes=30),
            published_at=(NOW+timedelta(minutes=1)).isoformat())
        self.assertIn(next_state["status"], (
            "EVALUATED_RESEARCH_PASS_NO_PRODUCTION", "EVALUATED_HOLD_NO_CLUSTERED_GAIN"))
        scored=next_state["verdict"]
        self.assertEqual(scored["sample_count"], 60)
        self.assertEqual(scored["workflow_clusters"], 12)
        self.assertTrue(scored["baseline_and_candidate_evaluated_on_exact_same_runs"])
        self.assertFalse(scored["production_authority"])
        self.assertFalse(scored["model_weights_changed"])
        self.assertTrue(scored["created_after_candidate_git_commit"])
        self.assertEqual(len(scored["future_run_ids_sha256"]), 64)
        self.assertFalse(report["automatic_module_admission"])
        m.check_state(next_state)

    def test_no_retraining_after_terminal_verdict(self):
        state, _ = freeze()
        after, _ = m.step(state, memory_documents(), history()+future(),
                          NOW+timedelta(minutes=30),
                          published_at=(NOW+timedelta(minutes=1)).isoformat())
        again, receipt = m.step(after, memory_documents(), history()+future(),
                                NOW+timedelta(minutes=45),
                                published_at=(NOW+timedelta(minutes=1)).isoformat())
        self.assertEqual(after, again)
        self.assertEqual(receipt["status"], "FROZEN_TERMINAL_VERDICT_NO_RETRAIN")

    def test_future_cohort_below_48_stays_pending_without_scoring(self):
        state, _ = freeze()
        same, report=m.step(state, memory_documents(),
                            history()+future(n=24),
                            NOW+timedelta(minutes=30),
                            published_at=(NOW+timedelta(minutes=1)).isoformat())
        self.assertEqual(state, same)
        self.assertEqual(report["created_after_git_publication"], 24)
        self.assertNotIn("comparison", report)

    def test_future_imbalanced_single_family_stays_pending(self):
        state, _ = freeze()
        rows=history()+m.rows_from_api(
            [done_run(1000+i, 22222, i%3,
                      base=NOW+timedelta(minutes=5)-timedelta(seconds=4000))
             for i in range(60)], NOW+timedelta(minutes=30))
        again, report=m.step(state, memory_documents(), rows,
                             NOW+timedelta(minutes=30),
                             published_at=(NOW+timedelta(minutes=1)).isoformat())
        self.assertEqual(again, state)
        self.assertEqual(report["workflow_families"], 1)

    def test_no_premature_scoring_if_candidate_not_git_published(self):
        state, _ = freeze()
        with self.assertRaisesRegex(ValueError, "PUBLICATION_TIME"):
            m.step(state, memory_documents(), history()+future(),
                   NOW+timedelta(minutes=30))

    def test_prepublication_future_samples_not_eligible(self):
        state, _=freeze()
        future_rows=future(base=NOW+timedelta(minutes=5))
        _, report=m.step(state,memory_documents(),history()+future_rows,
                        NOW+timedelta(minutes=30),
                        published_at=(NOW+timedelta(minutes=15)).isoformat())
        self.assertEqual(report["created_after_git_publication"], 0)

    def test_baseline_is_single_frozen_global_prior(self):
        model=m.count_priors(history())
        first=m.predict(model, history()[0], use_memory=False)
        second=m.predict(model, history()[1], use_memory=False)
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(first), 1)

    def test_candidate_is_workflow_conditioned_not_overwritten_by_future(self):
        model=m.count_priors(history())
        a=m.predict(model,history()[0],use_memory=True)
        b=m.predict(model,history()[1],use_memory=True)
        self.assertNotEqual(a,b)
        self.assertAlmostEqual(sum(a),1)

    def test_identical_pagination_observation_deduped(self):
        raw=samples(n=160)
        rows=m.rows_from_api(raw+[copy.deepcopy(raw[0])],NOW)
        self.assertEqual(len(rows),160)

    def test_conflicting_pagination_observation_fails_closed(self):
        raw=samples(n=160)
        corrupt=copy.deepcopy(raw[0])
        corrupt["updated_at"]=(m.utc(corrupt["updated_at"])+timedelta(seconds=20)).isoformat()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RUN_MUTATED"):
            m.rows_from_api(raw+[corrupt],NOW)

    def test_run_attempt_two_and_open_runs_excluded(self):
        raw=samples(n=160)
        raw[0]["run_attempt"]=2
        raw[1]["status"]="in_progress"
        self.assertEqual(len(m.rows_from_api(raw,NOW)),158)

    def test_future_training_label_leakage_guard(self):
        state,_=freeze()
        state["pending"]["frozen_training_prior"]["global"][0]+=1000
        state["state_sha256"]=m.seal({k:v for k,v in state.items() if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError, "CANDIDATE_FREEZE_CONTRACT_BROKEN"):
            m.check_state(state)

    def test_state_hash_tamper(self):
        state,_=freeze()
        state["status"]="EVALUATED_RESEARCH_PASS_NO_PRODUCTION"
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            m.check_state(state)

    def test_memory_only_does_not_prove_independent_gain(self):
        _,receipt=freeze()
        self.assertIs(receipt["independent_gain_proven"],False)
        self.assertIs(receipt["external_independent_replication"],False)

    def test_zero_untrusted_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_HISTORICAL"):
            m.count_priors(history()[:10])

    def test_explicit_memory_commit_sha_required(self):
        with self.assertRaisesRegex(ValueError,"UNPINNED_GIT_COMMIT"):
            m.freeze(m.verified_memories(*memory_documents()),history(),NOW,
                     source_commit=SRC,v32_commit="main",v33_commit="c"*40)

    def test_actual_manifest_root_is_still_inert(self):
        root=json.loads((Path(__file__).resolve().parents[1] /
                         ".janus/essence/manifest.json").read_text())
        self.assertIs(root["enabled"],False)
        self.assertEqual(root["birth_policy"],"PROPOSAL_ONLY")
        self.assertFalse(any(root["capabilities"].values()))


if __name__ == "__main__":
    unittest.main()
