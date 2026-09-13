from __future__ import annotations

import copy
import json
import pathlib

import pytest

from tools.demiurge_conductor import (
    admitted_buttons,
    classify_phase,
    select_with_scorer,
    validate_policy,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "demiurge/JANUS_CONDUCTOR_POLICY.json").read_text(encoding="utf-8"))
LAUNCHER = json.loads((ROOT / "demiurge/DEMIURGE_LAUNCHER_POLICY.json").read_text(encoding="utf-8"))


def active_inventory(*names: str):
    return [{"path": f".github/workflows/{name}", "name": name, "state": "active"} for name in names]


def test_policy_authority_ceiling_is_fail_closed():
    validate_policy(POLICY)
    bad = copy.deepcopy(POLICY)
    bad["authority"]["conductor_bypasses_nexus"] = True
    with pytest.raises(RuntimeError, match="AUTHORITY_FIREWALL"):
        validate_policy(bad)


def test_self_and_full_launcher_are_never_admitted_buttons(tmp_path):
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "janus-demiurge-conductor.yml").write_text("name: C\non:\n  workflow_dispatch:\n", encoding="utf-8")
    (wf / "janus-demiurge-full-launcher.yml").write_text("name: L\non:\n  workflow_dispatch:\n", encoding="utf-8")
    (wf / "janus-native-model.yml").write_text("name: N\non:\n  workflow_dispatch:\n", encoding="utf-8")
    rows = admitted_buttons(
        POLICY, LAUNCHER, wf,
        active_inventory("janus-demiurge-conductor.yml", "janus-demiurge-full-launcher.yml", "janus-native-model.yml"),
        "START", set(), 0,
    )
    names = {r["workflow"] for r in rows}
    assert "janus-native-model.yml" in names
    assert "janus-demiurge-conductor.yml" not in names
    assert "janus-demiurge-full-launcher.yml" not in names


def test_phase_graph_restricts_buttons(tmp_path):
    wf = tmp_path / "workflows"
    wf.mkdir()
    files = {
        "janus-research-spine.yml": "Research",
        "janus-native-model.yml": "Native",
        "janus-rex-need-discovery.yml": "Rex Needs",
        "demiurge-spiral-contract.yml": "Spiral",
        "janus-outcome-learning.yml": "Outcome",
    }
    for name, title in files.items():
        (wf / name).write_text(f"name: {title}\non:\n  workflow_dispatch:\n", encoding="utf-8")
    active = active_inventory(*files)
    start = admitted_buttons(POLICY, LAUNCHER, wf, active, "START", set(), 0)
    assert {r["phase"] for r in start} <= {"SENSE", "THINK"}
    build = admitted_buttons(POLICY, LAUNCHER, wf, active, "CHALLENGE", set(), 1)
    assert {r["phase"] for r in build} <= {"THINK", "BUILD", "VERIFY"}
    remember = admitted_buttons(POLICY, LAUNCHER, wf, active, "REMEMBER", set(), 2)
    assert len(remember) == 1 and remember[0]["kind"] == "COMPLETE"


def test_native_selector_only_selects_admitted_candidate_and_penalizes_recent_failure():
    candidates = [
        {"kind": "WORKFLOW", "workflow": "a.yml", "name": "A", "phase": "THINK", "score_text": "A"},
        {"kind": "WORKFLOW", "workflow": "b.yml", "name": "B", "phase": "BUILD", "score_text": "B"},
    ]
    scores = {"A": 1.00, "B": 1.03}
    chosen, table = select_with_scorer(
        "PROMPT", candidates, lambda _p, c: scores[c],
        current_phase="CHALLENGE",
        history=[{"workflow": "a.yml", "conclusion": "failure"}],
        policy=POLICY,
    )
    assert chosen["workflow"] == "b.yml"
    by_name = {row["workflow"]: row for row in table}
    assert by_name["a.yml"]["policy_penalty_nll"] >= POLICY["native_choice"]["failure_penalty_nll"]


def test_repeat_workflow_refused_within_cycle(tmp_path):
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "janus-native-model.yml").write_text("name: Native\non:\n  workflow_dispatch:\n", encoding="utf-8")
    rows = admitted_buttons(
        POLICY, LAUNCHER, wf, active_inventory("janus-native-model.yml"),
        "START", {"janus-native-model.yml"}, 0,
    )
    assert rows == []


def test_known_phase_overrides_are_stable():
    assert classify_phase("janus-research-spine.yml", POLICY) == "SENSE"
    assert classify_phase("janus-native-model.yml", POLICY) == "THINK"
    assert classify_phase("janus-rex-need-discovery.yml", POLICY) == "BUILD"
    assert classify_phase("janus-rex-nexus.yml", POLICY) == "VERIFY"
    assert classify_phase("janus-outcome-learning.yml", POLICY) == "REMEMBER"


def test_authority_law_and_budget_are_present():
    assert POLICY["max_steps_per_cycle"] <= 6
    assert POLICY["authority"]["authority_delta"] == 0
    assert POLICY["authority"]["conductor_grants_code_admission"] is False
    assert POLICY["authority"]["conductor_grants_lifecycle"] is False
    assert "NO_SELF_DISPATCH" in POLICY["firewall"]
    assert "NO_FULL_LAUNCHER_RECURSION" in POLICY["firewall"]
