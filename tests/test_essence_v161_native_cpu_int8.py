"""ESSENCE v1.6.1 actual dynamic-int8 operator source/contract checks."""
from __future__ import annotations
import unittest

import torch
from tools import essence_v16_real_checkpoint_bench as base
from tools import essence_v161_native_cpu_int8 as native
from janus_model.train_registry import load_checkpoint

class DynamicINT8NativeResearchTests(unittest.TestCase):
    def test_source_sha_bound(self):
        _,_,ids=base.require_source()
        self.assertEqual(ids["checkpoint_sha256"],base.CHECKPOINT_SHA256)

    def test_real_native_cpu_quantized_linear_exists(self):
        torch.set_num_threads(1)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=base.CHECKPOINT_SHA256)
        model.eval()
        native_model,native_layers=native.make_native_quantized(model)
        self.assertGreater(native_layers,0)
        self.assertEqual(native_model.config.vocab_size,258)

    def test_dynamic_quantized_model_can_forward_real_tokens(self):
        torch.set_num_threads(1)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=base.CHECKPOINT_SHA256)
        model.eval()
        quantized,native_layers=native.make_native_quantized(model)
        frozen,_,_=base.require_source()
        x,y=base.build_inputs(frozen)["historical_anchor"][0]
        with torch.inference_mode():
            logits,loss=quantized(x,y)
        self.assertEqual(tuple(logits.shape),(2,48,258))
        self.assertTrue(torch.isfinite(logits).all())
        self.assertTrue(torch.isfinite(loss).all())

    def test_original_checkpoint_is_byte_immutable(self):
        before=base.file_sha(base.CHECKPOINT)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=before)
        native.make_native_quantized(model)
        self.assertEqual(base.file_sha(base.CHECKPOINT),before)

if __name__=="__main__":
    unittest.main()
