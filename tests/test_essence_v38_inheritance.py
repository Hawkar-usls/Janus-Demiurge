"""ESSENCE v3.8: source-frozen two-generation actual-weight inheritance tests.

Synthetic fixtures are NOT the committed prospective cohort; CI pull requests
must never score the frozen production-code holdout before the main freeze.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v38_inheritance as m


def setup_fixture(root):
    roles = {}
    for role in ("train", "val", "holdout"):
        roles[role] = []
        for i, path in enumerate(m.ROLE_FILES[role]):
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            raw = ((f"# unique synthetic role={role} ordinal={i}\n" +
                    f"def test_{role}_{i}():\n    return {i + len(role)}\n")
                   * 90).encode("utf-8")
            p.write_bytes(raw)
            roles[role].append({"path": path,
                                "git_blob_sha1": m.blob_sha1(raw)})
    lock = {"schema": m.FREEZE, "experimental_admission": "RESEARCH_ONLY",
            "external_holdout": False, "frozen_before_parent_training": True,
            "steps": dict(m.STEPS),
            "criteria": {
                "min_child_loss_decrease": m.MIN_GAIN,
                "fail_closed_if_unavailable": True,
                "no_reselection_or_retry_after_exam": True},
            "roles": roles}
    path = root / "lock.json"
    path.write_text(json.dumps(lock))
    return path


class FrozenInheritance(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.lock_path = setup_fixture(self.root)
        self.freeze = m.inspect_lock(self.root, self.lock_path)

    def test_frozen_sha_and_roles(self):
        self.assertFalse(self.freeze["holdout_evaluated"])
        self.assertEqual(set(self.freeze["roles"]), {"train", "val", "holdout"})
        m.check_freeze(self.freeze)
        self.assertEqual(self.freeze["receipt_sha256"],
                         m.sha({k:v for k,v in self.freeze.items()
                                if k != "receipt_sha256"}))

    def test_source_mismatch_rejected_before_training(self):
        p = self.root / m.ROLE_FILES["holdout"][0]
        p.write_bytes(p.read_bytes() + b"\n# changed\n")
        with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE_BLOB_CHANGED"):
            m.inspect_lock(self.root, self.lock_path)

    def test_no_retroactive_criterion_edit(self):
        lock = json.loads(self.lock_path.read_text())
        lock["criteria"]["min_child_loss_decrease"] = -100.0
        self.lock_path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError,
                                    "POST_HOC_CRITERION_OR_STEPS_DRIFT"):
            m.inspect_lock(self.root, self.lock_path)

    def test_resigned_freeze_cannot_change_roles(self):
        fake = copy.deepcopy(self.freeze)
        fake["roles"]["holdout"][0]["path"] = m.ROLE_FILES["train"][0]
        fake["receipt_sha256"] = m.sha({
            k:v for k,v in fake.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "FROZEN_ROLE_DRIFT"):
            m.check_freeze(fake)

    def test_parent_child_real_tensors_and_frozen_comparison(self):
        import torch
        parent_path = self.root / "parent"
        child_path = self.root / "child"
        p = m.training(self.root, self.freeze, generation="parent",
                       output=parent_path)
        c = m.training(self.root, self.freeze, generation="child",
                       parent=parent_path, output=child_path)
        self.assertEqual(c["inherited_initial_weights_sha256"],
                         p["weights_sha256"])
        self.assertEqual(c["parent_checkpoint_manifest_sha256"],
                         p["checkpoint_manifest_sha256"])
        self.assertNotEqual(c["weights_sha256"], p["weights_sha256"])
        _, pm = m.load_checkpoint(parent_path, torch, self.freeze)
        _, cm = m.load_checkpoint(child_path, torch, self.freeze)
        self.assertEqual(pm["manifest_sha256"],
                         cm["parent_manifest_sha256"])
        exam = m.evaluation(self.root, self.freeze, parent_path, child_path)
        self.assertIn(exam["status"], ("PASS_INTERNAL_FROZEN_PAIRED_GAIN",
                                     "NO_GAIN_FROZEN_HOLDOUT"))
        self.assertEqual(exam["child_manifest_sha256"], cm["manifest_sha256"])
        self.assertFalse(exam["production_authority"])
        self.assertFalse(exam["independent_external_test"])
        self.assertFalse(exam["automatic_working_model_replacement"])
        self.assertEqual(exam["receipt_sha256"], m.sha({
            k:v for k,v in exam.items() if k != "receipt_sha256"}))
        # Destroy one byte of the persisted parent; hash must veto.
        old = parent_path / "weights.f32"
        raw = old.read_bytes()
        old.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_BYTES_TAMPERED"):
            m.load_checkpoint(parent_path, torch, self.freeze)

    def test_train_phase_never_opens_holdout(self):
        # Once frozen, even missing holdout files do not affect train.
        for name in m.ROLE_FILES["holdout"]:
            (self.root / name).unlink()
        row = m.training(self.root, self.freeze, generation="parent",
                         output=self.root / "parent2")
        self.assertFalse(row["holdout_accessed_by_training"])

    def test_reject_symlink_and_duplicate_corpus(self):
        path = self.root / m.ROLE_FILES["train"][0]
        dst = self.root / "target.py"
        dst.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(dst)
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_FILE"):
            m.inspect_lock(self.root, self.lock_path)

    def test_never_unpickle_original_or_promote(self):
        source = Path(m.__file__).read_text()
        self.assertNotIn("torch.load(", source)
        self.assertNotIn("pickle.load(", source)
        self.assertNotIn("requests.post(", source)
        self.assertEqual(m.STEPS, {"parent": 8, "child": 8})


if __name__ == "__main__":
    unittest.main()
