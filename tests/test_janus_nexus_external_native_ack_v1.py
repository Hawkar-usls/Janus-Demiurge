"""Pinned cross-repository external organ ACK adversarial tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.janus_nexus_external_native_ack_v1 import (
    ExternalHold,SOURCE_ROOT, SOURCE_RUN, SOURCE_ATTEMPT,SOURCE_CODE_SHA,
    MODEL_COMMIT,MODEL_CHECKPOINT_SHA256,SCHEMA,raw_sha,digest,source,
    consumer_prompt,make_receipt,verify_receipt,save_once,read,
)

RECV_SHA="e"*40
EXT_RUN="43280000001"


def fixture(root: Path, text: str="plain public output", *,
            full: bool=False):
    candidates=[]
    for ident,value in (("model-1","an alternative"),
                        ("model-2",text)):
        candidates.append({
            "variant_id":ident,
            "proposal":{"text":value,
                        "proposal_sha256":raw_sha(value.encode()),
                        "model_generated":True}
        })
    variants={
        "schema":"janus.nexus.integrated_native_git_lab.v1.variants",
        "model_generated_count":2,
        "code_patch_generated_or_tested":False,
        "authority_delta":0,
        "selected_variant_id":"model-2",
        "candidates":candidates,
    }
    checkpoint={
        "schema":"janus.nexus.integrated_native_git_lab.v1.checkpoint",
        "run_id":SOURCE_RUN,"attempt":SOURCE_ATTEMPT,
        "code_sha":SOURCE_CODE_SHA,
        "model_commit":MODEL_COMMIT,
        "checkpoint_model_sha256":MODEL_CHECKPOINT_SHA256,
        "variant_digest":digest(variants),
        "full_issue_162_acceptance":full,
        "source_writeback":False,"authority_delta":0
    }
    directory=root/SOURCE_ROOT
    directory.mkdir(parents=True)
    (directory/"checkpoint.json").write_text(json.dumps(checkpoint))
    (directory/"variants.json").write_text(json.dumps(variants))
    return checkpoint,variants


class ExternalAckContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        fixture(self.root)
        self.model=self.root/"model.pt"
        self.model.write_bytes(b"fixture-model")
        self.checkpoint,self.variants,self.selected=source(self.root)
        self.prompt=consumer_prompt(self.selected)
        self.raw=(self.prompt+" a real model response").encode()

    def ack(self, raw=None):
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            return make_receipt(self.root,self.model,self.raw if raw is None else raw,
                                EXT_RUN,RECV_SHA)

    def test_valid_external_receipt_is_distinct_from_production_ack(self):
        row=self.ack()
        self.assertEqual(row["status"],
            "PASS_EXTERNAL_DEMIURGE_NATIVE_MODEL_CONSUMED_PINNED_GENESIS_LAB_TEXT")
        self.assertEqual(row["received"],"RECEIVED")
        self.assertEqual(row["parsed"],"PARSED")
        self.assertEqual(row["loaded"],"LOADED")
        self.assertEqual(row["executed"],
                         "EXECUTED_ACTUAL_PINNED_DEMIURGE_MODEL_INFERENCE")
        self.assertTrue(row["real_external_organ_readonly_consumption_proven"])
        self.assertFalse(row["production_integration_consumption_proven"])
        self.assertFalse(row["full_issue_162_acceptance"])
        self.assertFalse(row["source_writeback"])
        self.assertEqual(row["selected_proposal_sha256"],
                         self.selected["proposal_sha256"])
        self.assertEqual(row["model_input_sha256"],
                         raw_sha(self.prompt.encode()))

    def test_independent_replay_and_forged_hash_rejected(self):
        row=self.ack()
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            verify_receipt(self.root,self.model,self.raw,row)
        row["model_stdout_sha256"]="0"*64
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            with self.assertRaisesRegex(ExternalHold,"EXTERNAL_ACK_REPLAY_MISMATCH"):
                verify_receipt(self.root,self.model,self.raw,row)

    def test_forged_claim_or_production_authority_rejected(self):
        row=self.ack()
        row["production_integration_consumption_proven"]=True
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            with self.assertRaisesRegex(ExternalHold,"EXTERNAL_ACK_REPLAY_MISMATCH"):
                verify_receipt(self.root,self.model,self.raw,row)

    def test_false_received_prefix_rejected(self):
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            with self.assertRaisesRegex(ExternalHold,"EXTERNAL_MODEL_INPUT_NOT_CONSUMED"):
                make_receipt(self.root,self.model,b"fake output",EXT_RUN,RECV_SHA)

    def test_empty_generation_is_rejected(self):
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            with self.assertRaisesRegex(ExternalHold,"EXTERNAL_MODEL_NO_GENERATED_SUFFIX"):
                make_receipt(self.root,self.model,self.prompt.encode(),EXT_RUN,RECV_SHA)

    def test_altered_source_sha_rejected(self):
        path=self.root/SOURCE_ROOT/"checkpoint.json"
        data=json.loads(path.read_text())
        data["code_sha"]="1"*40
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ExternalHold,"GENESIS_CHECKPOINT_PIN_MISMATCH"):
            source(self.root)

    def test_selected_variant_forgery_rejected(self):
        path=self.root/SOURCE_ROOT/"variants.json"
        data=json.loads(path.read_text())
        data["candidates"][1]["proposal"]["text"]="modified"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ExternalHold,"GENESIS_VARIANTS_INTEGRITY"):
            source(self.root)

    def test_source_claim_full_acceptance_fails_closed(self):
        path=self.root/SOURCE_ROOT/"checkpoint.json"
        data=json.loads(path.read_text())
        data["full_issue_162_acceptance"]=True
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ExternalHold,"GENESIS_CHECKPOINT_PIN_MISMATCH"):
            source(self.root)

    def test_receipt_write_append_only(self):
        p=self.root/"ack.json"
        row=self.ack()
        save_once(p,row)
        save_once(p,row)
        self.assertEqual(read(p),row)
        row["source_writeback"]=True
        with self.assertRaisesRegex(ExternalHold,"DURABLE_ACK_IMMUTABLE_CONFLICT"):
            save_once(p,row)

    def test_wrong_run_and_invalid_receiver_source_rejected(self):
        with patch("tools.janus_nexus_external_native_ack_v1.verify_checkpoint"):
            with self.assertRaisesRegex(ExternalHold,"EXTERNAL_RUN_ID_INVALID"):
                make_receipt(self.root,self.model,self.raw,"0",RECV_SHA)
            with self.assertRaisesRegex(ExternalHold,"RECEIVER_SOURCE_SHA_INVALID"):
                make_receipt(self.root,self.model,self.raw,EXT_RUN,"not-sha")

    def test_bound_utf8_prompt_never_calls_untrusted_command(self):
        p=consumer_prompt(self.selected)
        self.assertTrue(p.startswith("JANUS EXTERNAL ORGAN R0 READONLY: "))
        self.assertLessEqual(len(p.encode()),112)
        self.assertNotIn("exec",p.lower())


if __name__=="__main__":
    unittest.main()
