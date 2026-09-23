from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from janus_model.keymaster_trump_bridge import (
    BRIDGE_SCHEMA,
    build_bridge,
    load_json,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "trump" / "TRUMP_MANIFEST.json"


def fake_report() -> dict:
    return {
        "schema": "janus.keymaster.mechanism_composition_report.v1",
        "report_sha256": "a" * 64,
        "progress_readout": {
            "schema": "janus.keymaster.progress_readout.v1",
            "metric_kind": "PROOF_OBLIGATION_COMPLETENESS_NOT_PROBABILITY",
            "stage": 2,
            "stage_max": 5,
            "stage_label": "ONE_INTERFACE_AWAY_ON_BEST_TYPED_ROUTE",
            "best_route_coverage_percent": 90.0,
            "best_route": {
                "from_type": "A",
                "to_type": "B",
                "proved_context_edges": 9,
                "complete_path_edges_if_closed": 10,
                "lockpick_score": 90,
            },
            "authoritative_complete_route_count": 0,
            "shadow_complete_route_count": 0,
            "p_equals_np_probability": None,
            "p_vs_np": "OPEN",
            "proof_authorized": False,
            "laws": ["ROUTE_COVERAGE_PERCENT_IS_NOT_P_EQUALS_NP_PROBABILITY"],
        },
        "firewall": {
            "fundamentum_is_scientific_authority": True,
            "automatic_theorem_promotion": False,
            "automatic_d1_promotion": False,
            "automatic_p_equals_np_claim": False,
            "training_signal_is_evidence": False,
            "complete_path_is_proof": False,
            "path_requires_independent_replay": True,
            "D1": "EMPTY",
            "P_VS_NP": "OPEN",
        },
    }


class KeymasterTrumpBridgeTests(unittest.TestCase):
    def test_current_manifest_selects_one_admitted_runtime(self) -> None:
        manifest = load_json(MANIFEST)
        bridge = build_bridge(fake_report(), manifest)
        self.assertEqual(bridge["schema"], BRIDGE_SCHEMA)
        self.assertEqual(bridge["status"], "CANDIDATE_RUNTIME_SELECTED")
        self.assertEqual(bridge["selected_source_id"], "C025_UNIFIED_PROOF_CARRYING_AKINATOR_JEC")
        self.assertEqual(bridge["eligible_source_count"], 1)
        self.assertEqual(bridge["progress_readout"]["best_route_coverage_percent"], 90.0)
        self.assertFalse(bridge["firewall"]["route_coverage_is_probability"])
        self.assertFalse(bridge["self_application"]["proof_authority"])
        self.assertFalse(bridge["self_application"]["direct_main_writeback"])

    def test_higher_evidence_rank_wins_before_tie_break_priority(self) -> None:
        manifest = load_json(MANIFEST)
        base = copy.deepcopy(manifest["candidate_sources"][0])
        base["id"] = "LOWER_EVIDENCE_HIGH_PRIORITY"
        base["runtime_role"] = "EXECUTABLE_CANDIDATE"
        base["runtime_selection"]["evidence_level"] = "PINNED_SOURCE"
        base["runtime_selection"]["tie_break_priority"] = 9999

        stronger = copy.deepcopy(manifest["candidate_sources"][0])
        stronger["id"] = "HIGHER_EVIDENCE_LOW_PRIORITY"
        stronger["runtime_role"] = "EXECUTABLE_CANDIDATE"
        stronger["runtime_selection"]["evidence_level"] = "INDEPENDENT_REPLAY_PASS"
        stronger["runtime_selection"]["tie_break_priority"] = 1

        manifest["candidate_sources"] = [base, stronger]
        bridge = build_bridge(fake_report(), manifest)
        self.assertEqual(bridge["selected_source_id"], "HIGHER_EVIDENCE_LOW_PRIORITY")

    def test_authority_escalation_is_rejected(self) -> None:
        manifest = load_json(MANIFEST)
        manifest["activation"]["proof_authority"] = True
        with self.assertRaisesRegex(RuntimeError, "AUTHORITY_CEILING"):
            build_bridge(fake_report(), manifest)

    def test_probability_field_is_forbidden(self) -> None:
        report = fake_report()
        report["progress_readout"]["p_equals_np_probability"] = 0.9
        manifest = load_json(MANIFEST)
        with self.assertRaisesRegex(RuntimeError, "PNP_PROBABILITY_FORBIDDEN"):
            build_bridge(report, manifest)


if __name__ == "__main__":
    unittest.main()
