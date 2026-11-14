"""ESSENCE v1.9 localhost, real-neural-inference canary contract tests."""
from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import essence_v19_gradirnya as e
from tools import essence_v19_http_canary as c

class EphemeralServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        root=Path(tmp.name)
        data=root/"data"
        data.mkdir()
        for day in range(44):
            dt=(datetime.date(2026,7,1)+datetime.timedelta(days=day)).isoformat()
            for i,name in enumerate(("LINEAR","TRUMP","OSIRIS","CONNECTION","ECHO")):
                (data/f"JANUS-{name}-{dt}-CELL{day}-{i}.json").write_text(
                    json.dumps({"schema":"experiment","class":i,
                                f"source_{i}":1,"observed_date":dt,"context":{"i":i}}))
        cls.manifest=e.prepare(data,"f"*40,root/"splits")
        cls.validation=e.read_json(root/"splits"/"validation.json")
        cls.receipt=e.train(0,e.read_json(root/"splits"/"train.json"),
                            cls.validation,cls.manifest,root/"child",steps=40)
        cls.weights=root/"child"/"offspring.pt"
        cls.root=root

    def test_real_http_canary_fault_then_automatic_same_service_rollback(self):
        if not self.receipt["accepted_generations"]:
            self.skipTest("No validation-approved research child; fail-closed HOLD")
        result=c.exercise(self.weights,self.receipt,self.validation,
                          self.root/"service_receipt.json",requests=100)
        self.assertEqual(result["gate"],"PASS_ISOLATED_HTTP_RESEARCH_SERVICE_ONLY")
        self.assertEqual(result["actual_canary_requests"],100)
        self.assertEqual(result["rollbacks"],1)
        self.assertFalse(result["live_production_service_tested"])
        self.assertEqual(result["service_status_after"]["active_sha256"],
                         self.receipt["initial_weights_sha256"])

    def test_no_private_or_external_service_authority(self):
        manager=c.NeuralCanary(self.weights,self.receipt)
        self.assertFalse(manager.status()["production_authority"])
        with self.assertRaises(PermissionError):
            manager.change("canary","wrong-token")
        with self.assertRaises(ValueError):
            manager.predict([999,0])
        with self.assertRaises(ValueError):
            manager.change("unknown",manager.token)

    def test_checkpoint_tamper_rejected(self):
        bad=self.root/"forged.pt"
        bad.write_bytes(self.weights.read_bytes()+b"extra")
        with self.assertRaisesRegex(ValueError,"SERVICE_SHA_BINDING_FAILURE"):
            c.NeuralCanary(bad,self.receipt)

    def test_research_canary_cannot_consume_heldout_packet(self):
        held=e.read_json(self.root/"splits"/"holdout.json")
        with self.assertRaisesRegex(ValueError,"SERVICE_MUST_NOT_USE_SEALED_HOLDOUT"):
            c.exercise(self.weights,self.receipt,held,
                       self.root/"should_not_exist.json",requests=100)

    def test_canary_budget_bounded(self):
        with self.assertRaisesRegex(ValueError,"CANARY_REQUEST_BUDGET"):
            c.exercise(self.weights,self.receipt,self.validation,
                       self.root/"bad.json",requests=20000)

if __name__=="__main__":unittest.main()
