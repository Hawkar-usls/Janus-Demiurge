"""Adversarial checks for read-only Ocean import of Tachyon IO/AIFC receipt."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"experiments/ocean_transformer"))
import tachyon_io_aifc_consumer as c

SOURCE=ROOT/"tests/fixtures/tachyon_io_aifc_verified_20261111.json"

class TestOceanIOAIFC(unittest.TestCase):
    def setUp(self):
        self.item=json.loads(SOURCE.read_text(encoding="utf8"))

    def resign(self, item):
        item["receipt_sha256"]=c.sha(c.canonical({
            k:v for k,v in item.items() if k!="receipt_sha256"}))
        return item

    def test_actual_cloud_receipt_ingests_as_research_only(self):
        result=c.consume(self.item)
        self.assertEqual(result["status"],"EXTERNAL_OBSERVATION_AUDIT_IMPORTED_NOT_TRAINING")
        self.assertEqual(result["aifc_grade"],"NOT_ADMITTED")
        self.assertFalse(result["rights"]["may_trigger_training"])
        self.assertFalse(result["scientific_claim_promoted"])

    def test_tamper_original_digest_rejected(self):
        x=copy.deepcopy(self.item)
        x["aifc"]["grade"]="FORWARD_NULL_COMPATIBLE"
        with self.assertRaisesRegex(ValueError,"RECEIPT_DIGEST_MISMATCH"):
            c.consume(x)

    def test_rehashed_fake_positive_grade_rejected(self):
        x=copy.deepcopy(self.item)
        x["aifc"]["grade"]="FORWARD_NULL_INCOMPATIBILITY_CANDIDATE"
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"AIFC_CLAIM_PROMOTION"):
            c.consume(x)

    def test_rehashed_fake_full_io_chain_rejected(self):
        x=copy.deepcopy(self.item)
        x["proof_of_observation"]["full_independent_observation_chain"]=True
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"IO_INTEGRITY"):
            c.consume(x)

    def test_rehashed_wrong_ocean_precommit_rejected(self):
        x=copy.deepcopy(self.item)
        x["input"]["frozen_precommit_sha256"]="f"*64
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"ORIGINAL_OCEAN_PRECOMMIT_NOT_BOUND"):
            c.consume(x)

    def test_rehashed_gradient_permission_rejected(self):
        x=copy.deepcopy(self.item)
        x["eligible_as_gradient_label"]=True
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"TOPA_OR_MODEL_AUTHORITY"):
            c.consume(x)

    def test_rehashed_hide_incomplete_gates_rejected(self):
        x=copy.deepcopy(self.item)
        x["aifc"]["missing_or_unverified"]=[]
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"AIFC_CLAIM_PROMOTION"):
            c.consume(x)

    def test_rehashed_fake_topa_claim_rejected(self):
        x=copy.deepcopy(self.item)
        x["topa"]["claim_status"]="PROVED_IN_SCOPE"
        self.resign(x)
        with self.assertRaisesRegex(ValueError,"TOPA_OR_MODEL_AUTHORITY"):
            c.consume(x)

if __name__=="__main__":
    unittest.main()
