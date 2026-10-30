"""DADDY_KEYMASTER native-model admission: fast negative gates."""
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

from daddy_keymaster.native_calibration import (
    PROFILES, check_source, corpus_identity, canonical_checkpoint,
)
from janus_model.eval_contract import contract_identity


class NativeSwarmAdmissionTests(TestCase):
    def test_two_distinct_bounded_profiles(self):
        self.assertEqual(set(PROFILES), {"X64", "ARM64"})
        self.assertNotEqual(PROFILES["X64"]["seed"], PROFILES["ARM64"]["seed"])
        for p in PROFILES.values():
            self.assertLessEqual(p["steps"], 48)
            self.assertLessEqual(p["batch_size"], 8)
            self.assertLessEqual(p["lr"], 0.0002)

    def test_foreign_repository_refused(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "random/open",
               "GITHUB_EVENT_NAME":"push","GITHUB_SHA":"a"*40,
               "GITHUB_RUN_ID":"41111111111","GITHUB_RUN_ATTEMPT":"1"}
        with self.assertRaisesRegex(ValueError,"RUN_CONTEXT_REFUSED"):
            check_source(Path("."),env)

    def test_identity_drift_refused(self):
        env = {"GITHUB_ACTIONS": "true",
               "GITHUB_REPOSITORY":"Hawkar-usls/Janus-Demiurge",
               "GITHUB_EVENT_NAME":"push","GITHUB_SHA":"a"*40,
               "GITHUB_RUN_ID":"41111111111","GITHUB_RUN_ATTEMPT":"1"}
        with mock.patch("subprocess.check_output",return_value="b"*40+"\n"):
            with self.assertRaisesRegex(ValueError,"SOURCE_SHA_DRIFT"):
                check_source(Path("."),env)

    def test_forged_checkpoint_hash_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"janus_model/state").mkdir(parents=True)
            (root/"janus_model/checkpoints").mkdir(parents=True)
            (root/"janus_model/checkpoints/promoted.pt").write_bytes(b"X")
            (root/"janus_model/state/JANUS_MODEL_STATE.json").write_text(
                json.dumps({"schema":"janus.model.state.v1","checkpoint_sha256":"0"*64}))
            with self.assertRaisesRegex(ValueError,"INCUMBENT_SHA_MISMATCH"):
                canonical_checkpoint(root)

    def test_noncanonical_corpus_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"runtime/corpus").mkdir(parents=True)
            (root/"runtime/corpus/train.txt").write_bytes(b"x"*50001)
            (root/"runtime/corpus/holdout.txt").write_bytes(b"y"*10001)
            obj={"source_repository":"not-janus",
                 "source_commit":"a"*40, "source_digest":"b"*64,
                 "anchor_is_training_source":False,
                 "evaluation_contract_sha256":contract_identity()["contract_sha256"]}
            (root/"runtime/corpus/corpus_manifest.json").write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"CORPUS_INVALID"):
                corpus_identity(root)

    def test_training_anchor_leakage_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"runtime/corpus").mkdir(parents=True)
            (root/"runtime/corpus/train.txt").write_bytes(b"x"*50001)
            (root/"runtime/corpus/holdout.txt").write_bytes(b"y"*10001)
            obj={"source_repository":"Hawkar-usls/janus-meta-registry",
                 "source_commit":"a"*40, "source_digest":"b"*64,
                 "anchor_is_training_source":True,
                 "evaluation_contract_sha256":contract_identity()["contract_sha256"]}
            (root/"runtime/corpus/corpus_manifest.json").write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"CORPUS_INVALID"):
                corpus_identity(root)

    def test_untrusted_pickle_checkpoint_loading_prohibited(self):
        source=Path("janus_model/train_registry.py").read_text()
        self.assertIn('weights_only=True',source)
        self.assertNotIn('weights_only=False',source)
