from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "demiurge_reverse_spiral_council_v2.py"
spec = importlib.util.spec_from_file_location("reverse_council_v2", MODULE_PATH)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def payload(verdict: str, *, executed_gate: str | None = None, data_boundary: bool = False, access_changed: bool = False):
    p = {
        "schema": "janus.demiurge.reverse_spiral_council_input.v1",
        "new_result": {
            "verdict": verdict,
            "data_boundary": data_boundary,
            "access_condition_changed": access_changed,
        },
        "authority": {"target_identity": "UNCONFIRMED", "authority_delta_for_119hz": 0},
    }
    if executed_gate:
        p["previous_council"] = {"executed_gate": executed_gate}
    return p


def all_votes(p):
    mission = m.v1.load_mission()
    return [m.run_role(role["id"], p) for role in mission["roles"]]


def test_v2_preserves_17_role_council_and_119_veto():
    p = payload("PUBLIC_STATIONXML_DOES_NOT_ENCODE_KNOWN_FAULT_ERA_CHANGE")
    votes = all_votes(p)
    assert len(votes) == 17
    for vote in votes:
        target = next(r for r in vote["ranked_candidates"] if r["gate_id"] == "COUSTEAU_HA10_119HZ_REINTERPRETATION")
        assert target["score"] == -1000.0
    result = m.aggregate(votes, p)
    assert result["authority"]["authority_delta_for_119hz"] == 0


def test_exact_blocked_archive_gate_cannot_immediately_repeat():
    blocked = "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"
    p = payload(
        "BLOCKED_PRE_POST_2013_TRIPLET_DATA",
        executed_gate=blocked,
        data_boundary=True,
    )
    votes = all_votes(p)
    for vote in votes:
        row = next(r for r in vote["ranked_candidates"] if r["gate_id"] == blocked)
        assert row["score"] == -900.0
        assert blocked in vote["nonrepeatable_due_to_data_boundary"]
    result = m.aggregate(votes, p)
    assert result["selected_next_gate"] != blocked
    assert result["selected_next_gate"] == "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1"
    assert result["contradiction_resolution"]["applied"] is True


def test_access_change_allows_exact_gate_again():
    blocked = "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"
    p = payload(
        "BLOCKED_PRE_POST_2013_TRIPLET_DATA",
        executed_gate=blocked,
        data_boundary=True,
        access_changed=True,
    )
    votes = all_votes(p)
    assert all(vote["nonrepeatable_due_to_data_boundary"] == [] for vote in votes)
    result = m.aggregate(votes, p)
    assert result["selected_next_gate"] == blocked


def test_unrelated_blocked_gate_does_not_suppress_triplet():
    p = payload(
        "BLOCKED_PUBLIC_RESPONSE_EPOCH_AUDIT",
        executed_gate="COUSTEAU_HA10_PUBLIC_RESPONSE_EPOCH_AUDIT_V1",
        data_boundary=True,
    )
    result = m.aggregate(all_votes(p), p)
    assert result["selected_next_gate"] == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1"
