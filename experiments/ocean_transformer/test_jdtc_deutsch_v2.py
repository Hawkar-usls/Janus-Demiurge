#!/usr/bin/env python3
"""Fail-closed quantum-inspired JDTC v2 code checks; NOT a physics proof."""
import math
import random
import unittest
import torch
import janus_principle_deutsch_v2 as v2


class QuantumInspiredCalibrationTests(unittest.TestCase):
    def test_born_rule_normalization(self):
        x=torch.tensor([[-100., 0., 100.], [1.,2.,3.]])
        probs=v2.born_rule(x)
        self.assertTrue(bool(torch.isfinite(probs).all()))
        self.assertTrue(bool((probs>=0).all()))
        self.assertTrue(bool(torch.allclose(probs.sum(-1),torch.ones(2),atol=1e-6)))
        self.assertTrue(bool(torch.allclose(probs,torch.softmax(x,-1),atol=1e-6)))

    def test_reversible_orthogonal_pair_rotation(self):
        self.assertLess(v2.reversible_rotation_error(),1e-12)

    def test_mask_kernel_uses_past_only(self):
        tokens=torch.tensor([[1,2,3,4]*4,[2,3,4,5]*4],dtype=torch.long)
        original=tokens.clone()
        noisy, mask=v2.corrupt(tokens,31,.4,random.Random(88))
        self.assertEqual(noisy.shape,tokens.shape)
        self.assertTrue(bool(mask.any(dim=1).all()))
        self.assertTrue(bool((noisy[mask]==31).all()))
        self.assertTrue(bool(torch.equal(original,tokens)))
        self.assertTrue(bool(torch.equal(noisy[~mask],tokens[~mask])))

    def test_train_balancing_does_not_peek_at_validation(self):
        train=list(range(20,120))
        a=[0]*210
        for i in train:
            a[i]=1 if i%8==0 else 0
        w1=v2.balanced_training_weights(a,train,3)
        for i in range(120,210):
            a[i]=2
        w2=v2.balanced_training_weights(a,train,3)
        self.assertTrue(bool(torch.equal(w1,w2)))
        self.assertTrue(bool(torch.isfinite(w2).all()))

    def test_initial_network_finite(self):
        model=v2.model()
        x=torch.randint(0,30,(2,16))
        logits,_=model(x)
        p=v2.born_rule(logits[:,-1,:31])
        self.assertEqual(p.shape,(2,31))
        self.assertTrue(bool(torch.isfinite(p).all()))


if __name__=="__main__":
    unittest.main(verbosity=2)
