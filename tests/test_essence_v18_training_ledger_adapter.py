"""Pinned journal v1.8 replay; never a production or independent holdout claim."""
from __future__ import annotations
import copy
import hashlib
import unittest
from tools import essence_v18_training_ledger_adapter as a

class RecordedHistoryQuantization(unittest.TestCase):
    def test_pinned_real_journal_replays_without_weights_change(self):
        r=a.replay()
        self.assertGreaterEqual(r["observations"],16)
        self.assertGreaterEqual(r["added_saving_bytes"],0)
        self.assertFalse(r["production_authority"])
        self.assertFalse(r["independent_holdout_achieved"])
        self.assertFalse(r["live_service_rollback_tested"])
        self.assertEqual(r["locked_original_model_sha256"],a.PINNED_MODEL_SHA256)

    def test_original_checkpoint_unchanged(self):
        before=hashlib.sha256(a.MODEL.read_bytes()).hexdigest()
        a.replay()
        after=hashlib.sha256(a.MODEL.read_bytes()).hexdigest()
        self.assertEqual(before,after)

    def test_invalid_history_rejected(self):
        state,_=a.check_files()
        root=a.q15.load(a.ROOT_MANIFEST)
        for bad in [[],[{}]*16,[{"candidate_eval_loss":float("inf")}]*16]:
            fake=copy.deepcopy(state)
            fake["history"]=bad
            with self.assertRaises(ValueError):
                a.make_source(fake,root)

    def test_state_digest_and_repository_are_bound(self):
        state,digest=a.check_files()
        self.assertEqual(digest,hashlib.sha256(a.STATE.read_bytes()).hexdigest())
        root=a.q15.load(a.ROOT_MANIFEST)
        source,n=a.make_source(state,root)
        self.assertEqual(source["repository"],root["repository"])
        self.assertEqual(len(source["vectors"]),7)
        self.assertEqual({len(v) for v in source["vectors"].values()},{n})
        self.assertNotEqual(digest,"0"*64)

if __name__=="__main__":unittest.main()
