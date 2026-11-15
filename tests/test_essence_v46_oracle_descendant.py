import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.essence_v46_oracle_descendant import (
    EXAM_SCHEMA, FREEZE_SCHEMA, MODEL, REVISION, check_freeze, check_seal,
    digest, disjoint, freeze, lock_check, oracle_a, oracle_b, read,
    sample_set, write
)

LOCK = Path("research/essence/peer_v46/oracle_lock.json")


class OracleDescendantTests(unittest.TestCase):
    def setUp(self):
        self.lock = lock_check(read(LOCK))

    def test_model_revision_and_nonproduction_authority(self):
        self.assertEqual(self.lock["parent"], MODEL)
        self.assertEqual(self.lock["parent_revision"], REVISION)
        for field in ("auto_promotion", "sentinel_execution_authority",
                      "human_reviewed_dialogues_used", "external_independent_validation",
                      "training_samples_in_holdout"):
            self.assertIs(self.lock[field], False)

    def test_two_oracles_agree_and_splits_are_strict(self):
        train, holdout = disjoint(self.lock)
        self.assertEqual((len(train), len(holdout)), (32, 16))
        self.assertEqual(len({x["code"] for x in train + holdout}), 48)
        self.assertEqual({x["expected"] for x in train}, {"NORTH", "SOUTH"})
        self.assertEqual({x["expected"] for x in holdout}, {"NORTH", "SOUTH"})
        for x in train + holdout:
            self.assertEqual(oracle_a(x["code"]), oracle_b(x["code"]))
            self.assertEqual(oracle_a(x["code"]), x["expected"])
        with self.assertRaises(ValueError):
            oracle_a("Y-12345678")
        with self.assertRaises(ValueError):
            oracle_b("K-nothex!!")

    def test_freeze_is_reproducible_and_integrity_checked(self):
        f1, f2 = freeze(self.lock), freeze(self.lock)
        self.assertEqual(f1, f2)
        self.assertEqual(f1["schema"], FREEZE_SCHEMA)
        self.assertEqual(f1["train_commit_sha256"], digest(sample_set(self.lock, "train")))
        self.assertEqual(f1["holdout_commit_sha256"], digest(sample_set(self.lock, "holdout")))
        self.assertEqual(check_freeze(self.lock, f1), f1)
        broken = copy.deepcopy(f1)
        broken["holdout_commit_sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            check_freeze(self.lock, broken)
        broken["sha256"] = digest({k: v for k, v in broken.items() if k != "sha256"})
        with self.assertRaisesRegex(ValueError, "FROZEN_COHORT_DRIFT"):
            check_freeze(self.lock, broken)

    def test_training_source_lock_is_fail_closed(self):
        for mutation in (
            {"parent_revision": "untrusted"},
            {"auto_promotion": True},
            {"sentinel_execution_authority": True},
            {"dev_only": False},
            {"steps": 200},
            {"train_count": 16},
            {"external_independent_validation": True},
        ):
            other = dict(self.lock, **mutation)
            with self.assertRaisesRegex(ValueError, "ORACLE_LOCK_MUTATED"):
                lock_check(other)

    def test_receipts_are_append_only(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "freeze.json"
            original = freeze(self.lock)
            write(p, original)
            self.assertEqual(read(p), original)
            with self.assertRaisesRegex(ValueError, "REFUSE_OVERWRITE"):
                write(p, original)

    def test_no_training_imports_in_preflight(self):
        # Pure-Python corpus/suite lock validation never requires torch/HF/model weights.
        self.assertFalse(self.lock["human_reviewed_dialogues_used"])
        self.assertFalse(self.lock["external_independent_validation"])
        self.assertNotEqual(EXAM_SCHEMA, FREEZE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
