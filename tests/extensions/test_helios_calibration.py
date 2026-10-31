import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from janus_model.model import JanusModelConfig, JanusTinyTransformer
from janus_model.extensions.helios_calibration import canonical, validate_bias, validate_admission, attach_calibration, SCHEMA
from tools.extensions.helios_native_calibration import split_records
from tools.extensions.helios_learning_cycle import collect, immutable


def receipt():
    bias = [0.0] * 258
    bias[65], bias[66] = .01, -.01
    row = {"schema": SCHEMA, "status": "ADMITTED_NATIVE_CALIBRATION", "scope": "INFERENCE_LOGIT_CALIBRATION_ONLY", "checkpoint_sha256": "a"*64, "native_auditor_passed": True, "bias": bias, "log_scale": -.02, "metrics": {name:{"before":2.0,"after":1.99,"batches":24,"batch_size":8,"context_length":128} for name in ("adaptive","anchor")}}
    row["calibration_sha256"] = hashlib.sha256(canonical({"bias":bias,"log_scale":row["log_scale"]})).hexdigest()
    return row


class CalibrationTests(unittest.TestCase):
    def test_untrusted_shapes_nonfinite_and_excess_budget_rejected(self):
        for bias in ([0]*257, [True]+[0]*257, [float("nan")]+[0]*257, [.26]+[0]*257, [.01]*258):
            with self.subTest(bias=str(bias[:2])), self.assertRaises(ValueError):
                validate_bias(bias)

    def test_admission_bound_to_exact_checkpoint_and_metrics(self):
        good = receipt()
        self.assertEqual(len(validate_admission(good,"a"*64)),258)
        with self.assertRaises(ValueError): validate_admission(good,"b"*64)
        for change in ("digest","status","scale","regression","noise","evaluation"):
            bad = copy.deepcopy(good)
            if change=="digest": bad["bias"][0] = .001
            if change=="status": bad["status"] = "PENDING_NATIVE_AUDIT"
            if change=="scale": bad["log_scale"] = .5
            if change=="regression": bad["metrics"]["anchor"]["after"] = 2.1
            if change=="noise":
                for row in bad["metrics"].values(): row["after"] = 2
            if change=="evaluation": bad["metrics"]["anchor"]["batches"] = 1
            with self.subTest(change=change), self.assertRaises(ValueError): validate_admission(bad,"a"*64)

    def test_output_only_hook_training_refused_and_exact_rollback(self):
        torch.set_num_threads(1)
        torch.manual_seed(811)
        model=JanusTinyTransformer(JanusModelConfig(d_model=16,n_heads=2,n_layers=1,dropout=0))
        params={k:v.clone() for k,v in model.state_dict().items()}
        x=torch.tensor([[65,66,67]])
        model.eval()
        before,_=model(x)
        handle=attach_calibration(model,receipt(),"a"*64)
        after,loss=model(x,targets=x)
        self.assertTrue(torch.allclose(after,before*torch.exp(torch.tensor(-.02))+torch.tensor(receipt()["bias"])))
        self.assertTrue(torch.isfinite(loss))
        for k,v in model.state_dict().items(): self.assertTrue(torch.equal(v,params[k]))
        model.train()
        with self.assertRaises(RuntimeError): model(x)
        handle.remove();model.eval()
        restored,_=model(x)
        self.assertTrue(torch.equal(before,restored),"Removing optional adapter restores exact original output")

    def test_public_split_excludes_holdout_records_from_training(self):
        original="\n\n".join((str(i)+" pinned public research paragraph "*8) for i in range(50))
        train,holdout=split_records(original)
        self.assertTrue(train and holdout)
        self.assertFalse(set(train.split("\n\n"))&set(holdout.split("\n\n")))

    def test_append_only_lessons_and_one_candidate_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp);p=state/"attempts"/"first.json"
            immutable(p,{"result":"failed"});immutable(p,{"result":"failed"})
            with self.assertRaises(ValueError): immutable(p,{"result":"pass"})
            from tools.extensions.helios_learning_cycle import TASK_SHA
            rows=[{"candidate_id":x,"task_sha256":TASK_SHA,"consent_version":"HELIOS_NATIVE_CALIBRATION_2026_10_31"} for x in ("first","second","third","../bad")]
            raw=json.dumps({"schema":"janus.helios.public_candidates.v1","task_sha256":TASK_SHA,"candidates":rows}).encode()
            with patch("tools.extensions.helios_learning_cycle.read_public",return_value=raw):
                self.assertEqual([x["candidate_id"] for x in collect(state)],["second"])


if __name__=="__main__": unittest.main()
