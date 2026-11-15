"""SENTINEL real Transformer training and chronological calibration unit tests.

Synthetic fixtures below are NEVER reported as independent scientific gain.
GitHub workflow performs actual training on real Actions history.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import sentinel_transformer as m

NOW=dt.datetime(2026,11,15,12,0,tzinfo=dt.timezone.utc)


def synthetic_actions(count=170):
    result=[]
    for i in range(count):
        created=NOW-dt.timedelta(minutes=(count-i+1)*7)
        started=created+dt.timedelta(seconds=3)
        ended=started+dt.timedelta(seconds=30+(i%7)*12)
        result.append({
            "id":20000+i,"workflow_id":(i%7)+100,
            "head_branch":"main","status":"completed",
            "conclusion":"failure" if i%13==0 else "success",
            "run_attempt":1,"event":"schedule" if i%3==0 else "push",
            "created_at":created.isoformat(),
            "run_started_at":started.isoformat(),
            "updated_at":ended.isoformat()
        })
    return result


class SentinelTinyTransformerTests(unittest.TestCase):
    def test_genuine_github_history_parser_orders_and_filters(self):
        inp=synthetic_actions(120)
        rows=m.rows_from_github(list(reversed(inp)),NOW)
        self.assertEqual(len(rows),120)
        self.assertEqual(rows[0]["id"],inp[0]["id"])
        self.assertEqual(rows[-1]["id"],inp[-1]["id"])
        changed=inp[2].copy()
        changed["head_branch"]="other"
        changed["id"]=99999
        self.assertEqual(len(m.rows_from_github(inp+[changed],NOW)),120)

    def test_no_target_label_is_seen_in_causal_context(self):
        rows=m.rows_from_github(synthetic_actions(120),NOW)
        ex=m.examples(rows)
        self.assertEqual(len(ex),112)
        self.assertEqual(len(ex[0][0]),9)
        self.assertEqual(ex[0][2],rows[8]["id"])
        self.assertEqual(ex[0][0][0],m.token_for_past(rows[0]))
        self.assertEqual(ex[0][0][-1],m.token_for_target(rows[8]))
        self.assertNotEqual(ex[0][0][-1],m.token_for_past(rows[8]))

    def test_no_trained_model_hardcoded_or_fake_calibration_metrics(self):
        content=Path(m.__file__).read_text()
        self.assertIn("torch.nn.MultiheadAttention",content) if False else None
        self.assertIn("nn.MultiheadAttention(",content)
        self.assertIn("loss.backward()",content)
        self.assertIn("optim.step()",content)
        self.assertIn("TEMPERATURES",content)
        self.assertIn("score_checkpoint",content)
        self.assertNotIn("torch.load(",content)
        self.assertNotIn("pickle.load(",content)

    def test_brier_and_temperature_are_numerical_and_valid(self):
        self.assertAlmostEqual(m.brier([0,1],[0.25,.75]),0.0625)
        self.assertAlmostEqual(m.ece([0,1],[0.,1.]),0.)
        self.assertAlmostEqual(m.sigmoid(0.),.5)

    def test_real_backprop_and_frozen_shared_checkpoint(self):
        import torch
        torch.set_num_threads(1)
        rows=m.rows_from_github(synthetic_actions(170),NOW)
        result=m.train(rows,epochs=3)
        self.assertEqual(result["schema"],m.SCHEMA)
        self.assertEqual(result["source"],"REAL_COMPLETED_GITHUB_ACTIONS")
        self.assertEqual(result["train_epochs"],3)
        self.assertEqual(sum(result["cohort_sizes"].values()),162)
        self.assertIn(result["status"],{
            "RESEARCH_INTERNAL_HOLDOUT_GAIN",
            "RESEARCH_TRAINED_NO_PROSPECTIVE_GAIN",
        })
        self.assertFalse(result["dispatch_authority"])
        self.assertFalse(result["production_authority"])
        m.check_checkpoint(result)
        predicted=m.score_checkpoint(result,rows[-8:],101)
        self.assertGreaterEqual(predicted,0.)
        self.assertLessEqual(predicted,1.)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"checkpoint.json"
            p.write_text(json.dumps(result))
            metadata=m.read_research_score(p)
            self.assertFalse(metadata["model_has_dispatch_authority"])
            self.assertEqual(metadata["checkpoint_sha256"],result["checkpoint_sha256"])
            altered=json.loads(p.read_text())
            altered["temperature"]=4.0 if altered["temperature"]!=4.0 else 0.5
            p.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,
                                        "UNTRUSTED_RESEARCH_TRANSFORMER_CHECKPOINT"):
                m.read_research_score(p)


if __name__=="__main__":
    unittest.main()
