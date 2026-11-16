"""No-network fail-closed safety tests for real Qwen staged HTTP rollback."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools import essence_v54_qwen_stage as m


class QwenStageTests(unittest.TestCase):
    def test_static_model_allowlist_and_stage_policy(self):
        self.assertEqual(set(m.MODELS),{"g2","g3"})
        self.assertEqual(m.PARENT,len(m.PARENT)*"z" if False else m.MODELS["g2"])
        self.assertNotEqual(m.PARENT,m.CHILD)
        self.assertEqual(m.verify_route(m.route("g2")),"g2")
        self.assertEqual(m.verify_route(m.route("g3")),"g3")
        self.assertFalse(m.route("g3")["production_authority"])
        self.assertFalse(m.route("g3")["sentinel_dispatch"])
        for name in ("latest","main","production","../model","",None):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    m.route(name)

    def test_reject_escalated_or_tampered_active_routing(self):
        original=m.route("g2")
        for change in (
            {"target":"g3"},
            {"production_authority":True},
            {"sentinel_dispatch":True},
            {"adapter_sha256":m.CHILD},
            {"staging_only":False},
            {"sha256":"f"*64},
        ):
            with self.subTest(change=change):
                t=dict(original,**change)
                with self.assertRaises(ValueError):
                    m.verify_route(t)
        extra=m.seal({k:v for k,v in original.items() if k!="sha256"}|
                     {"secret_token":"accident"})
        with self.assertRaisesRegex(ValueError,"ROUTE_ESCALATION"):
            m.verify_route(extra)

    def test_atomic_routing_switch_rejects_untrusted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(ValueError,"INVALID_STAGE_DIR"):
                m.switch(root/"missing","g3")
            m.switch(root,"g2")
            self.assertEqual(m.load_route(root),"g2")
            m.switch(root,"g3")
            self.assertEqual(m.load_route(root),"g3")
            (root/"active.json").write_text('{"target":"g2"}')
            with self.assertRaises(ValueError):
                m.load_route(root)
            (root/"active.json").write_text('{"v":NaN}')
            with self.assertRaisesRegex(ValueError,"NONFINITE_JSON"):
                m.load_route(root)
            (root/"active.json").write_text('{"v":1,"v":2}')
            with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
                m.load_route(root)

    def test_model_provenance_fails_on_fake_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"parent"
            b=Path(tmp)/"child"
            a.mkdir();b.mkdir()
            for d in (a,b):
                (d/"adapter_model.safetensors").write_bytes(b"x"*3000)
                (d/"lineage.json").write_text(json.dumps(
                    m.seal({"generation":2,"adapter_sha256":m.PARENT})))
            with self.assertRaisesRegex(ValueError,"ADAPTER_BYTES_WRONG"):
                m.verify_pair(a,b)

    def test_live_service_requires_independent_runner_not_production(self):
        y=(Path(__file__).resolve().parents[1]/
           ".github/workflows/essence-v54-qwen-stage.yml").read_text()
        self.assertIn("real-live-qwen-loopback-rollout",y)
        self.assertIn("ref: essence-peer-shadow-state",y)
        self.assertIn("permissions:\n  contents: read",y)
        self.assertIn("staging-ephemeral",y)
        self.assertNotIn("actions: write",y)
        self.assertNotIn("production-deployment",y)
        self.assertIn("vars.ESSENCE_EVOLUTION_PAUSED != 'true'",y)
        s=(Path(__file__).resolve().parents[1]/
           "tools/essence_v54_qwen_stage.py").read_text()
        self.assertIn('ThreadingHTTPServer(("127.0.0.1",0)',s)
        self.assertIn("INJECTED_QWEN_STAGE_FAULT",s)
        self.assertIn("ST54_ROLLBACK_NOT_IDENTICAL",s)
        self.assertIn('"real_production_rollback_proven":False',s)
        self.assertIn('"actual_production_service_modified":False',s)


if __name__=="__main__":
    unittest.main()
