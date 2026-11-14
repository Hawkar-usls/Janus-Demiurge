"""ESSENCE v2.3 continuously rechecks signals but dispatches only when safe."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from unittest.mock import patch
import unittest

from tools import essence_v23_continuous_pulse as p

NOW = datetime(2026, 11, 14, 14, 30, tzinfo=timezone.utc)
LANE = p.LANES[0]

def change(at, sha="a" * 40):
    return {"sha": sha, "commit": {"committer": {"date": at.isoformat()}}}

def workflow(at, *, state="completed", conclusion="success", rid=222):
    return {"id": rid, "head_branch": "main",
            "created_at": at.isoformat(), "status": state,
            "conclusion": conclusion if state == "completed" else None}


class ContinuousPulseTest(unittest.TestCase):
    def test_no_repeated_work_without_new_source(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(hours=1))],
            [workflow(NOW - timedelta(minutes=45))], now=NOW)
        self.assertEqual(item["status"], "HOLD_NO_NEW_INPUT")

    def test_new_source_is_eligible_for_existing_gate(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(minutes=20))],
            [workflow(NOW - timedelta(minutes=50))], now=NOW)
        self.assertEqual(item["status"], "READY_EXISTING_GATED_WORKFLOW")
        self.assertEqual(item["workflow"], LANE.workflow)

    def test_queued_worker_not_duplicated(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(minutes=1))],
            [workflow(NOW - timedelta(minutes=5), state="in_progress")], now=NOW)
        self.assertEqual(item["status"], "HOLD_WORKER_ALREADY_RUNNING")

    def test_minimum_dispatch_interval(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(minutes=1))],
            [workflow(NOW - timedelta(minutes=10))], now=NOW)
        self.assertEqual(item["status"], "HOLD_DISPATCH_COOLDOWN")

    def test_failure_requires_two_hour_backoff(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(minutes=10))],
            [workflow(NOW - timedelta(minutes=60), conclusion="failure")], now=NOW)
        self.assertEqual(item["status"], "HOLD_WORKER_RETRY_BACKOFF")

    def test_failure_can_retry_after_backoff(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(hours=5))],
            [workflow(NOW - timedelta(hours=3), conclusion="failure")], now=NOW)
        self.assertEqual(item["status"], "READY_EXISTING_GATED_WORKFLOW")

    def test_max_idle_fallback_does_not_prove_improvement(self):
        item = p.source_decision(LANE,
            [change(NOW - timedelta(days=3))],
            [workflow(NOW - timedelta(hours=4))], now=NOW)
        self.assertEqual(item["status"], "READY_EXISTING_GATED_WORKFLOW")

    def test_future_source_clock_blocks(self):
        item = p.source_decision(LANE,
            [change(NOW + timedelta(hours=1))], [], now=NOW)
        self.assertEqual(item["status"], "HOLD_FUTURE_SOURCE_TIME")

    def test_no_source_commit_blocks(self):
        self.assertEqual(p.source_decision(LANE, [], [], now=NOW)["status"],
                         "HOLD_NO_SOURCE_COMMITS")

    def test_no_unbounded_wave_of_workers(self):
        source = [change(NOW - timedelta(minutes=1))]
        prior = [workflow(NOW - timedelta(hours=1))]
        inp = {lane.name: (source, prior) for lane in p.LANES}
        result = p.plan(inp, now=NOW)
        self.assertEqual(sum(x["status"] == "DISPATCH_PLANNED" for x in result), 2)
        self.assertEqual(sum(x["status"] == "HOLD_PULSE_CAPACITY" for x in result), 2)

    def test_suspect_run_origin_blocks_instead_of_dispatch(self):
        bad = workflow(NOW - timedelta(hours=1))
        bad["head_branch"] = "research/untrusted"
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_WORKFLOW_HISTORY"):
            p.source_decision(LANE, [change(NOW - timedelta(minutes=10))], [bad], now=NOW)

    def test_audit_receipt_cannot_promote_or_merge(self):
        source = [change(datetime.now(timezone.utc) - timedelta(minutes=2))]
        with patch.object(p, "fetch_inputs", return_value=(source, [])), \
             patch.object(p, "api_json", return_value={}):
            with patch.dict(os.environ,
                            {"GITHUB_REF": "refs/heads/main",
                             "GITHUB_EVENT_NAME": "schedule"}):
                result = p.run(token="placeholder", do_dispatch=True)
        self.assertEqual(result["requested_dispatches"], 2)
        self.assertTrue(all(x["status"] in
                            ("DISPATCH_REQUESTED_NOT_WORKER_PASS", "HOLD_PULSE_CAPACITY")
                            for x in result["lanes"]))
        for key in ("automatic_merge", "self_governance_override",
                    "automatic_production_model_promotion",
                    "main_code_changed_by_pulse",
                    "external_blind_improvement_proven"):
            self.assertIs(result[key], False)
        self.assertEqual(result["receipt_sha256"],
                         p.sha256({k: v for k, v in result.items()
                                   if k != "receipt_sha256"}))

    def test_pr_can_never_dispatch(self):
        with patch.dict(os.environ,
                        {"GITHUB_REF": "refs/pull/1/merge",
                         "GITHUB_EVENT_NAME": "pull_request"}):
            with self.assertRaisesRegex(ValueError, "WRITE_DISPATCH_REQUIRES_MAIN"):
                p.run(token="placeholder", do_dispatch=True)

    def test_source_api_failure_means_hold_not_birth(self):
        with patch.object(p, "fetch_inputs", side_effect=OSError("offline")):
            result = p.run(token="placeholder", do_dispatch=False)
        self.assertEqual(result["requested_dispatches"], 0)
        self.assertTrue(all(x["status"] == "HOLD_SOURCE_FETCH_FAILED"
                            for x in result["lanes"]))

    def test_backdated_inputs_yield_slow_idle_fallback(self):
        source = [change(NOW - timedelta(days=10))]
        prior = [workflow(NOW - timedelta(hours=1))]
        item = p.source_decision(LANE, source, prior, now=NOW)
        self.assertEqual(item["status"], "HOLD_NO_NEW_INPUT")


if __name__ == "__main__":
    unittest.main()
