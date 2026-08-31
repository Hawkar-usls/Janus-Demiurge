from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "demiurge_reverse_spiral_council_v3.py"
spec = importlib.util.spec_from_file_location("reverse_council_v3", MODULE_PATH)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def payload(guarded=None):
    return {
        "schema": "janus.demiurge.reverse_spiral_council_input.v1",
        "new_result": {
            "verdict": "CALIBRATION_SEQUENCE_PROVENANCE_RECOVERED__RAW_SEQUENCE_BYTES_NOT_PUBLICLY_RECOVERED_IN_THIS_PASS",
            "scientific_negative": False,
        },
        "progress_guard": {
            "nonrepeatable_gate_ids": list(guarded or []),
            "reasons": {},
        },
        "authority": {"target_identity": "UNCONFIRMED", "authority_delta_for_119hz": 0},
    }


def votes(p):
    mission = m.v1.load_mission()
    return [m.run_role(role["id"], p) for role in mission["roles"]]


def test_v3_moves_forward_after_calibration_recovery_and_old_archive_block():
    guarded = [
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1",
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1",
    ]
    p = payload(guarded)
    vv = votes(p)
    assert len(vv) == 17
    for vote in vv:
        assert vote["selector_version"] == "V3_MONOTONIC_EVIDENCE_PROGRESS"
        for gate in guarded:
            row = next(r for r in vote["ranked_candidates"] if r["gate_id"] == gate)
            assert row["score"] == -850.0
        target = next(r for r in vote["ranked_candidates"] if r["gate_id"] == "COUSTEAU_HA10_119HZ_REINTERPRETATION")
        assert target["score"] == -1000.0
    result = m.aggregate(vv, p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1"
    assert result["gate_stats"]["COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1"]["top1_votes"] == 17
    assert result["authority"]["authority_delta_for_119hz"] == 0
    assert result["authority"]["target_identity"] == "UNCONFIRMED"


def test_v3_without_explicit_progress_guard_preserves_default_ranking():
    p = payload([])
    result = m.aggregate(votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"
    assert result["nonrepeatable_due_to_data_boundary"] == []


def test_v3_rejects_unknown_nonrepeatable_gate():
    p = payload(["NOT_A_REAL_GATE"])
    try:
        m.explicit_nonrepeatable(p)
    except ValueError as exc:
        assert "UNKNOWN_NONREPEATABLE_GATE" in str(exc)
    else:
        raise AssertionError("expected unknown gate rejection")
