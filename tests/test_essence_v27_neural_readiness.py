"""ESSENCE v2.7 stdlib-only test battery for prospective GitHub readiness."""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
import copy
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import essence_v27_neural_readiness as r


class GitHubFutureReadiness(unittest.TestCase):
    def setUp(self):
        self.old=datetime(2026,11,11,9,tzinfo=timezone.utc)
        self.freeze=datetime(2026,11,14,17,8,tzinfo=timezone.utc)
        self.published=self.freeze+timedelta(seconds=16)
        self.now=self.freeze+timedelta(hours=4)
        self.historical=[self.one(i,self.old+timedelta(minutes=2*i),i%3)
                         for i in range(220)]
        self.future=[self.one(i+220,self.published+timedelta(minutes=i+1),i%3)
                     for i in range(49)]
        self.state=self.state_fixture()

    def one(self,i,created,label):
        started=created+timedelta(seconds=2)
        span=(15,62,201)[label]
        return {"id":100000+i,"workflow_id":2000+i%30,
            "head_branch":"main","run_attempt":1,"status":"completed",
            "conclusion":"success","event":"schedule",
            "created_at":created.isoformat(),
            "run_started_at":started.isoformat(),
            "updated_at":(started+timedelta(seconds=span)).isoformat()}

    def state_fixture(self):
        s={"schema":r.NEURAL_SCHEMA,"generation":0,"parent":{},
           "pending":{"status":"FROZEN_AWAITING_GITHUB_FUTURE",
                      "sealed_before":self.freeze.isoformat(),
                      "parent_sha256":"a"*64,"challenger_sha256":"b"*64},
           "history":[],"research_only":True,
           "production_authority":False}
        s["state_sha256"]=r.sealed(s)
        return s

    def report(self,state=None,raw=None):
        return r.readiness(self.state if state is None else state,
                           self.historical+self.future if raw is None else raw,
                           self.published,self.now)

    def test_only_one_postfreeze_job_must_hold_without_torch(self):
        outcome=self.report(raw=self.historical+self.future[:1])
        self.assertEqual(outcome["status"],"HOLD_NEED_MORE_POSTFREEZE_RUNS")
        self.assertEqual(outcome["completed_after_frozen_git_commit"],1)
        self.assertFalse(outcome["eligible"])

    def test_48_later_varied_real_run_shapes_make_exam_eligible(self):
        outcome=self.report()
        self.assertEqual(outcome["status"],"READY_PROSPECTIVE_NEURAL_EXAM")
        self.assertTrue(outcome["eligible"])
        self.assertEqual(outcome["completed_after_frozen_git_commit"],49)
        self.assertNotIn("labels",outcome)
        self.assertFalse(outcome["production_authority"])

    def test_future_cohort_cannot_be_single_class(self):
        future=[self.one(i+220,self.published+timedelta(minutes=i+1),0)
                for i in range(60)]
        outcome=self.report(raw=self.historical+future)
        self.assertEqual(outcome["status"],"HOLD_LOW_INFORMATION_FUTURE_COHORT")

    def test_precommit_rows_cannot_count_as_postfreeze(self):
        old=[self.one(i+5000,self.freeze+timedelta(seconds=i),i%3)
             for i in range(8)]
        outcome=self.report(raw=self.historical+old+self.future[:40])
        self.assertEqual(outcome["completed_after_frozen_git_commit"],40)
        self.assertEqual(outcome["status"],"HOLD_NEED_MORE_POSTFREEZE_RUNS")

    def test_parent_history_needs_new_runs_before_next_trial(self):
        state=copy.deepcopy(self.state)
        state["pending"]=None
        state["history"]=[{"accepted":False,
            "independent_future_verification":{
              "last_new_created_at":self.future[24]["created_at"]}}]
        state["state_sha256"]=r.sealed({k:v for k,v in state.items()
                                       if k!="state_sha256"})
        outcome=self.report(state=state,raw=self.historical+self.future[:45])
        self.assertEqual(outcome["status"],"HOLD_RETRAIN_REQUIRES_NEW_HISTORY")
        self.assertEqual(outcome["new_runs_since_previous_trial"],20)
        outcome=self.report(state=state)
        self.assertEqual(outcome["status"],"READY_TO_TRAIN_RESEARCH_CHALLENGER")

    def test_bad_receipt_or_future_commit_time_fails_closed(self):
        state=copy.deepcopy(self.state)
        state["generation"]=3
        with self.assertRaisesRegex(ValueError,"INVALID_SEALED_NEURAL_STATE"):
            self.report(state=state)
        with self.assertRaisesRegex(ValueError,"STATE_PUBLISHED_IN_FUTURE"):
            r.readiness(self.state,self.historical+self.future,
                        self.now+timedelta(minutes=1),self.now)

    def test_unfinished_and_untrusted_runs_not_counted(self):
        invalid=copy.deepcopy(self.future[0])
        invalid["id"]=999999
        invalid["status"]="in_progress"
        out=self.report(raw=self.historical+self.future[:1]+[invalid])
        self.assertEqual(out["completed_after_frozen_git_commit"],1)

    def test_unique_future_history_window_required(self):
        newer=[self.one(i+900,self.published+timedelta(minutes=i+1),i%3)
               for i in range(48)]
        # Fill the 800 item API window entirely with later runs: no
        # evidence that the parent cutoff is still covered.
        raw=[self.one(i+1000,self.published+timedelta(seconds=i*15+1),i%3)
             for i in range(800)]
        outcome=self.report(raw=raw)
        self.assertEqual(outcome["status"],"HOLD_GITHUB_HISTORY_TRUNCATED")


if __name__=="__main__":
    unittest.main()
