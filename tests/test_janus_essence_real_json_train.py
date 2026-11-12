"""R1: strict time holdouts, SHA lineage, deterministic real-data gradient training."""
import datetime
import json
from pathlib import Path
import tempfile
import unittest
import torch

from tools import janus_essence_real_json_train as r


class RealRegistryTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=self.root/"data"
        self.data.mkdir()
        # Real-shape JSON fixtures, not real historical content. CI worker uses
        # actual version-pinned Meta Registry checkout for its real run.
        for day in range(42):
            dt=(datetime.date(2026,8,1)+datetime.timedelta(days=day)).isoformat()
            for j in range(5):
                label=["JANUS-LINEAR","JANUS-TRUMP","JANUS-OSIRIS",
                       "ROWAN","SCOBY"][j]
                path=self.data/(f"{label}-{dt}-CASE{day:02}-{j}.json")
                payload={"artifact_id":f"{label}-{dt}","status":"PASS",
                         "measurements":{"n":3},"observed":dt,
                         f"feature_{j}":float(j)}
                path.write_text(json.dumps(payload))

    def test_source_dates_disjoint_and_never_random_split(self):
        g, d=r.collect(self.data)
        self.assertEqual(d["count"],210)
        self.assertEqual(d["split_sizes"]["train"]+d["split_sizes"]["validation"]
                         +d["split_sizes"]["test"],210)
        ds=[set(x["date"] for x in v) for v in g.values()]
        self.assertFalse(ds[0]&ds[1] or ds[1]&ds[2] or ds[0]&ds[2])
        self.assertTrue(d["keys_only"])
        self.assertEqual(len(d["dataset_sha256"]),64)

    def test_dedup_version_copies(self):
        original=self.data/"JANUS-TRUMP-2026-08-01-CASE00-1.json"
        (self.data/"JANUS-TRUMP-2026-08-01-CASE00-1-v1.1.json").write_bytes(original.read_bytes())
        _,d=r.collect(self.data)
        self.assertEqual(d["count"],210)
        self.assertGreaterEqual(d["skipped"]["duplicate"],1)

    def test_real_shape_cpu_update_then_sealed_holdout(self):
        receipt=r.train(0,self.data,"a"*40,self.root/"cell-0",steps=20)
        self.assertTrue(receipt["model_trained_on_real_json"])
        self.assertIsNone(receipt["test_metrics"])
        self.assertEqual(receipt["train_steps"],20)
        self.assertFalse(receipt["weights_deployed"])
        self.assertNotEqual(receipt["validation_before"]["nll"],
                            receipt["validation_after"]["nll"])
        # Missing siblings are a HOLD, and the surviving cell is still verified.
        output=r.verify(self.data,"a"*40,self.root,self.root/"verifier.json")
        self.assertEqual(output["verified_cells"],1)
        self.assertEqual(len(output["failures"]),5)
        self.assertEqual(output["status"],"HOLD_PARTIAL_OR_UNPROVEN")

    def test_no_value_or_secret_in_model_features(self):
        a=r.tokenize_keys(["hello","credential"])
        b=r.tokenize_keys(["hello","credential"])
        self.assertEqual(a,b)
        self.assertEqual(len(a),r.CONFIG.context_length)
        # Labels are determined by source naming, not read from JSON values.
        self.assertEqual(r.label_for("JANUS-LINEAR-2026-08-10-v1.json"),0)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            r.train(0,self.data,"main",self.root/"bad",steps=20)
        with self.assertRaises(ValueError):
            r.model_for(8)


if __name__=="__main__":
    unittest.main()
