"""Synthetic reconstruction of the historical Nexus/Conductor module ABI.

Never imports E: modules, public archive source, NAS state or real providers.
"""
import asyncio
import hashlib
import unittest
from restored.legacy_nexus_conductor import build_plan, probation_run

A = "a" * 64
B = "b" * 64


def spec(name, *, sha=A, priority=10, deps=None, mode="PLUGIN", caps=None,
         reviewed=True, synthetic_only=True):
    return {"id": name, "source_sha256": sha, "mode": mode,
            "priority": priority, "dependencies": deps or [],
            "capabilities": caps if caps is not None else ["PURE_COMPUTE"],
            "reviewed": reviewed, "synthetic_only": synthetic_only}


class LegacyNexusConductorTests(unittest.IsolatedAsyncioTestCase):
    async def test_priority_dependency_order_overrides_priority(self):
        plan = build_plan([
            spec("genesis", priority=0, deps=["memory"]),
            spec("memory", priority=50),
            spec("observer", priority=5)
        ], intent="genesis awakening")
        self.assertEqual(plan["status"], "PLAN_ONLY")
        self.assertEqual(plan["order"], ["observer", "memory", "genesis"])
        self.assertEqual(plan["selected_plugin"], "genesis")
        self.assertFalse(plan["authority"]["imports_legacy_files"])

    async def test_no_approval_no_execution(self):
        p = build_plan([spec("genesis")])
        events = []
        async def run(core):
            events.append(core)
        with self.assertRaisesRegex(PermissionError, "APPROVAL"):
            await probation_run(p, target="genesis", handlers={"genesis": run},
                               core_port=object())
        self.assertEqual(events, [])

    async def test_explicit_trusted_callbacks_and_dependency(self):
        p = build_plan([spec("memory", priority=8), spec("genesis", deps=["memory"])])
        calls = []
        async def memory(core): calls.append(("memory", core))
        async def genesis(core): calls.append(("genesis", core))
        port = object()
        out = await probation_run(p, target="genesis",
                                 handlers={"genesis": genesis, "memory": memory},
                                 core_port=port, operator_approved=True)
        self.assertEqual([n for n, _ in calls], ["memory", "genesis"])
        self.assertTrue(all(x is port for _, x in calls))
        self.assertEqual(out["outcomes"]["genesis"], "PROBATION_CALLBACK_COMPLETED")
        self.assertFalse(out["authority"]["model_promoted"])
        self.assertFalse(out["authority"]["production_service_started"])

    async def test_missing_dependency_and_cycle_fail_closed(self):
        missing = build_plan([spec("genesis", deps=["unknown"])])
        self.assertEqual(missing["status"], "HOLD")
        a = build_plan([spec("a", deps=["b"]), spec("b", deps=["a"])])
        self.assertEqual(a["status"], "HOLD")
        with self.assertRaisesRegex(ValueError, "VALID_PLAN_REQUIRED"):
            await probation_run(a, target="a", handlers={}, core_port=None,
                               operator_approved=True)

    async def test_generated_unreviewed_and_network_hold(self):
        self.assertEqual(build_plan([spec("gen_unsafe", reviewed=False)])["status"], "HOLD")
        self.assertEqual(build_plan([spec("send", caps=["NETWORK"])])["status"], "HOLD")
        self.assertEqual(build_plan([spec("write", caps=["WRITE_GRAPH"])])["status"], "HOLD")

    async def test_duplicate_ids_and_malformed_hash_hold(self):
        self.assertEqual(build_plan([spec("foo"), spec("foo", sha=B)])["status"], "HOLD")
        self.assertEqual(build_plan([spec("foo", sha="missing")])["status"], "HOLD")
        self.assertEqual(build_plan([spec("../../evil")])["status"], "HOLD")

    async def test_deterministic_fallback_and_label_match(self):
        records = [spec("mod_hero", priority=15), spec("mod_genesis", priority=1)]
        x = build_plan(records, intent="Hero rises")
        y = build_plan(list(reversed(records)), intent="Hero rises")
        self.assertEqual(x["plan_sha256"], y["plan_sha256"])
        self.assertEqual(x["selected_plugin"], "mod_hero")
        self.assertEqual(build_plan(records)["selected_plugin"], "mod_genesis")

    async def test_callback_crash_isolated_and_dependency_blocked(self):
        p = build_plan([spec("base"), spec("child", deps=["base"])])
        ran = []
        async def fail(core):
            raise RuntimeError("secret exception must not leak")
        async def child(core):
            ran.append("child")
        out = await probation_run(p, target="child", handlers={"base": fail,"child": child},
                                 core_port=None, operator_approved=True)
        self.assertEqual(out["outcomes"]["base"], "PROBATION_CALLBACK_ERROR")
        self.assertEqual(out["outcomes"]["child"], "HOLD_FAILED_DEPENDENCY")
        self.assertEqual(ran, [])
        self.assertNotIn("secret", str(out))

    async def test_bounded_timeout_and_no_child_execution(self):
        p = build_plan([spec("base"), spec("child", deps=["base"])])
        ran = []
        async def hung(core):
            await asyncio.sleep(0.1)
        async def child(core):
            ran.append("child")
        out = await probation_run(p, target="child",
                                 handlers={"base": hung, "child": child},
                                 core_port=None, operator_approved=True, timeout_seconds=0.01)
        self.assertEqual(out["outcomes"]["base"], "PROBATION_TIMEOUT")
        self.assertEqual(ran, [])

    async def test_service_is_one_shot_not_detached(self):
        p = build_plan([spec("bridge", mode="SERVICE")])
        called = []
        async def bridge(core): called.append(True)
        out = await probation_run(p, target="bridge",
                                 handlers={"bridge": bridge},
                                 core_port=None, operator_approved=True)
        self.assertEqual(called, [True])
        self.assertFalse(out["authority"]["production_service_started"])

    async def test_tampered_plan_or_authority_is_rejected(self):
        p = build_plan([spec("old_genesis")])
        async def handler(core):
            raise RuntimeError("must not be called")
        p["modules"][0]["capabilities"] = ["NETWORK"]
        with self.assertRaisesRegex(ValueError, "SHA_MISMATCH"):
            await probation_run(p, target="old_genesis",
                               handlers={"old_genesis": handler},
                               core_port=None, operator_approved=True)
        p = build_plan([spec("old_genesis")])
        p["authority"]["uses_exec"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY_FIREWALL"):
            await probation_run(p, target="old_genesis",
                               handlers={"old_genesis": handler},
                               core_port=None, operator_approved=True)

    async def test_sync_handler_not_accepted(self):
        p = build_plan([spec("legacy")])
        def legacy(core):
            raise RuntimeError("should not run")
        out = await probation_run(p, target="legacy",
                                 handlers={"legacy": legacy}, core_port=None, operator_approved=True)
        self.assertEqual(out["outcomes"]["legacy"], "HOLD_TRUSTED_ASYNC_HANDLER_MISSING")


if __name__ == "__main__":
    unittest.main()
