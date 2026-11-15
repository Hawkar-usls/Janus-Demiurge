"""Sealed GitHub model-store: no pickle, immutable and fail-closed checks."""
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v44_checkpoint_store as store
from tools import essence_v44_actions_async as worker


class FrozenGitHubCheckpointStoreTests(unittest.TestCase):
    def test_two_exact_known_weights_and_origins(self):
        self.assertEqual(set(store.EXPECTED),{"baseline14","physarum"})
        self.assertEqual(store.EXPECTED["baseline14"]["source_actions_run"],
                         43652825898)
        self.assertEqual(store.EXPECTED["physarum"]["source_actions_run"],
                         43650540561)
        self.assertEqual(store.EXPECTED["baseline14"]["weights_sha256"],
                         worker.EXPECTED["baseline14"])
        self.assertEqual(store.EXPECTED["physarum"]["weights_sha256"],
                         worker.EXPECTED["physarum"])

    def test_partial_store_cannot_be_silently_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"model-store"
            root.mkdir()
            (root/"baseline14").mkdir()
            with self.assertRaisesRegex(ValueError,
                                        "UNSAFE_OR_MISSING_SEALED_CHECKPOINT"):
                store.bootstrap(root,"invalid","invalid",Path(tmp)/"receipt.json")

    def test_invalid_source_cannot_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,
                                        "UNSAFE_OR_MISSING_SEALED_CHECKPOINT"):
                store.bootstrap(Path(tmp)/"model-store",
                                Path(tmp)/"nope",Path(tmp)/"nope2",
                                Path(tmp)/"receipt.json")

    def test_no_unsafe_weight_load_or_untrusted_url(self):
        source=Path(store.__file__).read_text()
        self.assertNotIn("torch.load(",source)
        self.assertNotIn("pickle.load(",source)
        self.assertNotIn("urllib.request",source)
        self.assertNotIn("subprocess",source)
        self.assertIn('"RESEARCH_ONLY_SHA_LOCKED"',source)
        self.assertIn("PERSISTENT_CHECKPOINT_STORE_RECHECK_FAILED",source)

    def test_symlinked_checkpoint_material_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            inner=root/"baseline14"
            inner.mkdir()
            (inner/"manifest.json").write_text("{}")
            (inner/"weights.f32").symlink_to(root/"missing")
            with self.assertRaisesRegex(ValueError,
                                        "UNSAFE_OR_MISSING_SEALED_CHECKPOINT"):
                store.read_one(inner,"baseline14")


if __name__=="__main__":
    unittest.main()
