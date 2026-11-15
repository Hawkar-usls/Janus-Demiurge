"""SENTINEL cron evidence gate fixtures. Synthetic tests never prove real uptime."""
from datetime import datetime,timezone,timedelta
import copy
import unittest

from tools import sentinel_cadence_audit as a

NOW=datetime(2026,11,16,18,0,tzinfo=timezone.utc)
ACTIVATED=NOW-timedelta(hours=25)


def sample():
    out={}
    for i,role in enumerate(a.FILES):
        # Realistic 15-minute stagger, 96 events in the last full day.
        events=[]
        for k in range(96):
            when=NOW-timedelta(hours=24)+timedelta(minutes=3+i*5+15*k)
            events.append({"id":1000+i*1000+k,
                "event":"schedule","head_branch":"main",
                "created_at":when.isoformat(),
                "status":"completed","conclusion":"success"})
        out[role]=events
    return out


class RealCronAuditGate(unittest.TestCase):
    def test_three_genuine_24h_windows_pass(self):
        r=a.evaluate(sample(),NOW,ACTIVATED)
        self.assertEqual(r["status"],"PASS_REAL_GITHUB_24H_CRON_DELIVERY")
        self.assertEqual(set(r["nodes"]),{"A","B","C"})
        self.assertTrue(r["only_schedule_events"])
        self.assertFalse(r["production_authority"])
        self.assertEqual(len(r["receipt_sha256"]),64)

    def test_early_policy_deployment_never_claims_24h(self):
        r=a.evaluate(sample(),NOW,NOW-timedelta(minutes=30))
        self.assertEqual(r["status"],"HOLD_WAIT_FOR_24H_AFTER_DEPLOY")

    def test_missed_heartbeats_fail_even_with_misleading_push_successes(self):
        data=sample()
        data["B"]=data["B"][:72]
        for idx in range(100):
            data["B"].append({"id":900000+idx,"event":"push",
                "head_branch":"main","created_at":NOW.isoformat(),
                "status":"completed","conclusion":"success"})
        r=a.evaluate(data,NOW,ACTIVATED)
        self.assertEqual(r["status"],"FAIL_REAL_GITHUB_24H_CRON_DELIVERY")
        self.assertEqual(r["nodes"]["B"]["successful_schedule_count"],72)

    def test_recent_failure_in_middle_is_not_healthy_full_delivery(self):
        data=sample()
        for idx in range(20,55):
            data["C"][idx]["conclusion"]="failure"
        r=a.evaluate(data,NOW,ACTIVATED)
        self.assertEqual(r["status"],"FAIL_REAL_GITHUB_24H_CRON_DELIVERY")

    def test_no_double_counting_or_untrusted_timestamps(self):
        data=sample()
        data["A"].append(copy.deepcopy(data["A"][0]))
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_BAD_SCHEDULE_RUN_ID"):
            a.evaluate(data,NOW,ACTIVATED)
        data=sample()
        data["B"][0]["created_at"]="not-a-date"
        with self.assertRaises(ValueError):
            a.evaluate(data,NOW,ACTIVATED)


if __name__=="__main__":
    unittest.main()
