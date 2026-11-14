"""Tests for DovoD-derived temporal witness; pure stdlib, no network or Torch."""
import copy
from datetime import datetime, timedelta, timezone
import unittest

from tools import essence_v31_dovod_temporal_witness as d


class DovodTemporalWitnessContract(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 22, 0, tzinfo=timezone.utc)
        self.cutoff = self.now - timedelta(hours=2)
        proof = {
            "status": "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN",
            "improvement_proven_under_registered_internal_thresholds": False,
            "production_authority": False,
            "last_new_created_at": self.cutoff.isoformat(),
        }
        proof["receipt_sha256"] = d.sha(proof)
        state = {
            "schema": d.STATE_SCHEMA, "generation": 0, "parent": None,
            "pending": None, "research_only": True, "production_authority": False,
            "history": [{
                "accepted": False, "independent_future_verification": proof
            }], "status": "RESEARCH_GEN0_HOLD",
        }
        state["state_sha256"] = d.sha(state)
        self.state = state

    def run_row(self, i, wid, minutes_ago, *, status="completed"):
        dt = self.now - timedelta(minutes=minutes_ago)
        started = dt + timedelta(seconds=1)
        ended = started + timedelta(seconds=40)
        return {
            "id": i, "workflow_id": wid, "head_branch": "main",
            "status": status, "conclusion": "success",
            "run_attempt": 1, "event": "workflow_dispatch",
            "created_at": dt.isoformat(),
            "run_started_at": started.isoformat(),
            "updated_at": ended.isoformat(),
        }

    def corpus(self):
        older = [self.run_row(i + 1, 1 + (i % 6), 180 + i)
                 for i in range(24)]
        fresh = [self.run_row(100 + i, 20 + (i % 12), 2 + i)
                 for i in range(36)]
        return older + fresh

    def test_three_historical_mechanisms_proposed_not_executed(self):
        receipt = d.inspect(self.state, self.corpus(), self.now)
        self.assertEqual(
            receipt["status"], "RESEARCH_NEW_COHORT_STRUCTURALLY_DIVERSE_NOT_NEURAL_PASS"
        )
        self.assertEqual(receipt["new_since_consumed_exam"]["completed_runs"], 36)
        self.assertEqual(receipt["new_since_consumed_exam"]["workflow_families"], 12)
        self.assertEqual(receipt["new_workflow_families"], 12)
        self.assertEqual(len(receipt["candidate_test_designs"]), 3)
        self.assertTrue(all(x["state"] == "PROPOSED_FOR_INDEPENDENT_TEST_ONLY"
                            for x in receipt["candidate_test_designs"]))
        for field in ("production_authority", "weights_updated",
                      "independent_neural_gain_proven",
                      "source_code_executed_from_archives",
                      "next_generation_accepted_by_this_witness"):
            self.assertIs(receipt[field], False)
        self.assertEqual(receipt["receipt_sha256"], d.sha({
            k: v for k, v in receipt.items() if k != "receipt_sha256"
        }))

    def test_consumed_future_cohort_never_reused(self):
        old = [self.run_row(i + 1, 1 + i % 10, 140 + i)
               for i in range(40)]
        receipt = d.inspect(self.state, old, self.now)
        self.assertEqual(receipt["new_since_consumed_exam"]["completed_runs"], 0)
        self.assertEqual(receipt["status"], "HOLD_TEMPORAL_EVIDENCE_INSUFFICIENT")

    def test_repeated_family_does_not_fake_independence(self):
        old = self.corpus()[:24]
        fresh = [self.run_row(100 + i, 20, i + 1) for i in range(50)]
        receipt = d.inspect(self.state, old + fresh, self.now)
        self.assertEqual(receipt["status"], "HOLD_TEMPORAL_EVIDENCE_INSUFFICIENT")
        self.assertEqual(receipt["new_since_consumed_exam"]["workflow_families"], 1)
        self.assertEqual(receipt["new_since_consumed_exam"]["effective_family_count"], 1.0)

    def test_tampered_neural_checkpoint_holds(self):
        bad = copy.deepcopy(self.state)
        bad["generation"] = 1
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            d.inspect(bad, self.corpus(), self.now)

    def test_tampered_proof_fails_even_if_outer_state_resealed(self):
        bad = copy.deepcopy(self.state)
        bad["history"][0]["independent_future_verification"]["last_new_created_at"] = self.now.isoformat()
        bad["state_sha256"] = d.sha({k: v for k, v in bad.items() if k != "state_sha256"})
        with self.assertRaisesRegex(ValueError, "UNSEALED_FUTURE_PROOF"):
            d.inspect(bad, self.corpus(), self.now)

    def test_duplicate_completed_id_fails_closed(self):
        rows = self.corpus()
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            d.inspect(self.state, rows + [copy.deepcopy(rows[0])], self.now)

    def test_clock_inversion_fails_closed(self):
        rows = self.corpus()
        rows[0]["updated_at"] = (self.now + timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "CAUSAL"):
            d.inspect(self.state, rows, self.now)

    def test_excludes_running_and_non_main_events(self):
        rows = self.corpus()
        rows[0]["status"] = "in_progress"
        rows[1]["head_branch"] = "feature"
        result = d.inspect(self.state, rows, self.now)
        self.assertEqual(result["before_consumed_cutoff"]["completed_runs"], 22)

    def test_history_empty_never_claims_new_future_evidence(self):
        state = copy.deepcopy(self.state)
        state["history"] = []
        state["state_sha256"] = d.sha({k: v for k, v in state.items() if k != "state_sha256"})
        result = d.inspect(state, self.corpus(), self.now)
        self.assertIsNone(result["consumed_future_cutoff_utc"])
        self.assertEqual(result["status"], "HOLD_TEMPORAL_EVIDENCE_INSUFFICIENT")

    def test_bounded_inputs(self):
        with self.assertRaisesRegex(ValueError, "UNBOUNDED"):
            d.inspect(self.state, [self.corpus()[0]] * 501, self.now)
        with self.assertRaisesRegex(ValueError, "UNZONED"):
            d.inspect(self.state, [], datetime(2026, 11, 14))


if __name__ == "__main__":
    unittest.main()
