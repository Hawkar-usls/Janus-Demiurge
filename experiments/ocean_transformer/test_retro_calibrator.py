#!/usr/bin/env python3
"""Local-independent regression tests for history-only JANUS calibration.

Fixture targets are **synthetic code tests**, not any physical/retrocause data.
The positive fixture is intentionally an artificial inverse correlation that
should activate the gate; independent random fixture must not.
"""
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time
import unittest
from types import SimpleNamespace

import retro_calibrator as c


def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj)+"\n",encoding="utf-8")


def fixture(folder,index,kind="random",seed=20261106):
    rng=random.Random(seed+index*1709)
    payload=bytes(rng.getrandbits(8) for _ in range(32))
    bits="".join(f"{b:08b}" for b in payload)
    if kind=="inverted":
        probs=[.1 if y=="1" else .9 for y in bits]
    else:
        probs=[.5] * 256
    pred="".join("1" if p>=.5 else "0" for p in probs)
    issued=time.time()-60000+index*400
    confirmed=issued+5
    generated=confirmed+121
    trial=f"synthetic-retro-{index:03}"
    base=folder/trial
    early={
        "schema":"janus.retro.lab.model_precommit.v1",
        "trial_id":trial,"model_sha256":c.MODEL_SHA,
        "issued_at_epoch_utc":issued,
        "predicted_bits":pred,
        "predicted_256_bits_sha256":hashlib.sha256(pred.encode()).hexdigest(),
        "p1_model_probs":probs
    }
    late={
        "schema":"janus.retro.lab.independent_future_rng.v1",
        "trial_id":trial,
        "receiver_commit_confirmed_epoch":confirmed,
        "future_generated_epoch_utc":generated,
        "target_payload_hex":payload.hex(),
        "target_sha256":hashlib.sha256(payload).hexdigest(),
        "future_bits":bits
    }
    comp={
        "trial_id":trial,"total_bits":256,
        "unconditional_matching_bits":sum(a==b for a,b in zip(pred,bits)),
        "late_random_sha256":late["target_sha256"]
    }
    dump(base/"early.json",early)
    dump(base/"future.json",late)
    dump(base/"comparison.json",comp)
    return base


class HistoryOnlyCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.trials=self.root/"trials"
        self.trials.mkdir()
        self.output=self.root/"result.json"

    def run_report(self,cutoff=None):
        c.report(SimpleNamespace(history_root=str(self.trials),
                    output=str(self.output),
                    as_of_epoch=cutoff if cutoff is not None else time.time()))
        result=c.read(self.output)
        self.output.unlink()
        return result

    def test_no_prior_trials_holds(self):
        record=self.run_report()
        self.assertEqual(record["previous_completed_trials"],0)
        self.assertEqual(record["status"],"HOLD_INSUFFICIENT_PRIOR_TRIALS")
        self.assertFalse(record["activated"])

    def test_partial_trials_are_ignored(self):
        fixture(self.trials,0)
        fixture(self.trials,1)
        (self.trials/"synthetic-retro-001"/"comparison.json").unlink()
        out=self.run_report()
        self.assertEqual(out["previous_completed_trials"],1)
        self.assertEqual(out["incomplete_trial_folders_skipped"],1)
        self.assertFalse(out["activated"])

    def test_random_negative_control_holds(self):
        for i in range(12):fixture(self.trials,i,kind="random")
        out=self.run_report()
        self.assertEqual(out["previous_completed_trials"],12)
        self.assertEqual(out["training_bits"],8*256)
        self.assertEqual(out["holdout_bits"],4*256)
        self.assertEqual(out["decision_epoch_completed"],1)
        self.assertFalse(out["activated"])
        self.assertEqual(out["status"],"HOLD_NO_INDEPENDENT_GAIN")

    def test_positive_code_fixture_activates_after_disjoint_holdout(self):
        for i in range(12):fixture(self.trials,i,kind="inverted")
        out=self.run_report()
        self.assertTrue(out["activated"])
        self.assertLess(out["fitted_slope"],0)
        self.assertLess(out["holdout_brier_candidate"],.01)
        self.assertLess(out["holdout_one_sided_binomial_pvalue"],out["per_epoch_significance_alpha"])
        self.assertEqual(set(out["training_trial_ids"]) & set(out["validation_trial_ids"]),set())
        self.assertEqual(out["validation_trial_ids"],[f"synthetic-retro-{j:03}" for j in range(8,12)])

    def test_one_more_trial_does_not_peek_again_at_holdout(self):
        for i in range(12):fixture(self.trials,i,kind="inverted")
        a=self.run_report()
        fixture(self.trials,12,kind="inverted")
        b=self.run_report()
        self.assertEqual(a["validation_trial_ids"],b["validation_trial_ids"])
        self.assertEqual(a["training_trial_ids"],b["training_trial_ids"])
        self.assertEqual(a["decision_epoch_completed"],b["decision_epoch_completed"])

    def test_time_cutoff_excludes_future_outcome(self):
        folders=[fixture(self.trials,i,"inverted") for i in range(12)]
        last=c.read(folders[-1]/"future.json")
        result=self.run_report(last["future_generated_epoch_utc"]-1)
        self.assertEqual(result["previous_completed_trials"],11)
        self.assertEqual(result["trials_finished_after_cutoff_skipped"],1)
        self.assertFalse(result["activated"])

    def test_corrupt_early_digest_fails_closed(self):
        folder=fixture(self.trials,0)
        early=c.read(folder/"early.json")
        early["predicted_bits"]="1"+early["predicted_bits"][1:]
        if early["predicted_bits"]==("1" if early["predicted_bits"][0]=="1" else "0"):
            pass
        # Break the digest with an explicit new byte and no corresponding hash update.
        early["predicted_bits"]=("0" if early["predicted_bits"][0]=="1" else "1")+early["predicted_bits"][1:]
        dump(folder/"early.json",early)
        with self.assertRaisesRegex(RuntimeError,"EARLY_DIGEST_FAIL"):
            self.run_report()


if __name__=="__main__":
    unittest.main(verbosity=2)
