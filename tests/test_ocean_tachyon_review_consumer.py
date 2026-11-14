"""Offline, standard-library test for Ocean consuming pinned Tachyon review."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'experiments/ocean_transformer'))
import tachyon_review_consumer as c

DATA=Path(__file__).with_name('fixtures')/'tachyon_ocean_early_20261112.json'

class TachyonConsumerTests(unittest.TestCase):
    def setUp(self):
        self.input=json.loads(DATA.read_text('utf-8'))
    def test_real_witness_shadow_accepts_without_grants(self):
        r=c.consume(self.input)
        self.assertEqual(r['status'],'RESEARCH_CONTEXT_ONLY_NOT_TRAINING')
        self.assertEqual(r['outcome_state'],'PENDING_FUTURE_OUTCOMES')
        self.assertFalse(r['model']['ocean_weights_modified'])
        self.assertFalse(r['rights']['may_modify_ocean_forecast'])
    def test_original_review_tamper_rejected(self):
        o=copy.deepcopy(self.input)
        o['tachyon_shadow_review']['feedback']['candidate_questions'][0] += ' SECRET'
        with self.assertRaisesRegex(ValueError,'TACHYON_REVIEW_TAMPERED'): c.consume(o)
    def test_gradient_permission_rejected_even_if_resigned(self):
        o=copy.deepcopy(self.input)
        v=o['tachyon_shadow_review']
        v['feedback']['eligible_as_gradient_label']=True
        v['receipt_sha256']=c.digest({k:x for k,x in v.items() if k!='receipt_sha256'})
        with self.assertRaisesRegex(ValueError,'FEEDBACK_RETRAINING'): c.consume(o)
    def test_invalid_topa_promotion_rejected(self):
        o=copy.deepcopy(self.input)
        v=o['tachyon_shadow_review']
        v['topa']['envelope']['status']='PROVED_IN_SCOPE'
        v['receipt_sha256']=c.digest({k:x for k,x in v.items() if k!='receipt_sha256'})
        with self.assertRaisesRegex(ValueError,'TOPA_CLAIM_ESCALATION'): c.consume(o)
    def test_source_commit_not_original_rejected(self):
        o=copy.deepcopy(self.input)
        o['original_source_commit']='f'*40
        with self.assertRaisesRegex(ValueError,'ORIGINAL_ARCHIVE_LINEAGE'): c.consume(o)
    def test_future_signal_claim_refused(self):
        o=copy.deepcopy(self.input)
        v=o['tachyon_shadow_review']
        v['physical_retrocausality_established']=True
        v['receipt_sha256']=c.digest({k:x for k,x in v.items() if k!='receipt_sha256'})
        with self.assertRaisesRegex(ValueError,'REVIEW_AUTHORITY'): c.consume(o)

if __name__=='__main__': unittest.main()
