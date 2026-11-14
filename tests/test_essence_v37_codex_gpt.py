"""CODEX GPT v3.7 independent bounded research microcore regression tests."""
import tempfile
from pathlib import Path
import unittest
from tools import essence_v37_codex_gpt as m


class CodexDonorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for i, name in enumerate(m.SPLIT["train"] + m.SPLIT["val"]):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((f"# file {i}\n".encode() +
                           bytes([65+i, 66+i, 10])*1800))

    def test_original_owner_code_bound_not_executed(self):
        self.assertEqual(m.SOURCE["source_sha256"],
                         "3b594ad258d8afb4d571f5cae9e87f0194e246a9a1fe517fd87a6df1b5f69606")
        self.assertFalse(m.SOURCE["legacy_python_executed"])
        source = Path(m.__file__).read_text()
        self.assertNotIn("torch.load(", source)
        self.assertNotIn("requests.post(", source)
        self.assertNotIn("subprocess.", source)

    def test_correlated_training_validation_content_veto(self):
        a = self.root / m.SPLIT["train"][0]
        b = self.root / m.SPLIT["val"][0]
        b.write_bytes(a.read_bytes())
        with self.assertRaisesRegex(ValueError, "TRAIN_VAL_CONTENT_LEAKAGE"):
            m.read_corpus(self.root)

    def test_symlink_corpus_veto(self):
        p = self.root / m.SPLIT["train"][0]
        target = self.root / "fake.py"
        target.write_text("x"*500)
        p.unlink()
        p.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "UNSAFE_CORPUS_PATH"):
            m.read_corpus(self.root)

    def test_resource_cap(self):
        for steps in (0, -1, 21, 100000, True, 1.5):
            with self.assertRaisesRegex(ValueError, "UNBOUNDED_TRAINING_STEPS"):
                m.run(self.root, steps=steps, verify_juxtapose=False)

    def test_actual_neural_training_quant_replay_and_nonpromotion(self):
        d = m.run(self.root, steps=3, verify_juxtapose=False)
        self.assertTrue(d["actual_ephemeral_neural_weight_updates"])
        self.assertNotEqual(d["baseline_val_loss"], d["final_val_loss"])
        self.assertFalse(d["production_weights_modified"])
        self.assertFalse(d["new_generation_promoted"])
        self.assertFalse(d["production_authority"])
        q = d["quantization"]
        self.assertLess(q["estimated_int8_plus_scale_bytes"],
                        q["fp32_parameter_bytes"])
        self.assertGreater(q["parameter_count"], 1000)
        self.assertFalse(q["native_int8_speed_proven"])
        self.assertFalse(q["quant_weights_deployed"])
        self.assertEqual(d["receipt_sha256"], m.seal({
            k:v for k,v in d.items() if k != "receipt_sha256"}))

    def test_seeded_results_reproduce(self):
        a = m.run(self.root, steps=2, verify_juxtapose=False)
        b = m.run(self.root, steps=2, verify_juxtapose=False)
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])

    def test_real_juxtapose_exact_verifier_still_vetoes(self):
        from tools import essence_v36_juxtapose_exact as jux
        d = jux.field_search([[1,2],[-1,3],[2,-3]], 80)
        self.assertTrue(d["exact_verifier_has_veto"])
        self.assertEqual(d["coverage_ratio"], 1.0)
        self.assertFalse(d["production_authority"])


if __name__ == "__main__":
    unittest.main()
