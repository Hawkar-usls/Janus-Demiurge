"""ESSENCE v3.9 G3 adversarial tests. PR CI never reads real external test bytes."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v39_g3 as g
from tools import essence_v37_codex_gpt as model_core


class G3ExternalSourceContract(unittest.TestCase):
    def real_lock(self):
        path = Path(__file__).resolve().parents[1] / g.LOCK_PATH
        return g.load_lock(path)

    def test_precisely_frozen_four_external_projects(self):
        lock=self.real_lock()
        self.assertEqual(len(lock["external_files"]), 4)
        self.assertEqual({x["repo"] for x in lock["external_files"]},
                         {"psf/requests", "pallets/click"})
        self.assertEqual(lock["g2_checkpoint_weights_sha256"],
                         g.G2_WEIGHT_SHA256)
        self.assertEqual(lock["exam_contract"]["min_mean_decrease"],
                         g.MIN_MEAN_GAIN)
        self.assertTrue(lock["external_source_only_not_external_replicator"])

    def test_missing_or_hostile_source_fails_closed(self):
        x=self.real_lock()
        altered=copy.deepcopy(x)
        altered["external_files"][0]["repo"]="hijack/test"
        with self.assertRaisesRegex(ValueError,"UNAPPROVED_EXTERNAL_ORIGINS"):
            g.examine_lock(altered)
        altered=copy.deepcopy(x)
        altered["external_files"][0]["path"]="../../secrets.py"
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_EXTERNAL_FILE"):
            g.examine_lock(altered)

    def test_posthoc_metric_change_fails(self):
        changed=copy.deepcopy(self.real_lock())
        changed["exam_contract"]["min_mean_decrease"]=-2.0
        with self.assertRaisesRegex(ValueError,"POST_HOC_EXAM_DRIFT"):
            g.examine_lock(changed)

    def test_parent_checksum_change_fails(self):
        changed=copy.deepcopy(self.real_lock())
        changed["g2_checkpoint_weights_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"G2_ORIGIN_CHANGED"):
            g.examine_lock(changed)

    def test_git_raw_source_hash_veto(self):
        raw=(b"# authors independently wrote this test code\n" +
             b"def add(a,b):\n    return a+b\n")*70
        source={"git_blob_sha1":g.git_blob_sha1(raw)}
        digest=g.verify_external_bytes(raw,source,set())
        self.assertEqual(digest,hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError,"EXTERNAL_GIT_SOURCE_HASH_MISMATCH"):
            g.verify_external_bytes(raw+b" ",source,set())
        with self.assertRaisesRegex(ValueError,"EXTERNAL_SOURCE_TRAIN_LEAKAGE"):
            g.verify_external_bytes(raw,source,{digest})

    def test_g3_changes_real_inherited_weights_without_seeing_exam(self):
        import torch
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            torch.manual_seed(777)
            real_start=model_core.new_model(torch)
            raw,_=g.previous.weight_bytes(torch,real_start)
            source_sha=hashlib.sha256(raw).hexdigest()
            fake_parent={"weights_sha256":source_sha,
                         "manifest_sha256":"a"*64}
            fake_freeze={"receipt_sha256":"b"*64}
            data=torch.tensor(list(b"def use_the_verified_training_only():\n"
                                   *200),dtype=torch.long)
            out=Path(folder)/"g3"
            lock=self.real_lock()
            def forbid_net(_):
                raise AssertionError("external bytes requested during training")
            with patch.object(g,"check_g2",return_value=(fake_freeze,real_start,fake_parent)),\
                 patch.object(g.previous,"train_bytes",return_value=(data,data)),\
                 patch.object(g,"github_fetch_pinned",side_effect=forbid_net):
                receipt=g.train_g3(folder,lock,"unused","unused",out)
            self.assertTrue(receipt["actual_parent_weights_inherited"])
            self.assertEqual(receipt["g3_start_weights_sha256"],source_sha)
            self.assertNotEqual(receipt["g3_weights_sha256"],source_sha)
            self.assertFalse(receipt["external_test_seen_during_training"])
            restored, manifest=g.previous.load_checkpoint(out,torch,fake_freeze)
            self.assertEqual(manifest["generation"],"g3")
            self.assertEqual(manifest["inherited_initial_weights_sha256"],
                             source_sha)
            self.assertEqual(manifest["parent_manifest_sha256"],
                             "a"*64)

    def test_exam_must_verify_lineage_before_fetch(self):
        import torch
        lock=self.real_lock()
        fake_freeze={"receipt_sha256":g.G2_FREEZE_SHA256}
        p=model_core.new_model(torch)
        g2={"manifest_sha256":"a"*64,"weights_sha256":"b"*64}
        invalid={"generation":"g3","parent_manifest_sha256":"WRONG",
                 "inherited_initial_weights_sha256":"b"*64,
                 "trained_steps":8,"weights_sha256":"c"*64}
        def forbidden(_):
            raise AssertionError("external task fetched before lineage checked")
        with patch.object(g,"check_g2",return_value=(fake_freeze,p,g2)),\
             patch.object(g.previous,"load_checkpoint",return_value=(p,invalid)):
            with self.assertRaisesRegex(ValueError,
                                        "FORGED_G2_TO_G3_WEIGHT_INHERITANCE"):
                g.exam_g3(lock,"g2","g3","freeze",fetch=forbidden)

    def test_no_model_promotion_or_pickle(self):
        source=Path(g.__file__).read_text()
        self.assertNotIn("torch.load(",source)
        self.assertNotIn("pickle.loads(",source)
        self.assertNotIn("subprocess.",source)
        self.assertEqual(g.STEPS,8)


if __name__=="__main__":
    unittest.main()
