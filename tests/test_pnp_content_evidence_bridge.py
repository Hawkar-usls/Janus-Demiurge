"""Offline source-content and adversarial replay tests. Never use network."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pnp_content_evidence_bridge as bridge
from beetle_runtime_consumer import _context, _write, CAPABILITIES


def topa_example() -> dict:
    return {
        "artifact_id": "TOPA-P-VS-NP-ISSUE-211-REFUTATION-FINAL-2026-08-24-v1.0",
        "status": "REFUTED_FOR_CURRENT_POLICY0A",
        "mathematical_effect": {"P_VS_NP": "OPEN", "P_EQUALS_NP": "NOT_ESTABLISHED"},
        "counterfamily": {"name": "PADDED_DIRECTED_GT_WITH_RESOLUTION_SINK",
                          "n_min": 3, "B": "256*n^2", "p": "64*n^2"},
        "ci": {"frozen_n3": {"literal_count": 31140, "attempt_budget": 124560,
                              "sink_pair_attempts_available": 331776,
                              "resolution_attempts": 124560, "resolution_additions": 0,
                              "branch_variable_class": "GT_CORE"}},
    }


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.f = self.root / "fundamentum"
        self.t = self.root / "topa"
        self.f.mkdir()
        self.t.mkdir()
        (self.f / bridge.FUNDAMENTUM_STATUS).parent.mkdir(parents=True)
        (self.f / bridge.FUNDAMENTUM_STATUS).write_text(
            "# A3 test fixture\nP_VS_NP = OPEN\n"
            "2^s * 3^r\nGENERAL_MATROID_PATHWIDTH_COMPLEXITY = UNCHANGED\n", encoding="utf-8")
        self.topa_file = self.t / bridge.TOPA_COUNTEREXAMPLE
        self.topa_file.parent.mkdir(parents=True)
        self.topa_file.write_text(json.dumps(topa_example()), encoding="utf-8")
        self.ctx = self.root / "CONTEXT.json"
        self.ack = self.root / "PROCESSING_ACK.json"
        context = _context([], 84)
        self.ctx.write_text(json.dumps(context), encoding="utf-8")
        self.ack.write_text(json.dumps({
            "schema": "janus.beetle.processing_ack.v1",
            "status": "TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED",
            "target_repository": "Hawkar-usls/Janus-Demiurge",
            "last_sequence": 84,
            "receipt_sha256": "e" * 64,
        }), encoding="utf-8")
        self.fsha = "a" * 40
        self.tsha = "b" * 40
        self.bsha = "c" * 40

    def build(self):
        with patch.object(bridge, "source_sha", side_effect=[self.fsha, self.tsha]):
            return bridge.build(self.f, self.t, self.ctx, self.ack, self.bsha)

    def test_source_bound_bounded_evidence_not_proof(self):
        bundle = self.build()
        self.assertEqual(bridge.validate_bundle(bundle, self.fsha), bundle)
        self.assertEqual(bundle["fundamentum"]["independent_finite_replay"]["case_count"], 16)
        finite = bundle["topa"]["independent_finite_replay"]
        self.assertEqual(finite["sink_pair_resolvents_checked"], 331776)
        self.assertEqual(finite["attempt_budget"], 124560)
        self.assertTrue(finite["all_sink_resolvents_tautological"])
        self.assertFalse(finite["source_refutation_proved_from_finite_check"])
        self.assertFalse(finite["full_policy0a_replay_executed"])
        self.assertEqual(bundle["beetle"]["last_processed_sequence"], 84)
        self.assertFalse(bundle["beetle"]["independent_source_truth_established"])
        self.assertEqual(bundle["research_handback"]["JANUS-PNP-POLY-SAT-CANDIDATE"][0],
                         "TOPA:C024_POLICY0A_RESIDUAL_POLYNOMIAL_BOUND")
        self.assertEqual(bundle["p_vs_np"], "OPEN")

    def test_topa_source_tamper_is_rejected(self):
        for mutation in (
            {"literal_count": 31139}, {"attempt_budget": 124561},
            {"sink_pair_attempts_available": 331777}, {"resolution_additions": 1}
        ):
            case = topa_example()
            case["ci"]["frozen_n3"].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(bridge.EvidenceHold):
                bridge.check_topa_finite_sink(case)

    def test_beetle_missing_ack_cannot_be_a_receipt(self):
        ack = json.loads(self.ack.read_text())
        ack["last_sequence"] = 83
        self.ack.write_text(json.dumps(ack))
        with self.assertRaises(bridge.EvidenceHold):
            self.build()

    def test_beetle_context_hash_cannot_be_spoofed(self):
        ctx = json.loads(self.ctx.read_text())
        ctx["hypothesis_routes"] = ["unverified false proof claim"]
        self.ctx.write_text(json.dumps(ctx))
        with self.assertRaises(ValueError):
            self.build()

    def test_bundle_sha_and_source_mutation_fail_closed(self):
        obj = self.build()
        obj["topa"]["source_reported_result"] = "P_EQUALS_NP_PROVED"
        with self.assertRaises(bridge.EvidenceHold):
            bridge.validate_bundle(obj, self.fsha)
        obj = self.build()
        with self.assertRaises(bridge.EvidenceHold):
            bridge.validate_bundle(obj, "0" * 40)
        obj = self.build()
        obj["authority"]["promote_p_vs_np"] = True
        obj.pop("bundle_sha256")
        obj["bundle_sha256"] = bridge.digest(obj)
        with self.assertRaises(bridge.EvidenceHold):
            bridge.validate_bundle(obj, self.fsha)

    def test_fundamentum_status_requires_open_global_question(self):
        status = self.f / bridge.FUNDAMENTUM_STATUS
        status.write_text("P_VS_NP = PROVED\n2^s * 3^r\nGENERAL_MATROID_PATHWIDTH_COMPLEXITY = UNCHANGED\n")
        with self.assertRaises(bridge.EvidenceHold):
            self.build()


if __name__ == "__main__":
    unittest.main()
