"""SENTINEL fault-injection and fail-closed scheduling tests (synthetic only)."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from tools import sentinel_core as s


NOW=dt.datetime(2026,11,15,12,0,tzinfo=dt.timezone.utc)
def row(rid,minutes,success=True,status="completed"):
    return {"id":rid,"created":s.to_iso(NOW-dt.timedelta(minutes=minutes)),
            "status":status,
            "conclusion":"success" if success else "failure" if status=="completed" else None,
            "event":"schedule","run_attempt":1}
def base():
    return {"schema":s.STATE,"epoch":0,"last_dispatch":{},
            "authority":"BOUNDED_GITHUB_ACTIONS_ONLY",
            "production_model_updates":False,"policy_source":"main"}
def inventory(a=8,b=10,c=12,worker=8):
    return {key:[row(i*100+1,minutes),row(i*100+2,240)]
            for i,(key,minutes) in
            enumerate((("A",a),("B",b),("C",c),("WORKER",worker)),1)}


class SentinelTest(unittest.TestCase):
    def test_real_github_pr_branch_is_ignored_before_trusted_main_checks(self):
        def fetch(path,token):
            self.assertTrue(path.endswith("sentinel-node-a.yml/runs?per_page=8"))
            return {"workflow_runs":[
                {"id":90,"event":"pull_request","head_branch":"research/sentinel",
                 "created_at":"2026-11-15T11:50:00Z",
                 "status":"completed","conclusion":"success","run_attempt":1,
                 "workflow_id":123},
                {"id":91,"event":"push","head_branch":"main",
                 "created_at":"2026-11-15T11:45:00Z",
                 "status":"completed","conclusion":"success","run_attempt":1,
                 "workflow_id":123}
            ]}
        rows=s.runs("A","synthetic-token",fetch=fetch)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["id"],91)
        self.assertEqual(rows[0]["workflow_id"],123)

    def test_nodes_identical_allowlist_and_roles(self):
        self.assertEqual(s.TARGETS["A"],("B","C","WORKER"))
        self.assertEqual(s.TARGETS["B"],("A","C","WORKER"))
        self.assertEqual(s.TARGETS["C"],("A","B"))
        self.assertEqual(len(set(s.ROLES.values())),3)
        self.assertEqual(len(set(s.TARGET_FILE.values())),4)

    def test_all_healthy_no_rescue_even_high_risk(self):
        d=s.decide("A","991",NOW,inventory(),base(),pending=2,
                   model={"risk_failure":.999})
        self.assertIsNone(d["target"])
        self.assertEqual(d["decision"],"OBSERVE_ONLY")
        self.assertFalse(d["model_has_dispatch_authority"])

    def test_b_recovers_failed_a_when_c_is_also_healthy(self):
        d=s.decide("B","991",NOW,inventory(a=90),base())
        self.assertEqual(d["target"],"A")
        self.assertEqual(d["target_last_run_id"],101)

    def test_a_takes_over_b_on_missed_wake(self):
        d=s.decide("A","991",NOW,inventory(b=95),base())
        self.assertEqual(d["target"],"B")

    def test_c_fences_once_when_both_a_and_b_stale(self):
        d=s.decide("C","991",NOW,inventory(a=90,b=110),base())
        self.assertIn(d["target"],("A","B"))
        self.assertEqual(d["recovery_actions_at_most_one"],True)
        updated=s.claim(base(),d)
        self.assertEqual(updated["epoch"],1)
        self.assertEqual(len(updated["last_dispatch"]),1)

    def test_healthy_a_or_b_recovers_c(self):
        for role in ("A","B"):
            d=s.decide(role,"991",NOW,inventory(c=90),base())
            self.assertEqual(d["target"],"C")

    def test_never_before_healthy_workflow_is_unknown_not_auto_dispatch(self):
        ins=inventory()
        ins["A"]=[]
        ins["B"]=[]
        d=s.decide("C","991",NOW,ins,base())
        self.assertEqual(d["statuses"]["A"]["status"],
                         "UNKNOWN_NO_OBSERVATIONS")
        self.assertIsNone(d["target"])

    def test_unfinished_target_run_is_busy_no_recursion(self):
        ins=inventory(b=100)
        ins["B"].insert(0,row(999999,3,status="in_progress"))
        d=s.decide("A","991",NOW,ins,base())
        self.assertIsNone(d["target"])

    def test_failed_recent_target_gets_grace(self):
        ins=inventory()
        ins["C"][0]=row(315,3,success=False)
        d=s.decide("A","991",NOW,ins,base())
        self.assertIsNone(d["target"])
        ins["C"][0]=row(315,15,success=False)
        d2=s.decide("A","991",NOW,ins,base())
        self.assertEqual(d2["target"],"C")

    def test_lease_epoch_cas_and_cooldown(self):
        d=s.decide("A","991",NOW,inventory(c=90),base())
        newest=s.claim(base(),d)
        self.assertTrue(s.claimed("C","A","991",1,newest))
        self.assertFalse(s.claimed("C","B","991",1,newest))
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_RECOVERY_CLAIM"):
            s.claim(newest,d)
        d2=s.decide("B","992",NOW+dt.timedelta(minutes=15),
                    inventory(c=100),newest)
        self.assertIsNone(d2["target"])

    def test_recovery_claim_fails_closed_for_forged_unknown_target(self):
        d=s.decide("A","991",NOW,inventory(b=95),base())
        d["target"]="outside-repository-agent"
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_RECOVERY_CLAIM"):
            s.claim(base(),d)

    def test_model_risk_never_expands_allowed_targets(self):
        ins=inventory()
        no_model=s.decide("A","991",NOW,ins,base(),model=None)
        with_model=s.decide("A","991",NOW,ins,base(),
                           model={"risk":1.0,"request":"delete repo"})
        self.assertEqual(no_model["target"],with_model["target"])
        self.assertFalse(with_model["production_model_updates"])

    def test_worker_is_woken_only_when_pending_and_stale(self):
        ins=inventory(worker=80)
        self.assertIsNone(s.decide("A","991",NOW,ins,base(),pending=0)["target"])
        self.assertEqual(s.decide("B","991",NOW,ins,base(),pending=1)["target"],
                         "WORKER")
        self.assertIsNone(s.decide("C","991",NOW,ins,base(),pending=2)["target"])

    def test_dispatch_same_repo_one_explicit_workflow_and_never_unclaimed(self):
        d=s.decide("A","991",NOW,inventory(c=90),base())
        sent=[]
        def fake(path,token,post=None):
            sent.append((path,post))
            if path.endswith("/runs?per_page=8"):
                # return the same oldest observed target C run as at plan
                return {"workflow_runs":[{
                    "id":d["target_last_run_id"],"created_at":s.to_iso(
                         NOW-dt.timedelta(minutes=90)),
                    "event":"schedule","status":"completed",
                    "conclusion":"success","head_branch":"main",
                    "run_attempt":1}]}
            return {"accepted":True,"status":204}
        with self.assertRaisesRegex(ValueError,"RECOVERY_CLAIM_NOT_OWNED"):
            s.dispatch(d,base(),"test-token-that-is-long",fetch=fake)
        granted=s.claim(base(),d)
        result=s.dispatch(d,granted,"test-token-that-is-long",fetch=fake)
        self.assertEqual(result["status"],204)
        self.assertEqual(sent[-1][0],
                         "/actions/workflows/sentinel-node-c.yml/dispatches")
        self.assertEqual(sent[-1][1],{"ref":"main","inputs":{"recovery_only":"true"}})
        self.assertEqual(len([x for x in sent if x[1] is not None]),1)

    def test_new_target_run_appearing_between_claim_and_dispatch_aborts(self):
        d=s.decide("A","991",NOW,inventory(c=90),base())
        def fake(path,token,post=None):
            if path.endswith("/runs?per_page=8"):
                return {"workflow_runs":[{
                   "id":d["target_last_run_id"]+1,
                   "created_at":s.to_iso(NOW-dt.timedelta(minutes=2)),
                   "event":"workflow_dispatch","status":"in_progress",
                   "conclusion":None,"head_branch":"main",
                   "run_attempt":1}]}
            raise AssertionError("No recovery dispatch")
        with self.assertRaisesRegex(ValueError,"NEWER_RUN_ABORT"):
            s.dispatch(d,s.claim(base(),d),"test-token-long",fetch=fake)

    def test_shared_github_outage_is_not_claimed_resilient(self):
        ins={k:[] for k in s.TARGET_FILE}
        d=s.decide("C","991",NOW,ins,base())
        self.assertEqual(d["decision"],"OBSERVE_ONLY")
        self.assertFalse(d["production_model_updates"])

    def test_file_overwrite_and_wrong_state_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"evidence.json"
            s.immutable(p,{"a":1})
            with self.assertRaisesRegex(ValueError,"NO_OVERWRITE_RECEIPT"):
                s.immutable(p,{"a":2})
        broken=base()
        broken["production_model_updates"]=True
        with self.assertRaisesRegex(ValueError,"SENTINEL_RECOVERY_STATE_INVALID"):
            s.state_check(broken)


if __name__=="__main__":
    unittest.main()
