"""ESSENCE v1.6.3 bounded 15-subset native INT8 research controls."""
import unittest
import torch
import torch.nn as nn
from tools import essence_v16_real_checkpoint_bench as base
from tools import essence_v163_layerwise_int8_sweep as layer
from janus_model.train_registry import load_checkpoint

class SelectiveNativeLayerwiseINT8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,cls.state,_=base.require_source()
    def test_all_fifteen_nonempty_masks_are_legal(self):
        self.assertEqual(len({layer.choose(i) for i in range(1,16)}),15)
        self.assertEqual(layer.choose(15),layer.LAYERS)
        self.assertEqual(layer.choose(1),(layer.LAYERS[0],))
    def test_bad_masks_denied(self):
        for n in (0,-1,16,True,"3",2.4):
            with self.subTest(n=n),self.assertRaises(ValueError):
                layer.choose(n)
    def test_actual_cpu_quantized_single_ffn_layer(self):
        torch.set_num_threads(1)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=base.CHECKPOINT_SHA256)
        q,names=layer.quantize_ffn_subset(model,mask=1)
        self.assertEqual(len(names),1)
        self.assertEqual(sum(isinstance(x,torch.ao.nn.quantized.dynamic.Linear) for x in q.modules()),1)
        self.assertIsInstance(q.lm_head,nn.Linear)
        self.assertEqual(q.lm_head.weight.data_ptr(),q.token.weight.data_ptr())
    def test_double_layer_quantized_runtime_forward(self):
        torch.set_num_threads(1)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=base.CHECKPOINT_SHA256)
        q,names=layer.quantize_ffn_subset(model,mask=3)
        q.eval()
        x,y=base.build_inputs(self.frozen)["historical_anchor"][0]
        with torch.inference_mode():
            output,loss=q(x,y)
        self.assertTrue(torch.isfinite(output).all())
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(output.shape,(2,48,258))
        self.assertEqual(len(names),2)
    def test_output_embedding_remains_tied_in_all_layers(self):
        torch.set_num_threads(1)
        model,_=load_checkpoint(base.CHECKPOINT,expected_sha256=base.CHECKPOINT_SHA256)
        q,names=layer.quantize_ffn_subset(model,mask=15)
        self.assertEqual(len(names),4)
        self.assertEqual(q.lm_head.weight.data_ptr(),q.token.weight.data_ptr())
        self.assertEqual(base.file_sha(base.CHECKPOINT),base.CHECKPOINT_SHA256)
    def test_no_deployment_or_auto_promotion_source_flag(self):
        self.assertEqual(layer.SUMMARY,"janus.essence.native_cpu_layer_search_summary/1.6.3")
        self.assertEqual(layer.TOP1,.97)
        self.assertEqual(layer.LOSS,.005)
        self.assertEqual(layer.MIN_PACKED_SAVING,.04)
        self.assertEqual(layer.MAX_FORWARD_REGRESSION,.15)

if __name__=="__main__":unittest.main()
