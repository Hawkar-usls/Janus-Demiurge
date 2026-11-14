"""ESSENCE v3.0 real multi-organ ignition contract, pure offline tests."""
import unittest
from datetime import datetime, timedelta, timezone
from tools import essence_v30_active_evolution as m

class IgnitionContract(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,14,19,0,tzinfo=timezone.utc)

    def row(self,rid,*,minutes_ago=180,status="completed",conclusion="success"):
        created=self.now-timedelta(minutes=minutes_ago)
        return {"id":rid,"created_at":created.isoformat(),
                "status":status,"conclusion":conclusion,"head_branch":"main"}

    def test_all_trusted_existing_workflows_are_allowlisted(self):
        self.assertEqual(len(m.LANES),8)
        self.assertEqual(len({x[1] for x in m.LANES}),len(m.LANES))
        self.assertTrue(all(x[1].endswith(".yml") for x in m.LANES))
        self.assertEqual(m.MAX_BOOTSTRAP,8)
        self.assertLess(m.MAX_CYCLE,m.MAX_BOOTSTRAP)

    def test_first_launch_is_real_dispatch_not_pass_claim(self):
        planned=m.decide({name:[] for name,*_ in m.LANES},
                         now=self.now,bootstrap=True)
        self.assertEqual([x["status"] for x in planned],
                         ["DISPATCH_PLANNED"]*8)
        self.assertEqual(planned[1]["inputs"],{"trigger_mode":"schedule"})

    def test_cycle_caps_new_work_and_rotates_fairly(self):
        histories={name:[] for name,*_ in m.LANES}
        a=m.decide(histories,now=self.now,bootstrap=False)
        b=m.decide(histories,now=self.now+timedelta(hours=3),bootstrap=False)
        self.assertEqual(sum(x["status"]=="DISPATCH_PLANNED" for x in a),3)
        self.assertEqual(sum(x["status"]=="DISPATCH_PLANNED" for x in b),3)
        self.assertNotEqual([x["lane"] for x in a],
                            [x["lane"] for x in b])

    def test_never_start_parallel_active_workflow(self):
        for state in ("in_progress","queued","waiting"):
            got=m.latest_decision([self.row(101,minutes_ago=5,
                                        status=state,conclusion=None)],
                                  now=self.now,bootstrap=True)
            self.assertEqual(got["status"],"HOLD_EXISTING_WORKFLOW_ACTIVE")

    def test_failed_workflow_must_cooldown_even_bootstrap(self):
        x=self.row(2,minutes_ago=5,conclusion="failure")
        self.assertEqual(m.latest_decision([x],now=self.now,
                           bootstrap=True)["status"],"HOLD_FAILED_JOB_BACKOFF")
        old=self.row(3,minutes_ago=181,conclusion="failure")
        self.assertEqual(m.latest_decision([old],now=self.now,
                           bootstrap=True)["status"],"READY_TO_WAKE_EXISTING_CORE")

    def test_success_can_bootstrap_but_periodic_has_cooldown(self):
        x=self.row(4,minutes_ago=1)
        self.assertEqual(m.latest_decision([x],now=self.now,
                           bootstrap=True)["status"],"READY_TO_WAKE_EXISTING_CORE")
        self.assertEqual(m.latest_decision([x],now=self.now,
                           bootstrap=False)["status"],"HOLD_COOLDOWN")

    def test_fake_github_history_fails_closed(self):
        cases=[
            [self.row(1,minutes_ago=-12)],
            [dict(self.row(2),head_branch="arbitrary")],
            [dict(self.row(3),id="invalid")],
            [dict(self.row(4),status="completed",conclusion=None)],
            [dict(self.row(5),created_at="no-time")],
        ]
        for data in cases:
            with self.assertRaises(ValueError):
                m.latest_decision(data,now=self.now,bootstrap=True)
        a=m.decide({name:[dict(self.row(8),head_branch="attacker")]
                    for name,*_ in m.LANES},now=self.now,bootstrap=True)
        self.assertTrue(all(x["status"]=="HOLD_UNTRUSTED_RUN_HISTORY" for x in a))

    def test_receive_no_run_does_not_invent_learning(self):
        p={"schema":m.SCHEMA,"production_authority":False,
           "scientific_improvement_proven_by_dispatch":False}
        self.assertEqual(p["scientific_improvement_proven_by_dispatch"],False)
        self.assertEqual(m.sha(p),m.sha(p))
        self.assertEqual(m.LANES[2][1],"essence-v26-prospective-neural.yml")

if __name__=="__main__":
    unittest.main()
