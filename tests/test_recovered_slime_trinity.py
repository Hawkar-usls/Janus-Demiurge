from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    # dataclasses and other runtime introspection expect the module to be
    # registered while its class bodies are executed.
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


SLIME = load_module("janus_slime_quantization_kernel", "models/slime/slime_quantization_kernel.py")
TRINITY = load_module("janus_trinity_core", "models/trinity/trinity_core.py")


class SlimeRecoveryTests(unittest.TestCase):
    def test_three_precision_bands_and_cleanup(self):
        kernel = SLIME.SlimeQuantizationKernel()
        weights = [[0.123456, -0.765432, 0.111111], [0.333333, -0.222222, 0.444444], [0.8, -0.7, 0.6]]
        traces = [[0.85, 0.85, 0.85], [0.50, 0.50, 0.50], [0.15, 0.15, 0.15]]
        _, classes = kernel.quantize_live(weights, traces)
        self.assertEqual(classes, {"HIGH_4_DECIMAL": 3, "INT8": 3, "INT4": 3})
        payload = kernel.export_mixed({"demo": weights}, {"demo": traces})
        self.assertEqual([row["bits"] for row in payload["matrices"]["demo"]], [12, 8, 4])
        cleaned, removed = kernel.cleanup(weights, traces)
        self.assertEqual(removed, 3)
        self.assertEqual(cleaned[-1], [0.0, 0.0, 0.0])

    def test_oxytocin_bond_is_bounded_and_error_sensitive(self):
        self.assertAlmostEqual(SLIME.SlimeQuantizationKernel.oxytocin_bond(0.0), 1.0)
        self.assertGreater(SLIME.SlimeQuantizationKernel.oxytocin_bond(0.2), SLIME.SlimeQuantizationKernel.oxytocin_bond(2.0))


class TrinityRecoveryTests(unittest.TestCase):
    def test_three_views_then_critic(self):
        calls = []

        async def runner(role: str, prompt: str) -> str:
            calls.append(role)
            return f"{role}:{prompt}"

        async def synth(prompt, views):
            return "|".join(views[k] for k in ("father", "son", "spirit"))

        async def critic(prompt, draft):
            return True, draft

        council = TRINITY.TrinityCouncil(runner, synth, critic)
        result = asyncio.run(council.consult("gate"))
        self.assertTrue(result.accepted)
        self.assertEqual(set(result.views), {"father", "son", "spirit"})
        self.assertEqual(set(calls), {"strategist_logic", "seer_alternative", "doer_action"})

    def test_temporal_two_of_three(self):
        decision = TRINITY.TemporalTrinityCouncil.decide({
            "past": (0.20, 0.30),
            "present": (0.25, 0.25),
            "future": (0.50, 0.00),
        })
        self.assertEqual(decision.consensus, "accelerate")
        self.assertEqual(decision.stage_bias, 1)

        stop = TRINITY.TemporalTrinityCouncil.decide({
            "past": (0.75, 0.10),
            "present": (0.70, 0.05),
            "future": (0.20, 0.30),
        })
        self.assertEqual(stop.consensus, "stabilize")
        self.assertEqual(stop.stage_bias, -1)


if __name__ == "__main__":
    unittest.main()
