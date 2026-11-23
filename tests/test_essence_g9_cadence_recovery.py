"""ESSENCE G9 schedule-gap recovery: simulated planner tests are NOT uptime proof."""
import copy
from datetime import datetime, timedelta, timezone
import unittest

from tools import essence_g9_cadence_recovery as g

NOW = datetime(2026, 11, 23, 13, 0, tzinfo=timezone.utc)


def record(role, minutes_ago, event="schedule", conclusion="success", rid=1):
    return {
        "id": 10000 + ord(role) * 100 + rid,
        "head_branch": "main",
        "event": event,
        "status": "completed" if conclusion is not None else "in_progress",
        "conclusion": conclusion,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


def healthy():
    return {role: [record(role, 10)] for role in g.WORKFLOWS}


class G9SentinelCadenceRecovery(unittest.TestCase):
    def test_recent_real_schedule_no_recovery(self):
        result = g.plan(healthy(), NOW)
        self.assertEqual(result["action"], "HOLD_NO_RECOVERY_NEEDED")
        self.assertIsNone(result["role"])
        self.assertFalse(result["physical_24h_cron_delivery_proven"])

    def test_stalled_all_recovers_only_one_node(self):
        history = {role: [record(role, 180)] for role in g.WORKFLOWS}
        result = g.plan(history, NOW)
        self.assertEqual(result["action"], "DISPATCH_ONE_BOUNDED_RECOVERY")
        self.assertEqual(result["role"], "A")
        self.assertEqual(result["workflow"], "sentinel-node-a.yml")
        self.assertEqual(result["maximum_dispatches_from_this_plan"], 1)
        self.assertEqual(result["workflow_input"], {"recovery_only": "true"})

    def test_only_degraded_role_eligible(self):
        history = healthy()
        history["B"] = [record("B", 200)]
        result = g.plan(history, NOW)
        self.assertEqual(result["role"], "B")

    def test_recent_manual_recovery_cooldown_prevents_loop(self):
        history = healthy()
        history["C"] = [
            record("C", 200),
            record("C", 15, "workflow_dispatch", "success", rid=2),
        ]
        result = g.plan(history, NOW)
        self.assertIsNone(result["role"])
        self.assertFalse(result["nodes"]["C"]["needs_recovery"])

    def test_recent_failed_workflow_cannot_cause_dispatch_storm(self):
        history = healthy()
        history["A"] = [
            record("A", 250),
            record("A", 5, "workflow_dispatch", "failure", rid=2),
        ]
        self.assertIsNone(g.plan(history, NOW)["role"])

    def test_previous_manual_never_counted_as_successful_cron(self):
        history = healthy()
        history["A"] = [record("A", 180, "workflow_dispatch", "success")]
        result = g.plan(history, NOW)
        self.assertIsNone(result["nodes"]["A"]["last_successful_schedule_utc"])
        self.assertEqual(result["nodes"]["A"]["successful_schedule_count_in_inventory"], 0)
        self.assertFalse(result["natural_schedule_events_fabricated"])

    def test_no_model_or_production_authority(self):
        x = g.plan(healthy(), NOW)
        self.assertFalse(x["changes_model_weights"])
        self.assertFalse(x["production_promotion"])
        self.assertTrue(x["common_github_failure_domain"])
        self.assertEqual(x["sha256"], g.sha({k:v for k,v in x.items() if k!="sha256"}))

    def test_wrong_repo_or_role_fails_closed(self):
        with self.assertRaises(ValueError):
            g.plan(healthy(), NOW, repo="someone/else")
        h=healthy();h.pop("B")
        with self.assertRaises(ValueError):
            g.plan(h,NOW)

    def test_duplicate_schedule_id_detected(self):
        h=healthy();h["A"].append(copy.deepcopy(h["A"][0]))
        with self.assertRaisesRegex(ValueError,"G9_UNTRUSTED_RUN_ID"):
            g.plan(h,NOW)

    def test_future_timestamp_rejected(self):
        h=healthy()
        h["B"][0]["created_at"]=(NOW+timedelta(hours=3)).isoformat()
        with self.assertRaisesRegex(ValueError,"G9_FUTURE_RUN_TIMESTAMP"):
            g.plan(h,NOW)

    def test_missing_runner_schedule_does_not_grant_pass(self):
        result=g.plan({role: [] for role in g.WORKFLOWS},NOW)
        self.assertEqual(result["action"],"DISPATCH_ONE_BOUNDED_RECOVERY")
        self.assertFalse(result["physical_24h_cron_delivery_proven"])
        self.assertEqual(result["role"], "A")


if __name__=="__main__":
    unittest.main()
