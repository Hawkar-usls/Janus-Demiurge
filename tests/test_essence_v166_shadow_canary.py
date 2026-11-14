"""ESSENCE v1.6.6 native INT8 shadow-only fallback and authorization tests."""
import copy
import unittest
import torch
from tools import essence_v166_shadow_canary as s

class ShadowCanary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=s.check_risk()
    def test_meta_registry_evidence_pinned(self):
        self.assertEqual(s.git_blob(s.RISK.read_bytes()),s.RISK_BLOB)
        self.assertFalse(self.evidence["authority"]["automatic_model_swap_allowed"])
    def test_reject_forged_production_promotion(self):
        p=copy.deepcopy(self.evidence["authority"])
        p["production_weights_change_allowed"]=True
        x=torch.zeros((2,3,258))
        with self.assertRaises(PermissionError):
            s.router(x,x,p)
    def test_fault_injection_switches_to_exact_baseline(self):
        base=torch.zeros((2,3,258))
        base[...,1]=1
        candidate=base.clone()
        safe,served=s.router(base,candidate,self.evidence["authority"],fault=False)
        fault,restored=s.router(base,candidate,self.evidence["authority"],fault=True)
        self.assertTrue(torch.equal(served,base))
        self.assertTrue(torch.equal(restored,base))
        self.assertEqual(fault["argmax_mismatched_positions"],6)
        self.assertEqual(fault["route"],"FP32_BASELINE_ONLY")
    def test_never_routes_candidate_to_serving(self):
        baseline=torch.zeros((2,3,258))
        baseline[...,1]=1
        candidate=baseline.clone()
        candidate[...,2]=2
        decision,result=s.router(baseline,candidate,self.evidence["authority"])
        self.assertTrue(torch.equal(result,baseline))
        self.assertNotEqual(candidate.argmax(-1)[0,0],result.argmax(-1)[0,0])
    def test_invalid_safe_baseline_denied(self):
        x=torch.zeros((2,3,258))
        x[0,0,0]=float("nan")
        with self.assertRaises(ValueError):
            s.router(x,torch.zeros_like(x),self.evidence["authority"])
    def test_real_checkpoint_source_immutable(self):
        from tools import essence_v16_real_checkpoint_bench as v
        frozen,_,_=v.require_source()
        self.assertEqual(v.file_sha(v.CHECKPOINT),s.EXPECTED_CKPT)

if __name__=="__main__":unittest.main()
