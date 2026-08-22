from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "demiurge_reverse_spiral_council.py"
spec = importlib.util.spec_from_file_location("reverse_council", MODULE_PATH)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def payload(verdict: str):
    return {
        "schema": "janus.demiurge.reverse_spiral_council_input.v1",
        "new_result": {"verdict": verdict},
        "authority": {"target_identity": "UNCONFIRMED", "authority_delta_for_119hz": 0},
    }


def all_votes(p):
    mission = m.load_mission()
    return [m.run_role(role["id"], p) for role in mission["roles"]]


def test_mission_has_exactly_17_unique_roles():
    mission = m.load_mission()
    assert len(mission["roles"]) == 17
    assert len({r["id"] for r in mission["roles"]}) == 17


def test_119_reinterpretation_is_always_vetoed():
    p = payload("PUBLIC_STATIONXML_DOES_NOT_ENCODE_KNOWN_FAULT_ERA_CHANGE")
    for vote in all_votes(p):
        row = next(r for r in vote["ranked_candidates"] if r["gate_id"] == "COUSTEAU_HA10_119HZ_REINTERPRETATION")
        assert row["score"] == -1000
        assert "COUSTEAU_HA10_119HZ_REINTERPRETATION" in vote["vetoes"]
        assert vote["authority"]["authority_delta_for_119hz"] == 0


def test_nonencoding_result_selects_direct_triplet_gate():
    p = payload("PUBLIC_STATIONXML_DOES_NOT_ENCODE_KNOWN_FAULT_ERA_CHANGE")
    result = m.aggregate(all_votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"
    assert result["authority"]["council_output_is_scientific_evidence"] is False


def test_encoding_result_still_selects_direct_triplet_gate():
    p = payload("PUBLIC_STATIONXML_ENCODES_FAULT_ERA_RESPONSE_CHANGE")
    result = m.aggregate(all_votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"


def test_mixed_result_selects_direct_triplet_gate():
    p = payload("MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING")
    result = m.aggregate(all_votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"


def test_blocked_metadata_still_allows_raw_first_direct_triplet_gate():
    p = payload("BLOCKED_PUBLIC_RESPONSE_EPOCH_AUDIT")
    result = m.aggregate(all_votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"


def test_aggregate_rejects_missing_role():
    p = payload("MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING")
    with pytest.raises(ValueError, match="17_UNIQUE_ROLE_VOTES"):
        m.aggregate(all_votes(p)[:-1], p)


def test_aggregate_rejects_input_hash_mismatch():
    p = payload("MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING")
    votes = all_votes(p)
    votes[0]["input_sha256"] = "wrong"
    with pytest.raises(ValueError, match="SAME_INPUT"):
        m.aggregate(votes, p)
