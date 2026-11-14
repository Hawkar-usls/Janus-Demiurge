"""Physarum v4.1 frozen new-source cohort contract; PR tests never fetch source."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v41_physarum_external_exam as p
from tools import essence_v37_codex_gpt as core


class PhysarumExternalNewCohort(unittest.TestCase):
    def lock(self):
        return p.load_lock(Path(__file__).resolve().parents[1] / p.LOCK_PATH)

    def test_precommitted_source_files_not_g3(self):
        lock=self.lock()
        self.assertEqual(lock["g4_source_run"],43650540561)
        self.assertEqual(len(lock["sources"]),4)
        self.assertEqual({x["repo"] for x in lock["sources"]},
                         {"encode/httpx","python-attrs/attrs"})
        self.assertFalse(set(p.NEW_SOURCE_PROJECTS)&p.G3_OLD_SOURCE_PROJECTS)
        self.assertTrue(lock["frozen_after_g4_weights_sealed"])
        self.assertEqual(lock["manifests_sha256"],p.G4_MANIFESTS)
        self.assertEqual(lock["weights_sha256"],p.G4_WEIGHTS)

    def test_frozen_rules_or_weight_sha_cannot_change(self):
        lock=self.lock()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"lock.json"
            changed=copy.deepcopy(lock)
            changed["exam_contract"]["minimum_mean_loss_decrease"]=-10
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,"POST_HOC_G4_METRIC_DRIFT"):
                p.load_lock(path)
            changed=copy.deepcopy(lock)
            changed["weights_sha256"]["physarum"]="0"*64
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,"EXTERNAL_G4_LOCK_INVALID"):
                p.load_lock(path)
            changed=copy.deepcopy(lock)
            changed["sources"][0]["repo"]="psf/requests"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,"INVALID_G4_EXTERNAL_SOURCES"):
                p.load_lock(path)

    def test_blob_verify_rejects_mutation_or_training_leak(self):
        raw=(b"def independent_function(x):\n return x\n"*70)
        record={"git_blob_sha1":p.origin.blob_sha1(raw)}
        digest=p.verify_external(record,raw,set())
        self.assertEqual(digest,hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError,"G4_EXTERNAL_GIT_BLOB_TAMPER"):
            p.verify_external(record,raw+b"!",set())
        with self.assertRaisesRegex(ValueError,"CROSS_SPLIT_OR_G3_HOLDOUT_LEAKAGE"):
            p.verify_external(record,raw,{digest})

    def test_no_fetch_before_both_checkpoint_validations(self):
        import torch
        lock=self.lock()
        def forbidden(_):
            raise AssertionError("FETCHED_BEFORE_G4_CHECKPOINT_VERIFIED")
        with patch.object(p,"verify_checkpoints",
                          side_effect=ValueError("INVALID_G4_CHECKPOINT")):
            with self.assertRaisesRegex(ValueError,"INVALID_G4_CHECKPOINT"):
                p.examine(str(Path(__file__).resolve().parents[1]/p.LOCK_PATH),
                          "freeze","control","physarum",fetch=forbidden)

    def test_mock_paired_exam_has_no_promotion_or_external_validation_claim(self):
        import torch
        torch.set_num_threads(1)
        lock=self.lock()
        synthetic=[]
        updated=copy.deepcopy(lock)
        for i,row in enumerate(updated["sources"]):
            raw=(f"# independent mock repo source {i}\n"
                 f"def stable_function_{i}(x):\n return x + {i}\n").encode()*90
            updated["sources"][i]["git_blob_sha1"]=p.origin.blob_sha1(raw)
            synthetic.append(raw)
        torch.manual_seed(99)
        control=core.new_model(torch)
        phys=core.new_model(torch)
        fakefreeze={"roles":{"train":[],"val":[]}}
        with patch.object(p,"load_lock",return_value=updated),\
             patch.object(p,"verify_checkpoints",
                          return_value=(fakefreeze,{"control":control,
                                                   "physarum":phys})):
            visited=[]
            def fetch(row):
                visited.append(row["path"])
                return synthetic[len(visited)-1]
            res=p.examine("fixture","fakefreeze","a","b",fetch=fetch)
        self.assertEqual(len(visited),4)
        self.assertIn(res["status"],
            ("PASS_INTERNAL_PHYSARUM_GAIN_ON_NEW_EXTERNAL_SOURCES",
             "NO_PHYSARUM_GAIN_ON_NEW_EXTERNAL_SOURCES"))
        self.assertEqual(len(res["per_repository"]),2)
        self.assertFalse(res["automatic_promotion"])
        self.assertFalse(res["scientific_external_replicator"])
        self.assertFalse(res["private_blind_custodian"])
        self.assertFalse(res["production_authority"])

    def test_never_exec_legacy_physarum_nor_unsafe_checkpoints(self):
        source=Path(p.__file__).read_text()
        self.assertNotIn("pickle.load(",source)
        self.assertNotIn("torch.load(",source)
        self.assertNotIn("import physarum_engine",source)


if __name__=="__main__":
    unittest.main()
