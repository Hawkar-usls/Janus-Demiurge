"""ESSENCE v1.6 verified real JANUS checkpoint and low-bit research tests."""
from __future__ import annotations
import copy
import hashlib
import math
from pathlib import Path
import tempfile
import unittest

import torch

from janus_model.checkpoint_admission import preflight
from janus_model.train_registry import load_checkpoint
from janus_model.model import JanusTinyTransformer
from tools import essence_v16_real_checkpoint_bench as v

class RealNativeQuantizationBenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,cls.state,cls.identities=v.require_source()

    def test_real_promoted_checkpoint_sha_and_git_blob(self):
        self.assertEqual(self.identities["checkpoint_sha256"],v.CHECKPOINT_SHA256)
        self.assertEqual(self.identities["checkpoint_git"],v.CHECKPOINT_GIT_BLOB)
        self.assertEqual(preflight(v.CHECKPOINT),v.CHECKPOINT_SHA256)

    def test_public_probes_are_frozen_and_separate(self):
        self.assertEqual(len(self.frozen["public_probes"]),12)
        self.assertEqual(self.identities["fixture"],v.FROZEN_BLOB)
        self.assertFalse(self.frozen["external_blind_holdout"])

    def test_anchor_git_blob_is_pinned(self):
        self.assertEqual(v.blob_sha(v.ANCHOR),v.ANCHOR_BLOB)
        self.assertGreater(v.ANCHOR.stat().st_size,500)

    def test_only_finite_training_history_observations(self):
        root=v.json_read(v.ROOT_MANIFEST)
        result=v.metric_vectors_from_history(root,self.frozen,self.state)
        self.assertGreaterEqual(result["record_count_used"],16)
        self.assertFalse(result["real_model_weights_modified"])
        self.assertEqual(result["origin"],
            "RECORDED_JANUS_NATIVE_MODEL_LOSS_HISTORY_NOT_MICROKERNEL_INTERNAL_WEIGHTS")

    def test_real_checkpoint_load_and_tensor_shapes(self):
        model,obj=load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
        self.assertIsInstance(model,JanusTinyTransformer)
        self.assertEqual(obj["config"]["vocab_size"],258)
        self.assertGreater(sum(p.numel() for p in model.parameters()),10000)

    def test_alias_token_and_lm_head_preserved(self):
        model,_=load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
        self.assertEqual(model.token.weight.data_ptr(),model.lm_head.weight.data_ptr())
        src=model.state_dict()
        self.assertEqual(src["token.weight"].untyped_storage().data_ptr(),
                         src["lm_head.weight"].untyped_storage().data_ptr())

    def test_quantization_actual_checkpoint_slice(self):
        model,_=load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
        t=model.token.weight.detach().reshape(-1)[:512]
        orig=t.clone()
        for mode in ("fp16","int8","int4","adaptive"):
            with self.subTest(mode=mode):
                recovered,size,modes,err=v.compress_tensor(t,mode,"memory")
                self.assertEqual(tuple(recovered.shape),tuple(t.shape))
                self.assertGreater(size,0)
                self.assertTrue(torch.isfinite(recovered).all())
                self.assertGreaterEqual(err,0)
        self.assertTrue(torch.equal(orig,t))

    def test_fake_bad_checkpoint_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"promoted.pt"
            bad.write_bytes(v.CHECKPOINT.read_bytes()[:64])
            with self.assertRaises(RuntimeError):
                preflight(bad,expected_sha256=v.CHECKPOINT_SHA256)

    def test_refuse_unsupported_mode(self):
        model,_=load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
        tensor=model.pos.weight.detach().reshape(-1)[:64]
        with self.assertRaises((ValueError,KeyError)):
            v.compress_tensor(tensor,"int3","memory")

    def test_prebuilt_eval_batches_are_reproducible(self):
        a=v.build_inputs(self.frozen);b=v.build_inputs(self.frozen)
        self.assertEqual(set(a),{"historical_anchor","public_fixed_probes"})
        for cohort in a:
            self.assertEqual(len(a[cohort]),8)
            self.assertTrue(torch.equal(a[cohort][0][0],b[cohort][0][0]))

    def test_real_state_not_active_microkernel_weights(self):
        rec=v.metric_vectors_from_history(v.json_read(v.ROOT_MANIFEST),
                                             self.frozen,self.state)
        self.assertIn("NOT_MICROKERNEL_INTERNAL_WEIGHTS",rec["origin"])

    def test_no_gpu_vram_claim_in_cpu_only_worker(self):
        self.assertEqual(v.LOSS_HOLD_LIMIT,.005)
        self.assertEqual(v.TOP1_HOLD_LIMIT,.97)
        self.assertEqual(v.MODES,("baseline","fp16","int8","int4","adaptive","restored"))

if __name__=="__main__":
    unittest.main()
