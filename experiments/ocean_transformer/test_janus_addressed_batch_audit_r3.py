#!/usr/bin/env python3
"""JANUS batch 20-way R3 aggregation fail-closed synthetic tests."""
import json
from pathlib import Path
import tempfile
import unittest

import janus_addressed_handshake_cpu_r2 as r2
import janus_addressed_batch_audit_r3 as batch


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj),encoding="utf-8")


def fixture(root,run_id="90909090"):
    for slot in range(batch.SHARDS):
        trial_id=f"{run_id}{slot:02d}"
        early=r2.create_early(trial_id,nonce=f"{slot:064x}")
        future=r2.create_future(trial_id)
        future["generated_epoch_utc"]=early["created_epoch_utc"]+120.
        score=r2.score(early,future,permutations=199,seed=91)
        for phase, filename, obj in (
            ("early","early.json",early),
            ("future","future.json",future),
            ("comparison","score.json",score)
        ):
            save(root/f"janus-addressed-r3-{phase}-{run_id}-{slot}"/filename,obj)


class BatchAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_20_workers_all_1280_attempts_and_each_cell_320(self):
        x=batch.aggregate(self.root,"90909090",permutations=199)
        self.assertEqual(x["shards"],20)
        self.assertEqual(x["unfiltered_total_trials"],1280)
        self.assertEqual(len(x["per_shard"]),20)
        self.assertEqual(set(x["balanced_four_cell_counts"].values()),{320})
        self.assertEqual(x["status"],"TEST_ONLY_REDUCED_BUDGET")
        self.assertFalse(x["physical_retrocausal_principle_proven"])
        self.assertFalse(x["production_promotion"])

    def test_missing_worker_cannot_be_ignored(self):
        p=self.root/"janus-addressed-r3-early-90909090-19"/"early.json"
        p.unlink()
        with self.assertRaisesRegex(ValueError,"MISSING_SHARD_ARTIFACT"):
            batch.collect(self.root,"90909090")

    def test_extra_worker_is_rejected(self):
        (self.root/"janus-addressed-r3-future-90909090-20").mkdir()
        with self.assertRaisesRegex(ValueError,"MISSING_OR_EXTRA_ARTIFACT_DIRECTORY"):
            batch.collect(self.root,"90909090")

    def test_changed_early_record_does_not_past_drift(self):
        p=self.root/"janus-addressed-r3-early-90909090-3"/"early.json"
        obj=json.loads(p.read_text())
        obj["records"][0]["guess_addressed"]^=1
        save(p,obj)
        with self.assertRaisesRegex(ValueError,"RECORD_DIGEST_CONTRADICTION"):
            batch.collect(self.root,"90909090")

    def test_forged_comparison_delta_rejected(self):
        p=self.root/"janus-addressed-r3-comparison-90909090-1"/"score.json"
        obj=json.loads(p.read_text())
        obj["addressing_interaction_difference_in_differences"]=12345.
        save(p,obj)
        with self.assertRaisesRegex(ValueError,"REPORTED_INTERACTION_CHANGED"):
            batch.collect(self.root,"90909090")

    def test_wrong_run_id_or_repeated_shard_blocked(self):
        p=self.root/"janus-addressed-r3-early-90909090-2"/"early.json"
        obj=json.loads(p.read_text())
        obj["trial_id"]="9090909001"
        save(p,obj)
        with self.assertRaisesRegex(ValueError,"TRIAL_ID_MISMATCH"):
            batch.collect(self.root,"90909090")

    def test_permutation_reproducible_seed_and_exact_tail(self):
        g,_,rows=batch.collect(self.root,"90909090")
        d,_=r2.interaction(rows)
        x=batch.global_permutation_p(g,d,count=199,seed=4)
        y=batch.global_permutation_p(g,d,count=199,seed=4)
        self.assertEqual(x,y)
        self.assertTrue(0<x<=1)
        self.assertEqual(batch.exact_tail(8,8),1/256)
        self.assertEqual(batch.exact_tail(8,0),1)


if __name__=="__main__":
    unittest.main(verbosity=2)
