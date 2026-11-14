"""Research-only prospective weight inheritance contract, no GH writes."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import copy
import math
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import essence_v26_neural_prospective as n


def row(i,when,label):
    return {"id":100000+i,"workflow_id":1001+label+3*((i//3)%5),
            "event":"schedule" if i%2 else "workflow_dispatch",
            "created_at":when.isoformat(),"label":label,
            "elapsed_seconds":12 if label==0 else 60 if label==1 else 180}


class ProspectiveNeuralContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t0=datetime(2026,11,10,tzinfo=timezone.utc)
        cls.past=[row(i,cls.t0+timedelta(minutes=i),i%3) for i in range(240)]
        cls.freeze=cls.t0+timedelta(days=2)
        cls.future=[row(i+240,cls.freeze+timedelta(minutes=i+1),i%3)
                    for i in range(75)]
        cls.initial=n.empty()
        cls.frozen,cls.first=n.step(cls.initial,cls.past,cls.freeze)
        assert cls.frozen["pending"] is not None,cls.first

    def test_torch_gradients_produce_frozen_distinct_tensor(self):
        p=self.frozen["pending"]
        self.assertNotEqual(p["parent_sha256"],p["challenger_sha256"])
        self.assertEqual(p["parent_sha256"],n.seal(self.frozen["parent"]))
        self.assertEqual(p["challenger_sha256"],n.seal(p["challenger"]))
        self.assertEqual(p["training"]["true_gradient_updates"],45)
        self.assertLess(p["training"]["historical_child_nll"],
                        p["training"]["historical_parent_nll"])
        self.assertFalse(self.frozen["production_authority"])

    def test_future_wait_does_not_retrain_or_evaluate_old_history(self):
        next_state,verdict=n.step(self.frozen,self.past,
                                 self.freeze+timedelta(minutes=5))
        self.assertEqual(verdict["status"],"HOLD_FUTURE_COHORT_NOT_YET_DIVERSE")
        self.assertEqual(next_state["state_sha256"],self.frozen["state_sha256"])

    def test_actual_frozen_weights_score_later_unseen_cohort(self):
        completed=sorted(self.past+self.future,key=lambda x:x["created_at"])
        result=n.future_decision(self.frozen["pending"],
                                 n.load_state(self.frozen["parent"]),
                                 completed,self.freeze+timedelta(days=1))[0]
        self.assertEqual(result["status"],"PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN")
        self.assertEqual(result["sample_count"],75)
        self.assertTrue(result["improvement_proven_under_registered_internal_thresholds"])
        self.assertGreater(result["paired_one_sided_95pct_lower_bound"],0.0)
        self.assertGreaterEqual(result["workflow_clusters"],8)
        self.assertGreater(result["cluster_conservative_lower_bound"],0)
        self.assertGreaterEqual(result["positive_workflow_fraction"],0.625)
        next_state,receipt=n.step(self.frozen,completed,
                                 self.freeze+timedelta(days=1))
        self.assertEqual(next_state["generation"],1)
        self.assertTrue(next_state["history"][-1]["accepted"])
        proof=next_state["history"][-1]["independent_future_verification"]
        self.assertEqual(proof["receipt_sha256"],n.seal({
            k:v for k,v in proof.items() if k!="receipt_sha256"}))
        self.assertEqual(next_state["history"][-1]["parent_sha256"],
                         self.frozen["pending"]["parent_sha256"])
        self.assertEqual(n.seal(next_state["parent"]),
                         self.frozen["pending"]["challenger_sha256"])
        if next_state["pending"] is not None:
            self.assertGreater(n.at(next_state["pending"]["sealed_before"]),
                               n.at(self.frozen["pending"]["sealed_before"]))
            self.assertEqual(next_state["pending"]["parent_sha256"],
                             n.seal(next_state["parent"]))
        else:
            # A near-perfect inherited model must not invent a gradient gain
            # merely to continue the cycle. The accepted weights are preserved.
            self.assertEqual(next_state["status"],"RESEARCH_GEN1_ACCEPTED")
            self.assertEqual(receipt["receipt_sha256"],n.seal({
                k:v for k,v in receipt.items() if k!="receipt_sha256"}))

    def test_mismatched_child_or_seal_fails_closed(self):
        for k in ("challenger_sha256","parent_sha256"):
            corrupted=copy.deepcopy(self.frozen)
            corrupted["pending"][k]="b"*64
            corrupted["state_sha256"]=n.seal({k:v for k,v in corrupted.items()
                                              if k!="state_sha256"})
            with self.assertRaisesRegex(ValueError,
                                        "MUTATED_PARENT_CHILD_STATE_BINDING"):
                n.check(corrupted)
        corrupted=copy.deepcopy(self.frozen)
        corrupted["parent"]["0.weight"]["values"][0]=float("nan")
        corrupted["state_sha256"]="bad"
        with self.assertRaises(ValueError):
            n.check(corrupted)

    def test_no_future_but_new_repo_history_rejected(self):
        candidate=copy.deepcopy(self.frozen)
        new_rows=[row(1000+i,self.freeze+timedelta(minutes=i+1),0)
                  for i in range(80)]
        result=n.future_decision(candidate["pending"],
            n.load_state(candidate["parent"]),
            self.past+new_rows,self.freeze+timedelta(days=1))[0]
        self.assertEqual(result["status"],"HOLD_FUTURE_COHORT_NOT_YET_DIVERSE")

    def test_future_window_truncated_fail_closed(self):
        later=[row(800+i,self.freeze+timedelta(minutes=i+1),i%3)
               for i in range(200)]
        state,v=n.step(self.frozen,later,self.freeze+timedelta(days=1))
        self.assertEqual(v["status"],"HOLD_FUTURE_HISTORY_WINDOW_EXPIRED")
        self.assertEqual(state["state_sha256"],self.frozen["state_sha256"])

    def test_source_does_not_expose_duration_or_outcome_to_features(self):
        a=copy.deepcopy(self.past[0])
        b=copy.deepcopy(a)
        b["label"]=2
        b["elapsed_seconds"]=2000
        xa,ya=n.features([a])
        xb,yb=n.features([b])
        self.assertTrue((xa==xb).all().item())
        self.assertNotEqual(ya.item(),yb.item())

    def test_timestamps_and_labels_from_completed_successful_runs(self):
        t=self.freeze
        def sample(i,duration,conclusion="success",status="completed"):
            started=t+timedelta(seconds=i*200)
            return {"id":i+1,"workflow_id":1001,"event":"schedule",
                    "run_attempt":1,"head_branch":"main","status":status,
                    "conclusion":conclusion,
                    "created_at":started.isoformat(),
                    "run_started_at":started.isoformat(),
                    "updated_at":(started+timedelta(seconds=duration)).isoformat()}
        arr=n.source_rows([sample(1,15),sample(2,50),sample(3,400),
                          sample(4,22,status="in_progress"),
                          sample(5,20,conclusion="cancelled")],
                          t+timedelta(days=1))
        self.assertEqual([x["label"] for x in arr],[0,1,2])
        self.assertTrue(all("conclusion" not in x for x in arr))

    def test_repetitions_of_three_workflows_are_not_independent(self):
        rows=[]
        for i in range(75):
            item=row(i+300,self.freeze+timedelta(minutes=i+1),i%3)
            item["workflow_id"]=7000+i%3
            rows.append(item)
        result,child=n.future_decision(self.frozen["pending"],
            n.load_state(self.frozen["parent"]),self.past+rows,
            self.freeze+timedelta(days=1))
        self.assertEqual(result["status"],"HOLD_FUTURE_WORKFLOW_CLUSTER_INFORMATION")
        self.assertEqual(result["distinct_workflows"],3)
        self.assertIsNone(child)

    def test_only_post_publication_github_runs_are_scored(self):
        # Weights were frozen in memory at freeze; Git did not publish them
        # until 15 minutes later. These earlier jobs are NOT future evidence.
        published=self.freeze+timedelta(minutes=15)
        observed=self.past+self.future
        result=n.future_decision(self.frozen["pending"],
            n.load_state(self.frozen["parent"]),observed,
            self.freeze+timedelta(days=1),published_at=published.isoformat())[0]
        self.assertEqual(result["sample_count"],60)
        self.assertTrue(result["future_records_created_after_weights_git_commit"])
        self.assertGreater(n.at(result["first_new_created_at"]),published)

    def test_unpublished_future_time_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PUBLISHED_STATE_TIME"):
            n.future_decision(self.frozen["pending"],
                n.load_state(self.frozen["parent"]),self.past+self.future,
                self.freeze+timedelta(minutes=1),
                published_at=(self.freeze+timedelta(hours=3)).isoformat())

    def failed_state(self):
        trial=copy.deepcopy(self.frozen)
        # A deliberately non-improving challenger has exactly the same
        # weights as the parent; do not claim it is a real improvement.
        trial["pending"]["challenger"]=copy.deepcopy(trial["parent"])
        trial["pending"]["challenger_sha256"]=n.seal(trial["parent"])
        trial["state_sha256"]=n.seal({k:v for k,v in trial.items()
                                      if k!="state_sha256"})
        return trial

    def test_failed_future_trial_cannot_automatically_retry_same_cohort(self):
        trial=self.failed_state()
        rows=sorted(self.past+self.future,key=lambda x:x["created_at"])
        completed,decision=n.step(trial,rows,self.freeze+timedelta(days=1))
        self.assertEqual(decision["status"],"HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN")
        self.assertEqual(completed["generation"],0)
        self.assertIsNone(completed["pending"])
        self.assertFalse(completed["history"][-1]["accepted"])
        self.assertEqual(completed["history"][-1]["consecutive_accepted_generations"],0)
        v=completed["history"][-1]["independent_future_verification"]
        self.assertEqual(v["receipt_sha256"],n.seal({k:x for k,x in v.items()
                                                 if k!="receipt_sha256"}))
        replay,why=n.step(completed,rows,self.freeze+timedelta(days=1,hours=1))
        self.assertEqual(why["status"],"HOLD_RETRAIN_REQUIRES_NEW_HISTORY")
        self.assertEqual(replay["state_sha256"],completed["state_sha256"])

    def test_rejected_trial_requires_an_additional_24_new_complete_runs(self):
        rows=sorted(self.past+self.future,key=lambda x:x["created_at"])
        stopped,_=n.step(self.failed_state(),rows,
                         self.freeze+timedelta(days=1))
        additional=[row(900+i,self.freeze+timedelta(days=1,minutes=i+1),i%3)
                    for i in range(24)]
        _,verdict=n.step(stopped,sorted(rows+additional,
            key=lambda x:x["created_at"]),self.freeze+timedelta(days=2))
        self.assertEqual(verdict["status"],"RETRAIN_ALLOWED_AFTER_NEW_HISTORY")

    def test_only_contiguous_hash_linked_future_gains_count_toward_two(self):
        def accepted(parent,child):
            proof={"status":"PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN",
                "improvement_proven_under_registered_internal_thresholds":True,
                "future_records_created_after_weights_git_commit":True,
                "clustered_prospective_gate_version":"2.8",
                "workflow_clusters":15,
                "largest_workflow_fraction":0.10,
                "cluster_conservative_lower_bound":0.04,
                "positive_workflow_fraction":0.80,
                "training_saw_future_labels":False,
                "production_authority":False,
                "frozen_parent_sha256":parent,
                "frozen_child_sha256":child}
            proof["receipt_sha256"]=n.seal(proof)
            return {"accepted":True,"parent_sha256":parent,
                    "child_sha256":child,
                    "independent_future_verification":proof}
        a=accepted("a"*64,"b"*64)
        b=accepted("b"*64,"c"*64)
        failure={"accepted":False,"independent_future_verification":{
            "status":"HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"}}
        self.assertEqual(n.consecutive_accepted([a,b]),2)
        self.assertEqual(n.consecutive_accepted([a,failure,b]),1)
        bogus=copy.deepcopy(b)
        bogus["child_sha256"]="d"*64
        with self.assertRaisesRegex(ValueError,
                                    "UNVERIFIED_ACCEPTED_NEURAL_GENERATION"):
            n.consecutive_accepted([a,bogus])
        wrong_parent=accepted("e"*64,"f"*64)
        with self.assertRaisesRegex(ValueError,
                                    "UNVERIFIED_ACCEPTED_NEURAL_GENERATION"):
            n.consecutive_accepted([a,wrong_parent])

    def test_no_synthetic_pass_can_claim_external_custodian(self):
        completed=self.past+self.future
        result=n.future_decision(self.frozen["pending"],
            n.load_state(self.frozen["parent"]),completed,
            self.freeze+timedelta(days=1))[0]
        self.assertFalse(result["external_custodian"])
        self.assertFalse(result["production_authority"])
        self.assertFalse(result["training_saw_future_labels"])


if __name__=="__main__":
    unittest.main()
