"""ESSENCE v4.2 independent-scoring-contract tests; no upstream external bytes in PR."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from research.essence.physarum_v42 import cleanroom_verifier as clean
from tools import essence_v42_physarum_full_cost as cost
from tools import essence_v38_inheritance as prior
from tools import essence_v37_codex_gpt as original


class CleanroomContractTests(unittest.TestCase):
    def setUp(self):
        self.lock=Path(__file__).resolve().parents[1]/cost.LOCK
        self.policy=clean.policy(self.lock)

    def test_preregistered_12_unique_new_external_tasks(self):
        rows=self.policy["source_repos"]
        self.assertEqual(len(rows),4)
        self.assertEqual(sum(len(x["paths"]) for x in rows),12)
        self.assertEqual([x["repo"] for x in rows],list(clean.SOURCE_PROJECTS))
        self.assertTrue(self.policy["source_scoring_executed_before_seal"] is False)
        self.assertTrue(self.policy["external_sources_are_public"] is True)
        self.assertFalse(self.policy["external_custodian_independent"])
        self.assertEqual(self.policy["cost_contract"]["baseline14_model_train_steps"],14)
        self.assertEqual(self.policy["cost_contract"]["physarum_total_model_train_steps"],14)
        self.assertEqual(self.policy["exam_contract"]["threshold_loss_decrease"],0.0001)
        self.assertEqual(cost.read_lock(self.lock),self.policy)

    def test_metric_or_source_cannot_be_redefined(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lock.json"
            x=copy.deepcopy(self.policy)
            x["exam_contract"]["threshold_loss_decrease"]=-1.0
            path.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"PREREGISTRATION_DRIFT"):
                clean.policy(path)
            x=copy.deepcopy(self.policy)
            x["source_repos"][0]["repo"]="psf/requests"
            path.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,"SOURCE_COHORT_NOT_LOCKED"):
                clean.policy(path)

    def test_standalone_cleanroom_code_does_not_import_evolution_modules(self):
        text=Path(clean.__file__).read_text()
        self.assertIsNone(re.search(r"^\s*(from|import)\s+tools\b",text,re.M))
        self.assertNotIn("torch.load(",text)
        self.assertNotIn("pickle.load(",text)
        self.assertNotIn("subprocess.",text)

    def test_float32_model_roundtrip_independently_restated(self):
        import torch
        torch.set_num_threads(1)
        torch.manual_seed(12)
        with tempfile.TemporaryDirectory() as tmp:
            model=original.new_model(torch)
            folder=Path(tmp)/"sealed"
            fakefreeze={"receipt_sha256":clean.FREEZE_HASH}
            manifest=prior.save_checkpoint(
                folder,torch,model,generation="g4_fixed_budget14",
                freeze=fakefreeze,initial_weights_sha256=clean.G3_HASH,
                parent_manifest_sha256="0"*64,
                trained_steps=14,rejected=0)
            expected={"generation":"g4_fixed_budget14","steps":14,
                      "manifest_sha256":manifest["manifest_sha256"],
                      "weights_sha256":manifest["weights_sha256"]}
            reconstructed,_=clean.checkpoint(folder,expected)
            model.eval()
            tokens=torch.randint(0,256,(2,24))
            with torch.no_grad():
                self.assertTrue(torch.allclose(model(tokens),
                                               reconstructed(tokens),
                                               atol=1e-6,rtol=1e-6))
            with (folder/"weights.f32").open("r+b") as f:
                first=f.read(1)
                f.seek(0)
                f.write(bytes([first[0]^2]))
            with self.assertRaisesRegex(ValueError,
                                        "CHECKPOINT_BYTES_SHA256_MISMATCH"):
                clean.checkpoint(folder,expected)

    def test_reject_invalid_external_blob_even_if_mock_fetches_it(self):
        fake={"repo":"pallets/werkzeug",
              "commit":"0"*40,
              "paths":[{"path":"src/werkzeug/x.py","git_blob_sha1":"0"*40}]}
        bad=b"x"*3000
        with self.assertRaisesRegex(ValueError,
                                    "EXTERNAL_SOURCE_GIT_BLOB_MISMATCH"):
            with patch.object(clean,"urlopen") as connection:
                connection.return_value.__enter__.return_value.read.return_value=bad
                clean.verified_source(fake,fake["paths"][0])

    def test_missing_full_cost_replay_rejected_before_model_or_data_access(self):
        stub={
          "schema":cost.SCHEMA,
          "lock_sha256":clean.digest(self.policy),
          "g3_source_sha256":clean.G3_HASH,
          "physarum_source_sha256":clean.KNOWN_OLD_G4["physarum"]["weights_sha256"],
          "baseline14_weights_sha256":"f"*64,
          "baseline14_manifest_sha256":"e"*64,
          "baseline14":{"train_steps":14},
          "physarum":{"total_training_steps":14},
          "full_cost_includes_all_probes_and_selection":True,
          "external_exam_bytes_read":False,
          "production_authority":False,
        }
        stub["receipt_sha256"]=clean.digest(stub)
        with tempfile.TemporaryDirectory() as tmp:
            cost_path=Path(tmp)/"receipt.json"
            cost_path.write_text(json.dumps(stub))
            with patch.object(clean,"checkpoint",
                              side_effect=ValueError("BAD_MANIFEST")):
                with self.assertRaisesRegex(ValueError,"BAD_MANIFEST"):
                    clean.evaluate(self.lock,cost_path,"m14","ctrl","phys")

    def test_invalid_cost_proof_veto(self):
        stub={"schema":cost.SCHEMA,"receipt_sha256":"bad"}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cost.json"
            path.write_text(json.dumps(stub))
            with self.assertRaisesRegex(ValueError,"SHA256_SEAL_VETO"):
                clean.evaluate(self.lock,path,"m14","ctrl","phys")


if __name__=="__main__":
    unittest.main()
