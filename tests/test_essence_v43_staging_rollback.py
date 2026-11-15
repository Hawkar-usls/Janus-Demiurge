"""ESSENCE v4.3: staging rollback contract negative tests. No real service in PR."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v43_staging_rollback as m


class IsolatedHttpStagingRollback(unittest.TestCase):
    def test_byte_transformer_context_and_model_hashes_are_exact(self):
        self.assertEqual(len(m.SAMPLE_TOKENS),24)
        self.assertEqual(set(m.ALLOWED),{"baseline14","physarum"})
        self.assertEqual(m.ALLOWED["baseline14"]["sha256"],
                         "a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174")
        self.assertEqual(m.ALLOWED["physarum"]["sha256"],
                         "dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f")

    def test_atomic_stage_only_route_and_back_to_original(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            m.stage_switch(d,"baseline14")
            self.assertEqual(m.read_active(d),"baseline14")
            m.stage_switch(d,"physarum")
            self.assertEqual(m.read_active(d),"physarum")
            m.stage_switch(d,"baseline14")
            self.assertEqual(m.read_active(d),"baseline14")
            self.assertEqual(len(list(d.glob(".stage-switch-*"))),0)

    def test_unauthorized_or_wrong_checksum_veto(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_STAGING_MODEL"):
                m.stage_switch(d,"production")
            m.stage_switch(d,"baseline14")
            orig=json.loads((d/"active.json").read_text())
            orig["checkpoint_weights_sha256"]="0"*64
            m.atomic_json(d/"active.json",orig)
            with self.assertRaisesRegex(ValueError,"ROUTE_NOT_PINNED"):
                m.read_active(d)
            orig=m.active_payload("physarum")
            orig["production_authority"]=True
            with self.assertRaisesRegex(ValueError,"ROUTE_NOT_PINNED"):
                m.validate_active(orig)

    def test_symlink_and_oversized_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            m.stage_switch(p,"baseline14")
            (p/"active.json").unlink()
            (p/"target.json").write_text(json.dumps(m.active_payload("baseline14")))
            (p/"active.json").symlink_to(p/"target.json")
            with self.assertRaisesRegex(ValueError,"UNSAFE_ACTIVE_ROUTE_FILE"):
                m.read_active(p)

    def test_invalid_inference_receipt_model_and_pid_rejected(self):
        valid={
            "model":"baseline14",
            "sha256":m.ALLOWED["baseline14"]["sha256"],
            "logits_digest":"a"*64,
            "pid":12345,"predicted_next_byte":42,
            "production_authority":False,
        }
        m.verify_response(valid,"baseline14",12345)
        with self.assertRaisesRegex(ValueError,"LIVE_STAGING_RESPONSE_NOT_FROM_LOCKED_MODEL"):
            m.verify_response(valid,"physarum",12345)
        with self.assertRaisesRegex(ValueError,"LIVE_STAGING_RESPONSE_NOT_FROM_LOCKED_MODEL"):
            m.verify_response(valid,"baseline14",11111)

    def test_no_public_server_or_live_promotion_allowed(self):
        source=Path(m.__file__).read_text()
        self.assertIn('("127.0.0.1",0)',source)
        self.assertIn("proc=subprocess.Popen(",source)
        self.assertIn("observed_candidate_fault_http_status",source)
        self.assertIn("restore_model(torch,manifest,data,target",source)
        self.assertIn("same live staging service process",source)
        self.assertNotIn("torch.load(",source)
        self.assertNotIn("pickle.load(",source)
        self.assertNotIn("0.0.0.0",source)
        self.assertNotIn("docker ",source)
        self.assertNotIn("kubectl ",source)
        self.assertNotIn("production_authority\":True",source)


if __name__=="__main__":
    unittest.main()
