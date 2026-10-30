"""Read-only negative controls on the ACTUAL committed JANUS checkpoint.

Never trains, promotes, overwrites or stages the canonical checkpoint. This test
checks fail-closed behavior for a forged identity claim against genuine weights.
It intentionally makes NO claim that a better canonical candidate exists.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest

import torch

from daddy_keymaster.broker import sha
from daddy_keymaster.champion_release import (
    CHECKPOINT, STATE, Hold, authoritative_state, hash_file, verify_audit,
)
from janus_model.eval_contract import DEFAULT_ANCHOR
from janus_model.model import ByteTokenizer
from janus_model.train_registry import eval_loss, load_checkpoint, promotion_gate, tokens


ROOT = Path(__file__).resolve().parents[1]


class RealCanonicalCheckpointNegativeControls(unittest.TestCase):
    def test_real_main_checkpoint_sha_and_cpu_inference(self):
        state, checkpoint_sha = authoritative_state(ROOT)
        self.assertEqual(checkpoint_sha, hash_file(ROOT / CHECKPOINT))
        self.assertEqual(checkpoint_sha, state['checkpoint_sha256'])
        self.assertEqual(len(checkpoint_sha), 64)
        self.assertEqual(len((ROOT / CHECKPOINT).read_bytes()) > 100000, True)
        torch.manual_seed(20261031)
        torch.set_num_threads(2)
        model, payload = load_checkpoint(ROOT / CHECKPOINT)
        self.assertEqual(model.config.to_dict(), state['config'])
        self.assertEqual(payload['config'], state['config'])
        anchor = tokens(DEFAULT_ANCHOR)
        baseline_loss = eval_loss(model, anchor, 2, 4, 1366)
        self.assertTrue(math.isfinite(baseline_loss))
        self.assertGreater(baseline_loss, 0.0)
        tie = promotion_gate(candidate_loss=baseline_loss,
                             incumbent_loss=baseline_loss,
                             candidate_anchor_loss=baseline_loss,
                             incumbent_anchor_loss=baseline_loss)
        self.assertFalse(tie['promote'])
        with torch.no_grad():
            torch.manual_seed(71)
            output = model.generate(
                torch.tensor([ByteTokenizer.encode('JANUS:', bos=True)]),
                max_new_tokens=4)
        self.assertGreater(output.numel(), 0)
        print(json.dumps({
            'status': 'REAL_CANONICAL_INCUMBENT_INFERENCE_PASS__NO_WINNER',
            'checkpoint_sha256': checkpoint_sha, 'anchor_loss': baseline_loss,
            'promotion_on_tie': tie['promote'],
        }, sort_keys=True))

    def test_corrupted_real_checkpoint_refused_without_deserializing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checkpoint = root / CHECKPOINT
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / CHECKPOINT, checkpoint)
            statefile = root / STATE
            statefile.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / STATE, statefile)
            with checkpoint.open('r+b') as f:
                f.seek(100)
                old = f.read(1)
                f.seek(100)
                f.write(bytes([old[0] ^ 1]))
            with self.assertRaisesRegex(Hold, 'INCUMBENT_STATE_MISMATCH'):
                authoritative_state(root)
            # No torch.load attempt on these deliberately corrupted bytes.

    def test_forged_audit_cannot_repromote_the_same_real_weights(self):
        checkpoint_sha = hash_file(ROOT / CHECKPOINT)
        bad = {
            'schema': 'janus.daddy_keymaster.native_calibration_audit.v1',
            'status': 'BEST_CANDIDATE_REVIEW_ONLY',
            'main_checkpoint_mutated': False,
            'automatic_production_promotion': False,
            'incumbent_checkpoint_sha256': checkpoint_sha,
            'commit': '1' * 40, 'source_digest': '2' * 64,
            'evaluation_contract_sha256': '3' * 64,
            'workers': [
                {'architecture': 'X64',
                 'verdict': 'INDEPENDENTLY_VERIFIED_BETTER',
                 'candidate_checkpoint_sha256': checkpoint_sha},
                {'architecture': 'ARM64', 'verdict': 'REJECTED_BY_ORIGINAL_GATE'}],
            'winner': {'architecture': 'X64',
                       'candidate_checkpoint_sha256': checkpoint_sha},
        }
        bad['receipt_sha256'] = sha(bad)
        with self.assertRaisesRegex(Hold, 'CANDIDATE_IDENTICAL_TO_INCUMBENT'):
            verify_audit(bad, checkpoint_sha, checkpoint_sha)


if __name__ == '__main__':
    unittest.main()
