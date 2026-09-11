import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from janus_model.extensions import trump_frontier_attention as tfa


class TrumpFrontierAttentionTests(unittest.TestCase):
    def frontier(self):
        return {
            "schema": "janus.trump.frontier_observation.v1",
            "status": "READ_ONLY_ADVISORY_FRONTIER",
            "observation_sha256": "f" * 64,
            "candidates": [
                {
                    "ref": "refs/heads/proof/trump-alpha-2026-09-11",
                    "commit": "a" * 40,
                    "date_hint": "2026-09-11",
                },
                {
                    "ref": "refs/heads/research/janus-trump-beta-2026-09-10",
                    "commit": "b" * 40,
                    "date_hint": "2026-09-10",
                },
            ],
            "authority": {
                "read_only_observation": True,
                "changes_active_lineage": False,
                "changes_proof_ladder": False,
                "grants_theorem_authority": False,
                "grants_runtime_promotion": False,
                "mutates_observed_repository": False,
            },
        }

    def write_frontier(self, root: Path) -> Path:
        path = root / "frontier.json"
        path.write_text(json.dumps(self.frontier()), encoding="utf-8")
        return path

    def test_frontier_authority_leak_is_rejected(self):
        obj = self.frontier()
        obj["authority"]["mutates_observed_repository"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY_REJECTED"):
            tfa.validate_frontier(obj)

    def test_native_checkpoint_can_select_one_branch_but_gains_no_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            checkpoint = root / "brain.pt"
            checkpoint.write_bytes(b"checkpoint")
            frontier = self.write_frontier(root)

            def score(_model, _prompt, continuation):
                if "trump-alpha" in continuation:
                    return 1.0
                if "trump-beta" in continuation:
                    return 1.4
                return 1.8

            with mock.patch.object(tfa, "load_checkpoint", return_value=(object(), {})), \
                 mock.patch.object(tfa, "sha256_file", return_value="c" * 64), \
                 mock.patch.object(tfa, "continuation_avg_nll", side_effect=score):
                out = tfa.choose_frontier(checkpoint, frontier, margin=0.01)

        self.assertEqual(out["status"], "READ_ONLY_INSPECTION_SELECTED")
        self.assertEqual(out["selected"]["commit"], "a" * 40)
        self.assertEqual(out["scientific_boundary"]["P_VS_NP"], "OPEN")
        self.assertFalse(out["authority"]["may_write_observed_repository"])
        self.assertFalse(out["authority"]["may_change_active_lineage"])
        self.assertFalse(out["authority"]["may_promote_theorem"])
        self.assertFalse(out["authority"]["may_merge"])

    def test_insufficient_margin_forces_abstention(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            checkpoint = root / "brain.pt"
            checkpoint.write_bytes(b"checkpoint")
            frontier = self.write_frontier(root)

            def score(_model, _prompt, continuation):
                if "trump-alpha" in continuation:
                    return 1.000
                if "trump-beta" in continuation:
                    return 1.005
                return 1.020

            with mock.patch.object(tfa, "load_checkpoint", return_value=(object(), {})), \
                 mock.patch.object(tfa, "sha256_file", return_value="c" * 64), \
                 mock.patch.object(tfa, "continuation_avg_nll", side_effect=score):
                out = tfa.choose_frontier(checkpoint, frontier, margin=0.01)

        self.assertEqual(out["status"], "ABSTAIN")
        self.assertEqual(out["reason"], "INSUFFICIENT_TOP_MARGIN__ABSTAIN")
        self.assertIsNone(out["selected"]["commit"])

    def test_no_inspection_may_win_naturally(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            checkpoint = root / "brain.pt"
            checkpoint.write_bytes(b"checkpoint")
            frontier = self.write_frontier(root)

            def score(_model, _prompt, continuation):
                return 0.5 if continuation == "NO_INSPECTION" else 1.0

            with mock.patch.object(tfa, "load_checkpoint", return_value=(object(), {})), \
                 mock.patch.object(tfa, "sha256_file", return_value="c" * 64), \
                 mock.patch.object(tfa, "continuation_avg_nll", side_effect=score):
                out = tfa.choose_frontier(checkpoint, frontier)

        self.assertEqual(out["status"], "ABSTAIN")
        self.assertEqual(out["reason"], "TOP_IS_NO_INSPECTION")


if __name__ == "__main__":
    unittest.main()
