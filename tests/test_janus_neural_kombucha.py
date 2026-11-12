"""Neural Kombucha tests: real CPU gradients, isolation, and immutable SHA controls."""
import json
from pathlib import Path
import tempfile
import unittest
import torch

from tools import janus_neural_kombucha as nk


def fake_observation(folder):
    p = Path(folder) / "observation.json"
    nk.save_json(p, {
        "schema": "janus.cooling_tower.async_microkernel.v1",
        "bounded_rounds": 2, "private_repositories_excluded": True,
        "public_repositories": 48,
        "new_workflow_dispatches": 0, "production_code_writes": 0,
        "full_autonomy_accepted": False, "run_id": "test-123",
        "source_sha": "a" * 40, "observations": [{"cycle": 1}, {"cycle": 2}],
    })
    return p


class NeuralKombuchaTests(unittest.TestCase):
    def test_six_distinct_transformer_cells(self):
        self.assertEqual(len(nk.CELL_NAMES), 6)
        self.assertEqual(len(set(nk.CELL_NAMES)), 6)
        samples = []
        for i in range(6):
            m = nk.make_model(i)
            self.assertLess(nk.parameter_count(m), 10000)
            g = torch.Generator().manual_seed(i + 17)
            x, y = nk.draw(i, 8, g)
            self.assertEqual(tuple(x.shape), (8, nk.CFG.context_length))
            self.assertTrue(bool(torch.isfinite(nk.logits_for(m, x)).all()))
            samples.append(float(m.token.weight[0, 0]))
        self.assertGreater(len(set(samples)), 1)

    def test_reject_authority_escalation_from_observer(self):
        with tempfile.TemporaryDirectory() as temp:
            path = fake_observation(temp)
            self.assertEqual(len(nk.observation_header(path)["sha256"]), 64)
            state = json.loads(path.read_text())
            state["full_autonomy_accepted"] = True
            nk.save_json(path, state)
            with self.assertRaisesRegex(ValueError, "OBSERVATION_CONTRACT"):
                nk.observation_header(path)

    def test_actual_training_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            obs = fake_observation(temp)
            folder = Path(temp) / "cell-0"
            receipt = nk.train_cell(0, obs, folder, steps=40, batch=32, budget=35)
            self.assertEqual(receipt["rounds"], 40)
            self.assertEqual(receipt["heldout_before"]["n"], 512)
            self.assertEqual(receipt["heldout_after"]["n"], 512)
            self.assertNotEqual(receipt["heldout_before"]["nll"], receipt["heldout_after"]["nll"])
            self.assertFalse(receipt["production_promotion"])
            self.assertFalse(receipt["real_github_observations_used_for_gradients"])
            self.assertEqual(receipt["replay_source"], "ONLINE_TRAINING_BATCHES_ONLY")
            self.assertTrue(receipt["frozen_holdout_never_replayed"])
            self.assertGreater(receipt["replay_uses"], 0)
            self.assertLessEqual(receipt["replay_uses"], receipt["rounds"] * 8)
            nk.verify_cell(folder, 0, nk.sha256(obs))
            receipt_path = folder / "receipt.json"
            forged = dict(receipt)
            forged["frozen_holdout_never_replayed"] = False
            nk.save_json(receipt_path, forged)
            with self.assertRaisesRegex(ValueError, "CELL_RECEIPT_REJECTED"):
                nk.verify_cell(folder, 0, nk.sha256(obs))
            nk.save_json(receipt_path, receipt)
            with (folder / "weights.pt").open("ab") as stream:
                stream.write(b"CORRUPTION")
            with self.assertRaisesRegex(ValueError, "CELL_WEIGHTS_DIGEST"):
                nk.verify_cell(folder, 0, nk.sha256(obs))

    def test_one_missing_cell_does_not_erase_other_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            obs = fake_observation(temp)
            nk.train_cell(0, obs, Path(temp) / "rivers/cell-0", steps=40, batch=24, budget=35)
            aggregate = nk.aggregate(obs, Path(temp) / "rivers", Path(temp) / "aggregate.json")
            self.assertEqual(aggregate["verified_cells"], 1)
            self.assertEqual(aggregate["expected_cells"], 6)
            self.assertEqual(len(aggregate["holdouts"]) >= 5, True)
            self.assertEqual(aggregate["synthetic_readiness"], "HOLD_PARTIAL_OR_NO_GAIN")

    def test_no_weight_or_code_promotion_in_source(self):
        source = (Path(__file__).resolve().parents[1] / "tools/janus_neural_kombucha.py").read_text()
        self.assertIn('"production_promotion": False', source)
        self.assertIn('"remote_module_import": False', source)
        self.assertIn("torch.load(weights, weights_only=True", source)
        self.assertNotIn("exec_module", source)
