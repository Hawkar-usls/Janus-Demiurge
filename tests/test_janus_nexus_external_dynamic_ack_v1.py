"""Independent source-bound organ ACK contract; no GitHub secrets or model runtime."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.janus_nexus_external_dynamic_ack_v1 import (
    SCHEMA,DynamicAckHold,bound_prompt,digest,hash_raw,make_receipt,
    validate_source,read,save
)
RUN="43290000001"
RECEIVER_RUN="43290000002"
SOURCE="a"*40
B_HEAD="b"*40
RECEIVER_SHA="c"*40

class DynamicOrganAckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=self.root/"data/nexus_integrated_native_lab/runs"/(RUN+"-1")
        self.base.mkdir(parents=True)
        proposal={"text":"selected actual model text",
                  "model_generated":True,
                  "proposal_sha256":hash_raw(b"selected actual model text")}
        self.variants={
            "schema":"janus.nexus.integrated_native_git_lab.v1.variants",
            "model_generated_count":2,"selected_variant_id":"model-2",
            "rejected_variant_ids_retained":["model-1"],
            "candidates":[
               {"variant_id":"model-1","source":"PINNED_REAL_NATIVE_MODEL_CALL",
                "proposal":{"text":"discarded","model_generated":True,
                            "proposal_sha256":hash_raw(b"discarded")}},
               {"variant_id":"model-2","source":"PINNED_REAL_NATIVE_MODEL_CALL",
                "proposal":proposal}],
        }
        self.checkpoint={
            "schema":"janus.nexus.integrated_native_git_lab.v1.checkpoint",
            "run_id":RUN,"attempt":1,"code_sha":SOURCE,
            "model_commit":"c8c890206f53591d6bfe444d103ed5dd07ec2296",
            "checkpoint_model_sha256":"fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463",
            "variant_digest":digest(self.variants),"selected_variant_id":"model-2",
            "authority_delta":0,"source_writeback":False}
        self.a={"variant_digest":digest(self.variants),
                "checkpoint_digest":digest(self.checkpoint)}
        self.receiver={"consumed_proposal_sha256":proposal["proposal_sha256"]}
        self.b={"run_id":RUN,"attempt":1,
                "status":"LAB_CONSUMED_COMPLETED_ONCE",
                "variants_digest":digest(self.variants),
                "checkpoint_digest":digest(self.checkpoint),
                "receiver_digest":digest(self.receiver),
                "completion_id":"d"*64,
                "authority_delta":0,"source_writeback":False}
        self.rows={"checkpoint.json":self.checkpoint,
                   "variants.json":self.variants,
                   "worker-a.json":self.a,
                   "worker-b.json":self.b,
                   "receiver.json":self.receiver}
        self.refresh()
        self.model=self.root/"model.pt"
        self.model.write_bytes(b"fake model")
        self.prompt=bound_prompt(RUN,proposal)
        self.raw=(self.prompt+" neural output suffix").encode()

    def refresh(self):
        for name,row in self.rows.items():
            (self.base/name).write_text(json.dumps(row))

    def make(self,**kwargs):
        params={"root":self.root,"checkpoint":self.model,
                "output":self.raw,"source_run":RUN,"attempt":1,
                "source_sha":SOURCE,"b_head":B_HEAD,
                "receiver_run":RECEIVER_RUN,"receiver_sha":RECEIVER_SHA}
        params.update(kwargs)
        with patch("tools.janus_nexus_external_dynamic_ack_v1.verify_model"):
            return make_receipt(**params)

    def test_real_external_origin_not_production_promotion(self):
        r=self.make()
        self.assertEqual(r["status"],
          "PASS_REAL_EXTERNAL_DEMIURGE_NATIVE_CONSUMPTION_SCOPED")
        self.assertEqual(r["sender_source_run_id"],RUN)
        self.assertEqual(r["sender_b_git_head"],B_HEAD)
        self.assertEqual(r["sender_completion_id"],"d"*64)
        self.assertEqual(r["received"],"RECEIVED")
        self.assertEqual(r["parsed"],"PARSED")
        self.assertEqual(r["loaded"],"LOADED")
        self.assertEqual(r["executed"],"EXECUTED_ACTUAL_PINNED_DEMIURGE_MODEL_INFERENCE")
        self.assertTrue(r["external_organ_is_separate_git_repository_and_runner"])
        self.assertFalse(r["production_integration_consumption_proven"])
        self.assertFalse(r["source_writeback"])
        self.assertFalse(r["full_issue_162_acceptance"])

    def test_reject_replayed_historical_source_run(self):
        with self.assertRaisesRegex(DynamicAckHold,"GENESIS_CHECKPOINT_NOT_PINNED"):
            self.make(source_run="43275243138")

    def test_reject_changed_sender_sha(self):
        with self.assertRaisesRegex(DynamicAckHold,"GENESIS_CHECKPOINT_NOT_PINNED"):
            self.make(source_sha="e"*40)

    def test_invalid_git_sha_rejected(self):
        with self.assertRaisesRegex(DynamicAckHold,"SOURCE_OR_RECEIVER_SHA_INVALID"):
            self.make(b_head="not a sha")

    def test_empty_generated_suffix_rejected(self):
        with self.assertRaisesRegex(DynamicAckHold,"MODEL_GENERATION_EMPTY"):
            self.make(output=self.prompt.encode())

    def test_wrong_model_prefix_rejected(self):
        with self.assertRaisesRegex(DynamicAckHold,"MODEL_NOT_CONSUMING_EXACT_GENESIS_TEXT"):
            self.make(output=b"unrelated model text")

    def test_forged_selected_variant_digest_rejected(self):
        self.variants["candidates"][1]["proposal"]["text"]="changed"
        self.refresh()
        with self.assertRaisesRegex(DynamicAckHold,"VARIANT_PROVENANCE_DRIFT"):
            self.make()

    def test_forged_worker_b_completion_rejected(self):
        self.b["status"]="PENDING_CLEAN_WORKER_B"
        self.refresh()
        with self.assertRaisesRegex(DynamicAckHold,"GENESIS_WORKER_B_RECEIPT_DRIFT"):
            self.make()

    def test_wrong_checkpoint_hash_fails_closed(self):
        with self.assertRaisesRegex(DynamicAckHold,"MODEL_CHECKPOINT_SHA_DRIFT"):
            make_receipt(self.root,self.model,self.raw,RUN,1,SOURCE,
                         B_HEAD,RECEIVER_RUN,RECEIVER_SHA)

    def test_single_immutable_ack_rejects_overwrite(self):
        p=self.root/"ack.json"
        save(p,self.make())
        self.assertEqual(read(p)["sender_b_git_head"],B_HEAD)
        with self.assertRaisesRegex(DynamicAckHold,"DURABLE_ACK_OVERWRITE_DENIED"):
            save(p,self.make())

    def test_symlink_source_rejected(self):
        target=self.base/"worker-b.json"
        link=self.root/"link.json"
        link.symlink_to(target)
        with self.assertRaisesRegex(DynamicAckHold,"MISSING_OR_UNSAFE_SOURCE"):
            read(link)

    def test_no_model_commands_in_prompt(self):
        self.assertLessEqual(len(self.prompt.encode()),160)
        self.assertTrue(self.prompt.startswith("JANUS EXTERNAL ORGAN CAUSAL R1"))

if __name__=="__main__":
    unittest.main()
